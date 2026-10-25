"""Live coaching compliance summary, based on the dashboard's current records."""
from datetime import date
from html import escape
from pathlib import Path

def render(coaches, records):
    today=date.today()
    items=sorted(coaches.items(),key=lambda kv:kv[1].get('name','').casefold())
    results={k:{'current':[],'outstanding':[],'warning':[]} for k in ('garda','safeguarding')}
    for key,coach in items:
        name=str(coach.get('name') or key)
        for typ in results:
            record=records.get(key,{}).get(typ,{})
            if not isinstance(record,dict):record={}
            expiry=record.get('expiry') or (coach.get('garda_expiry') if typ=='garda' else None)
            try: exp=date.fromisoformat(str(expiry))
            except (ValueError,TypeError):exp=None
            status=str(coach.get('garda_vetted' if typ=='garda' else 'safeguarding','Unknown')).strip().lower()
            # A recorded certificate expiry is evidence of status even when the imported flag is unknown.
            evidence=bool(record.get('file') or record.get('drive_file_id') or exp)
            current=(status=='yes' or evidence) and exp is not None and exp>=today
            if current:
                results[typ]['current'].append((name,exp.isoformat()))
                days=(exp-today).days
                if days<=90:results[typ]['warning'].append((name,exp.isoformat(),days))
            else:
                reason='Expired' if exp and exp<today else 'Expiry date not recorded' if status=='yes' or evidence else 'Not completed' if status=='no' else 'Status not confirmed'
                results[typ]['outstanding'].append((name,reason))
    n=len(items)
    def table(headers,rows):
        head=''.join('<th>'+escape(x)+'</th>' for x in headers)
        body=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)
        if not body:body='<tr><td colspan="'+str(len(headers))+'">None recorded</td></tr>'
        return '<table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>'
    g=results['garda'];s=results['safeguarding']
    def pct(x):return f'{len(x["current"])*100/n:.0f}%' if n else '—'
    css="""<style>
    .compliance-cover{height:1030px;max-width:900px;margin:20px auto;background:#004b32;color:white;font-family:Arial,sans-serif;display:flex;flex-direction:column;justify-content:space-between}.compliance-cover .cover-head{padding:45px;display:flex;align-items:center;gap:25px}.compliance-cover .cover-head img{width:110px;height:125px;object-fit:contain}.compliance-cover .cover-head strong{font-size:34px}.compliance-cover .cover-photo{height:370px;background-image:url("/report-pitch.png");background-size:cover;background-position:center;border-top:9px solid #edc449;border-bottom:9px solid #edc449}.compliance-cover .cover-bottom{padding:35px 55px 65px}.compliance-cover h1{font-size:59px;line-height:1.1;margin:0;color:white}.compliance-cover h1 span{color:#edc449}.compliance-cover .cover-year{font-size:26px;color:#edc449}.compliance-cover .cover-areas{font-size:17px;letter-spacing:2px;margin:25px 0}.compliance-cover .cover-motto{font-size:12px;letter-spacing:2px}.compliance-report{max-width:900px;margin:20px auto;background:#fff;padding:30px;color:#123b2b;font-family:Arial,sans-serif}
    .approved-compliance-cover{display:block!important;position:relative!important;width:min(100%,900px)!important;max-width:900px!important;height:auto!important;aspect-ratio:1024/1448!important;min-height:0!important;margin:20px auto 36px!important;padding:0!important;overflow:hidden!important;clear:both!important;box-sizing:border-box!important}
    .approved-compliance-cover img{display:block!important;position:static!important;width:100%!important;height:100%!important;max-width:100%!important;object-fit:fill!important}
    .compliance-report{clear:both!important;position:relative!important;box-sizing:border-box!important;width:min(100%,900px)!important;max-width:900px!important;margin:0 auto 24px!important;overflow:visible!important}
    .compliance-report table{table-layout:fixed!important;max-width:100%!important;overflow-wrap:anywhere!important}
    .compliance-report td,.compliance-report th{overflow-wrap:anywhere!important;word-break:normal!important}
    @media print{
      @page{size:A4;margin:0}
      html,body{margin:0!important;padding:0!important;width:210mm!important;max-width:210mm!important}
      .approved-compliance-cover{width:210mm!important;max-width:210mm!important;height:297mm!important;aspect-ratio:auto!important;margin:0!important;padding:0!important;break-after:page!important;page-break-after:always!important}
      .approved-compliance-cover img{width:210mm!important;height:297mm!important}
      .compliance-report{width:210mm!important;max-width:210mm!important;margin:0!important;padding:15mm!important;box-sizing:border-box!important;overflow:visible!important}
      .compliance-report .scores{display:block!important}
      .compliance-report .score{display:inline-block!important;vertical-align:top!important;width:46%!important;box-sizing:border-box!important;margin-right:2%!important}
      .compliance-report table{width:100%!important;table-layout:fixed!important;font-size:10px!important}
      .compliance-report th,.compliance-report td{padding:5px!important}
    }
    .compliance-report h1{font-size:29px;margin:0;color:#005638}.compliance-report .subtitle{color:#657c70;margin:8px 0 22px}
    .compliance-report .scores{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px}
    .compliance-report .score{border-top:6px solid #e9bd3e;background:#edf7f0;border-radius:8px;padding:16px}
    .compliance-report .score strong{display:block;font-size:38px;color:#005638}
    .compliance-report h2{font-size:18px;border-bottom:2px solid #e9bd3e;padding-bottom:7px;margin:22px 0 9px}
    .compliance-report table{border-collapse:collapse;width:100%;font-size:12px;page-break-inside:auto}
    .compliance-report th{background:#005638;color:white;text-align:left;padding:9px}
    .compliance-report td{padding:7px 9px;border-bottom:1px solid #dce8df}
    .compliance-report tr{break-inside:avoid}
    .compliance-report .note{font-size:12px;color:#566c60;line-height:1.5}
    .compliance-report .report-tools{margin-bottom:20px}
    @page{size:A4;margin:14mm}
    @media print{.approved-compliance-cover{width:210mm;height:297mm;max-width:none;margin:0;break-after:page;page-break-after:always}.approved-compliance-cover img{width:100%;height:100%;object-fit:fill}.compliance-cover .cover-photo{height:100mm}.compliance-cover h1{font-size:48px}.compliance-report{padding:0;margin:0;max-width:none}.compliance-report h2{break-after:avoid}.compliance-report thead{display:table-header-group}.compliance-report .report-tools{display:none}}
    </style>"""
    tools='<div class="report-tools"><a class="btn" href="/reports">Back to Reports</a> <a class="btn" href="/reports/compliance.pdf">Download PDF</a></div>'
    cover='<section class="compliance-cover approved-compliance-cover"><img src="/compliance-cover.png" alt="Eastern Gaels Coaching Compliance report cover"></section>'
    h=css+cover+'<article class="compliance-report">'+tools+'<h1>Eastern Gaels · Coaching Compliance</h1><p class="subtitle">Garda Vetting &amp; Safeguarding · As at '+today.strftime('%d %B %Y')+'</p>'
    h+='<div class="scores"><div class="score"><strong>'+pct(g)+'</strong><b>Garda vetted</b><p>'+str(len(g['current']))+' of '+str(n)+' coaches</p></div><div class="score"><strong>'+pct(s)+'</strong><b>Safeguarding current</b><p>'+str(len(s['current']))+' of '+str(n)+' coaches</p></div></div>'
    h+='<p class="note">Current = positive status or recorded evidence AND a valid expiry date. Unknown or missing dates are treated as outstanding until confirmed; expired records are not counted as current.</p>'
    for typ,label in [('garda','Garda Vetting'),('safeguarding','Safeguarding')]:
        v=results[typ]
        h+='<h2>'+label+' · Current ('+str(len(v['current']))+')</h2>'+table(['Coach','Expiry date'],v['current'])
    h+='<h2>Outstanding · Garda Vetting ('+str(len(g['outstanding']))+')</h2>'+table(['Coach','Action / status'],g['outstanding'])
    h+='<h2>Outstanding · Safeguarding ('+str(len(s['outstanding']))+')</h2>'+table(['Coach','Action / status'],s['outstanding'])
    warning=sorted([(name,'Garda Vetting',expiry,str(days)+' days') for name,expiry,days in g['warning']]+[(name,'Safeguarding',expiry,str(days)+' days') for name,expiry,days in s['warning']],key=lambda x:x[2])
    h+='<h2>Expiry warning · Within 90 days ('+str(len(warning))+')</h2>'+table(['Coach','Requirement','Expiry date','Remaining'],warning)
    h+='<p class="note">Source: live Coaching &amp; Teams records and Compliance certificate dates. The warning table includes dates from today through the next 90 days. Please confirm missing certificate expiry dates on the Compliance page.</p></article>'
    return h

def pdf(coaches,records,base):
    from weasyprint import HTML
    html=render(coaches,records)
    html=html.replace('/compliance-cover.png',Path(base,'compliance-cover.png').as_uri())
    return HTML(string='<html><head><meta charset="utf-8"></head><body>'+html+'</body></html>',base_url=Path(base).as_uri()).write_pdf()
