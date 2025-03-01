from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from deep_translator import GoogleTranslator
from datetime import timedelta
import ollama
import requests
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure key

# Configure session duration
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)  # Session lasts for 30 days if "Remember Me" is checked

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Dummy user database (replace with a real database in production)
users = {
    'ruth': {'password': '123'},  # Default admin credentials
    'user1': {'password': 'password1'}  # Other users
}

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username in users:
        return User(username)
    return None

# Load financial dataset
with open('data/financial_data.json', 'r') as file:
    financial_data = json.load(file)

# Home route
@app.route('/')
@login_required
def home():
    return render_template('index.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')  # Check if "Remember Me" is selected

        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user, remember=remember)  # Set remember=True if "Remember Me" is checked
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username not in users:
            users[username] = {'password': password}
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        flash('Username already exists')
    return render_template('register.html')

# API route to handle user queries
@app.route('/ask', methods=['POST'])
@login_required
def ask():
    user_query = request.json.get('query')
    language = request.json.get('language', 'en')  # Default to English

    # Step 1: Check if the query is related to the dataset
    response = handle_local_query(user_query)
    if not response:
        # Step 2: If not found locally, perform a web search
        response = perform_web_search(user_query)

    # Translate response to the user's preferred language
    if language != 'en':
        response = translate_text(response, language)

    return jsonify({"response": response})

# Function to handle local queries using the dataset
def handle_local_query(query):
    try:
        # Use Ollama to generate a response based on the dataset
        prompt = f"""
        You are a friendly financial advisor in India. Explain things in simple English and use examples relevant to India.
        Use the following dataset to answer the user's query:
        {financial_data}

        User Query: {query}
        """
        response = ollama.generate(model="llama2", prompt=prompt)  # Use a smaller model
        return response['response']
    except Exception as e:
        print(f"Error generating response: {e}")
        return None

# Function to perform a web search using Google Custom Search JSON API
def perform_web_search(query):
    try:
        # Google Custom Search API endpoint
        api_key = "YOUR_GOOGLE_API_KEY"  # Replace with your Google API key
        search_engine_id = "YOUR_SEARCH_ENGINE_ID"  # Replace with your Search Engine ID
        search_url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={api_key}&cx={search_engine_id}"

        # Make the API request
        response = requests.get(search_url)
        if response.status_code == 200:
            search_results = response.json()
            # Extract the first result's snippet
            if 'items' in search_results and len(search_results['items']) > 0:
                return search_results['items'][0]['snippet']
            return "No relevant information found."
        return "Unable to fetch results from the web."
    except Exception as e:
        print(f"Web search error: {e}")
        return "Sorry, I couldn't fetch results from the web. Please try again later."

# Function to translate text
def translate_text(text, target_language):
    try:
        return GoogleTranslator(source='auto', target=target_language).translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return the original text if translation fails

# Route to generate a PDF report
@app.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
    user_query = request.json.get('query')
    response = handle_local_query(user_query)

    # Create a PDF report
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Financial Advisor Report", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Query: {user_query}", ln=True, align='L')
    pdf.multi_cell(0, 10, txt=f"Response: {response}")

    # Save the PDF
    report_path = os.path.join('reports', f'report_{current_user.id}.pdf')
    pdf.output(report_path)

    return jsonify({"report_path": report_path})

# Run the Flask app
if __name__ == '__main__':
    os.makedirs('reports', exist_ok=True)
    app.run(host='0.0.0.0', port=8080, debug=False)