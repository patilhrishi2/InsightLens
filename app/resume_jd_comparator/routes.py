from flask import Blueprint, request, jsonify
from resume_jd_comparator.comparison_engine import ResumeJDComparator

# Create Blueprint
comparator_bp = Blueprint('comparator_bp', __name__)

@comparator_bp.route('/compare-resume-jd', methods=['POST'])
def compare_resume_to_jd():
    try:
        data = request.json

        resume_json = data.get('resume_json')
        jd_json = data.get('jd_json')

        if not resume_json or not jd_json:
            return jsonify({'error': 'Missing resume_json or jd_json in request.'}), 400

        comparator = ResumeJDComparator(resume_json, jd_json)
        comparison_result = comparator.compare()

        return jsonify({'status': 'success', 'comparison_result': comparison_result}), 200

    except Exception as e:
        print(f"[ERROR] Exception in Resume-JD comparison: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
