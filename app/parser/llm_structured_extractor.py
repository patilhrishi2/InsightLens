import json
import requests
import re
from requests.adapters import HTTPAdapter, Retry



OLLAMA_URL = "http://2401-35-222-14-208.ngrok-free.app/llm" #original http://localhost:11434/api/generate
MODEL_NAME = "phi3"

def deduplicate_sections(data):
    """
    De-duplicate achievements and skills between primary fields and 'other_sections'.
    """
    # Deduplicate achievements
    if 'achievements' in data and 'Achievements' in data.get('other_sections', {}):
        achievement_list = set([a.lower().strip() for a in data['achievements']])
        other_achievements = [a.strip() for a in data['other_sections']['Achievements'].split(',')]

        filtered = [a for a in other_achievements if a.lower() not in achievement_list]
        if filtered:
            data['other_sections']['Achievements'] = ', '.join(filtered)
        else:
            del data['other_sections']['Achievements']

    # Deduplicate skills
    if 'skills' in data and 'Skills' in data.get('other_sections', {}):
        skill_list = set([s.lower().strip() for s in data['skills']])
        other_skills = [s.strip() for s in data['other_sections']['Skills'].split(',')]

        filtered = [s for s in other_skills if s.lower() not in skill_list]
        if filtered:
            data['other_sections']['Skills'] = ', '.join(filtered)
        else:
            del data['other_sections']['Skills']

    return data


def clean_symbols(text_list):
    """
    Remove unwanted leading symbols like '*', '+', '-' from strings in a list.
    Only process string items.
    """
    cleaned_list = []
    for item in text_list:
        if isinstance(item, str):
            if item.strip() != "":
                cleaned_list.append(item.lstrip('*+-• ').strip())
        else:
            print(f"[WARNING] Skipping non-string item in clean_symbols: {item} of type {type(item)}")
    return cleaned_list


def clean_other_sections(other_sections):
    """
    Clean symbols inside 'other_sections' and remove keys with empty values.
    """
    cleaned_sections = {}
    for key, value in other_sections.items():
        if isinstance(value, list):
            cleaned_list = clean_symbols(value)
            if cleaned_list:
                cleaned_sections[key] = cleaned_list
        elif isinstance(value, str):
            cleaned_value = clean_symbols([value])
            if cleaned_value:
                cleaned_sections[key] = cleaned_value[0]
        else:
            print(f"[WARNING] Skipping key {key} with unexpected type {type(value)} in other_sections.")
    return cleaned_sections

def post_process_llm_output(data):
    """
    Runs all post-processing steps on the LLM output JSON.
    """
    
    
    # Clean symbols
    data['achievements'] = clean_symbols(data.get('achievements', []))
    data['trainings'] = clean_symbols(data.get('trainings', []))
    data['skills'] = clean_symbols(data.get('skills', []))

    # Clean other_sections
    data['other_sections'] = clean_other_sections(data.get('other_sections', {}))

    # Deduplicate overlapping content
    data = deduplicate_sections(data)
    return data

def deep_clean_llm_response(response_text):
    """
    Removes:
    1. Entire lines starting with '//'
    2. Any text after '//' on a valid JSON line
    """
    # ✅ Type guard to handle dict input directly
    if isinstance(response_text, dict):
        return response_text

    # Step 1: Remove full-line comments
    no_full_line_comments = re.sub(r'^\s*//.*$', '', response_text, flags=re.MULTILINE)

    # Step 2: Remove trailing comments (after //) in any line
    no_inline_comments = re.sub(r'(?<!http:)(?<!https:)//.*', '', no_full_line_comments)

    # Optional: Remove multiple blank lines caused by comment deletion
    cleaned_response = re.sub(r'\n\s*\n', '\n', no_inline_comments)

    return cleaned_response.strip()



# def clean_llm_response(response_text):
#     """
#     Removes lines starting with '//' to clean out comments from LLM output.
#     """
#     cleaned_lines = []
#     for line in response_text.split('\n'):
#         if not line.strip().startswith('//'):
#             cleaned_lines.append(line)
#     return '\n'.join(cleaned_lines)    not using anymore

def validate_json(response_text):
    """
    Attempts to parse the response as JSON.
    If the response includes extra commentary or minor formatting issues, attempts to clean it.
    """
    try:
        # Extract JSON boundaries
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        cleaned_text = response_text[json_start:json_end]

        return json.loads(cleaned_text)
    except Exception as e:
        print(f"[DEBUG] JSON parsing failed: {str(e)}")
        return None
    
def extract_json_strict(text):
    """
    Extracts the first balanced JSON object found in the text, even if it's surrounded by extra text.
    Uses a manual brace-balancing approach since Python's re module does not support recursive patterns.
    """
    try:
        start = text.find('{')
        if start == -1:
            raise ValueError("No JSON object found in response.")

        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

        raise ValueError("No complete JSON object found in response.")
    except Exception as e:
        print(f"[ERROR] JSON strict extraction failed: {str(e)}")
        return None

def build_llm_prompt(extracted_text):
    return f"""
You are a highly skilled resume parser. Your task is to extract structured information from the provided unstructured resume text.

Return your output strictly in the following JSON format:
{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": [],
  "education": [
    {{"degree": "", "year": "", "line": ""}}
  ],
  "experience": [
    {{"title_line": "", "dates": [], "organisation": "", "description": ""}}
  ],
  "projects": [
    {{"title": "", "description": ""}}
  ],
  "trainings": [],
  "achievements": [],
  "other_sections": {{}}
}}

### STRICT JSON RULE:
- Never write long sentences as keys.
- All keys in "other_sections" must be short titles only.
- Never insert complete experience descriptions or project details as keys in JSON. Those must always be inside 'description' fields.
- Ensure every JSON object has keys followed by ':' and then a value.
- If unsure about any section, skip adding it to 'other_sections'.
- Never create keys that start with a job title or include full sentences. Those must be part of 'experience' or 'projects'.

### Field-Specific Rules:
- "other_sections" must always be a dictionary with meaningful section titles as keys and their content as values (strings or list of strings).
- For each project, always include both "title" and "description". If not available, use an empty string.
- For all sections, return clean text without visual cues or formatting markers.
- Words like 'Tools', or 'Technology' or 'Tech Stack' mean that they are skills.

### Experience Dates Extraction Rules:
- Dates for experience must be provided as a list of exactly **two elements: [Start Date, End Date]**.
- Each date must strictly follow the format: YYYY-MM.
- Example: "May 2022 to Present" → ["2022-05", "Present"]
- Example: "Jan 2020 to March 2022" → ["2020-01", "2022-03"]
- Example: "05/22 - 01/23" → ["2022-05", "2023-01"]
- Example: "2016" → ["2016-01", "2016-01"]
- Example: "Feb 2023" → "2023-02"  
- Example: "June 2019" → "2019-06"  
- Never return dates like "May 2022 - Present" as a single string. Always separate them into two list items.
- All dates must always follow this two-item list structure.
- If the date is written as 'Aug 2021', you must return '2021-08'.
- If the date is written as just '2022', you must return '2022-01'.
- Never return dates like 'Aug 2021' or '2022' as-is. Always convert them to YYYY-MM format.



### Extraction Instructions:
- Extract the candidate’s full name accurately.
- Extract the most relevant and correctly formatted email and phone number.
- Skills must be a list of unique skills mentioned in the resume.
- For education, include degree, graduation year, and the full text line.
- "Extract **all experiences and all education qualifications, whether past or current, whether internships, jobs, or freelancing. Do not skip any entry. Include dates and organization for each role. Even if you are unsure, include the entry."
- For experience:
    - Extract each job title, organization, description, and date range.
    - Dates must always follow **YYYY-MM** format as described above.
- For projects, list each project’s title and its description.
- Include trainings and achievements as individual strings.
- If you find sections not matching the above (e.g., publications, certifications, languages, interests, summary), add them to "other_sections" as key-value pairs.

### Input Resume:
{extracted_text}

### Output:
Return the parsed JSON only. Do not add extra commentary or code snippets.
"""



#     return f"""
# Extract structured resume information in strict JSON format with the following keys:
# name, email, phone, skills, education, experience, projects, trainings, achievements, other_sections.

# Always include all keys, even if empty. No extra text, no comments.

# Resume:
# {extracted_text}
# """

def call_phi3_model(prompt):
    print("[INFO] Feeding the input to the model now\n")
    payload = {
        "model": MODEL_NAME,
        "prompt": f"<s>[INST] {prompt} [/INST]",
        "stream": False
    }

    session = requests.Session()

    # Add retries with exponential backoff
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        response = session.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()
        response_json = response.json()

        if 'response' in response_json:
            structured_output = response_json['response']
            print("[DEBUG] Raw LLM Response:\n", structured_output)

            cleaned_output = deep_clean_llm_response(structured_output)
            parsed_output = validate_json(cleaned_output)

            if parsed_output:
                cleaned_output = post_process_llm_output(parsed_output)
                return cleaned_output
            else:
                raise Exception("Invalid JSON returned by the model.")

    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] LLM processing failed: {str(e)}")
        return None
    
