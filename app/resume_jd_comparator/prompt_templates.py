def comprehensive_comparison_prompt(jd_json, resume_json, years_of_experience, min, max, preferred):
    return f"""
You are an expert resume evaluator and career coach.

You will evaluate the following resume against the provided job description (JD). Follow these strict evaluation steps in order.

Job Description:
{jd_json}

Candidate's Resume:
{resume_json}

1. **Education Check (Eligibility Gate):**
   - Verify if the candidate's education matches the JD.
   - If education does not match, set "education_flag" to false.

2. **Experience Check (Eligibility Gate):**
   - The candidate has {years_of_experience} years of experience (pre-calculated, do not re-calculate).
   - The JD mentions that the minimum required experience is: {min}, the maximum required experience is: {max}, and the preferred experience is: {preferred}.
   - If the candidate's experience is LESS THAN the minimum required experience, set "experience_flag" to false.
   - There is no flexibility or human judgment in this step. This is a hard gate. No exceptions.

3. **Skills Scoring (80% Weightage):**
   - Must Have Skills (70% of skill score, max 56 points)
   - Good to Have Skills (30% of skill score, max 24 points)
   - If the JD does not have any "Good to Have Skills" mentioned, allot full score for "Good to Have Skills" to the candidate.

   Important: You must ONLY consider the skills listed in the JD JSON under "Must Have Skills" and "Good to Have Skills."

   Do NOT add, infer, or assume any other skills beyond what is explicitly listed in the JD JSON.

   Compare the candidate's skills strictly against these lists.
   Identify which skills from the JD are present in the candidate’s resume, and which are missing.

4. **Experience Scoring (20% Weightage):**
   - If the JD provides a range (minimum and maximum years), score proportionally:
     Experience Score = ((Candidate's experience - Minimum required experience) / (Maximum preferred experience - Minimum required experience)) * 20.
     Award full 20 points if the candidate's experience is equal to or exceeds the JD's maximum preferred experience.

   - If the JD only provides a minimum requirement (and no maximum is given), award full 20 points if the candidate meets or exceeds the minimum.

   - If no experience requirement is provided in the JD, assume full 20 points.

5. **Final Score Calculation:**
   - Total Score = Must Have Skill Score + Good to Have Skill Score + Experience Score (Max: 100)

6. **Soft Skills Feedback:**
   - Check if soft skills from JD are present in resume.
   - Provide feedback but do not score.

7. **Final Feedback:**
   - Offer detailed, actionable, positive suggestions to improve the resume.
   - Write this as a single continuous paragraph. Do NOT use numbered lists, bullet points, or line breaks inside this field.
   - Do NOT write "1.", "2.", "3." or any numbering. Do NOT use "-" or "*" as list markers. Write flowing prose only.

8. **Eligibility Criteria**
   - Set "eligible" flag to true ONLY IF "education_flag" is true AND "experience_flag" is true

**IMPORTANT RULES:**
- You must evaluate the eligibility gates IN ORDER:
   1. First check education. If education does not meet the JD requirement, set 'education_flag': false .
   2. Then check experience. If experience does not meet the minimum, set 'experience_flag': false.
   3. If 'education_flag' or 'experience_flag' are false, set 'eligible': false.

- Eligibility must be determined, but you must ALWAYS complete scoring and feedback, even if the candidate is ineligible. **Scoring is mandatory for both eligible and ineligible candidates.**

**Standardize Wording:**
- If the candidate meets or exceeds the minimum experience, say: "The candidate has {years_of_experience} years of experience, which meets the minimum required experience of {min} years in the JD."
- If the candidate falls short, say: "The candidate has {years_of_experience} years of experience, which does not meet the minimum required experience of {min} years in the JD. The candidate is ineligible for this role based on experience."

Return this JSON (single-line compact format):
{{
  "eligible": true/false,
  "education_flag": true/false,
  "experience_flag": true/false,
  "education_feedback": "string",
  "experience_feedback": "string",
  "must_have_skills_matched": [],
  "must_have_skills_missing": [],
  "good_to_have_skills_matched": [],
  "good_to_have_skills_missing": [],
  "must_have_score": 0,
  "good_to_have_score": 0,
  "experience_score": 0,
  "overall_score": 0,
  "soft_skills_feedback": "string",
  "final_feedback": "string"
}}

Important:
- You must always perform and return scoring, regardless of eligibility.
- All JSON keys must be included.
- Return JSON in a single compact line, no line breaks.
- The order of the JSON keys must exactly match the provided structure. Start with 'eligible'.
- All string fields ("education_feedback", "experience_feedback", "soft_skills_feedback", "final_feedback") must be plain prose sentences only. Do NOT use numbered lists, bullet points, dashes, asterisks, newlines, or any markdown formatting inside any string field. Write everything as continuous flowing text.
"""
