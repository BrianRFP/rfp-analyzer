import os
import json
import io
import smtplib
import argparse
import requests
from email.message import EmailMessage
from PyPDF2 import PdfReader
from docx import Document

# Anthropic API Client Setup
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Function to interact with Claude model
def call_claude(prompt: str) -> str:
    url = "https://api.anthropic.com/v1/complete"  # URL for Anthropic API
    headers = {
        "Authorization": f"Bearer {ANTHROPIC_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "claude-v1",  # Specify Claude model version
        "prompt": prompt,
        "max_tokens": 1000,  # Adjust based on your requirement
        "temperature": 0.7,  # Adjust based on your requirement
        "stop_sequences": ["\n"]  # Optional, to control stopping of the model
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()  # Raise error if the request failed
    
    # Extract the model's completion from the response
    return response.json()['completion']

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--payload-path", required=True)
args = parser.parse_args()

# Load the event payload from GitHub
evt = json.load(open(args.payload_path))
email    = evt["client_payload"]["email"]
fname    = evt["client_payload"]["filename"]
file_url = evt["client_payload"]["file_url"]  # Updated: using file_url from R2

# Download file from Cloudflare R2 using requests
try:
    response = requests.get(file_url)
    response.raise_for_status()  # Ensure we stop on any download error
    data = response.content
except requests.exceptions.RequestException as e:
    print(f"Error downloading file: {e}")
    exit(1)

# Extract text from file
if fname.lower().endswith(".pdf"):
    reader = PdfReader(io.BytesIO(data))
    text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
elif fname.lower().endswith(".docx"):
    doc = Document(io.BytesIO(data))
    text = "\n\n".join(p.text for p in doc.paragraphs)
else:
    print("Unsupported file format.")
    exit(1)

# Define prompts to send to Claude (Anthropic)
prompts = [
    "You are a consultant that helps vendors respond to RFPs and other formal tenders. Your client has received the attached tender document. Your first task is to review the entire document and understand it. Provide a breakdown of the document. Do not give a preamble or explanation—just the breakdown.",
    "Think about what a winning response would look like. What sections must your client's response document have to be responsive and compliant? Just list the structure—no preamble or conclusion.",
    "Extract each requirement that the responding party needs to fulfill. Organize them into a bulleted list or table, categorizing by functional, technical, and compliance requirements.",
    "Using the extracted requirements, create a compliance matrix with columns: Requirement, Compliance (Yes/No/Partial), Notes or Additional Information. Leave only the first column (Requirement) blank.",
    "For each section, produce a list of questions your client must answer to draft their response. The list must be comprehensive: if all questions are answered, you can draft that section. Organize by section—no preamble or summary."
]

responses = []
for user_prompt in prompts:
    try:
        # Call Claude via the Anthropic API with each prompt
        response = call_claude(user_prompt + "\n\n" + text)
        responses.append(response)
    except Exception as e:
        print(f"Error during Claude API request: {e}")
        continue

# Combine all responses into one markdown document
analysis_md = "\n\n---\n\n".join(responses)

# Build email message and send via Gmail SMTP
msg = EmailMessage()
msg["Subject"] = "Your RFP Analysis"
msg["From"]    = os.environ["GMAIL_USER"]
msg["To"]      = email
msg.set_content(analysis_md)

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_PASS"])
        s.send_message(msg)
    print(f"✅ Analysis sent to {email}")
except Exception as e:
    print(f"Error sending email: {e}")

