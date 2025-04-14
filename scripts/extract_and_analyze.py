import os
import json
import io
import smtplib
import argparse
import requests
from email.message import EmailMessage
from PyPDF2 import PdfReader
from docx import Document
# from openai import OpenAI  # Commented out for test email only

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--payload-path", required=True)
args = parser.parse_args()

# Load the event payload from GitHub
evt = json.load(open(args.payload_path))
email    = evt["client_payload"]["email"]
fname    = evt["client_payload"]["filename"]
file_url = evt["client_payload"]["file_url"]

# Download file from Cloudflare R2 using requests
response = requests.get(file_url)
response.raise_for_status()
data = response.content

# Extract text from file
if fname.lower().endswith(".pdf"):
    reader = PdfReader(io.BytesIO(data))
    text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
else:
    doc = Document(io.BytesIO(data))
    text = "\n\n".join(p.text for p in doc.paragraphs)

# --- ChatGPT/OpenAI functionality commented out for testing email only ---

# client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
# 
# prompts = [
#     "You are a consultant that helps vendors respond to RFPs and other formal tenders. Your client has received the attached tender document. Your first task is to review the entire document and understand it. Provide a breakdown of the document. Do not give a preamble or explanation—just the breakdown.",
#     "Think about what a winning response would look like. What sections must your client's response document have to be responsive and compliant? Just list the structure—no preamble or conclusion.",
#     "Extract each requirement that the responding party needs to fulfill. Organize them into a bulleted list or table, categorizing by functional, technical, and compliance requirements.",
#     "Using the extracted requirements, create a compliance matrix with columns: Requirement, Compliance (Yes/No/Partial), Notes or Additional Information. Leave only the first column (Requirement) blank.",
#     "For each section, produce a list of questions your client must answer to draft their response. The list must be comprehensive: if all questions are answered, you can draft that section. Organize by section—no preamble or summary."
# ]
# 
# responses = []
# for user_prompt in prompts:
#     resp = client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": "You are an RFP analyzer. Output only markdown—no preamble or explanation."},
#             {"role": "user", "content": user_prompt + "\n\n" + text}
#         ]
#     )
#     responses.append(resp.choices[0].message.content)
# 
# analysis_md = "\n\n---\n\n".join(responses)

# For testing: Replace ChatGPT output with a simple message
analysis_md = "Hello from your RFP analyzer!"

# Build email message and send via Gmail SMTP
msg = EmailMessage()
msg["Subject"] = "Test Email from RFP Analyzer"
msg["From"]    = os.environ["GMAIL_USER"]
msg["To"]      = email
msg.set_content(analysis_md)

with smtplib.SMTP("smtp.gmail.com", 587) as s:
    s.starttls()
    s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_PASS"])
    s.send_message(msg)

print(f"✅ Test email sent to {email}")


