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

# Call OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
      {"role":"system","content":
       "You are an RFP analyzer. Output *only* markdown with headings: 
Summary, Risks, Next Steps."},
      {"role":"user","content": text}
    ]
)
analysis_md = resp.choices[0].message.content

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

print(f"Analysis sent to {email}")
