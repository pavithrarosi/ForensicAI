
let state={cases:[],selectedCase:null,page:"dashboard",records:[],reports:[],filter:"",type:""};
const $=id=>document.getElementById(id);
async function api(url,opt={}){const r=await fetch(url,opt);if(!r.ok)throw new Error(await r.text());return r.json()}
function enterApp(){const name=$("loginName").value.trim()||"Investigator";localStorage.faUser=name;$("userName").textContent=name;$("avatar").textContent=name[0].toUpperCase();$("login").classList.add("hidden");$("app").classList.remove("hidden");loadCases();navigate("dashboard")}
function logout(){localStorage.removeItem("faUser");location.reload()}
if(localStorage.faUser){$("login").classList.add("hidden");$("app").classList.remove("hidden");$("userName").textContent=localStorage.faUser;$("avatar").textContent=localStorage.faUser[0].toUpperCase()}
document.querySelectorAll(".nav[data-page]").forEach(b=>b.onclick=()=>navigate(b.dataset.page));
async function loadCases(){state.cases=await api("/api/cases");if(!state.selectedCase&&state.cases.length)state.selectedCase=state.cases[0].case_id;render()}
function navigate(p){state.page=p;document.querySelectorAll(".nav[data-page]").forEach(b=>b.classList.toggle("active",b.dataset.page===p));render()}
async function render(){if(!$("app")||$("app").classList.contains("hidden"))return;const m=$("main");m.innerHTML=`<div class="page-head"><div><div class="eyebrow">FORENSICAI WORKSPACE</div><h1>${title(state.page)}</h1></div><div class="actions">${state.selectedCase?`<button class="secondary" onclick="navigate('evidence')">Evidence</button>`:""}<button class="primary" onclick="newCase()">＋ New case</button></div></div>`;if(state.page==="dashboard")await dashboard(m);if(state.page==="cases")await casesPage(m);if(state.page==="evidence")await evidencePage(m);if(state.page==="timeline")await timelinePage(m);if(state.page==="indicators")await indicatorsPage(m);if(state.page==="assistant")assistantPage(m);if(state.page==="reports")await reportsPage(m);if(state.page==="audit")await auditPage(m)}
function title(p){return ({dashboard:"Investigation overview",cases:"Case workspace",evidence:"Evidence Explorer",timeline:"Evidence Timeline",indicators:"Suspicious Indicators",assistant:"Forensic AI Assistant",reports:"Investigation Reports",audit:"Audit Log"})[p]}
async function dashboard(m){if(!state.selectedCase){m.innerHTML+=`<div class="empty"><strong>No case selected</strong>Create your first investigation case to begin.</div>`;return}let s=await api(`/api/cases/${state.selectedCase}/summary`);let c=await api(`/api/cases/${state.selectedCase}`);m.innerHTML+=`<div class="hero"><div><div class="eyebrow">ACTIVE CASE · ${c.case_id}</div><h2>${esc(c.name)}</h2><p>${esc(c.description||"No case description supplied.")}</p></div><div class="hero-stat"><b>${s.reports}</b><span>UFDR report${s.reports===1?"":"s"}</span></div></div><div class="cards">${metric("◈","Records",s.records,"Extracted from reports")}${metric("▣","Messages",s.counts.message||0,"Extracted records")}${metric("☎","Calls",s.counts.call||0,"Extracted records")}${metric("⌖","Locations",s.counts.location||0,"Extracted records")}</div><div class="grid2"><div class="panel"><h3>Evidence activity</h3>${s.records?`<div class="table-wrap"><table class="table"><tr><th>Artifact</th><th>Count</th><th>Source</th></tr>${Object.entries(s.counts).map(([k,v])=>`<tr><td>${k}</td><td><b>${v}</b></td><td>Uploaded UFDR</td></tr>`).join("")}</table></div>`:`<div class="empty"><strong>No forensic data available.</strong>Upload a UFDR report to populate this area.</div>`}</div><div class="panel"><h3>Investigation status</h3><div class="empty"><strong>${s.reports?"Report processing complete":"Awaiting evidence"}</strong>${s.reports?`${s.processed_reports} processed · ${s.failed_reports} failed`:"No report has been uploaded to this case."}</div></div></div>`}
function metric(icon,label,val,sub){return `<div class="metric"><div class="micon">${icon}</div><b>${val}</b><small>${label}</small><small>${sub}</small></div>`}
async function casesPage(m){m.innerHTML+=`<div class="filters"><input placeholder="Search cases..." oninput="filterCases(this.value)"></div><div id="caseGrid" class="case-grid">${state.cases.length?state.cases.map(caseCard).join(""):`<div class="empty" style="grid-column:1/-1"><strong>No cases created.</strong>Create a case to start an investigation.</div>`}</div>`}
function caseCard(c){return `<div class="case-card" onclick="selectCase('${esc(c.case_id)}')"><div class="case-id">${esc(c.case_id)}</div><h3>${esc(c.name)}</h3><p class="muted">${esc(c.description||"No description")}</p><div class="case-meta"><span>Examiner: ${esc(c.examiner||"—")}</span><span>${c.investigation_date||"No date"}</span></div></div>`}
function filterCases(q){$("caseGrid").innerHTML=state.cases.filter(c=>JSON.stringify(c).toLowerCase().includes(q.toLowerCase())).map(caseCard).join("")||`<div class="empty" style="grid-column:1/-1">No matching cases.</div>`}
function selectCase(id){state.selectedCase=id;navigate("dashboard");toast("Case selected")}
function newCase(){modal(`<h2>Create investigation case</h2><form class="form" id="caseForm"><label>Case ID</label><input name="case_id" required placeholder="CASE-2026-001"><label>Case name</label><input name="name" required placeholder="Investigation title"><label>Description</label><textarea name="description" rows="3" placeholder="Case scope"></textarea><label>Examiner</label><input name="examiner" placeholder="Investigator name"><label>Investigation date</label><input name="investigation_date" type="date"><button class="primary">Create case</button></form>`);$("caseForm").onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.target);try{let c=await api("/api/cases",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(fd))});state.cases.push(c);state.selectedCase=c.case_id;closeModal();navigate("dashboard");toast("Case created")}catch(err){toast("Could not create case")}}}
async function evidencePage(m){if(!state.selectedCase){m.innerHTML+=`<div class="empty"><strong>Select a case first.</strong></div>`;return}state.reports=await api(`/api/cases/${state.selectedCase}/reports`);state.records=await api(`/api/cases/${state.selectedCase}/records?type=${encodeURIComponent(state.type)}&q=${encodeURIComponent(state.filter)}`);m.innerHTML+=`<div class="panel" style="margin-bottom:18px"><div class="upload"><div class="upload-icon">⇧</div><h3>Import forensic evidence</h3><p class="muted">Upload a PDF UFDR report. The uploaded report is the source of truth.</p><label class="primary" style="display:inline-block;cursor:pointer">Choose UFDR PDF<input type="file" accept=".pdf" onchange="uploadUFDR(this.files[0])"></label></div></div><div class="panel"><div class="filters"><input value="${esc(state.filter)}" placeholder="Search extracted evidence..." oninput="state.filter=this.value;render()"><select onchange="state.type=this.value;render()"><option value="">All artifact types</option>${["message","call","contact","location","media","browser","application","other"].map(x=>`<option ${state.type===x?"selected":""}>${x}</option>`).join("")}</select></div>${state.records.length?`<div class="table-wrap"><table class="table"><tr><th>Record</th><th>Type</th><th>Report</th><th>Extracted content</th></tr>${state.records.map(r=>`<tr><td>${r.record_id}</td><td><span class="badge">${r.type}</span></td><td>${r.report_id}</td><td>${esc(r.summary)}</td></tr>`).join("")}</table></div>`:`<div class="empty"><strong>No forensic data available.</strong>No matching records were extracted from this case.</div>`}</div>`}
async function uploadUFDR(file){if(!file||!state.selectedCase)return;let fd=new FormData();fd.append("file",file);toast("Processing report...");try{let r=await api(`/api/cases/${state.selectedCase}/reports`,{method:"POST",body:fd});toast(r.status==="processed"?"Report processed successfully":"Report processing failed");render()}catch(e){toast("Upload failed")}}
async function timelinePage(m){if(!state.selectedCase){m.innerHTML+=`<div class="empty">Select a case first.</div>`;return}let rows=await api(`/api/cases/${state.selectedCase}/timeline`);m.innerHTML+=`<div class="panel">${rows.length?rows.map((r,i)=>`<div style="padding:15px 0;border-bottom:1px solid var(--line);display:flex;gap:18px"><b style="color:var(--accent)">${String(i+1).padStart(2,"0")}</b><div><strong>${esc(r.type)}</strong><p class="muted">${esc(r.summary)}</p><small>${r.report_id} · ${r.record_id}</small></div></div>`).join(""):`<div class="empty"><strong>No timeline events.</strong>Timeline entries appear only after evidence is extracted.</div>`}</div>`}
async function indicatorsPage(m){if(!state.selectedCase){m.innerHTML+=`<div class="empty">Select a case first.</div>`;return}let rows=await api(`/api/cases/${state.selectedCase}/records`);let hits=rows.filter(r=>/password|threat|suspicious|malware|deleted|recovered|urgent|unknown/i.test(r.raw||""));m.innerHTML+=`<div class="panel"><h3>Rule-based triage leads</h3><p class="muted">These are review leads, not conclusions. They are generated only from extracted report text.</p>${hits.length?hits.map(r=>`<div style="padding:14px 0;border-bottom:1px solid var(--line)"><span class="badge warn">REVIEW</span> <b>${r.record_id}</b><p>${esc(r.summary)}</p><small>Source: ${r.report_id}</small></div>`).join(""):`<div class="empty"><strong>No indicators detected.</strong>No matching triage terms were found in extracted records.</div>`}</div>`}
function assistantPage(m){m.innerHTML+=`<div class="ai"><div class="panel chat"><div class="messages" id="messages"><div class="bubble">I answer from the selected case's extracted evidence only. Ask about messages, calls, locations, contacts, or report coverage.</div></div><div class="chat-input"><input id="question" placeholder="Ask about this case..." onkeydown="if(event.key==='Enter')ask()"><button class="primary" onclick="ask()">Ask</button></div></div><div class="panel"><h3>Grounding rules</h3><p class="muted">No invented evidence. No default statistics. Answers are limited to the selected case.</p><div class="empty">Upload a report first to give the assistant evidence to work with.</div></div></div>`}
async function ask(){let q=$("question").value.trim();if(!q||!state.selectedCase)return;let box=$("messages");box.innerHTML+=`<div class="bubble me">${esc(q)}</div>`;$("question").value="";let r=await api(`/api/cases/${state.selectedCase}/assistant`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})});box.innerHTML+=`<div class="bubble">${esc(r.answer)}<small style="margin-top:7px">Grounded records: ${r.grounded_records}</small></div>`}
async function reportsPage(m){if(!state.selectedCase){m.innerHTML+=`<div class="empty">Select a case first.</div>`;return}let rs=await api(`/api/cases/${state.selectedCase}/reports`);m.innerHTML+=`<div class="panel"><h3>Source reports</h3>${rs.length?`<table class="table"><tr><th>Report</th><th>Filename</th><th>Status</th><th>SHA-256</th></tr>${rs.map(r=>`<tr><td>${r.report_id}</td><td>${esc(r.filename)}</td><td><span class="badge ${r.status==="failed"?"fail":""}">${r.status}</span></td><td style="font-family:monospace;font-size:10px">${r.sha256}</td></tr>`).join("")}</table><div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px"><button class="primary" onclick="generateSuspiciousPDF()">Generate Suspicious Activity PDF</button><button class="secondary" onclick="generateReport()">Export raw case data (JSON)</button></div>`:`<div class="empty"><strong>No source reports.</strong>Upload a UFDR report from Evidence Explorer.</div>`}</div>`}
async function generateReport(){
  if(!state.selectedCase){toast("Select a case first");return;}
  try{
    toast("Generating investigation report...");
    const response=await fetch(`/api/cases/${encodeURIComponent(state.selectedCase)}/generate-report`,{method:"POST"});
    if(!response.ok){throw new Error(await response.text());}
    const blob=await response.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;
    a.download=`${state.selectedCase}_investigation_report.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    toast("Investigation report generated successfully");
  }catch(e){
    console.error(e);
    toast("Report generation failed");
  }
}

async function generateSuspiciousPDF(){
  if(!state.selectedCase){toast("Select a case first");return;}
  try{
    toast("Generating suspicious activity PDF...");
    const response=await fetch(`/api/cases/${encodeURIComponent(state.selectedCase)}/generate-suspicious-pdf`,{method:"POST"});
    if(!response.ok){throw new Error(await response.text());}
    const blob=await response.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;
    a.download=`${state.selectedCase}_suspicious_activity_report.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    toast("Suspicious activity PDF generated successfully");
  }catch(e){
    console.error(e);
    toast("PDF generation failed");
  }
}
async function auditPage(m){if(!state.selectedCase){m.innerHTML+=`<div class="empty">Select a case first.</div>`;return}let a=await api(`/api/cases/${state.selectedCase}/audit`);m.innerHTML+=`<div class="panel"><table class="table"><tr><th>Time</th><th>Action</th><th>Details</th></tr>${a.map(x=>`<tr><td>${x.timestamp}</td><td>${x.action}</td><td>${esc(x.details)}</td></tr>`).join("")||`<tr><td colspan="3">No audit events.</td></tr>`}</table></div>`}
function modal(content){let x=document.createElement("div");x.className="modal";x.id="modal";x.innerHTML=`<div class="modal-card"><button class="close" onclick="closeModal()">×</button>${content}</div>`;document.body.appendChild(x)}
function closeModal(){$("modal")?.remove()}
function toast(t){let x=document.createElement("div");x.style.cssText="position:fixed;right:22px;bottom:22px;background:#18211f;color:#fff;padding:12px 16px;border-radius:10px;z-index:100";x.textContent=t;document.body.appendChild(x);setTimeout(()=>x.remove(),2500)}
function esc(v){return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}
function globalSearch(q){if(q.length>1)navigate("cases")}
loadCases();
