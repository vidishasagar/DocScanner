# DocScanner

DocScanner is a web application that allows users to upload documents (PDF, DOC, DOCX), extract text, and classify the document type using the Gemini API. It includes a credit system where users get 20 free scans per day.

## Features

- **File Upload**: Upload PDF, DOC, or DOCX files.
- **Text Extraction**: Extract text from uploaded documents.
- **Document Classification**: Classify the document type using the Gemini API.
- **Credit System**: Users get 20 free scans per day.
- **Responsive UI**: Clean and modern user interface.

- **Daily Free Credits**:
   Every user starts with 20 free credits at midnight (local server reset).
   If credits are exhausted, the user must wait till the next day or request admin approval for more credits.

- **Admin Credit Management**:
   Users can submit a request for additional credits.
   Admin can approve or deny requests.
   Admin can manually adjust user credit balances.

- **Handling Credit Deductions**:
   Each document scan deducts 1 credit.
   If a user has 0 credits, they cannot scan until:
   The next daily reset, OR
   Admin manually adds more credits.

## Prerequisites

- Python 3.x
- Flask
- SQLAlchemy
- PyPDF2
- python-docx
- google-generativeai

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/DocScanner.git
   cd DocScanner
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**:
   ```bash
   python app.py
   ```

4. **Access the Application**:
   Open your browser and go to `http://127.0.0.1:5000`.

## Usage

1. **Register/Login**:
   - Register a new account or log in with existing credentials.

2. **Upload a File**:
   - Upload a PDF, DOC, or DOCX file to extract text.

3. **Classify Document**:
   - Classify the extracted text to determine the document type.

4. **Check Credits**:
   - Your remaining credits are displayed in the navigation bar.

## File Structure

```
DocScanner/
├── app.py                  # Main application file
├── requirements.txt        # List of dependencies
├── templates/              # HTML templates
│   ├── index.html          # Home page
│   ├── login.html          # Login page
│   ├── register.html       # Registration page
│   └── dashboard.html      # Dashboard page
├── static/                 # Static files (CSS, JS, etc.)
└── database.db             # SQLite database
```

## API Keys

To use the Gemini API, you need to configure your API key in `app.py`:

```python
genai.configure(api_key="YOUR_GEMINI_API_KEY")
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

Let me know if you need further adjustments or additional sections!
