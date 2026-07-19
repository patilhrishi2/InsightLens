from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import json
from parser.resume_extractor import extract_text_from_pdf
from parser.llm_structured_extractor import build_llm_prompt
from parser.groq_fallback import call_groq_model
from parser.gemma3 import call_gemma3_model
from hr_dashboard.batch_processor import run_batch_processor
from parser.gemma3_queue import add_gemma3_task
import glob
from jd_parser.llm_9_parser import parse_jd_with_gemma
import threading
from auth.auth_utils import auth_required

hr_dashboard_bp = Blueprint('hr_dashboard', __name__)
batch_processor = run_batch_processor()

UPLOAD_FOLDER = 'app/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# COMPARISON_LOG_FILE = 'app/parsed_json/groq_vs_gemma3_comparison.jsonl'

batch_results_lock = threading.Lock()


@hr_dashboard_bp.route('/hr-dashboard', methods=['GET'])
@auth_required('hr')
def hr_dashboard_page():
    return render_template('hr_dashboard/dashboard.html')

# =============================== ROUTE 1 ====================================
@hr_dashboard_bp.route('/batch-results', methods=['GET'])
@auth_required('hr')
def batch_results():
    results = []
    file_path = 'batch_results/batch_output.json'

    with batch_results_lock:
        if not os.path.exists(file_path):
            return jsonify({'results': results})

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"[WARNING] Skipping invalid JSON line in batch output.")
        except Exception as e:
            print(f"[ERROR] Failed to read batch results: {e}")
            return jsonify({'error': 'Failed to read batch results.'}), 500

    return jsonify({'results': results})

# =============================== GEMMA 4  POLLING ROUTE ====================================
@hr_dashboard_bp.route('/gemma3-result/<filename>', methods=['GET'])
@auth_required('hr')
def get_gemma3_result(filename):
    result_path = os.path.join('app/parsed_json/gemma3_async_results', f'{filename}_gemma3_result.json')
    print(f"[DEBUG] Fetching Gemma 4 result for file: {filename}")
    print(f"[DEBUG] Full path: {result_path}")

    if os.path.exists(result_path):
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                result_json = json.load(f)

            file_status = result_json.get('status', 'processing')

            if file_status == 'completed':
                return jsonify({'status': 'completed', 'result': result_json})
            elif file_status == 'processing':
                return jsonify({'status': 'processing'})
            elif file_status == 'failed':
                return jsonify({'status': 'failed', 'message': 'Gemma 4 processing failed for this file.'})
            else:
                return jsonify({'status': 'error', 'message': 'Unknown status in file.'}), 500

        except Exception as e:
            print(f"[ERROR] Failed to load JSON for {filename}: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to load JSON'}), 500

    else:
        print(f"[DEBUG] Result file not found for {filename}, assuming processing is ongoing.")
        return jsonify({'status': 'processing'})

# =============================== ROUTE 4 ====================================
@hr_dashboard_bp.route('/upload-batch', methods=['POST'])
@auth_required('hr')
def upload_batch():
    selected_model = request.form.get('model')
    if not selected_model:
        return jsonify({'error': 'Model selection missing.'}), 400

    print(f"[INFO] Selected model: {selected_model}")

    if 'resumes' not in request.files:
        print("[ERROR] No resume files provided.")
        return jsonify({'error': 'No resume files provided.'}), 400

    jd_text = request.form.get('jd')
    if not jd_text:
        print("[ERROR] Job Description text missing.")
        return jsonify({'error': 'Job Description text missing.'}), 400

    # try:
    #     open('batch_results/batch_output.json', 'w').close()
    #     # open(COMPARISON_LOG_FILE, 'w').close()
    #     print("[INFO] Cleared previous batch and comparison results.")
    # except Exception as e:
    #     print(f"[ERROR] Failed to clear previous batch/comparison results: {e}")

    try:
        parsed_jd_response = parse_jd_with_gemma(jd_text)
        jd = parsed_jd_response["parsed_output"]
        with open('app/parsed_json/latest_JD.json', 'w', encoding='utf-8') as f:
            json.dump(jd, f, ensure_ascii=False, indent=2)
        print("[INFO] JD parsed successfully.")

    except Exception as e:
        print(f"[ERROR] JD Parsing failed: {e}")
        return jsonify({'error': f'JD Parsing failed: {e}'}), 500

    files = request.files.getlist('resumes')
    if not files:
        print("[ERROR] No files uploaded.")
        return jsonify({'error': 'No files uploaded.'}), 400

    print(f"[INFO] Number of resumes uploaded: {len(files)}")

    results = []

    for idx, file in enumerate(files, 1):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        print(f"[INFO] Saved file {idx}: {filename}")

        try:
            resume_text = extract_text_from_pdf(file_path)
            print(f"[INFO] Extracted text from {filename}")

            prompt = build_llm_prompt(resume_text)
            print(f"[INFO] Built LLM prompt for {filename}")

            if selected_model == 'llama3.1-instant':
                structured_resume, latency = call_groq_model(prompt)
                print(f"[INFO] LLaMA 3.1 processed {filename} in {latency:.2f} seconds")
                batch_processor.add_task(structured_resume, jd)

            elif selected_model == 'gemma3':
                add_gemma3_task(prompt, filename, jd)
                print(f"[DEBUG] Added {filename} to Gemma 4 queue. Current queue size: {batch_processor.queue.qsize()}")

                comparison_save_path = os.path.join('comparison_results', f'{filename}_comparison.json')
                os.makedirs('comparison_results', exist_ok=True)

                comparison_data = {
                    'filename': filename,
                    'job_description': jd,
                    'resume_prompt': prompt
                }

                try:
                    with open(comparison_save_path, 'w', encoding='utf-8') as f:
                        json.dump(comparison_data, f, indent=4)
                    print(f"[DEBUG] Saved comparison input for {filename} at {comparison_save_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to save comparison input for {filename}: {e}")

            elif selected_model == 'gemini-1.5-flash':
                print(f"[INFO] Gemini 1.5 Flash processing is not yet implemented.")

            else:
                print(f"[ERROR] Invalid model selection: {selected_model}")
                return jsonify({'error': f'Invalid model selection: {selected_model}'}), 400

        except Exception as e:
            print(f"[ERROR] Failed to process {filename}: {e}")

    filenames = [secure_filename(file.filename) for file in files]
    return jsonify({
        'message': 'Batch processing started. Please wait for results.',
        'expected_count': len(files),
        'filenames': filenames
    }), 200

# =============================== ROUTE 5 ====================================
@hr_dashboard_bp.route('/hr-summary', methods=['GET'])
@auth_required('hr')
def hr_summary():
    summary_path = 'app/parsed_json/hr_summary.jsonl'
    results = []

    if os.path.exists(summary_path):
        with open(summary_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    results.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    print(f"[WARNING] Skipping invalid line in HR summary file.")

    return jsonify({'summary': results})
