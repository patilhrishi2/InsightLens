# jd_google_api.py

import os
import requests

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_GEMMA_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent?key={GOOGLE_API_KEY}"

def call_google_api(prompt):
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0
        }
    }

    response = requests.post(GOOGLE_GEMMA_ENDPOINT, json=payload)
    return response
