from resume_jd_comparator.prompt_templates import comprehensive_comparison_prompt
from resume_jd_comparator.utils import (
    call_llm_api, calculate_total_experience, try_json_loads
)
from resume_jd_comparator.utils import call_openai_gpt4o
import re


class ResumeJDComparator:

    def __init__(self, resume_json, jd_json):
        self.resume_json = resume_json
        self.jd_json = jd_json
    def safe_cast_to_int(value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def compare(self):
        # Extract experience from JD
        # jd_experience_required = extract_required_experience(self.jd_json.get('Experience', ''))
        jd_experience_required = self.jd_json.get('Experience', {
    'minimum_experience': None,
    'maximum_experience': None,
    'preferred_experience': None
    })
        # Calculate experience from Resume
        experience_result = calculate_total_experience(self.resume_json.get('experience', []), self.resume_json)
        resume_experience_years = round(experience_result['total_months'] / 12, 2)
        formatted_experience = experience_result['formatted']

        print(f"[INFO] JD Required Experience: {jd_experience_required} years")
        print(f"[INFO] Resume Total Experience: {resume_experience_years} years")
        # Determine if candidate meets minimum experience requirement
        min_exp = ResumeJDComparator.safe_cast_to_int(jd_experience_required.get('minimum_experience'))
        max_exp = ResumeJDComparator.safe_cast_to_int(jd_experience_required.get('maximum_experience'))
        preferred_exp = ResumeJDComparator.safe_cast_to_int(jd_experience_required.get('preferred_experience'))

        
        prompt = comprehensive_comparison_prompt(self.jd_json, self.resume_json, resume_experience_years, min_exp, max_exp, preferred_exp)
        # print(f"[DEBUG] Prompt for full comparison:\n{prompt}\n")

        raw_response = call_llm_api(prompt)

        if isinstance(raw_response, dict):
            result = raw_response
        elif isinstance(raw_response, str):
            result = try_json_loads(raw_response)
            if result is None:
                print("[ERROR] LLM returned invalid JSON. Using fallback response.")
                return {'error': 'LLM response invalid. Please try again.'}
        else:
            print(f"[ERROR] Unexpected LLM response type: {type(raw_response)}")
            return {'error': 'Unexpected LLM response type.'}

        return result
    

    def get_experience_years(self):
        experience_data = calculate_total_experience(self.resume_json.get('experience', []), self.resume_json)
        total_months = experience_data['total_months']
        return round(total_months / 12, 2)  # Round ed for clean table display

