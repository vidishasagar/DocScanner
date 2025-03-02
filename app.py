from flask import Flask, request, render_template, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import PyPDF2
import google.generativeai as genai
from werkzeug.utils import secure_filename
from docx import Document
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx'}
db = SQLAlchemy(app)
app.secret_key = 'secret_key'

# Initialize Gemini API
genai.configure(api_key="AIzaSyDWHgluGwk5bK8LFs0xuKs2RPe4cuFu8N8")

# User model with credits
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    credits = db.Column(db.Integer, default=20)  # Default credits
    last_reset = db.Column(db.DateTime, default=datetime.utcnow)  # Track last reset time

    def __init__(self, email, password, name):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.credits = 20  # Initialize with 20 credits
        self.last_reset = datetime.utcnow()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

# Create tables
with app.app_context():
    db.create_all()

# Helper function to reset credits daily
def reset_credits_if_needed(user):
    if datetime.utcnow() - user.last_reset >= timedelta(days=1):
        user.credits = 20  # Reset credits
        user.last_reset = datetime.utcnow()
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        new_user = User(name=name, email=email, password=password)
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            return render_template('register.html', error=f"Database error: {str(e)}")
        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['email'] = user.email
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Invalid user')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'email' in session:
        user = User.query.filter_by(email=session['email']).first()
        reset_credits_if_needed(user)  # Reset credits if needed
        return render_template('dashboard.html', user=user)
    
    return redirect('/login')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect('/login')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'email' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(email=session['email']).first()
    reset_credits_if_needed(user)  # Reset credits if needed

    if user.credits <= 0:
        return jsonify({"error": "No credits remaining. Please try again tomorrow."}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower()
    extracted_text = ""

    try:
        if file_ext == "pdf":
            extracted_text = extract_text_from_pdf(file)
        elif file_ext in {"doc", "docx"}:
            extracted_text = extract_text_from_doc(file)
        
        # Decrement credits
        user.credits -= 1
        db.session.commit()

        return jsonify({"extracted_text": extracted_text, "filename": filename, "credits_remaining": user.credits})
    
    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500

def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        pdf_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text.append(text.strip())
        return "\n".join(pdf_text) if pdf_text else "No readable text found in the PDF."
    except Exception as e:
        return f"Unexpected error: {str(e)}"

def extract_text_from_doc(doc_file):
    try:
        doc = Document(doc_file)
        text = "\n".join([para.text.strip() for para in doc.paragraphs if para.text.strip()])
        return text if text else "No readable text found in the document."
    except Exception as e:
        return f"Error processing Word document: {str(e)}"

@app.route('/classify', methods=['POST'])
def classify_document():
    data = request.get_json()
    extracted_text = data.get('text', '')

    if not extracted_text:
        return jsonify({"error": "No text provided"}), 400

    document_types = """
    Legal Documents: Contracts, Terms & Conditions, Privacy Policies, Wills & Testaments.
    Financial & Business Documents: Invoices, Balance Sheets, Profit & Loss Statements, Tax Forms.
    Government & Identity Documents: Passports, Aadhar Cards, Driving Licenses, Voter ID Cards.
    Academic & Research Documents: Research Papers, Thesis, Lecture Notes, Student Transcripts.
    Medical Documents: Prescriptions, Medical Reports, Insurance Claims, Discharge Summaries.
    HR & Employee Documents: Resumes, Offer Letters, Salary Slips, Appraisal Reports.
    Marketing & Promotional Documents: Brochures, Advertisements, Newsletters, Press Releases.
    Personal & Miscellaneous Documents: Diaries, Letters, Certificates, Receipts.
    """

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Classify the given document into one of the following categories:\n{document_types}\n\n"
            "If the document does not match exactly with any category, use your intelligence to determine the closest category and document type.\n"
            "Provide the output in the following structured format:\n"
            "Document Category: <Category Name>\n\n"
            "Potential Document Type: <Specific Document Name>\n\n"
            f"Document Text:\n{extracted_text}"
            "Ensure there are no extra characters, symbols, or markdown in the response."
        )
        response = model.generate_content(prompt)
        classification = response.text.strip() if response and hasattr(response, "text") else "Classification not available"
        return jsonify({"classification": classification})

    except Exception as e:
        return jsonify({"error": f"Failed to classify document: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)