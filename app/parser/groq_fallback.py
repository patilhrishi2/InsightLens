import os
import json
import requests
from parser.llm_structured_extractor import deep_clean_llm_response, post_process_llm_output
from json_repair import repair_json
import time
from parser.llm_fallback import call_gpt4o_mini_fallback
from parser.llm_structured_extractor import extract_json_strict



GROQ_API_KEY = os.getenv('GROQ_API_KEY')


def call_groq_model(prompt):
    print("[INFO] Calling Groq Llama3-8B...")

    url = "https://api.groq.com/openai/v1/chat/completions"    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant", #deepseek r1, llama 3 8b, llama 3 70 b
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 2048
    }

    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=payload)
        end_time = time.time()

        latency = end_time - start_time
        print(f"[INFO] Groq API call latency: {latency:.2f} seconds")

        response.raise_for_status()

        response_json = response.json()
        if 'choices' in response_json and len(response_json['choices']) > 0:
            groq_output = response_json['choices'][0]['message']['content']
            # log_file_path = 'app/parsed_json/groq_raw_output.json'
            # with open(log_file_path, 'w', encoding='utf-8') as log_file:
            #     json.dump({'raw_groq_output': groq_output}, log_file, ensure_ascii=False, indent=2)
            # print(f"[DEBUG] Raw Groq output logged at: {log_file_path}")

            # ✅ If Groq returned a dictionary directly
            if isinstance(groq_output, dict):
                print("[DEBUG] Groq returned a dict. Skipping cleaning and validation.")

                post_start = time.time()
                final_output = post_process_llm_output(groq_output)
                post_end = time.time()

                post_processing_time = post_end - post_start
                print(f"[TIMER] Post-LLM processing took {post_processing_time:.2f} seconds")

                return final_output, latency

            # ✅ If Groq returned a string
            elif isinstance(groq_output, str):
                print("[DEBUG] Groq returned a string. Attempting to repair and parse JSON.")

                try:
                    repaired_json_string = repair_json(groq_output)
                    parsed_output = json.loads(repaired_json_string)
                except Exception as e:
                    print(f"[ERROR] JSON repair failed: {str(e)}")

                    # 🔥 Try strict JSON extraction as last-resort

                    strict_json_string = extract_json_strict(groq_output)
                    if strict_json_string:
                        try:
                            parsed_output = json.loads(strict_json_string)
                        except Exception as inner_e:
                            print(f"[ERROR] Strict JSON parsing failed: {str(inner_e)}")
                            raise Exception("Failed to strictly extract JSON.")
                    else:
                        raise Exception("Failed to repair and strictly extract JSON.")


                if parsed_output:
                    post_start = time.time()
                    final_output = post_process_llm_output(parsed_output)
                    post_end = time.time()

                    post_processing_time = post_end - post_start
                    print(f"[TIMER] Post-LLM processing took {post_processing_time:.2f} seconds")

                    return final_output, latency
                else:
                    raise Exception("Invalid JSON returned by Groq.")

            else:
                raise Exception("Unexpected Groq response type.")

        else:
            raise Exception("Groq returned no valid choices.")

    except Exception as e:
            print(f"[ERROR] Groq Llama-3 API call failed: {str(e)}")
            print("[INFO] Attempting fallback to GPT-4o-mini...")
            fallback_output = call_gpt4o_mini_fallback(prompt)
            if fallback_output:
                return fallback_output, None  # Fallback succeeded but latency is not measured here
            else:
                return None, None

