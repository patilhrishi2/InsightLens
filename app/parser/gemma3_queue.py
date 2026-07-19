# app/parser/gemma3_queue.py
import threading
import time
import queue
import json
import os
from parser.gemma3 import call_gemma3_model
from resume_jd_comparator.comparison_engine import ResumeJDComparator

# Queue to hold Gemma3 tasks
gemma3_task_queue = queue.Queue()

# Token rate limit configuration
MAX_TOKENS_PER_MIN = 15000
estimated_tokens_per_call = 3000  # You can adjust this if your average is higher or lower
SECONDS_PER_CALL = 60 * estimated_tokens_per_call / MAX_TOKENS_PER_MIN  # Interval between calls

# Result storage
GEMMA3_RESULT_FOLDER = 'app/parsed_json/gemma3_async_results'
os.makedirs(GEMMA3_RESULT_FOLDER, exist_ok=True)

def process_gemma3_tasks():
    print("[INFO] Gemma 4 async worker started.")
    while True:
        if not gemma3_task_queue.empty():
            task = gemma3_task_queue.get()

            prompt = task['prompt']
            filename = task['filename']
            jd_json = task['jd_json']

            try:
                # 👉 STEP 1: Immediately write temp file with status: processing
                result_path = os.path.join(GEMMA3_RESULT_FOLDER, f'{filename}_gemma3_result.json')
                with open(result_path, 'w', encoding='utf-8') as temp_file:
                    json.dump({
                        'filename': filename,
                        'gemma3_output': None,
                        'gemma_latency_sec': None,
                        'score': None,
                        'status': 'processing'
                    }, temp_file, ensure_ascii=False, indent=2)
                print(f"[INFO] Temporary processing file created for {filename}.")

                structured_resume_gemma, latency_gemma = call_gemma3_model(prompt)
                if structured_resume_gemma:
                    print(f"[INFO] Gemma 4 async processed {filename} in {latency_gemma:.2f} seconds.")
                    try:
                        jd_path = 'app/parsed_json/latest_JD.json'
                        with open(jd_path, 'r', encoding='utf-8') as jd_file:
                            jd_json = json.load(jd_file)

                        print(f"[INFO] Starting JD-Resume Comparison for {filename}...")
                        comparator = ResumeJDComparator(structured_resume_gemma, jd_json)
                        comparison_result = comparator.compare()
                        experience_years = comparator.get_experience_years()
                        print(f"************this is the comparison result*****************{comparison_result}")
                        if 'eligible' in comparison_result:
                            eligible = comparison_result['eligible']
                        else:
                            print("[WARNING] Eligibility not found in comparison result. Defaulting to False.")
                            eligible = False  # ✅ You forgot this!

                        if 'overall_score' in comparison_result:
                            score = comparison_result['overall_score']
                        else:
                            print("[WARNING] Score not found in comparison result. Defaulting to 0.")
                            score = 0
                            
                        # if 'overall_score' in comparison_result:
                        #     score = comparison_result['overall_score']
                        # else:
                        #     print("[WARNING] Score not found in comparison result. Defaulting to 0.")
                        #     score = 0
                        # Save to HR Summary file
                        hr_summary_path = 'app/parsed_json/hr_summary.jsonl'
                        with open(hr_summary_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'filename': filename,
                                'score': score,
                                'resume_path': f'/uploads/{filename}'
                            }) + '\n')

                        print(f"[INFO] JD-Resume Comparison completed for {filename} with Score: {score}")
                    except Exception as e:
                        print(f"[ERROR] JD-Resume Comparison failed for {filename}: {str(e)}")
                        score = 0

                    # 👉 STEP 2: Overwrite the temp file with final result (status: completed)
                    with open(result_path, 'w', encoding='utf-8') as result_file:
                        json.dump({
                            'filename': filename,
                            'gemma3_output': structured_resume_gemma,
                            'gemma_latency_sec': latency_gemma,
                            'score': score,
                            'eligible':eligible,
                            'experience_years': experience_years,
                            'status': 'completed'
                        }, result_file, ensure_ascii=False, indent=2)
                    print(f"[INFO] Gemma 4 async final result stored at: {result_path}")

                else:
                    print(f"[WARNING] Gemma 4 async processing failed for {filename}")

                     # 🚨 Always write a fallback result
                    with open(result_path, 'w', encoding='utf-8') as result_file:
                        json.dump({
                            'filename': filename,
                            'gemma3_output': None,
                            'gemma_latency_sec': None,
                            'score': 0,
                            'eligible':False,
                            'experience_years': 0,
                            'status': 'failed'
                        }, result_file, ensure_ascii=False, indent=2)
                    print(f"[INFO] Wrote fallback result for {filename} after Gemma failure.")

            except Exception as e:
                print(f"[ERROR] Gemma 4 async processing error for {filename}: {str(e)}")

            print(f"[RATE LIMIT] Sleeping for {SECONDS_PER_CALL:.2f} seconds to respect token limit...")
            time.sleep(SECONDS_PER_CALL)

        else:
            time.sleep(1)

# Start the async worker thread
worker_thread = threading.Thread(target=process_gemma3_tasks, daemon=True)
worker_thread.start()

def add_gemma3_task(prompt, filename, jd_json):
    gemma3_task_queue.put({'prompt': prompt, 'filename': filename, 'jd_json': jd_json})
    print(f"[QUEUE] Added Gemma 4 task for {filename}. Current queue size: {gemma3_task_queue.qsize()}")

