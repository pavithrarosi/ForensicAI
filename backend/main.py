
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib, json, re, uuid, shutil, html

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
REPORTS = DATA / "reports"
STORE = DATA / "store.json"
FRONTEND = BASE / "frontend"

for p in (UPLOADS, REPORTS):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ForensicAI", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def load():
    if STORE.exists():
        try: return json.loads(STORE.read_text(encoding="utf-8"))
        except Exception: pass
    return {"cases": [], "reports": [], "records": [], "audit": []}

def save(db):
    STORE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

def audit(db, case_id, action, details=""):
    db["audit"].insert(0, {"id": str(uuid.uuid4()), "case_id": case_id, "action": action, "details": details,
                           "timestamp": datetime.now().isoformat(timespec="seconds")})
    save(db)

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()

def parse_pdf(path):
    if PdfReader is None: raise RuntimeError("pypdf is not installed")
    reader=PdfReader(str(path))
    pages=[]
    for p in reader.pages:
        try: pages.append(p.extract_text() or "")
        except Exception: pages.append("")
    text="\n".join(pages)
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    records=[]
    # Extract line-oriented forensic artifacts conservatively. No demo fallback.
    patterns = [
        ("message", r"(whatsapp|signal|telegram|sms|imessage).*(message|chat|text)"),
        ("call", r"\b(call|incoming|outgoing|missed)\b"),
        ("location", r"(latitude|longitude|gps|location)"),
        ("browser", r"(http://|https://|browser|search query|visited)"),
        ("media", r"(\.jpg|\.jpeg|\.png|\.mp4|\.mov|\.wav|\.mp3)\b"),
        ("application", r"(installed application|application name|version)"),
        ("contact", r"(contact name|phone number|email)")
    ]
    for i,line in enumerate(lines):
        low=line.lower()
        kind="other"
        for k,p in patterns:
            if re.search(p,low): kind=k; break
        records.append({"record_id": f"R{i+1:05d}", "type": kind, "timestamp": "",
                        "summary": line[:500], "raw": line})
    # Capture common metadata fields without inventing values.
    metadata={}
    for key, labels in {
        "case_id":["case id","case number"], "case_name":["case name"],
        "agency":["agency"], "examiner":["examiner","investigator"],
        "device":["device model","model"], "manufacturer":["manufacturer"],
        "os":["operating system","os"], "sha256":["sha-256","sha256"]
    }.items():
        for line in lines:
            for label in labels:
                m=re.match(rf"^\s*{re.escape(label)}\s*[:\-]\s*(.+)$", line, re.I)
                if m: metadata[key]=m.group(1).strip(); break
            if key in metadata: break
    return {"pages":len(reader.pages), "text":text, "records":records, "metadata":metadata}

@app.get("/")
def home():
    return FileResponse(FRONTEND/"index.html")

@app.get("/assets/{name}")
def assets(name:str):
    path=FRONTEND/name
    if not path.exists(): raise HTTPException(404)
    return FileResponse(path)

@app.get("/api/health")
def health(): return {"ok":True, "version":"2.0"}

@app.get("/api/cases")
def cases():
    return load()["cases"]

class CaseIn(BaseModel):
    case_id:str
    name:str
    description:str=""
    examiner:str=""
    investigation_date:str=""

@app.post("/api/cases")
def create_case(c:CaseIn):
    db=load()
    if any(x["case_id"]==c.case_id for x in db["cases"]):
        raise HTTPException(409,"Case ID already exists")
    item={**c.model_dump(), "created_at":datetime.now().isoformat(timespec="seconds")}
    db["cases"].append(item); save(db); audit(db,c.case_id,"CASE_CREATED",c.name)
    return item

@app.get("/api/cases/{case_id}")
def get_case(case_id:str):
    db=load(); c=next((x for x in db["cases"] if x["case_id"]==case_id),None)
    if not c: raise HTTPException(404,"Case not found")
    return c

@app.get("/api/cases/{case_id}/reports")
def case_reports(case_id:str):
    db=load(); return [r for r in db["reports"] if r["case_id"]==case_id]

@app.post("/api/cases/{case_id}/reports")
async def upload_report(case_id:str, file:UploadFile=File(...)):
    db=load()
    if not any(x["case_id"]==case_id for x in db["cases"]): raise HTTPException(404,"Case not found")
    rid="RPT-"+uuid.uuid4().hex[:10].upper()
    safe=Path(file.filename or "report.pdf").name
    path=UPLOADS/(rid+"_"+safe)
    with open(path,"wb") as out: shutil.copyfileobj(file.file,out)
    digest=sha256(path)
    report={"report_id":rid,"case_id":case_id,"filename":safe,"sha256":digest,
            "uploaded_at":datetime.now().isoformat(timespec="seconds"),"status":"processing","pages":0}
    try:
        parsed=parse_pdf(path)
        report.update({"status":"processed","pages":parsed["pages"],"metadata":parsed["metadata"]})
        for rec in parsed["records"]:
            rec.update({"case_id":case_id,"report_id":rid})
            db["records"].append(rec)
    except Exception as e:
        report.update({"status":"failed","error":str(e)})
    db["reports"].append(report); save(db); audit(db,case_id,"REPORT_UPLOADED",rid)
    return report

@app.get("/api/cases/{case_id}/summary")
def summary(case_id:str):
    db=load(); rec=[r for r in db["records"] if r["case_id"]==case_id]
    cnt=Counter(r["type"] for r in rec)
    reports=[r for r in db["reports"] if r["case_id"]==case_id]
    return {"case_id":case_id,"reports":len(reports),"records":len(rec),"counts":dict(cnt),
            "processed_reports":sum(r["status"]=="processed" for r in reports),
            "failed_reports":sum(r["status"]=="failed" for r in reports)}

@app.get("/api/cases/{case_id}/records")
def records(case_id:str, q:str="", type:str="", report_id:str=""):
    db=load(); rows=[r for r in db["records"] if r["case_id"]==case_id]
    if type: rows=[r for r in rows if r["type"]==type]
    if report_id: rows=[r for r in rows if r["report_id"]==report_id]
    if q:
        q=q.lower(); rows=[r for r in rows if q in json.dumps(r,ensure_ascii=False).lower()]
    return rows[:2000]

@app.get("/api/cases/{case_id}/timeline")
def timeline(case_id:str):
    db=load(); return [r for r in db["records"] if r["case_id"]==case_id][:500]

@app.get("/api/cases/{case_id}/audit")
def audit_log(case_id:str):
    return [x for x in load()["audit"] if x["case_id"]==case_id]

class AssistantIn(BaseModel):
    question:str

@app.post("/api/cases/{case_id}/assistant")
def assistant(case_id:str, body:AssistantIn):
    db=load(); rec=[r for r in db["records"] if r["case_id"]==case_id]
    q=body.question.lower()
    counts=Counter(r["type"] for r in rec)
    if not rec: answer="No forensic records are available for this case. Upload and process a UFDR report first."
    elif "message" in q: answer=f"The current case contains {counts.get('message',0)} extracted message-related records."
    elif "call" in q: answer=f"The current case contains {counts.get('call',0)} extracted call-related records."
    elif "location" in q or "gps" in q: answer=f"The current case contains {counts.get('location',0)} extracted location-related records."
    elif "contact" in q: answer=f"The current case contains {counts.get('contact',0)} extracted contact-related records."
    else: answer=f"I found {len(rec)} extracted records across {len(set(r['report_id'] for r in rec))} report(s). I can answer only from those extracted records."
    audit(db,case_id,"ASSISTANT_QUERY",body.question)
    return {"answer":answer,"grounded_records":len(rec)}

@app.post("/api/cases/{case_id}/generate-report")
def generate_report(case_id:str):
    db=load(); rec=[r for r in db["records"] if r["case_id"]==case_id]
    payload={"case_id":case_id,"generated_at":datetime.now().isoformat(timespec="seconds"),
             "reports":[r for r in db["reports"] if r["case_id"]==case_id],
             "record_counts":dict(Counter(r["type"] for r in rec)),
             "records":rec}
    out=REPORTS/(case_id+"_investigation_report.json")
    out.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    audit(db,case_id,"REPORT_GENERATED",out.name)
    return FileResponse(out, filename=out.name, media_type="application/json")

SUSPICIOUS_TERMS = re.compile(
    r"password|threat|suspicious|malware|deleted|recovered|urgent|unknown|hidden|secret|credential|phishing|fraud",
    re.I,
)

def suspicious_records(records):
    return [r for r in records if SUSPICIOUS_TERMS.search((r.get("raw") or "") + " " + (r.get("summary") or ""))]

def _p(text, style):
    return Paragraph(html.escape(str(text or "")).replace("\n", "<br/>"), style)

@app.post("/api/cases/{case_id}/generate-suspicious-pdf")
def generate_suspicious_pdf(case_id:str):
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(500, "PDF generation is unavailable. Install reportlab and restart the server.")
    db=load()
    case=next((x for x in db["cases"] if x["case_id"]==case_id), None)
    if not case:
        raise HTTPException(404, "Case not found")
    records=[r for r in db["records"] if r["case_id"]==case_id]
    hits=suspicious_records(records)
    reports=[r for r in db["reports"] if r["case_id"]==case_id]
    out=REPORTS/(case_id+"_suspicious_activity_report.pdf")

    styles=getSampleStyleSheet()
    title=ParagraphStyle("ForensicTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=20, leading=24, spaceAfter=12)
    subtitle=ParagraphStyle("ForensicSubtitle", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10, leading=14, textColor=colors.HexColor("#5c6865"), spaceAfter=18)
    h1=ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, leading=18, spaceBefore=12, spaceAfter=8)
    h2=ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, leading=14, spaceBefore=8, spaceAfter=5)
    body=ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=13, spaceAfter=5)
    small=ParagraphStyle("Small", parent=body, fontSize=7.5, leading=10)
    note=ParagraphStyle("Note", parent=body, textColor=colors.HexColor("#6a3d00"), backColor=colors.HexColor("#fff4df"), borderPadding=7, spaceBefore=6, spaceAfter=10)

    doc=SimpleDocTemplate(str(out), pagesize=A4, rightMargin=38, leftMargin=38, topMargin=42, bottomMargin=42, title=f"{case_id} Suspicious Activity Report")
    story=[]
    story += [_p("FORENSICAI", title), _p("AI-Assisted Digital Forensic Investigation", subtitle), _p("SUSPICIOUS ACTIVITY REVIEW REPORT", h1)]
    story.append(_p("This report is generated only from forensic records extracted from the UFDR report(s) uploaded to this case. The indicators below are rule-based review leads and are not conclusions of criminal activity.", note))

    info=[
        [_p("Case ID", small), _p(case.get("case_id"), small)],
        [_p("Case Name", small), _p(case.get("name"), small)],
        [_p("Examiner", small), _p(case.get("examiner"), small)],
        [_p("Investigation Date", small), _p(case.get("investigation_date"), small)],
        [_p("Generated", small), _p(datetime.now().isoformat(timespec="seconds"), small)],
        [_p("Extracted Records", small), _p(len(records), small)],
        [_p("Review Leads", small), _p(len(hits), small)],
    ]
    t=Table(info, colWidths=[120, 390])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#edf2f0")),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#cbd5d1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [t, Spacer(1,12)]

    story.append(_p("Source UFDR Reports", h1))
    if reports:
        rows=[[_p("Report ID",small),_p("Filename",small),_p("Status",small),_p("SHA-256",small)]]
        for r in reports:
            rows.append([_p(r.get("report_id"),small),_p(r.get("filename"),small),_p(r.get("status"),small),_p(r.get("sha256"),small)])
        rt=Table(rows,colWidths=[85,120,65,240],repeatRows=1)
        rt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1f3a36")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd5d1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        story.append(rt)
    else:
        story.append(_p("No UFDR report has been uploaded to this case.", body))

    story.append(_p("Suspicious Activity Review", h1))
    if not records:
        story.append(_p("No forensic data is available. No suspicious-activity assessment was generated.", body))
    elif not hits:
        story.append(_p("No rule-based suspicious indicators were detected in the extracted records reviewed. This does not establish that no suspicious activity occurred; it means that none of the configured review terms were found in the extracted text.", body))
    else:
        counts=Counter(r.get("type","other") for r in hits)
        summary_rows=[[_p("Artifact Type",small),_p("Review Leads",small)]] + [[_p(k,small),_p(v,small)] for k,v in sorted(counts.items())]
        st=Table(summary_rows,colWidths=[260,250],repeatRows=1)
        st.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1f3a36")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd5d1")),("ALIGN",(1,1),(1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story += [st, Spacer(1,10)]
        for n,r in enumerate(hits,1):
            story.append(KeepTogether([_p(f"Review Lead {n}: {r.get('record_id','')}", h2),
                _p(f"Artifact type: {r.get('type','other')} | Source report: {r.get('report_id','')} | Timestamp: {r.get('timestamp') or 'Not extracted'}", small),
                _p(r.get('summary') or r.get('raw') or '', body)]))
            story.append(Spacer(1,5))

    story.append(PageBreak())
    story.append(_p("Methodology and Evidence Notes", h1))
    story.append(_p("The suspicious-activity section is produced by scanning extracted UFDR record text for configured review terms such as suspicious, threat, malware, deleted, recovered, urgent, unknown, password, phishing, and fraud. Only records belonging to the selected Case ID are considered. No default or sample forensic records are inserted.", body))
    story.append(_p("These indicators are triage leads for investigator review. They should be validated against the underlying UFDR evidence and the original forensic examination context before being treated as findings.", body))
    story.append(_p("Case/report separation: every included record retains its case_id and report_id so evidence is traceable to its source report.", body))

    doc.build(story)
    audit(db,case_id,"SUSPICIOUS_ACTIVITY_PDF_GENERATED",out.name)
    return FileResponse(out, filename=out.name, media_type="application/pdf")

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=8000)
