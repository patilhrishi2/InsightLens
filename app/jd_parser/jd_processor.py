# jd_processor.py

import re
import json

# =========================
# JSON Extraction Function
# =========================
def extract_json(text):
    try:
        # Remove markdown code block if present
        text = text.strip()
        if text.startswith('```json'):
            text = text.replace('```json', '', 1).strip()
        if text.endswith('```'):
            text = text[:-3].strip()

        # Gemma 4 sometimes does chain-of-thought reasoning before producing
        # the actual JSON at the end of the response. So we collect ALL complete
        # balanced JSON objects and return the LAST one, which is always the
        # final answer rather than an intermediate reasoning fragment.
        candidates = []
        i = 0
        while i < len(text):
            if text[i] != '{':
                i += 1
                continue

            # Found a '{' — try to walk to its matching '}'
            start = i
            depth = 0
            in_string = False
            escape_next = False
            j = i

            while j < len(text):
                char = text[j]
                if escape_next:
                    escape_next = False
                    j += 1
                    continue
                if char == '\\' and in_string:
                    escape_next = True
                    j += 1
                    continue
                if char == '"':
                    in_string = not in_string
                    j += 1
                    continue
                if in_string:
                    j += 1
                    continue
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start:j + 1])
                        i = j + 1
                        break
                j += 1
            else:
                # No matching '}' found from this '{' — move on
                i += 1

        if not candidates:
            return {"error": "No JSON object found in the model response.", "raw_output": text}

        # Try parsing from last candidate to first — last is most likely the real answer
        for json_str in reversed(candidates):
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue

        return {"error": "No valid JSON object found in the model response.", "raw_output": text}

    except Exception as e:
        return {"error": f"JSON extraction failed: {str(e)}", "raw_output": text}


# =========================
# JD Prompt Templates
# =========================
def get_jd_prompt(jd_text):
    """Single combined prompt that extracts all JD fields in one API call."""
    return f"""Output this JSON object filled with data extracted from the Job Description below. Do not write anything before or after the JSON. Do not explain your reasoning. Stop immediately after the closing curly brace.

{{
    "Job Title": "Software Engineer",
    "Company Name": "Acme Corp",
    "Location": "New York, USA",
    "Salary": "100000 USD",
    "Employment Type": "Full-time",
    "Experience": {{
        "minimum_experience": 2,
        "maximum_experience": 5,
        "preferred_experience": null
    }},
    "Must Have Skills": ["Python", "Machine Learning"],
    "Good to Have Skills": ["Docker", "Kubernetes"],
    "Soft Skills": ["Communication", "Teamwork"],
    "Education": "Bachelor's degree in Computer Science or related field"
}}

Rules:
- Use null for any field not mentioned in the JD.
- Experience values must be integers or null. Do not use strings.
- Must Have Skills: skills that are explicitly required or mandatory.
- Good to Have Skills: skills that are preferred, optional, or nice to have. Use empty list if none mentioned.
- Soft Skills: behavioral skills like communication, teamwork, leadership, adaptability. Use empty list if none mentioned.
- Education: extract as a single string. Use null if not mentioned.
- Your entire response must be only the JSON object above, filled with real values from the JD.
- Do NOT think out loud. Do NOT use bullet points. Do NOT add any text outside the JSON.

---
Job Description:
{jd_text}
---"""

# =========================
# Post Processing Function
# =========================
def merge_results(combined_result):
    final_output = {}
    for key, value in combined_result.items():
        if isinstance(value, dict):
            final_output.update(value)
        else:
            final_output[key] = value
    return final_output
