"""Read-only preview for the proposed Eastern Gaels dashboard refresh."""
from datetime import date
from html import escape

def render(coaches,records):
    today=date.today()
    rows=[]
    for key,c in sorted(coaches.items(),key=lambda item:str(item[1].get('name','')).casefold()):
        name=str(c.get('name') or key)
        record=records.get(key,{})
        vals=[]
        for kind,field in [('garda','garda_vetted'),('safeguarding','safeguarding')]:
            rec=record.get(kind,{})
            if not isinstance(rec,dict):rec={}
            raw=rec.get('expiry') or (c.get('garda_expiry') if kind=='garda' else None)
            try:expiry=date.fromisoformat(str(raw))
            except (ValueError,TypeError):expiry=None
            status=str(c.get(field,'')).lower()
            evidence=bool(rec.get('file') or rec.get('drive_file_id') or expiry)
            if expiry and expiry>=today and (status=='yes' or evidence):
                days=(expiry-today).days
                state='due' if days<=90 else 'current'
            else:
                days=None
                state='expired' if expiry and expiry<today else 'missing'
            vals.append({'date':expiry,'state':state,'days':days,'kind':kind})
        rows.append({'name':name,'g':vals[0],'s':vals[1]})
    def compliance_order(row):
        states=(row['g']['state'],row['s']['state'])
        if all(state in ('current','due') for state in states):group=0
        elif 'missing' in states:group=2
        else:group=1
        return (group,row['name'].casefold())
    rows.sort(key=compliance_order)
    n=len(rows)
    count=lambda kind:sum(r[kind]['state'] in ('current','due') for r in rows)
    alerts=sorted([(r['name'],v) for r in rows for v in (r['g'],r['s']) if v['state']=='due'],key=lambda x:x[1]['days'])
    issues=[(r['name'],v) for r in rows for v in (r['g'],r['s']) if v['state'] in ('missing','expired')]
    pct=lambda k:f'{round(100*count(k)/n)}%' if n else '—'
    e=escape
    def cell(v):
        d=v['date'].strftime('%d %b %Y') if v['date'] else 'No expiry recorded'
        return f'<span class="eg-status eg-{v["state"]}">{e(v["state"].title())}</span><span class="eg-date">{e(d)}</span>'
    table=''.join(f'<tr data-coach="{e(r["name"].lower())}" data-state="{e(" ".join([r["g"]["state"],r["s"]["state"]]))}"><td><strong>{e(r["name"])}</strong></td><td>{cell(r["g"])}</td><td>{cell(r["s"])}</td></tr>' for r in rows)
    warning=''.join(f'<tr><td>{e(name)}</td><td>{e("Garda Vetting" if v["kind"]=="garda" else "Safeguarding")}</td><td>{v["date"].strftime("%d %b %Y")}</td><td><span class="eg-status eg-due">{v["days"]} days</span></td></tr>' for name,v in alerts) or '<tr><td colspan="4">No certificates due within 90 days.</td></tr>'
    missing=''.join(f'<tr><td>{e(name)}</td><td>{e("Garda Vetting" if v["kind"]=="garda" else "Safeguarding")}</td><td><span class="eg-status eg-expired">{e(v["state"].title())}</span></td></tr>' for name,v in issues) or '<tr><td colspan="3">No missing or expired records.</td></tr>'
    fully=[r for r in rows if all(r[k]['state'] in ('current','due') for k in ('g','s'))]
    partial=[r for r in rows if sum(r[k]['state'] in ('current','due') for k in ('g','s')) == 1]
    none=[r for r in rows if all(r[k]['state'] not in ('current','due') for k in ('g','s'))]
    fully_table=''.join(f'<tr><td><strong>{e(r["name"])}</strong></td><td>{cell(r["g"])}</td><td>{cell(r["s"])}</td></tr>' for r in fully) or '<tr><td colspan="3">No fully compliant coaches recorded.</td></tr>'
    partial_table=''.join(f'<tr><td><strong>{e(r["name"])}</strong></td><td>{cell(r["g"])}</td><td>{cell(r["s"])}</td></tr>' for r in partial) or '<tr><td colspan="3">No partially compliant coaches.</td></tr>'
    none_table=''.join(f'<tr><td><strong>{e(r["name"])}</strong></td><td>{cell(r["g"])}</td><td>{cell(r["s"])}</td></tr>' for r in none) or '<tr><td colspan="3">No coaches in this category.</td></tr>'
    style="""<style>
    .eg-preview{font-family:Arial,sans-serif;color:#102f26;max-width:1180px;margin:0 auto;padding:12px 10px 36px}
    .eg-hero{background:linear-gradient(115deg,#003b29,#006b4a);color:white;border-bottom:5px solid #e9bb38;border-radius:14px;padding:28px;display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap}
    .eg-hero h1{font-size:29px;margin:0;color:white}.eg-hero p{color:#d7e9dd;margin:7px 0 0}
    .eg-hero a{background:white;color:#004832;padding:11px 15px;border-radius:8px;text-decoration:none;font-weight:bold}
    .eg-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
    .eg-kpi{background:#fff;border:1px solid #dce9e2;border-top:5px solid #d4a829;border-radius:12px;padding:18px;box-shadow:0 4px 14px #0b42200c}
    .eg-kpi strong{font-size:32px;display:block;color:#00573c;margin:8px 0}.eg-kpi small{color:#60756c}
    .eg-three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}\n    .eg-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
    .eg-panel{background:#fff;border:1px solid #dce9e2;border-radius:12px;padding:17px;min-width:0;overflow:auto;margin-bottom:14px}
    .eg-panel h2{font-size:18px;color:#063d2c;margin:0 0 14px}
    .eg-panel table{width:100%;border-collapse:collapse;font-size:13px}
    .eg-panel th{background:#eff5f2;color:#274b3c;text-align:left;padding:10px}
    .eg-panel td{border-bottom:1px solid #e8eee9;padding:10px;vertical-align:middle}
    .eg-status{display:inline-block;padding:5px 8px;border-radius:18px;font-size:11px;font-weight:bold}
    .eg-current{background:#d7f4e0;color:#126039}.eg-due{background:#fff0bc;color:#805600}.eg-missing,.eg-expired{background:#ffe0de;color:#a52a2a}
    .eg-date{display:block;font-size:11px;color:#62746a;margin-top:5px}
    .eg-search{padding:11px;border:1px solid #c9d9d0;border-radius:8px;min-width:210px;max-width:100%}
    .eg-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
    .eg-toolbar select{padding:10px;border:1px solid #c9d9d0;border-radius:8px}
    .eg-note{color:#62746a;font-size:12px;line-height:1.5}
    @media(max-width:900px){.eg-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.eg-grid{grid-template-columns:1fr}.eg-three{grid-template-columns:1fr}}
    @media(max-width:500px){.eg-kpis{grid-template-columns:1fr 1fr}.eg-hero h1{font-size:23px}.eg-kpi{padding:12px}.eg-kpi strong{font-size:25px}}
    </style>"""
    html=style+'<div class="eg-preview"><section class="eg-hero"><div><small>EASTERN GAELS · DASHBOARD DESIGN PREVIEW</small><h1>Coaching Compliance Centre</h1><p>Live Garda Vetting &amp; Safeguarding status · '+today.strftime('%d %B %Y')+'</p></div><a href="/reports/compliance">Existing Compliance Report</a></section>'
    html+='<div class="eg-kpis">'
    for label,value,detail in [('Garda vetted',pct('g'),f'{count("g")} of {n} coaches'),('Safeguarding',pct('s'),f'{count("s")} of {n} coaches'),('Due within 90 days',str(len(alerts)),'Certificate renewals'),('Missing / expired',str(len(issues)),'Requirements needing action')]:
        html+=f'<div class="eg-kpi"><span>{e(label)}</span><strong>{e(value)}</strong><small>{e(detail)}</small></div>'
    html+='</div><div class="eg-three"><section class="eg-panel"><h2>Full Compliance · '+str(len(fully))+'</h2><p class="eg-note">Both Garda Vetting and Safeguarding current.</p><table><thead><tr><th>Coach</th><th>Garda</th><th>Safeguarding</th></tr></thead><tbody>'+fully_table+'</tbody></table></section>'
    html+='<section class="eg-panel"><h2>Partially Compliance · '+str(len(partial))+'</h2><p class="eg-note">One requirement current; one outstanding.</p><table><thead><tr><th>Coach</th><th>Garda</th><th>Safeguarding</th></tr></thead><tbody>'+partial_table+'</tbody></table></section>'
    html+='<section class="eg-panel"><h2>No Compliance · '+str(len(none))+'</h2><p class="eg-note">Neither requirement confirmed current.</p><table><thead><tr><th>Coach</th><th>Garda</th><th>Safeguarding</th></tr></thead><tbody>'+none_table+'</tbody></table></section></div>'
    html+='<div class="eg-grid"><section class="eg-panel"><h2>Compliance Expiry Dates Due · Next 90 days</h2><table><thead><tr><th>Coach</th><th>Requirement</th><th>Expiry</th><th>Days</th></tr></thead><tbody>'+warning+'</tbody></table></section>'
    html+='<section class="eg-panel"><h2>Missing or expired · Action list</h2><table><thead><tr><th>Coach</th><th>Requirement</th><th>Status</th></tr></thead><tbody>'+missing+'</tbody></table></section></div>'
    html+='<section class="eg-panel"><h2>All coaches · Fully compliant first, then outstanding, then missing dates</h2><div class="eg-toolbar"><input class="eg-search" id="eg-coach-search" type="search" placeholder="Search coach names..." oninput="egFilter()"><select id="eg-coach-filter" onchange="egFilter()"><option value="all">All statuses</option><option value="due">Due within 90 days</option><option value="missing">Missing / expired</option><option value="current">Fully current</option></select></div><table><thead><tr><th>Coach</th><th>Garda Vetting</th><th>Safeguarding</th></tr></thead><tbody id="eg-coach-rows">'+table+'</tbody></table></section>'
    html+='''<script>function egFilter(){var q=document.getElementById("eg-coach-search").value.toLowerCase(),f=document.getElementById("eg-coach-filter").value;document.querySelectorAll("#eg-coach-rows tr").forEach(function(r){var s=r.dataset.state;var match=f==="all"||(f==="due"&&s.includes("due"))||(f==="missing"&&(s.includes("missing")||s.includes("expired")))||(f==="current"&&!s.includes("missing")&&!s.includes("expired")&&!s.includes("due"));r.style.display=match&&r.dataset.coach.includes(q)?"":"none";});}</script>'''
    html+='<p class="eg-note">Preview only: existing data, forms, permissions and all three downloadable reports are unchanged. Compliance percentages require a current certificate expiry date. Missing dates remain flagged for confirmation.</p></div>'
    return html
