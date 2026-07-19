import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from flask import Flask, render_template
from candidate.routes import candidate_bp
from jd_parser.routes import jd_parser_bp
from resume_jd_comparator.routes import comparator_bp  # ✅ Import this
from hr_dashboard.routes import hr_dashboard_bp
from auth.routes import auth_bp
from datetime import timedelta

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'app/uploads'
# app.secret_key = 'your_secret_key'  # Required for sessions
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')

# 🔒 Optional: Set session lifetime (e.g., 30 minutes)
app.permanent_session_lifetime = timedelta(minutes=30)
# Register blueprints
app.register_blueprint(candidate_bp, url_prefix='/candidate')
app.register_blueprint(jd_parser_bp)
app.register_blueprint(comparator_bp)  # ✅ Register this
app.register_blueprint(hr_dashboard_bp)
app.register_blueprint(auth_bp)

# ✅ Add this route to serve the landing page
@app.route('/')
def landing_page():
    return render_template('index.html')

# ✅ Register Page Route
@app.route('/register')
def register_page():
    return render_template('registerPage.html')

# ✅ Login Page Route
# @app.route('/login')
# def login_page():
#     return render_template('loginPage.html')

if __name__ == '__main__':
    app.run(debug=True)
