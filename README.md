# ForensicAI — Final Advanced Version

AI-assisted UFDR analysis and digital forensic investigation web application.

## Features
- Presentation login gate (NOT real authentication; OTP/Gmail intentionally deferred)
- Cases and case selection
- Multiple UFDR reports per case
- PDF extraction using pypdf
- SHA-256 integrity hash
- Dynamic artifact counts from uploaded evidence
- Evidence Explorer
- Timeline
- Explainable triage indicators
- Case-grounded AI assistant
- Investigation report JSON
- Audit log
- Empty states with NO fabricated forensic data

## Run
From `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

The login page is only a visual/presentation gate. It does not claim to provide real authentication.
