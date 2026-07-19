from flask import Blueprint, request, jsonify
from jd_parser.llm_9_parser import parse_jd_with_gemma

# Create Blueprint
jd_parser_bp = Blueprint('jd_parser_bp', __name__)

@jd_parser_bp.route('/parse-jd-gemma', methods=['POST'])
def parse_jd_gemma_route():
    try:
        data = request.json

        # Validate input
        jd_text = data.get('jd_text', '')
        if not jd_text.strip():
            return jsonify({'error': 'No JD text provided.'}), 400

        # Call the Google Gemma JD parser
        result = parse_jd_with_gemma(jd_text)

        return jsonify({'status': 'success', 'parsed_output': result}), 200

    except Exception as e:
        print(f"[ERROR] Exception in JD parsing: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
