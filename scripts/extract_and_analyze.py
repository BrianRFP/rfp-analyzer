import os
import json
import io
import smtplib
import argparse
import requests
import markdown
from email.message import EmailMessage
from PyPDF2 import PdfReader
from docx import Document
from openai import OpenAI

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
response = requests.get(file_url)
response.raise_for_status()  # Ensure we stop on any download error
data = response.content

# Extract text from file
if fname.lower().endswith(".pdf"):
    reader = PdfReader(io.BytesIO(data))
    text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
else:
    doc = Document(io.BytesIO(data))
    text = "\n\n".join(p.text for p in doc.paragraphs)

# Call OpenAI with multiple structured prompts
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompts = [
    # Prompt 1: Document Breakdown
    "You are a consultant that helps vendors respond to RFPs and other formal tenders. Your client has received the attached tender document. Your first task is to review the entire document and understand it. Please review it and develop an understanding of the document contents. Provide a breakdown of the document. Do not give a preamble or explanation of what you did, and do not describe what the breakdown is or its value. Just provide the breakdown.",
    # Prompt 2: Suggested Response Structure
    "Think about what a winning response would look like. What are the sections that your client's response document must have in order to be responsive and compliant with the tender document? Just provide the suggested structure, don't give a preamble or conclusion.",
    # Prompt 3: Extract Requirements
    "Extract each requirement that the responding party needs to fulfill. Organize them into a bulleted list or table format, categorizing them by functional, technical, and compliance requirements.",
    # Prompt 4: Compliance Matrix
    "Using the extracted requirements, create a compliance matrix with the following columns: Requirement, Compliance (Yes/No/Partial), Notes or Additional Information Don't fill in the table, other than the first column (Requirement).",
    # Prompt 5: Go/No-Go Questions
    "For each section, produce a list of questions that your client must answer in order for you to draft their response. The list of questions must be comprehensive and complete: if all of the questions for a given section are answered by your client, you should have enough information to draft that section of the document. Just provide the list of questions organized by section. Don't give a preamble or summary.",
    #Prompt 6: Another Prompt
    "From these questions, select the questions that your client should answer in order to perform a go/no-go analysis. Just provide the list of questions organized by section. Don't give a preamble or summary."
]

responses = []
for user_prompt in prompts:
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an RFP analyzer. Output only markdown—no preamble or explanation."},
            {"role": "user", "content": user_prompt + "\n\n" + text}
        ]
    )
    responses.append(resp.choices[0].message.content)

# Combine all responses into one markdown document
analysis_md = "\n\n---\n\n".join(responses)

analysis_html = markdown.markdown(analysis_md)


# Build email message and send via Gmail SMTP
msg = EmailMessage()
msg["Subject"] = "Your RFP Analysis"
msg["From"]    = os.environ["GMAIL_USER"]
msg["To"]      = email
msg.set_content(analysis_html)

with smtplib.SMTP("smtp.gmail.com", 587) as s:
    s.starttls()
    s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_PASS"])
    s.send_message(msg)

print(f"✅ Analysis sent to {email}")
