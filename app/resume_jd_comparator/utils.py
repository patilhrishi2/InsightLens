# app/resume_jd_comparator/utils.py

import os
import json
import requests
import time
import re
from dateutil import parser
from datetime import datetime
from word2number import w2n

def try_json_loads(response_text):
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing failed: {e}")
        # Save problematic response for inspection
        with open('app/parsed_json/debug_invalid_json.json', 'w', encoding='utf-8') as f:
            f.write(response_text)
        return None


def extract_declared_experience(resume_json):
    sections_to_check = [
        resume_json.get("other_sections", {}).get("Summary", ""),
        resume_json.get("other_sections", {}).get("Overview", ""),
        resume_json.get("other_sections", {}).get("About Me", "")
    ]

    combined_text = " ".join(sections_to_check)

    # Updated regex: supports decimals like '4.1 years', '4.1+ years', '4.1 years of experience'
    match = re.search(r'(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s*(?:of)?\s*experience', combined_text, re.IGNORECASE)

    if match:
        years = float(match.group(1))
        print(f"[INFO] Declared Experience found: {years} years")
        return int(years * 12)  # convert to months

    return None


def clean_llm_response(text_response):
    cleaned = re.sub(r'^```(?:json)?\n', '', text_response.strip())
    cleaned = re.sub(r'\n```$', '', cleaned)
    return cleaned

def parse_flexible_date(date_str):
    from dateutil import parser
    from datetime import datetime

    date_str = date_str.strip()

    if not date_str:
        return None

    if 'present' in date_str.lower():
        return 'Present'

    try:
        # ✅ Try parsing common formats directly
        parsed = parser.parse(date_str)
        return parsed.strftime('%Y-%m')
    except Exception:
        pass

    if '/' in date_str:
        try:
            parts = date_str.split('/')
            if len(parts) == 2:
                month = int(parts[0])
                year_suffix = parts[1]
                year = int('20' + year_suffix) if int(year_suffix) < 50 else int('19' + year_suffix)
                return f"{year}-{month:02d}"
        except Exception as e:
            print(f"[ERROR] Failed to parse MM/YY date: {date_str} | {e}")
            return None

    if len(date_str) == 4 and date_str.isdigit():
        return f"{date_str}-01"

    print(f"[ERROR] Fallback parser failed for date: {date_str}")
    return None



import re

def extract_required_experience(jd_string):
    jd_string = jd_string.strip().lower()
    result = {'minimum_experience': None, 'maximum_experience': None, 'preferred_experience': None}

    # Extract ranges like "3 to 5 years", "between 3 and 5 years", "3-5 years"
    range_match = re.search(r'(?:between\s+)?(\d+)\s*(?:to|–|-|and)\s*(\d+)\s*years?', jd_string)
    if range_match:
        result['minimum_experience'] = int(range_match.group(1))
        result['maximum_experience'] = int(range_match.group(2))
        return result

    # Extract minimum experience
    min_match = re.search(r'(?:at least|min(?:imum)?|not less than|greater than|more than)\s*(\d+)\s*years?', jd_string)
    if min_match:
        result['minimum_experience'] = int(min_match.group(1))
        return result

    # Extract maximum experience
    max_match = re.search(r'(?:up to|max(?:imum)?|not more than|less than)\s*(\d+)\s*years?', jd_string)
    if max_match:
        result['maximum_experience'] = int(max_match.group(1))
        return result

    # Extract preferred experience
    pref_match = re.search(r'(?:preferred|ideally|typically)\s*(\d+)\s*years?', jd_string)
    if pref_match:
        result['preferred_experience'] = int(pref_match.group(1))
        return result

    # Extract standalone experience number if no qualifier is found
    digit_match = re.search(r'(\d+)\s*years?', jd_string)
    if digit_match:
        result['minimum_experience'] = int(digit_match.group(1))
        return result

    # Return default structure if nothing is found
    return result


def calculate_total_experience(experience_list, resume_json):
    from datetime import datetime

    declared_months = extract_declared_experience(resume_json)
    if declared_months:
        total_years = declared_months // 12
        remaining_months = declared_months % 12
        readable_experience = f"{total_years} years {remaining_months} months" if total_years > 0 else f"{remaining_months} months"
        print(f"[INFO] Final Experience (Declared): {readable_experience}")
        return {
            "total_months": declared_months,
            "formatted": readable_experience,
            "flagged_experiences": []
        }

    intervals = []
    flagged_experiences = []

    for exp in experience_list:
        title = exp['title_line'].lower()

        if any(keyword in title for keyword in ['intern', 'internship', 'researcher']):
            continue

        date_list = exp.get('dates', [])

        try:
            if len(date_list) == 2:
                start_str = parse_flexible_date(date_list[0].strip())
                end_str = parse_flexible_date(date_list[1].strip())

                if start_str is None or end_str is None:
                    flagged_experiences.append({'title': exp['title_line'], 'raw_date': date_list})
                    continue

                start_date = datetime.strptime(start_str, "%Y-%m")
                end_date = datetime.now() if end_str == 'Present' else datetime.strptime(end_str, "%Y-%m")

                if start_date > end_date:
                    print(f"[WARNING] Skipping entry: Start date {start_date} is after end date {end_date}.")
                    flagged_experiences.append({'title': exp['title_line'], 'start_date': start_str, 'end_date': end_str})
                    continue

                intervals.append((start_date, end_date))

            else:
                flagged_experiences.append({'title': exp['title_line'], 'raw_date': date_list})
                continue

        except Exception as e:
            print(f"[ERROR] Failed to parse dates: {date_list}")
            flagged_experiences.append({'title': exp['title_line'], 'raw_date': date_list})
            continue

    if not intervals:
        print("[ERROR] No valid experiences found.")
        return {
            "total_months": 0,
            "formatted": "0 months",
            "flagged_experiences": flagged_experiences
        }

    # Step 1: Sort intervals by start date
    intervals.sort(key=lambda x: x[0])

    # Step 2: Merge overlapping intervals
    merged = []
    current_start, current_end = intervals[0]

    for start, end in intervals[1:]:
        if start <= current_end:  # Overlapping
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    merged.append((current_start, current_end))

    # Step 3: Sum total months
    total_months = 0
    for start, end in merged:
        months = (end.year - start.year) * 12 + (end.month - start.month)
        total_months += months

    total_years = total_months // 12
    remaining_months = total_months % 12

    readable_experience = f"{total_years} years {remaining_months} months" if total_years > 0 else f"{remaining_months} months"
    print(f"[INFO] Total Experience (after merging overlaps): {readable_experience}")

    return {
        "total_months": total_months,
        "formatted": readable_experience,
        "flagged_experiences": flagged_experiences
    }


def call_llm_api(prompt, retries=3, delay=15):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
       
        "x-goog-api-key": os.getenv('GEMINI_FLASH_API_KEY')
    }

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 1,
            "topK": 1
        }
    }

    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))

            if response.status_code == 200:
                response_json = response.json()

                try:
                    text_response = response_json['candidates'][0]['content']['parts'][0]['text']
                except Exception as e:
                    print(f"[ERROR] Gemini response parsing failed: {str(e)}")
                    time.sleep(delay * (2 ** attempt))
                    continue

                if not text_response.strip():
                    print(f"[WARNING] Empty Gemini response. Retrying... Attempt {attempt + 1}")
                    time.sleep(delay * (2 ** attempt))
                    continue

                cleaned_response = clean_llm_response(text_response)
                cleaned_response = cleaned_response.replace('\n', ' ').replace('\r', ' ')

                try:
                    result = try_json_loads(cleaned_response)
                    if result is None:
                        print(f"[ERROR] JSON parsing failed. Retrying... Attempt {attempt + 1}")
                        time.sleep(delay * (2 ** attempt))
                        continue

                    return result

                except Exception as e:
                    print(f"[ERROR] Final JSON parsing failed: {str(e)}")
                    time.sleep(delay * (2 ** attempt))
                    continue

            elif response.status_code == 429:
                print(f"[WARNING] Rate limit hit. Retrying... Attempt {attempt + 1}")
                time.sleep(delay * (2 ** attempt))
                continue

            else:
                print(f"[ERROR] API call failed with status code {response.status_code}. Attempt {attempt + 1}")
                print(f"[DEBUG] Response: {response.text}")
                time.sleep(delay * (2 ** attempt))
                continue

        except Exception as e:
            print(f"[ERROR] Exception during Gemini API call: {str(e)}")
            time.sleep(delay * (2 ** attempt))
            continue

    print("[ERROR] Gemini API call failed after all retries.")
    return {
        "eligible": False,
        "education_flag": False,
        "experience_flag": False,
        "education_feedback": "API call failed.",
        "experience_feedback": "API call failed.",
        "must_have_skills_matched": [],
        "must_have_skills_missing": [],
        "good_to_have_skills_matched": [],
        "good_to_have_skills_missing": [],
        "must_have_score": 0,
        "good_to_have_score": 0,
        "experience_score": 0,
        "overall_score": 0,
        "soft_skills_feedback": "API call failed.",
        "final_feedback": "The API call failed after multiple retries. Please try again later or use a fallback model."
    }

# ============================== PREVIOUS MISTRAL CODE (COMMENTED) ==============================

# def call_llm_api(prompt, retries=5, delay=2):
#     url = "https://openrouter.ai/api/v1/chat/completions"
#     headers = {
#         "Authorization": "Bearer ,
#         "Content-Type": "application/json",
#         "HTTP-Referer": "https://your-site.com",
#         "X-Title": "ResumeParser",
#     }

#     payload = {
#         "model": "mistralai/mistral-7b-instruct:free",
#         "messages": [
#             {"role": "user", "content": prompt}
#         ]
#     }

#     for attempt in range(retries):
#         try:
#             response = requests.post(url, headers=headers, data=json.dumps(payload))

#             if response.status_code == 200:
#                 response_json = response.json()
#                 text_response = response_json['choices'][0]['message']['content']

#                 if not text_response.strip():
#                     print(f"[WARNING] Empty LLM text response. Retrying... Attempt {attempt + 1}")
#                     time.sleep(delay * (2 ** attempt))
#                     continue

#                 cleaned_response = clean_llm_response(text_response)
#                 cleaned_response = cleaned_response.replace('\n', ' ').replace('\r', ' ')

#                 try:
#                     result = try_json_loads(cleaned_response)
#                     if result is None:
#                         print(f"[ERROR] Groq Llama-3 API call failed: {str(e)}")
#                         time.sleep(delay * (2 ** attempt))
#                         continue

#                     return result
#                 except Exception as e:
#                     print(f"[ERROR] JSON parsing failed: {str(e)}")
#                     print(f"[DEBUG] Raw response text: {text_response}")
#                     time.sleep(delay * (2 ** attempt))
#                     continue

#             elif response.status_code == 429:
#                 print(f"[WARNING] Rate limit hit. Retrying... Attempt {attempt + 1}")
#                 time.sleep(delay * (2 ** attempt))
#                 continue

#             else:
#                 print(f"[ERROR] API call failed with status code {response.status_code}. Attempt {attempt + 1}")
#                 print(f"[DEBUG] Response: {response.text}")
#                 time.sleep(delay * (2 ** attempt))
#                 continue

#         except Exception as e:
#             print(f"[ERROR] Exception during API call: {str(e)}")
#             time.sleep(delay * (2 ** attempt))
#             continue

#     print("[ERROR] API call failed after all retries.")
#     return {
#         "eligible": False,
#         "education_feedback": "API call failed.",
#         "experience_feedback": "API call failed.",
#         "must_have_skills_matched": [],
#         "must_have_skills_missing": [],
#         "good_to_have_skills_matched": [],
#         "good_to_have_skills_missing": [],
#         "must_have_score": 0,
#         "good_to_have_score": 0,
#         "experience_score": 0,
#         "overall_score": 0,
#         "soft_skills_feedback": "API call failed.",
#         "final_feedback": "The API call failed after multiple retries. Please try again later or use a fallback model."
#     }


def call_openai_gpt4o(prompt, retries=5, delay=2):
    import openai
    import time


    openai.api_key = os.getenv('OPENAI_GPT4O_API_KEY')

    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert resume evaluator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            content = response['choices'][0]['message']['content']
            cleaned_response = clean_llm_response(content)
            result = json.loads(cleaned_response)
            return result

        except Exception as e:
            print(f"[ERROR] Exception: {str(e)}. Attempt {attempt + 1}")
            time.sleep(delay * (2 ** attempt))

    print("[ERROR] GPT-4o mini call failed after all retries.")
    return {
        "score": 0,
        "justification": "OpenAI API call failed after retries.",
        "recommendations": "Try again later."
    }
