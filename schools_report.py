"""Schools coaching report drawn from visible coaching sessions."""
from collections import defaultdict
from datetime import datetime
from html import escape as e
from pathlib import Path
import re

def summary(rows):
    statuses={'Completed':0,'Scheduled':0,'Cancelled':0,'School Closed':0}
    schools=defaultdict(lambda:[0,0]);coaches=defaultdict(lambda:[0,0]);months=defaultdict(int)
    hours=0;attendance=0
    for r in rows:
        st=r['actual_status'] or 'Scheduled'
        statuses[st]=statuses.get(st,0)+1
        done=st=='Completed'
        for d,k in ((schools,r['school'] or 'Unknown'),(coaches,r['coach'] or 'Unknown')):
            d[k][1]+=1;d[k][0]+=int(done)
        if done:
            attendance+=r['attendance'] or 0
            if r['start'] and r['end']:
                try:
                    a=datetime.strptime(r['start'],'%H:%M');b=datetime.strptime(r['end'],'%H:%M')
                    hours+=max(0,(b-a).total_seconds()/3600)
                except (ValueError,TypeError): pass
            try: month=datetime.strptime(r['date'],'%Y-%m-%d').strftime('%b %Y')
            except (ValueError,TypeError): month=str(r['date'] or 'Unknown')[:7]
            months[month]+=1
    n=len(rows)
    return dict(total=n,done=statuses['Completed'],pct=round(statuses['Completed']*100/n) if n else 0,
        scheduled=statuses['Scheduled'],hours=hours,attendance=attendance,status=statuses,
        schools=dict(schools),coaches=dict(coaches),months=dict(months))

def barlist(items):
    mx=max([v[0] for v in items.values()] or [1]) or 1
    return ''.join('<div class="bar"><span>'+e(str(k))+'</span><div class="track"><i style="width:'+str(round(v[0]*100/mx))+'%"></i></div><b>'+str(v[0])+'</b></div>' for k,v in sorted(items.items(),key=lambda x:(-x[1][0],x[0]))) or '<p>No completed sessions yet.</p>'

def render(d, membership=None, juvenile_total=None):
    membership = membership or {}
    tools='<div class="report-tools"><a class="btn" href="/reports">Back to Reports</a> <a class="btn" href="/reports/schools/styled.pdf">Download PDF</a></div>'
    logos='<img src="/report-eastern-gaels.jpg" alt="Eastern Gaels"><img src="/report-meath.png" alt="Meath">'
    cover='''<section class="school-page"><div class="accent"></div><div class="cover">
      <div class="logos">'''+logos+'''</div><div class="motto">OUR CLUB · OUR SCHOOLS · OUR COMMUNITY</div>
      <div class="illustration"><svg viewBox="0 0 560 250" aria-label="School, football and young players">
      <path d="M25 78L174 10 323 78Z" fill="#efc44b"/><rect x="43" y="78" width="260" height="150" rx="6" fill="#fff8e4"/>
      <rect x="147" y="151" width="52" height="77" fill="#005638"/><rect x="78" y="111" width="45" height="40" fill="#9cdbbb"/><rect x="223" y="111" width="45" height="40" fill="#9cdbbb"/>
      <text x="173" y="103" font-size="17" font-weight="bold" fill="#005638" text-anchor="middle">SCHOOL</text>
      <circle cx="395" cy="115" r="44" fill="white" stroke="#e8bd42" stroke-width="5"/><path d="M376 102l19-12 20 12-7 24h-27z" fill="#005638"/>
      <circle cx="495" cy="85" r="19" fill="#f1c9a6"/><path d="M470 126Q495 108 520 126L532 198H458Z" fill="#efc44b"/>
      <path d="M473 198l-8 32M515 198l9 32" stroke="#f8f8f8" stroke-width="12"/>
      <path d="M25 232H545" stroke="#efc44b" stroke-width="5"/></svg></div>
      <div class="eyebrow">EASTERN GAELS GAA · MEATH</div><h1>Club &amp; School,<br>Gaelic is Cool!</h1>
      <h2>Schools Coaching Programme</h2><div class="year">2026–2027</div>
      <p>Sponsored by Romar Energy · Growing Gaelic Games through our schools</p><div class="motto">OUR CLUB — OUR COMMUNITY</div>
      </div></section>'''
    metrics=[('Sessions completed',str(d['done']),'of '+str(d['total'])+' planned','▣'),('Programme complete',str(d['pct'])+'%',str(d['scheduled'])+' still scheduled','✓'),('Coaching hours',f"{d['hours']:.1f}",'completed sessions','◷'),('Recorded attendance',str(d['attendance']),'total contacts entered','★')]
    tiles=''.join('<div class="metric"><em>'+icon+'</em><strong>'+value+'</strong><b>'+name+'</b><small>'+sub+'</small></div>' for name,value,sub,icon in metrics)
    statuscolors=[('Completed','#07824c'),('Scheduled','#edc449'),('Cancelled','#b95148'),('School Closed','#8c9e98')]
    statusbar=''.join('<i style="background:'+color+';width:'+str(d['status'].get(k,0)*100/max(1,d['total']))+'%"></i>' for k,color in statuscolors)
    legend=''.join('<div><i style="background:'+color+'"></i>'+k+' <b>'+str(d['status'].get(k,0))+'</b></div>' for k,color in statuscolors)
    months=barlist({k:[v,v] for k,v in d['months'].items()})
    items=sorted(d['schools'].items());mid=(len(items)+1)//2
    def col(part):
        return '<div class="school-col">'+''.join('<div class="school-row"><span>'+e(str(k))+'</span><b>'+str(v[0])+' / '+str(v[1])+' · '+str(round(100*v[0]/v[1]) if v[1] else 0)+'%</b></div>' for k,v in part)+'</div>'
    membership_items=sorted(((str(k),int(v or 0)) for k,v in membership.items()),key=lambda x:(-x[1],x[0]))
    membership_total=sum(v for _,v in membership_items)
    juvenile_total=membership_total if juvenile_total is None else int(juvenile_total)
    if juvenile_total > membership_total:
        membership_items.append(("School not recorded", juvenile_total-membership_total))
    membership_total=sum(v for _,v in membership_items)
    def membership_col(part):
        return '<div class="school-col">'+''.join('<div class="school-row"><span>'+e(k)+'</span><b>'+str(v)+'</b></div>' for k,v in part)+'</div>'
    membership_mid=(len(membership_items)+1)//2
    membership_html='<div class="panel school-membership-panel"><h3>School breakdown of club membership · '+str(membership_total)+' juvenile players</h3><div class="school-cols">'+membership_col(membership_items[:membership_mid])+membership_col(membership_items[membership_mid:])+'</div></div>' if membership_items else '<div class="panel school-membership-panel"><h3>School breakdown of club membership</h3><p>No membership school figures available.</p></div>'
    body='''<section class="school-page"><div class="accent"></div><div class="content">
      <div class="heading"><div><h2>Club &amp; School, Gaelic is Cool! — Coaching Summary</h2><p>2026–2027 · Live programme figures</p></div><div class="mini-logos">'''+logos+'''</div></div>
      <div class="metrics">'''+tiles+'''</div><div class="panels">
      <div class="panel"><h3>▥ Completed sessions by month</h3>'''+months+'''</div>
      <div class="panel"><h3>◉ Session status</h3><div class="statusbar">'''+statusbar+'''</div><div class="legend">'''+legend+'''</div></div>
      <div class="panel"><h3>⌂ Completed by school</h3>'''+barlist(d['schools'])+'''</div>
      <div class="panel"><h3>★ Completed by coach</h3>'''+barlist(d['coaches'])+'''</div></div>
      <div class="panel school-progress-panel"><h3>Programme progress across each school · completed / planned · %</h3><div class="school-cols">'''+col(items[:mid])+col(items[mid:])+'''</div></div>'''+membership_html+'''
      <div class="sponsor-credit">The Club &amp; School, Gaelic is Cool! Schools Coaching Programme is run and sponsored by <strong>Romar Energy</strong>.</div></div><div class="footer">EASTERN GAELS GAA · CLUB &amp; SCHOOL, GAELIC IS COOL! · ROMAR ENERGY</div></section>'''
    css='''<style>
    .report-tools{display:flex;gap:12px;margin:20px 0}.school-page{box-sizing:border-box;width:840px;min-height:1120px;margin:20px auto;background:white;color:#005638;box-shadow:0 5px 25px #0002;font-family:Arial,sans-serif;overflow:hidden}.school-page *{box-sizing:border-box}.accent{height:18px;background:linear-gradient(110deg,#005638 0 70%,#e9bd3e 70% 84%,#005638 84%)}.cover{height:1102px;background:#004b32;color:white;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:25px;padding:38px 55px}.logos{display:flex;justify-content:space-between;width:100%}.logos img{width:105px;height:112px;object-fit:contain}.motto{color:#efc54c;font-weight:bold;letter-spacing:2px}.illustration{width:100%;background:#0b6744;border:3px solid #efc54c;border-radius:18px;padding:20px}.illustration svg{width:100%;height:auto}.eyebrow{letter-spacing:3px;color:#f4d679;font-weight:bold}.cover h1{font-size:66px;line-height:1.05;margin:0}.cover h2{font-size:25px;color:#f1c94d;margin:0}.year{font-size:34px;font-weight:bold}.cover p{font-style:italic;font-size:18px}.content{padding:24px 27px 12px}.heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.heading h2{font-size:24px;margin:0}.heading p{color:#658071;margin:5px 0}.mini-logos{display:flex;gap:9px}.mini-logos img{width:48px;height:52px;object-fit:contain}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.metric{background:linear-gradient(140deg,#f7fff9,#d5ecde);border:1px solid #cbded1;border-top:5px solid #e9bc3b;border-radius:12px;padding:10px 5px;text-align:center;display:flex;flex-direction:column;gap:5px}.metric em{font-size:22px;font-style:normal}.metric strong{font-size:31px}.metric b{font-size:12px}.metric small{font-size:10px}.panels{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.panel{border:1px solid #d4e5da;border-radius:12px;padding:11px;min-width:0;box-shadow:0 3px 9px #003e2b12}.panel h3{font-size:16px;margin:0 0 11px}.bar{display:flex;align-items:center;gap:6px;margin:6px 0;font-size:11px}.bar span{width:38%;overflow-wrap:anywhere}.track{flex:1;background:#e0eee6;height:13px;border-radius:8px;overflow:hidden}.track i{display:block;height:100%;border-radius:8px;background:linear-gradient(90deg,#007c49,#eac145)}.bar b{min-width:15px;text-align:right}.statusbar{display:flex;height:35px;border-radius:7px;overflow:hidden;margin:16px 0}.legend{display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:11px}.legend>div{display:flex;align-items:center;gap:5px}.legend i{width:12px;height:12px;border-radius:3px}.legend b{margin-left:auto}.school-progress-panel{margin-top:10px}.school-membership-panel{margin-top:8px}.sponsor-credit{text-align:center;font-size:12px;color:#005638;margin-top:10px;padding:8px;border-top:2px solid #e9bd3e}.sponsor-credit strong{font-size:15px;color:#087e94}.school-membership-panel .school-row{padding:3px 0;font-size:10px}.school-cols{display:flex;gap:13px}.school-col{flex:1;min-width:0}.school-row{display:flex;justify-content:space-between;gap:6px;border-bottom:1px solid #e2eee6;padding:5px 0;font-size:11px}.school-row span{overflow-wrap:anywhere}.school-row b{white-space:nowrap}.school-page{position:relative}.school-page .footer{position:absolute;bottom:0;left:0;right:0}.school-page .content{padding-bottom:38px}.school-page .panels .panel{min-height:0}.school-progress-panel .school-row{padding:5px 0;font-size:11px}.school-progress-panel .school-cols{gap:12px}.footer{text-align:center;background:#005638;color:white;font-weight:bold;letter-spacing:2px;font-size:11px;padding:12px}
    @media print{@page{size:A4;margin:0}.report-tools{display:none}.school-page{width:210mm;height:297mm;min-height:297mm;max-height:297mm;margin:0;box-shadow:none;break-after:page;page-break-after:always}.school-page:last-child{break-after:auto}.accent{height:5mm}.cover{height:292mm}.content{padding:8mm 9mm 3mm}.heading h2{font-size:19px}.metrics{gap:6px}.metric{padding:5px 3px}.metric strong{font-size:25px}.metric em{font-size:17px}.panels{gap:7px;margin-top:9px}.panel{padding:7px}.panel h3{font-size:12px;margin-bottom:6px}.bar{font-size:9px;margin:4px 0}.track{height:9px}.school-row{font-size:9px;padding:3px 0}.school-progress-panel .school-row{font-size:9px;padding:3px 0}.school-progress-panel{margin-top:8px}.footer{font-size:9px;padding:7px}}
    </style>'''
    return css+tools+cover+body

def pdf(d,base,membership=None,juvenile_total=None):
    from weasyprint import HTML
    html=re.sub(r'<div class="report-tools">.*?</div>','',render(d,membership,juvenile_total),count=1,flags=re.S)
    for route,name in {'/report-eastern-gaels.jpg':'Eastern Gaels .jpg','/report-meath.png':'Meath Logo.png'}.items():
        html=html.replace('src="'+route+'"','src="'+Path(base,name).as_uri()+'"')
    return HTML(string='<html><head><meta charset="utf-8"></head><body>'+html+'</body></html>',base_url=Path(base).as_uri()).write_pdf()
