"""Read-only local preview. Run: python code/preview.py --port 8765."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import argparse
import csv
import json
import re

ROOT=Path(__file__).resolve().parents[1]
FAVICON=b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" rx="10" fill="#142631"/><path d="M10 32V19c0-8 4-12 10-12s10 4 10 12v13l-5-3-5 3-5-3-5 3Z" fill="none" stroke="#7ce1c3" stroke-width="2" stroke-linejoin="round"/><path d="M16 18v3m8-3v3" stroke="#7ce1c3" stroke-width="2.5" stroke-linecap="round"/></svg>'''

def data():
    def csv_rows(path):
        with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
    requests={r['case_id']:r for r in csv_rows(ROOT/'dataset/deletion_requests.csv')}
    diagnostic_path=ROOT/'.audit_cache/decisions.json'
    diagnostics=json.loads(diagnostic_path.read_text()) if diagnostic_path.exists() else {}
    metadata_path=ROOT/'.audit_cache/full_run.json'
    metadata=json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    report=(ROOT/'code/evaluation/evaluation_report.md').read_text(encoding='utf-8')
    metrics={}
    for line in report.splitlines():
        cells=[cell.strip() for cell in line.split('|')]
        if len(cells)==5 and '%' in cells[3]:metrics[cells[1]]={'count':cells[2],'value':cells[3]}
    cases=[]
    for row in csv_rows(ROOT/'output.csv'):
        cid=row['case_id'];request=requests[cid];diagnostic=diagnostics.get(cid,{})
        cases.append(dict(id=cid,email=request['email'],status=row['deletion_status'],steps=json.loads(row['steps_json']),requested_at=request['requested_at'],audit_at=request['audit_at'],request=request['request_text'],subject=diagnostic.get('subject',''),review=diagnostic.get('needs_review',False),reasons=diagnostic.get('review_reasons',[])))
    return dict(cases=cases,metadata=metadata,metrics=metrics)

HTML=r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#142631"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><title>Ghost Audit · Deletion assurance</title>
<style>
:root{--navy:#142631;--ink:#172d38;--muted:#6d7b82;--line:#dde4e5;--bg:#f4f6f5;--teal:#087d74;--amber:#956013;--red:#b45146}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 'Segoe UI',Arial,sans-serif}button,input,select{font:inherit}button,a,input,select{outline-offset:4px}button{cursor:pointer}a{color:inherit}aside{width:224px;position:fixed;inset:0 auto 0 0;background:var(--navy);color:#d2dde0;padding:29px 22px;display:flex;flex-direction:column}.brand{display:flex;align-items:center;gap:12px;color:white;font-size:21px;font-weight:650;letter-spacing:-.6px}.brand svg{width:34px;height:38px;color:#7ce1c3}.brand small{font-size:10px;display:block;color:#91a9b3;letter-spacing:2px;font-weight:500;margin-top:-2px}.navlabel{font-size:10px;letter-spacing:2px;color:#809aa5;margin:48px 12px 12px}.navlink{border:0;display:flex;gap:12px;align-items:center;text-decoration:none;color:#bfd0d6;padding:12px;border-radius:7px;font-size:13px;margin:3px 0;background:none;text-align:left}.navlink.active,.navlink:hover{background:#25424d;color:#fff}.navlink span{font-size:17px;line-height:1}.sidebottom{margin-top:auto;padding:18px 10px 0;border-top:1px solid #304550;color:#91a9b3;font-size:11px}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#7ce1c3;margin-right:6px}.workspace{margin-left:224px}.topbar{height:71px;background:#fff;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;padding:0 42px}.breadcrumb{color:var(--muted);font-size:12px}.breadcrumb b{color:var(--ink);font-weight:500}.topright{display:flex;gap:18px;align-items:center;color:var(--muted);font-size:11px}.local{border:1px solid var(--line);padding:5px 10px;border-radius:20px}.avatar{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:#e8f1ee;color:#365c54;font-weight:600}main{max-width:1510px;padding:35px 42px 42px;margin:auto}.eyebrow{font-size:10px;letter-spacing:2px;color:var(--teal);font-weight:700;margin-bottom:9px}.heading{display:flex;justify-content:space-between;gap:20px;align-items:center}.heading h1{font-size:33px;line-height:1.2;letter-spacing:-1.2px;margin:0 0 10px;font-weight:600}.heading p{margin:0;color:var(--muted);font-size:13px}.button{border:1px solid #cfd9d9;border-radius:6px;padding:9px 14px;background:#fff;text-decoration:none;display:inline-flex;align-items:center;gap:8px;color:var(--ink);font-weight:550;font-size:12px;white-space:nowrap}.button.primary{background:var(--teal);border-color:var(--teal);color:white}.button:hover{filter:brightness(.96)}.actions{display:flex;gap:9px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:27px 0 20px}.stat{background:white;border:1px solid var(--line);border-radius:9px;padding:19px 21px;position:relative}.stat label{display:block;font-size:12px;color:var(--muted)}.stat .value{font-size:33px;letter-spacing:-1px;font-weight:600;margin:8px 0 3px;line-height:1.2}.stat small{color:var(--muted);font-size:10px}.stat .icon{position:absolute;right:19px;top:18px;display:grid;place-items:center;background:#f0f4f3;width:27px;height:27px;border-radius:7px;color:#718886}.stat.alert .value{color:var(--amber)}.notice{display:flex;align-items:flex-start;gap:12px;border:1px solid #e4d4af;border-radius:8px;background:#fbf7ec;padding:14px 17px;color:#70562d;font-size:12px}.notice .symbol{font-size:17px;line-height:1.5}.notice b{font-weight:600}.notice a{margin-left:auto;white-space:nowrap;font-weight:600;padding-top:2px}.panel{background:white;border:1px solid var(--line);border-radius:9px;margin-top:24px;overflow:hidden}.panelhead{padding:20px 22px;display:flex;justify-content:space-between;align-items:center;gap:16px;border-bottom:1px solid var(--line)}.panelhead h2{font-size:16px;font-weight:600;margin:0 0 3px;letter-spacing:-.2px}.panelhead p{font-size:11px;color:var(--muted);margin:0}.subtle{font-size:10px;letter-spacing:1px;color:var(--muted)}.filters{display:flex;align-items:center;gap:12px;padding:16px 22px;border-bottom:1px solid var(--line)}.searchwrap{position:relative;flex:1;max-width:390px}.searchwrap span{position:absolute;left:12px;top:7px;color:#80939a;font-size:17px}.searchwrap input{width:100%;padding:9px 12px 9px 37px;border:1px solid #d6dfe0;border-radius:6px;background:#fafcfc;font-size:12px;color:var(--ink)}select{padding:9px 30px 9px 12px;border:1px solid #d6dfe0;background:#fff;border-radius:6px;font-size:12px;color:var(--ink)}.reviewfilter{display:flex;gap:7px;align-items:center;color:#60717a;font-size:12px;white-space:nowrap}.reviewfilter input{accent-color:var(--teal)}.countlabel{margin-left:auto;font-size:11px;color:var(--muted)}.tablewrap{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left}th{font-size:10px;letter-spacing:.7px;text-transform:uppercase;background:#fafbfb;color:#71828a;font-weight:600;padding:11px 22px;border-bottom:1px solid var(--line)}td{padding:13px 22px;border-bottom:1px solid #edf0ef;font-size:12px;vertical-align:middle}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:#f8fbfa}.caseid{font-weight:600;color:#24414c;font-size:12px}.subject{max-width:250px;overflow:hidden;text-overflow:ellipsis;font-size:11px;display:block;color:var(--muted);margin-top:2px}.badge{display:inline-flex;align-items:center;gap:5px;font-size:9px;letter-spacing:.4px;border-radius:4px;padding:4px 7px;font-weight:600;white-space:nowrap}.INCOMPLETE{background:#fcf0e8;color:#9a5b30}.COMPLETE{background:#e9f5ee;color:#287558}.NOT_APPLICABLE{background:#eef1f4;color:#657987}.reviewtag{color:var(--amber);font-size:10px}.verifiedtag{color:#729286;font-size:10px}.inspect{background:none;border:1px solid #d9e2e0;border-radius:5px;color:#47636d;font-size:10px;padding:5px 9px}.pagination{padding:13px 22px;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;font-size:10px;color:var(--muted)}.pagination div{display:flex;gap:7px;align-items:center}.pagination button{border:1px solid var(--line);background:#fff;padding:4px 10px;border-radius:4px;color:var(--ink)}button:disabled{opacity:.35;cursor:default}.bottomgrid{display:grid;grid-template-columns:1.35fr 1fr;gap:20px}.metricgrid{display:grid;grid-template-columns:1fr 1fr;gap:22px;padding:23px}.metric .metricnum{font-size:24px;letter-spacing:-.8px;font-weight:600}.metric .metricname{font-size:11px;color:var(--muted);margin:3px 0 9px}.track{height:4px;background:#e8efed;border-radius:5px;overflow:hidden}.track i{display:block;background:var(--teal);height:100%}.metric.amber .metricnum{color:var(--amber)}.metric.amber .track i{background:#c89650}.panelnote{font-size:10px;color:var(--muted);padding:0 23px 21px}.downloads{padding:7px 22px}.download{display:flex;gap:12px;align-items:center;padding:14px 0;border-bottom:1px solid #edf0ef;text-decoration:none}.download:last-child{border-bottom:0}.fileicon{width:31px;height:35px;background:#eef4f2;display:grid;place-items:center;color:#538277;border-radius:5px;font-size:9px;font-weight:700}.download b{font-weight:550;font-size:12px}.download small{display:block;color:var(--muted);font-size:10px}.download .arrow{margin-left:auto;color:var(--teal);font-size:17px}.footer{display:flex;justify-content:space-between;color:#8b989e;font-size:10px;margin-top:23px}.empty{padding:45px;text-align:center;color:var(--muted)}dialog{border:1px solid #dce4e2;border-radius:12px;padding:0;width:min(900px,94vw);max-height:88vh;color:var(--ink);box-shadow:0 20px 100px #132d3844}dialog::backdrop{background:#11273088;backdrop-filter:blur(3px)}.dialoghead{display:flex;justify-content:space-between;align-items:flex-start;gap:15px;padding:23px 26px;border-bottom:1px solid var(--line)}.dialoghead h2{margin:0 0 5px;font-size:23px;letter-spacing:-.6px}.dialoghead p{color:var(--muted);font-size:12px;margin:0}.close{border:0;background:#eff3f2;border-radius:50%;width:29px;height:29px;font-size:18px;color:#60757d}.dialogbody{padding:20px 26px}.requesttext{padding:14px;background:#f4f7f6;border:1px solid var(--line);border-radius:7px;font-size:12px;margin:15px 0}.dates{display:flex;gap:30px;color:var(--muted);font-size:10px}.reasons{padding:11px 14px;background:#fbf7ec;color:var(--amber);font-size:11px;border-radius:6px;margin-top:15px}.tabs{display:flex;gap:7px;margin:22px 0 16px;flex-wrap:wrap}.tabs button{background:white;border:1px solid var(--line);padding:7px 11px;border-radius:5px;color:#667d85;font-size:11px}.tabs button.selected{border-color:var(--teal);background:#eaf5f1;color:var(--teal)}.step{border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin:9px 0;display:flex;gap:13px}.stepno{width:25px;height:25px;background:#edf3f1;border-radius:50%;display:grid;place-items:center;color:var(--teal);font-size:11px;flex-shrink:0}.step b{font-size:12px;font-weight:550}.step code{font-size:11px;color:#687b83}.step .stepmeta{font-size:10px;color:#839299;margin-top:5px}.dialogfoot{padding:15px 26px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;font-size:10px;color:var(--muted);align-items:center}.error{background:#fff0ec;color:#a34835;padding:25px;border:1px solid #eccdc4;border-radius:8px}
@media(min-width:1500px){main{padding-top:42px}.stats{gap:20px}.stat{padding:23px}.filters{padding-top:18px;padding-bottom:18px}td{padding-top:15px;padding-bottom:15px}}@media(max-width:1050px){aside{width:185px;padding:25px 16px}.workspace{margin-left:185px}main{padding:27px 24px}.topbar{padding:0 24px}.stats{gap:10px}.stat{padding:16px}.stat .value{font-size:28px}.bottomgrid{grid-template-columns:1fr}.heading h1{font-size:28px}.notice a{display:none}.countlabel{display:none}td,th{padding-left:16px;padding-right:16px}}@media(max-width:720px){aside{position:static;width:100%;padding:16px 20px;display:block}.brand{font-size:19px}.brand small{display:none}.brand svg{width:27px;height:30px}aside .navlabel,aside .navlink,aside .sidebottom{display:none}.workspace{margin:0}.topbar{height:52px;padding:0 18px}.topright .local{display:none}main{padding:22px 16px}.heading{align-items:flex-start;flex-direction:column}.heading h1{font-size:28px}.stats{grid-template-columns:1fr 1fr;gap:10px;margin-top:23px}.stat .value{font-size:29px}.stat small{font-size:9px}.filters{flex-wrap:wrap;padding:14px}.searchwrap{max-width:100%;flex:1 0 100%}.reviewfilter{margin-left:auto}.panelhead{padding:17px 15px}.notice{font-size:11px}.metricgrid{gap:20px}.footer{gap:10px}.subject{max-width:170px}.tablewrap th:nth-child(3),.tablewrap td:nth-child(3){display:none}.dialogbody{padding:16px}.dialoghead{padding:20px 16px}.dates{flex-direction:column;gap:4px}.dialogfoot{padding:15px}.stat .icon{right:13px;top:14px}}
/* Flexible containment applies at every width, including narrow tablet panes. */
html{scroll-behavior:smooth;scroll-padding-top:18px}
.workspace,main,.heading>div,.panel,.bottomgrid>*,.stat,.metric,.searchwrap{min-width:0}
.stats{grid-template-columns:repeat(4,minmax(0,1fr))}
.bottomgrid{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}
.heading,.panelhead{flex-wrap:wrap}
.actions{flex-wrap:wrap}
.download>div,.step>div{min-width:0}
.download small,.requesttext,.dialoghead p,.step code,.stepmeta{overflow-wrap:anywhere}
.close{flex-shrink:0}
.step code{white-space:normal}
@media(min-width:901px) and (max-width:1150px){
  .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .bottomgrid{grid-template-columns:minmax(0,1fr)}
  .filters{flex-wrap:wrap}.searchwrap{flex-basis:100%;max-width:none}
}
@media(max-width:900px){
  html{scroll-padding-top:130px}
  aside{position:sticky;top:0;z-index:20;width:100%;padding:12px 16px 9px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
  .brand{grid-column:1/-1;gap:10px;font-size:20px;padding-bottom:5px}
  .brand svg{width:27px;height:30px}.brand small{display:none}
  aside .navlabel,aside .sidebottom{display:none}
  aside .navlink{display:flex;align-items:center;justify-content:center;gap:5px;min-height:42px;margin:0;padding:7px 4px;font-size:11px;line-height:1.25;text-align:center}
  .navlink span{font-size:15px}.workspace{margin-left:0;width:100%}
  .topbar{height:46px;padding:0 18px}.topright{gap:8px}.topright .local{display:none}
  main{padding:22px 16px 28px;width:100%}.heading{align-items:flex-start;flex-direction:column;gap:17px}
  .heading h1{font-size:29px;line-height:1.2;letter-spacing:-1px}.heading p{line-height:1.6;font-size:13px}
  .actions{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);width:100%;gap:9px}
  .actions .button{justify-content:center;white-space:normal;text-align:center;min-height:44px;padding:10px;font-size:12px}
  .stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin:23px 0 18px}
  .stat{display:grid;grid-template-rows:auto 1fr auto;padding:16px;min-height:145px}
  .stat label{font-size:12px;padding-right:22px;min-height:36px;line-height:1.4}
  .stat .value{font-size:30px;margin:6px 0;align-self:end}.stat small{font-size:11px;line-height:1.45}
  .stat .icon{width:23px;height:23px;top:13px;right:12px}
  .notice{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 10px;padding:13px;font-size:12px;line-height:1.6}
  .notice a{display:block;grid-column:2;margin:0;white-space:normal;min-height:34px;padding-top:4px}
  .panel{margin-top:20px}.panelhead{padding:17px 16px;flex-direction:column;align-items:flex-start;gap:9px}
  .panelhead h2{font-size:17px}.panelhead p{font-size:12px;line-height:1.5}
  .subtle{font-size:10px;line-height:1.5;overflow-wrap:anywhere}
  .filters{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;padding:14px}
  .searchwrap{max-width:none;width:100%;flex:none}.searchwrap span{top:9px}
  .searchwrap input,select{font-size:16px;min-height:46px;width:100%}
  .searchwrap input{padding-left:36px}.reviewfilter{margin-left:0;min-height:40px;font-size:13px}
  .reviewfilter input{width:18px;height:18px}.countlabel{display:none}
  .tablewrap{overflow:visible}table,tbody{display:block;width:100%}
  thead{display:none}tbody{padding:12px;display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
  tbody tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:11px 10px;padding:14px;border:1px solid var(--line);border-radius:8px;background:#fff;min-width:0}
  .tablewrap td,.tablewrap td:nth-child(3){display:block;padding:0;border:0;min-width:0}
  .tablewrap td:nth-child(1){grid-column:1/-1;border-bottom:1px solid #edf0ef;padding-bottom:10px}
  .tablewrap td:nth-child(2){grid-column:1;align-self:center}
  .tablewrap td:nth-child(3){grid-column:2;align-self:center;text-align:right}
  .tablewrap td:nth-child(4){grid-column:1;align-self:center}
  .tablewrap td:nth-child(5){grid-column:2;text-align:right}
  .caseid{font-size:14px}.subject{max-width:none;white-space:normal;overflow:visible;overflow-wrap:anywhere;font-size:12px;margin-top:4px}
  .badge{font-size:10px;min-height:27px;padding:5px 8px}.reviewtag,.verifiedtag{font-size:12px;white-space:normal}
  .inspect{min-height:42px;min-width:82px;font-size:12px;padding:9px 12px}
  .pagination{padding:13px 15px;gap:10px;flex-wrap:wrap;font-size:11px}.pagination button{min-height:40px;min-width:40px;font-size:14px}
  .bottomgrid{grid-template-columns:minmax(0,1fr);gap:0}
  .metricgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:22px 17px;padding:20px}
  .metric .metricnum{font-size:27px}.metric .metricname,.panelnote{font-size:12px;line-height:1.5}
  .downloads{padding:3px 17px}.download{min-height:75px}.download b{font-size:14px}.download small{font-size:12px;line-height:1.4}
  .footer{flex-direction:column;gap:6px;font-size:11px;line-height:1.5}
  dialog{width:calc(100% - 20px);max-width:700px;max-height:calc(100dvh - 20px);margin:auto;overflow:auto}
  .dialoghead{padding:18px 16px;gap:10px}.dialoghead h2{font-size:24px}.dialoghead p{font-size:13px}
  .close{width:40px;height:40px;font-size:22px}.dialogbody{padding:16px}.requesttext{font-size:13px;line-height:1.65;padding:13px}
  .dates{flex-direction:column;gap:6px;font-size:11px}.reasons{font-size:12px}
  .tabs{gap:6px;margin-top:19px}.tabs button{flex:1;min-height:44px;padding:8px;font-size:12px}
  .step{padding:12px 10px;gap:9px}.step b{font-size:13px}.step code{font-size:12px;line-height:1.6}.step .stepmeta{font-size:11px;line-height:1.6}
  .dialogfoot{padding:15px 16px;flex-direction:column;align-items:stretch;font-size:11px;line-height:1.5}.dialogfoot .button{justify-content:center;min-height:44px}
}
@media(min-width:600px) and (max-width:900px){
  tbody{grid-template-columns:repeat(2,minmax(0,1fr))}
  .filters{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.searchwrap{grid-column:1/-1}
  .actions{max-width:440px}.stats{grid-template-columns:repeat(4,minmax(0,1fr))}
  .stat{padding:14px 12px}.stat small{font-size:10px}
}
@media(max-width:359px){
  main{padding-left:12px;padding-right:12px}.heading h1{font-size:26px}
  .stat{padding:14px 12px}.stat label{font-size:11px}.stat small{font-size:10px}.stat .value{font-size:28px}
  aside .navlink{font-size:10px;gap:3px}.navlink span{font-size:12px}
  .metric .metricnum{font-size:24px}.tabs button{font-size:11px;padding:7px 5px}
}
</style></head><body>
<aside><div class="brand"><svg viewBox="0 0 36 40" fill="none" aria-hidden="true"><path d="M6 33V17C6 8 11 3 18 3s12 5 12 14v16l-6-4-6 4-6-4-6 4Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M13 17v4m10-4v4" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg><div>Ghost Audit<small>DELETION ASSURANCE</small></div></div><div class="navlabel">WORKSPACE</div><a class="navlink active" href="#overview"><span>▦</span> Overview</a><a class="navlink" href="#explorer"><span>⌕</span> Case explorer</a><a class="navlink" href="#evaluation"><span>◷</span> Evaluation</a><a class="navlink" href="#downloads"><span>⇩</span> Submission files</a></aside>
<div class="workspace"><header class="topbar"><div class="breadcrumb">Workspace <span style="margin:0 11px;color:#aebcbf">/</span> <b>Audit overview</b></div><div class="topright"><span class="local"><span class="dot" style="background:#40927e"></span>Local snapshot</span><span class="avatar">GA</span></div></header><main id="overview"><div class="eyebrow">NORTHSTAR SHOP · PRIVACY OPERATIONS</div><div class="heading"><div><h1>Deletion audit overview</h1><p>Trace the evidence. Find what remains. Review the next steps.</p></div><div class="actions"><button class="button" id="refresh">↻ Refresh results</button><a class="button primary" href="/download/output.csv">↓ Export predictions</a></div></div>
<div id="error"></div><section class="stats" aria-label="Audit summary"><div class="stat"><span class="icon">▤</span><label>Total requests</label><div class="value" id="total">—</div><small>All supplied deletion requests</small></div><div class="stat"><span class="icon" style="color:#aa6d34;background:#fcf1e7">!</span><label>Predicted incomplete</label><div class="value" id="incomplete">—</div><small>Remaining records or recreation risks</small></div><div class="stat"><span class="icon" style="color:#43856d;background:#e9f5ee">✓</span><label>Predicted complete</label><div class="value" id="complete">—</div><small>Review flags still apply</small></div><div class="stat alert"><span class="icon" style="color:#9b712c;background:#fbf4e5">⚑</span><label>Need evidence review</label><div class="value" id="reviewcount">—</div><small>Unresolved proof or identity coverage</small></div></section>
<div class="notice"><span class="symbol">ⓘ</span><div><b>Prediction is different from proof.</b> Cases flagged for review have unresolved evidence. A COMPLETE prediction is provisional until those gaps are resolved.</div><a href="/reports/coverage" target="_blank" rel="noopener">Read coverage report ↗</a></div>
<section class="panel" id="explorer"><div class="panelhead"><div><h2>Case explorer</h2><p>Inspect findings, remediation, and verification for each request.</p></div><span class="subtle" id="runtime">EVIDENCE SNAPSHOT</span></div><div class="filters"><div class="searchwrap"><span>⌕</span><input id="search" type="search" aria-label="Search cases" placeholder="Search case, email, subject, or resource…"></div><select id="status" aria-label="Filter by deletion status"><option value="">All statuses</option><option value="INCOMPLETE">Incomplete</option><option value="COMPLETE">Complete</option><option value="NOT_APPLICABLE">Not applicable</option></select><label class="reviewfilter"><input type="checkbox" id="reviewonly"> Needs review only</label><span class="countlabel" id="countlabel"></span></div><div class="tablewrap"><table><thead><tr><th>Case / request identity</th><th>Predicted status</th><th>Plan steps</th><th>Evidence coverage</th><th><span style="opacity:0">Action</span></th></tr></thead><tbody id="rows"></tbody></table></div><div class="pagination"><span id="showing">Loading results…</span><div><button id="previous" aria-label="Previous page">←</button><span id="pagecount"></span><button id="next" aria-label="Next page">→</button></div></div></section>
<div class="bottomgrid"><section class="panel" id="evaluation"><div class="panelhead"><div><h2>Evaluation, without the guesswork</h2><p>Measured against the 32 public development samples.</p></div><a href="/reports/evaluation" target="_blank" rel="noopener" class="subtle" style="text-decoration:none">FULL REPORT ↗</a></div><div class="metricgrid" id="metrics"></div><div class="panelnote">Public-sample performance does not establish hidden-set accuracy. Exact plans remain a material limitation.</div></section><section class="panel" id="downloads"><div class="panelhead"><div><h2>Submission files</h2><p>The code, predictions, and development transcript.</p></div><span class="subtle">READY TO REVIEW</span></div><div class="downloads"><a class="download" href="/download/code.zip"><span class="fileicon">ZIP</span><div><b>Runnable solution</b><small>Source, setup guide, tests, and evaluation reports</small></div><span class="arrow">↓</span></a><a class="download" href="/download/output.csv"><span class="fileicon">CSV</span><div><b>Predictions</b><small id="csvdetail">One ordered plan per request</small></div><span class="arrow">↓</span></a><a class="download" href="/download/log.txt"><span class="fileicon">TXT</span><div><b>Development transcript</b><small>Conversation summaries and implementation actions</small></div><span class="arrow">↓</span></a></div></section></div><footer class="footer"><span>Ghost Data Still Exists · Local results preview</span><span>Read-only · No deletion actions are executed</span></footer></main></div>
<dialog id="detail"><div class="dialoghead"><div><div class="eyebrow">CASE INSPECTION</div><h2 id="detailtitle"></h2><p id="detailemail"></p></div><button class="close" id="close" aria-label="Close case details">×</button></div><div class="dialogbody"><div id="detailbadge"></div><div class="requesttext" id="requesttext"></div><div class="dates"><span id="requested"></span><span id="audit"></span></div><div id="reasons"></div><div class="tabs" id="tabs"></div><div id="steps"></div></div><div class="dialogfoot"><span>Evidence IDs cite observed facts. Empty citations describe future work.</span><button class="button" id="downloadcase">↓ Case JSON</button></div></dialog>
<script>
'use strict';let payload=null,filtered=[],page=0,selected=null,phase='FINDING';const size=8;const $=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const labels={COMPLETE:'COMPLETE',INCOMPLETE:'INCOMPLETE',NOT_APPLICABLE:'NOT APPLICABLE'};const reasonLabels={MISSING_PROFILE_PROOF:'The selected evidence does not explicitly prove the profile state.',TEMPORAL_IDENTITY_HEURISTIC:'A resource association relies on a temporal heuristic.',LATER_WRITE_WITHOUT_READBACK:'A later write has no subsequent state readback.',ONLY_PRE_REQUEST_EVIDENCE:'Only evidence from before this request is available.',CONFLICTING_SUBJECT_EVIDENCE:'A claimed association conflicts with an explicit subject reference.',AMBIGUOUS_SHARED_IDENTIFIER:'An identifier is shared by more than one person.'};function badge(status){return `<span class="badge ${esc(status)}">${esc(labels[status]||status)}</span>`}function pretty(s){return s.toLowerCase().replaceAll('_',' ')}
async function load(){try{$('refresh').disabled=true;const response=await fetch('/api/results',{cache:'no-store'});if(!response.ok)throw new Error('Could not load the local result snapshot.');payload=await response.json();$('total').textContent=payload.cases.length;$('incomplete').textContent=payload.cases.filter(c=>c.status==='INCOMPLETE').length;$('complete').textContent=payload.cases.filter(c=>c.status==='COMPLETE').length;$('reviewcount').textContent=payload.cases.filter(c=>c.review).length;$('runtime').textContent=`${payload.metadata.seconds??'—'}s CACHED RUN · LOCAL OCR`;$('csvdetail').textContent=`${payload.cases.length} validated rows · ordered JSON plans`;const definitions=[['Case status','Status accuracy',false],['Entire case (status and every ordered step)','Exact plan accuracy',true],['Positional step fields','Field accuracy',false],['Custom regression tests','Independent tests',false]];$('metrics').innerHTML=definitions.map(([key,name,amber])=>{const metric=payload.metrics[key]||{value:'—',count:'—'};const shown=key==='Custom regression tests'?metric.count:metric.value;return `<div class="metric ${amber?'amber':''}"><div class="metricnum">${esc(shown)}</div><div class="metricname">${esc(name)}</div><div class="track"><i style="width:${Math.min(100,parseFloat(metric.value)||0)}%"></i></div></div>`}).join('');$('error').innerHTML='';filter()}catch(error){$('error').innerHTML=`<div class="error">${esc(error.message)}</div>`}finally{$('refresh').disabled=false}}
function filter(){if(!payload)return;const query=$('search').value.trim().toLowerCase(),status=$('status').value,review=$('reviewonly').checked;filtered=payload.cases.filter(c=>(!status||c.status===status)&&(!review||c.review)&&(!query||[c.id,c.email,c.subject,...c.steps.map(s=>s.resource_id+' '+s.system_id)].join(' ').toLowerCase().includes(query)));page=0;render()}
function render(){const start=page*size,shown=filtered.slice(start,start+size);$('rows').innerHTML=shown.length?shown.map(c=>`<tr><td><span class="caseid">${esc(c.id)}</span><span class="subject">${esc(c.email)}</span></td><td>${badge(c.status)}</td><td>${c.steps.length}<span style="color:#96a2a7;margin-left:5px;font-size:10px">steps</span></td><td>${c.status==='NOT_APPLICABLE'?'<span class="verifiedtag">No deletion authorized</span>':c.review?'<span class="reviewtag">⚑ Review required</span>':'<span class="verifiedtag">✓ No coverage flag</span>'}</td><td><button class="inspect" data-case="${esc(c.id)}" aria-label="Inspect ${esc(c.id)}">Inspect ↗</button></td></tr>`).join(''):'<tr><td colspan="5"><div class="empty">No cases match these filters. Try another search or status.</div></td></tr>';$('showing').textContent=filtered.length?`Showing ${start+1}–${Math.min(start+size,filtered.length)} of ${filtered.length} cases`:'0 matching cases';$('pagecount').textContent=`${page+1} / ${Math.max(1,Math.ceil(filtered.length/size))}`;$('previous').disabled=page===0;$('next').disabled=start+size>=filtered.length;$('countlabel').textContent=filtered.length+' results'}
function inspect(id){selected=payload.cases.find(c=>c.id===id);if(!selected)return;$('detailtitle').textContent=selected.id;$('detailemail').textContent=selected.email+' · '+selected.subject;$('detailbadge').innerHTML=badge(selected.status);$('requesttext').textContent=selected.request;$('requested').textContent='Requested: '+selected.requested_at.replace('T',' ').replace('Z',' UTC');$('audit').textContent='Audit cutoff: '+selected.audit_at.replace('T',' ').replace('Z',' UTC');$('reasons').innerHTML=selected.reasons.length?`<div class="reasons"><b>Evidence review required</b><ul style="padding-left:17px;margin-bottom:0">${selected.reasons.map(r=>`<li>${esc(reasonLabels[r]||r)}</li>`).join('')}</ul></div>`:'';phase=selected.steps.some(s=>s.phase==='FINDING')?'FINDING':'VERIFICATION';renderSteps();$('detail').showModal()}
function renderSteps(){$('tabs').innerHTML=['FINDING','REMEDIATION','VERIFICATION'].map(p=>`<button data-phase="${p}" class="${phase===p?'selected':''}">${esc(pretty(p))} · ${selected.steps.filter(s=>s.phase===p).length}</button>`).join('');const steps=selected.steps.filter(s=>s.phase===phase);$('steps').innerHTML=steps.length?steps.map(s=>`<div class="step"><span class="stepno">${s.step_no}</span><div><b style="text-transform:capitalize">${esc(pretty(s.operation))}</b><div><code>${esc(s.system_id)} / ${esc(s.resource_id)}</code></div><div class="stepmeta">${esc(s.state)} · ${s.evidence_id?'Evidence: '+esc(s.evidence_id):'Proposed action or future verification'}</div></div></div>`).join(''):'<div class="empty">'+(selected.status==='NOT_APPLICABLE'?'This request does not authorize deletion. No deletion steps apply.':'No steps in this phase.')+'</div>'}
$('search').addEventListener('input',filter);$('status').addEventListener('change',filter);$('reviewonly').addEventListener('change',filter);$('refresh').addEventListener('click',load);$('previous').addEventListener('click',()=>{page--;render()});$('next').addEventListener('click',()=>{page++;render()});$('rows').addEventListener('click',event=>{const target=event.target.closest('[data-case]');if(target)inspect(target.dataset.case)});$('tabs').addEventListener('click',event=>{const target=event.target.closest('[data-phase]');if(target){phase=target.dataset.phase;renderSteps()}});$('close').addEventListener('click',()=>$('detail').close());$('detail').addEventListener('click',event=>{if(event.target===$('detail')){const r=$('detail').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('detail').close()}});$('downloadcase').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(selected,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=selected.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});document.querySelectorAll('.navlink').forEach(link=>link.addEventListener('click',()=>{document.querySelectorAll('.navlink').forEach(l=>l.classList.remove('active'));link.classList.add('active')}));load();
</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        try:
            if path=='/':return self.send(HTML.encode(),'text/html; charset=utf-8')
            if path in ('/favicon.svg','/favicon.ico'):return self.send(FAVICON,'image/svg+xml')
            if path=='/.well-known/appspecific/com.chrome.devtools.json':
                self.send_response(204)
                self.send_header('Content-Length','0')
                self.end_headers()
                return
            if path=='/api/results':return self.send(json.dumps(data()).encode(),'application/json; charset=utf-8')
            reports={'/reports/evaluation':'evaluation_report.md','/reports/coverage':'coverage_report.md','/reports/usage':'usage_report.md'}
            if path in reports:return self.send((ROOT/'code/evaluation'/reports[path]).read_bytes(),'text/plain; charset=utf-8')
            downloads={'/download/code.zip':('code.zip','application/zip'),'/download/output.csv':('output.csv','text/csv; charset=utf-8'),'/download/log.txt':('log.txt','text/plain; charset=utf-8')}
            if path in downloads:
                name,kind=downloads[path]
                return self.send((ROOT/name).read_bytes(),kind,name)
            self.send_error(404)
        except FileNotFoundError:self.send_error(503,'Run the audit and evaluation first.')
        except Exception as exc:
            print(type(exc).__name__,str(exc),flush=True)
            self.send_error(500,'Could not read the result snapshot.')
    def send(self,body,kind,filename=None):
        self.send_response(200)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers();self.wfile.write(body)

def main():
    parser=argparse.ArgumentParser(description='Read-only deletion audit result preview')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Local preview: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
