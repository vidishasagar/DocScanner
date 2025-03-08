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

# Admin model
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

# Credit Request model
# Credit Request model
class CreditRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Define a relationship to the User model
    user = db.relationship('User', backref='credit_requests')

    def __init__(self, user_id, amount):
        self.user_id = user_id
        self.amount = amount
        # self.amount = amount

# Create tables and add default admin
with app.app_context():
    db.create_all()
    # Add a default admin (for testing)
    if not Admin.query.filter_by(username='admin').first():
        default_admin = Admin(username='admin', password='admin@123')  # Updated password
        db.session.add(default_admin)
        db.session.commit()

# Helper function to reset credits daily (for users only)
def reset_credits_if_needed(user):
    if datetime.utcnow() - user.last_reset >= timedelta(days=1):
        user.credits = 20  # Reset credits
        user.last_reset = datetime.utcnow()
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update_credits/<int:user_id>', methods=['POST'])
def update_credits(user_id):
    if 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    new_credits = data.get('credits')

    if not new_credits or not isinstance(new_credits, int):
        return jsonify({"error": "Invalid credits value"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.credits = new_credits
    db.session.commit()

    return jsonify({"message": "Credits updated successfully"}), 200

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

# Admin Login Route
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin'] = admin.username
            return redirect('/admin')  # Redirect to admin dashboard
        else:
            return render_template('admin_login.html', error='Invalid admin credentials')

    return render_template('admin_login.html')

# Admin Dashboard Route
@app.route('/admin')
def admin_dashboard():
    if 'admin' in session:
        # Fetch all users and their credits
        users = User.query.all()
        # Fetch all pending credit requests
        credit_requests = CreditRequest.query.filter_by(status='pending').all()
        return render_template('admin.html', users=users, credit_requests=credit_requests)
    return redirect('/admin_login')

# Admin Logout Route
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin_login')

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
    if 'email' not in session and 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = None
    if 'email' in session:
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
        
        # Decrement credits only for regular users
        if user:
            user.credits -= 1
            db.session.commit()

        return jsonify({
            "extracted_text": extracted_text,
            "filename": filename,
            "credits_remaining": user.credits if user else "Unlimited"
        })
    
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

# Route to handle credit requests
@app.route('/request_credits', methods=['POST'])
def request_credits():
    if 'email' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    amount = data.get('amount')

    # Debugging: Log the incoming amount
    print(f"Incoming amount: {amount} (Type: {type(amount)})")

    if not amount or not isinstance(amount, int) or amount < 1:
        return jsonify({"error": "Invalid credit amount"}), 400

    user = User.query.filter_by(email=session['email']).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Create a new credit request
    new_request = CreditRequest(user_id=user.id, amount=amount)
    db.session.add(new_request)
    db.session.commit()

    return jsonify({"success": True, "message": "Credit request submitted successfully"}), 200

# Route to approve a credit request
@app.route('/approve_credit_request/<int:request_id>', methods=['POST'])
def approve_credit_request(request_id):
    if 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    credit_request = CreditRequest.query.get(request_id)
    if not credit_request:
        return jsonify({"error": "Credit request not found"}), 404

    user = User.query.get(credit_request.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Update user credits
    user.credits += credit_request.amount
    credit_request.status = 'approved'
    db.session.commit()

    return jsonify({"success": True, "message": "Credit request approved successfully"}), 200

# Route to deny a credit request
@app.route('/deny_credit_request/<int:request_id>', methods=['POST'])
def deny_credit_request(request_id):
    if 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    credit_request = CreditRequest.query.get(request_id)
    if not credit_request:
        return jsonify({"error": "Credit request not found"}), 404

    credit_request.status = 'denied'
    db.session.commit()

    return jsonify({"success": True, "message": "Credit request denied successfully"}), 200

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
