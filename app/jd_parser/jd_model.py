# jd_model.py  /google api key-AIzaSyAv3d_j0PymvBBYzwUECfmuk5MMh_BUcmo
import os
import requests
from jd_parser.jd_processor import extract_json, get_jd_prompt, merge_results
import time

# =========================
# Model Inference Endpoints
# =========================
MODEL_ENDPOINTS = {
    "phi3": "https://api-inference.huggingface.co/models/microsoft/Phi-3-mini-4k-instruct",
    "gemma": "https://api-inference.huggingface.co/models/bastienp/Gemma-2-2B-Instruct-structured-output",
    "mistral": "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
    "nous": "https://api-inference.huggingface.co/models/NousResearch/Nous-Hermes-2-Mistral-7B-DPO"
}


HEADERS = {
    "Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}",
    "Content-Type": "application/json"
}

# =========================
# JD Parsing with Model
# =========================
def parse_jd_with_model(jd_text):
    model_name = "mistral"  # Fixed to Mistral for now
    if model_name not in MODEL_ENDPOINTS:
        raise ValueError(f"Unsupported model: {model_name}")

    api_url = MODEL_ENDPOINTS[model_name]
    passes = get_jd_prompt(jd_text)  # Single combined prompt

    combined_result = {}
    start_time = time.time()

    for step in passes:
        payload = {
            "inputs": step["prompt"],
            "parameters": {
                "temperature": 0.1
            }
        }

        response = requests.post(api_url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            combined_result[step["name"]] = {"error": f"API Error: {response.status_code}", "raw_output": response.text}
            continue

        model_output = response.json()

        if isinstance(model_output, list) and 'generated_text' in model_output[0]:
            generated_text = model_output[0]['generated_text']
        else:
            combined_result[step["name"]] = {"error": "Unexpected response format", "raw_output": model_output}
            continue

        end_time = time.time()  # End timer
        total_time = end_time - start_time  # Calculate elapsed time
        print(f"[INFO] Total response time: {total_time:.2f} seconds")
        extracted_json = extract_json(generated_text)
        combined_result[step["name"]] = extracted_json

    final_output = merge_results(combined_result)

    return {
        "model_used": model_name,
        "parsed_output": final_output
    }
