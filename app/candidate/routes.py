from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import json
from concurrent.futures import ThreadPoolExecutor

# Importing your existing utilities
from parser.resume_extractor import extract_text_from_pdf
#from parser.structured_extractor_positional import build_resume_json_positional
#from parser.structured_extractor import segment_sections
from parser.save_structured_text import save_structured_sections
#from parser.positional_extractor import extract_with_positions
from parser.llm_structured_extractor import build_llm_prompt, validate_json, deep_clean_llm_response, post_process_llm_output
from parser.llm_fallback import call_gpt4o_mini_fallback
# from ai_models.tinyllama_runner import call_tinyllama
from parser.groq_fallback import call_groq_model
from jd_parser.jd_model import parse_jd_with_model
from jd_parser.llm_9_parser import parse_jd_with_gemma
from resume_jd_comparator.comparison_engine import ResumeJDComparator

from auth.auth_utils import auth_required

candidate_bp = Blueprint('candidate', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
UPLOAD_FOLDER = 'app/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========================= Render Upload Page ============================
@candidate_bp.route('/dashboard', methods=['GET'])
@auth_required('candidate')
def tinyllama_upload_form():
    return render_template('candidate/dashboard.html')

# ========================= Full Parsing and Comparison ===================
@candidate_bp.route('/parse-all', methods=['POST'])
@auth_required('candidate')
def parse_all():
    if 'file' not in request.files or 'job_description' not in request.form:
        return jsonify({'error': 'Missing resume or job description'}), 400

    file = request.files['file']
    jd_text = request.form['job_description']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        try:
            def process_resume():
                extracted_text = extract_text_from_pdf(file_path)
                prompt = build_llm_prompt(extracted_text)
                structured_data, latency = call_groq_model(prompt)

                if structured_data is None:
                    raise Exception('Resume parsing failed with Groq model')

                if isinstance(structured_data, str):
                    try:
                        structured_data = json.loads(structured_data)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Failed to decode JSON from string: {e}")
                        raise Exception('Groq model returned invalid JSON string')

                with open('app/parsed_json/latest_resume.json', 'w', encoding='utf-8') as f:
                    json.dump(structured_data, f, ensure_ascii=False, indent=2)

                return structured_data

            def process_jd():
                parsed_jd = parse_jd_with_gemma(jd_text)
                if 'parsed_output' in parsed_jd:
                    return parsed_jd['parsed_output']
                return parsed_jd

            with ThreadPoolExecutor() as executor:
                future_resume = executor.submit(process_resume)
                future_jd = executor.submit(process_jd)

                resume_json = future_resume.result()
                jd_json = future_jd.result()

            if not resume_json or not jd_json:
                raise Exception('Parsing failed for either resume or JD.')

            with open('app/parsed_json/latest_JD.json', 'w', encoding='utf-8') as f:
                json.dump(jd_json, f, ensure_ascii=False, indent=2)

            comparator = ResumeJDComparator(resume_json, jd_json)
            comparison_result = comparator.compare()

            return jsonify({
                'message': 'Resume, JD parsed and compared successfully',
                'resume_json': resume_json,
                'jd_json': jd_json,
                'comparison_result': comparison_result
            }), 200

        except Exception as e:
            print(f"[ERROR] Full Exception Trace: {str(e)}")
            return jsonify({'error': f'Failed to process: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file format. Only PDF and DOCX allowed'}), 400

# ========================= Groq Structure Parsing ========================
@candidate_bp.route('/groq-structure', methods=['POST'])
@auth_required('candidate')
def groq_structure():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            extracted_text = extract_text_from_pdf(file_path)
            prompt = build_llm_prompt(extracted_text)
            structured_data, latency = call_groq_model(prompt)

            if structured_data is None:
                return jsonify({'error': 'Failed to process resume with Groq'}), 500

            if isinstance(structured_data, str):
                try:
                    structured_data = json.loads(structured_data)
                except json.JSONDecodeError as e:
                    return jsonify({'error': 'Groq returned invalid JSON string.'}), 500

            with open('app/parsed_json/latest_resume.json', 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)

            return jsonify({
                'message': 'File uploaded and structured with Groq successfully',
                'file_path': file_path,
                'text_preview': extracted_text[:500],
                'structured_data': structured_data,
                'structured_json_file': 'app/parsed_json/latest_resume.json'
            }), 200

        except Exception as e:
            return jsonify({'error': f'Failed to process with Groq: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file format. Only PDF and DOCX allowed'}), 400

# ========================= Parse JD - Phi3 ================================
@candidate_bp.route('/parse-jd', methods=['POST'])
@auth_required('candidate')
def parse_jd():
    jd_text = request.form['job_description']
    model_name = request.form.get('model_name', 'phi3')

    parsed_output = parse_jd_with_model(jd_text)

    return jsonify({'model_used': model_name, 'parsed_output': parsed_output})

# ========================= Parse JD - Gemma ================================
@candidate_bp.route('/parse-jd-gemma', methods=['POST'])
@auth_required('candidate')
def parse_jd_gemma():
    jd_text = request.form.get('job_description')
    if not jd_text:
        return jsonify({'error': 'Job description is required.'}), 400

    try:
        parsed_output = parse_jd_with_gemma(jd_text)
        return jsonify({
            'model_used': parsed_output['model_used'],
            'parsed_output': parsed_output['parsed_output']
        }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to parse JD with Gemma 4: {str(e)}'}), 500

# ========================= Compare Resume and JD ==========================
@candidate_bp.route('/compare-resume-jd', methods=['POST'])
@auth_required('candidate')
def compare_resume_jd():
    try:
        with open('app/parsed_json/latest_resume.json', 'r', encoding='utf-8') as f:
            resume_json = json.load(f)
        with open('app/parsed_json/latest_JD.json', 'r', encoding='utf-8') as f:
            jd_json = json.load(f)

        comparator = ResumeJDComparator(resume_json, jd_json)
        comparison_result = comparator.compare()

        return jsonify({
            'message': 'Resume-JD comparison completed successfully',
            'comparison_result': comparison_result
        }), 200

    except Exception as e:
        return jsonify({'error': f'Failed to compare resume and JD: {str(e)}'}), 500
