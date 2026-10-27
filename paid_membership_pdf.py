"""Paid Membership 2026 PDF using the Demographics Report's original vector pie charts."""
from collections import Counter
from html import escape
from pathlib import Path
from weasyprint import HTML
from demographics_report import catchment_pie

def build_pdf(demo, base):
    juvenile = demo.get('players_by_age', {})
    adults = demo.get('adult_payment', {})
    age_keys = sorted(juvenile, key=lambda v: (int(v[1:]) if v[1:].isdigit() else 999, str(v)))
    groups = [(('U13' if str(name).strip().upper() == 'U1' else name), juvenile[name]) for name in age_keys] + list(adults.items())
    members = [m for _, group in groups for m in group]
    counts = Counter(m.get('paid') for m in members)
    paid, unpaid = counts['YES'], counts['NO']
    unknown = len(members) - paid - unpaid
    known = paid + unpaid
    rate = f'{100 * paid / known:.1f}%' if known else 'N/A'
    cover = Path(base, 'paid-membership-cover.png')
    if cover.exists():
        cover_markup = '<img class="cover-image" src="' + cover.as_uri() + '" alt="Paid Membership 2026 cover">'
    else:
        cover_markup = '<div class="fallback-cover"><h1>EASTERN GAELS</h1><h2>PAID MEMBERSHIP 2026</h2></div>'
    sections = []
    for name, group in groups:
        cc = Counter(m.get('paid') for m in group)
        yes, no = cc['YES'], cc['NO']
        other = len(group) - yes - no
        chart = catchment_pie({'Paid': yes, 'Not paid': no, 'Not recorded': other})
        unpaid_names = [escape(str(m.get('name') or 'Name not recorded')) for m in group if m.get('paid') == 'NO']
        names_html = '<ul>' + ''.join('<li>' + n + '</li>' for n in unpaid_names) + '</ul>' if unpaid_names else '<p class="clear">No unpaid members recorded.</p>'
        sections.append('<section class="group"><h2>' + escape(str(name)) + '</h2><div class="chart">' + chart + '</div><h3>Members recorded as not paid (' + str(no) + ')</h3>' + names_html + '</section>')
    css = """
    @page { size:A4; margin:15mm 14mm 16mm; }
    @page:first { margin:0; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:Arial,Helvetica,sans-serif; color:#164832; font-size:10pt; }
    .cover { height:297mm; width:210mm; page-break-after:always; overflow:hidden; }
    .cover-image { width:210mm; height:297mm; display:block; object-fit:fill; }
    .fallback-cover { height:297mm; background:#075438; color:white; padding:80mm 20mm; text-align:center; }
    .intro { border-top:6px solid #e9b62e; padding-top:12px; margin-bottom:15px; }
    h1 { font-size:25pt; color:#075438; margin:0 0 8px; }
    .subtitle { color:#547162; margin:0 0 14px; }
    .summary { width:100%; border-collapse:separate; border-spacing:6px; margin:12px -6px; }
    .summary td { background:#eaf4ed; border:1px solid #c3d8ca; border-bottom:5px solid #b4cebd; border-radius:9px; text-align:center; padding:12px 5px; width:25%; }
    .summary strong { display:block; font-size:22pt; color:#075438; }
    .summary span { font-size:8pt; font-weight:bold; }
    .note { color:#536d60; font-size:9pt; line-height:1.5; }
    .group { page-break-inside:avoid; break-inside:avoid; margin:18px 0; padding:12px 16px 14px; border:1px solid #cddfd3; border-bottom:5px solid #c0d8c7; border-radius:13px; background:#f5faf6; }
    .group h2 { color:#075438; font-size:17pt; margin:0 0 4px; border-bottom:3px solid #e9b62e; padding-bottom:6px; }
    .group h3 { font-size:10pt; color:#164832; margin:8px 0 4px; }
    .chart { width:100%; }
    .catchment-pie-layout { display:flex; flex-direction:row; align-items:center; gap:22px; }
    .catchment-pie-layout svg { width:42%; height:175px; flex:none; }
    .catchment-pie-key { width:55%; font-size:9pt; }
    .catchment-legend-heading { font-size:9pt; font-weight:900; color:#005638; letter-spacing:1px; margin-bottom:5px; }
    .catchment-legend-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #dce8df; }
    .catchment-swatch { width:12px; height:12px; flex:none; border-radius:2px; }
    .catchment-area { flex:1; }
    .catchment-legend-row strong { color:#005638; white-space:nowrap; }
    .catchment-total { border-top:1px solid #c9dbcf; margin-top:6px; padding-top:6px; font-weight:bold; }
    ul { columns:2; padding-left:18px; margin:5px 0; line-height:1.5; }
    li { break-inside:avoid; }
    .clear { color:#11834d; margin:4px 0; }
    """
    summary = ''.join('<td><strong>' + str(value) + '</strong><span>' + label + '</span></td>' for value, label in [
        (len(members), 'TOTAL RECORDS'), (paid, 'PAID'), (unpaid, 'NOT PAID'), (unknown, 'NOT RECORDED')])
    body = ('<html><head><meta charset="utf-8"><style>' + css + '</style></head><body>'
            + '<section class="cover">' + cover_markup + '</section>'
            + '<div class="intro"><h1>Paid Membership 2026</h1><p class="subtitle">EASTERN GAELS · MEMBERSHIP REPORT</p></div>'
            + '<table class="summary"><tr>' + summary + '</tr></table>'
            + '<p class="note"><b>' + rate + '</b> of members with a recorded YES/NO status are paid. '
            + str(unknown) + ' records have no confirmed payment status and are not counted as unpaid. '
            + 'Figures represent member records, not euro amounts.</p>'
            + ''.join(sections) + '</body></html>')
    return HTML(string=body, base_url=Path(base).as_uri()).write_pdf()
