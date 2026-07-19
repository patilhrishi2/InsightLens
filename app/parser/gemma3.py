import os
import json
import requests
import time
from parser.llm_structured_extractor import deep_clean_llm_response, post_process_llm_output, extract_json_strict
from json_repair import repair_json

# Google Cloud Gemini / Gemma 3 API URL
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent"

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Folder to store outputs
OUTPUT_FOLDER = 'app/parsed_json/gemma3'
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def call_gemma3_model(prompt):
    print("[INFO] Calling Google Gemma 3 model...")

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 2048
        }
    }

    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=payload)
        end_time = time.time()

        latency = end_time - start_time
        print(f"[INFO] Gemma 3 API call latency: {latency:.2f} seconds")

        response.raise_for_status()
        response_json = response.json()

        gemma_output = response_json['candidates'][0]['content']['parts'][0]['text']
        log_file_path = os.path.join(OUTPUT_FOLDER, 'gemma3_raw_output.json')

        with open(log_file_path, 'w', encoding='utf-8') as log_file:
            json.dump({'raw_gemma3_output': gemma_output}, log_file, ensure_ascii=False, indent=2)
        print(f"[DEBUG] Raw Gemma 3 output logged at: {log_file_path}")

        # Try to repair and parse JSON
        try:
            repaired_json_string = repair_json(gemma_output)
            parsed_output = json.loads(repaired_json_string)
        except Exception as e:
            print(f"[ERROR] JSON repair failed: {str(e)}")

            # Try strict JSON extraction
            strict_json_string = extract_json_strict(gemma_output)
            if strict_json_string:
                try:
                    parsed_output = json.loads(strict_json_string)
                except Exception as inner_e:
                    print(f"[ERROR] Strict JSON parsing failed: {str(inner_e)}")
                    raise Exception("Failed to strictly extract JSON from Gemma 3 output.")
            else:
                raise Exception("Failed to repair and strictly extract JSON from Gemma 3 output.")

        if parsed_output:
            # Guard: repair_json or the model can return a list e.g. [{...}] instead of {...}.
            # Silently unwrap a single-element list so processing continues normally.
            if isinstance(parsed_output, list):
                non_empty = [item for item in parsed_output if isinstance(item, dict) and item]
                if non_empty:
                    parsed_output = non_empty[0]
                    print("[WARNING] Gemma 3 returned a JSON list — unwrapped first dict element.")
                else:
                    raise Exception("Gemma 3 returned a JSON list with no valid dict inside.")

            post_start = time.time()
            final_output = post_process_llm_output(parsed_output)
            post_end = time.time()

            post_processing_time = post_end - post_start
            print(f"[TIMER] Post-LLM processing took {post_processing_time:.2f} seconds")

            # Save final processed JSON
            final_output_path = os.path.join(OUTPUT_FOLDER, 'output.json')
            with open(final_output_path, 'w', encoding='utf-8') as json_file:
                json.dump(final_output, json_file, ensure_ascii=False, indent=2)
            print(f"[INFO] Processed Gemma 3 JSON stored at: {final_output_path}")

            return final_output, latency

        else:
            raise Exception("Invalid JSON returned by Gemma 3.")

    except Exception as e:
        print(f"[ERROR] Gemma 3 API call failed: {str(e)}")
        return None, None
