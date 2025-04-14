import os, json, base64, io, smtplib, argparse
from email.message import EmailMessage
from PyPDF2 import PdfReader
from docx import Document
from openai import OpenAI

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--payload-path", required=True)
args = parser.parse_args()

evt = json.load(open(args.payload_path))
email    = evt["client_payload"]["email"]
fname    = evt["client_payload"]["filename"]
b64      = evt["client_payload"]["data_b64"]
data     = base64.b64decode(b64)

# Extract text
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
    "You are a consultant that helps vendors respond to RFPs and other formal tenders. Your client has received the attached tender document. Your first task is to review the entire document and understand it. Provide a breakdown of the document. Do not give a preamble or explanation—just the breakdown.",

    # Prompt 2: Suggested Response Structure
    "Think about what a winning response would look like. What sections must your client's response document have to be responsive and compliant? Just list the structure—no preamble or conclusion.",

    # Prompt 3: Extract Requirements
    "Extract each requirement that the responding party needs to fulfill. Organize them into a bulleted list or table, categorizing by functional, technical, and compliance requirements.",

    # Prompt 4: Compliance Matrix
    "Using the extracted requirements, create a compliance matrix with columns: Requirement, Compliance (Yes/No/Partial), Notes or Additional Information. Leave only the first column (Requirement) blank.",

    # Prompt 5: Go/No-Go Questions
    "For each section, produce a list of questions your client must answer to draft their response. The list must be comprehensive: if all questions are answered, you can draft that section. Organize by section—no preamble or summary."
]

responses = []
for user_prompt in prompts:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an RFP analyzer. Output only markdown—no preamble or explanation."},
            {"role": "user", "content": user_prompt + "\n\n" + text}
        ]
    )
    responses.append(resp.choices[0].message.content)

# Combine into one markdown document
analysis_md = "\n\n---\n\n".join(responses)

# Email via Gmail SMTP
msg = EmailMessage()
msg["Subject"] = "Your RFP Analysis"
msg["From"]    = os.environ["GMAIL_USER"]
msg["To"]      = email
msg.set_content(analysis_md)

with smtplib.SMTP("smtp.gmail.com", 587) as s:
    s.starttls()
    s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_PASS"])
    s.send_message(msg)

print(f"✅ Analysis sent to {email}")

