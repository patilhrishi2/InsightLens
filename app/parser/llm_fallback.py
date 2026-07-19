import os
import json
import requests
from parser.llm_structured_extractor import deep_clean_llm_response, validate_json, post_process_llm_output

# Set your OpenAI API key here or from environment variable

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
def call_gpt4o_mini_fallback(prompt):
    print("[INFO] Falling back to GPT-4o-mini...")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        response_json = response.json()
        if 'choices' in response_json and len(response_json['choices']) > 0:
            gpt_output = response_json['choices'][0]['message']['content']
            print("[DEBUG] Raw GPT-4o-mini Response:\n", gpt_output)

            cleaned_output = deep_clean_llm_response(gpt_output)
            parsed_output = validate_json(cleaned_output)

            if parsed_output:
                final_output = post_process_llm_output(parsed_output)
                return final_output, None
            else:
                raise Exception("Invalid JSON returned by GPT-4o-mini.")

    except Exception as e:
        print(f"[ERROR] GPT-4o-mini fallback failed: {str(e)}")
        return None
