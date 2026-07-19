from jd_parser.jd_processor import extract_json, get_jd_prompt
from jd_parser.jd_google_api import call_google_api
import json
import time

def extract_google_response(response_json):
    try:
        return response_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return {"error": f"Response parsing failed: {str(e)}", "raw_output": response_json}

def parse_jd_with_gemma(jd_text):
    start_time = time.time()

    print(f"[DEBUG] Sending payload to Google API for JD parsing (single call)")
    response = call_google_api(get_jd_prompt(jd_text))

    if response.status_code != 200:
        print(f"[ERROR] API Error during JD parsing: {response.status_code}")
        return {
            "model_used": "gemma-4-26b-a4b-it (Google API)",
            "parsed_output": {"error": f"API Error: {response.status_code}"}
        }

    response_json = response.json()
    generated_text = extract_google_response(response_json)

    if isinstance(generated_text, dict) and "error" in generated_text:
        print(f"[ERROR] Response parsing failed during JD parsing")
        return {
            "model_used": "gemma-4-26b-a4b-it (Google API)",
            "parsed_output": generated_text
        }

    total_time = time.time() - start_time
    extracted = extract_json(generated_text)

    if isinstance(extracted, dict) and 'error' in extracted:
        print(f"[ERROR] JSON extraction failed: {extracted['error']}")
    else:
        print(f"[INFO] JD parsed in {total_time:.2f} seconds")

    return {
        "model_used": "gemma-4-26b-a4b-it (Google API)",
        "parsed_output": extracted
    }
