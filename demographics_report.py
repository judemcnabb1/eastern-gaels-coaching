"""Printable Eastern Gaels demographics report, using the dashboard's live DEMO data."""
from html import escape

def render(demo, charts):
    growth = demo.get("growth", {})
    ages = demo.get("age_totals", {})
    parish = demo.get("catchment", {})
    schools = demo.get("school_totals", {})
    years = sorted((str(y) for y in growth if str(y).isdigit()), key=int)
    year = years[-1] if years else "Current"
    juvenile = sum(int(v or 0) for v in ages.values())
    adult = sum(int(demo.get(k, 0) or 0) for k in ("senior_adult_non_playing_count", "senior_adult_ladies_count", "senior_adult_mens_count"))
    metrics = [("Total members", juvenile + adult), ("Juvenile players", juvenile), ("Adult members", adult), ("Age groups", len(ages))]
    tiles = "".join(f'<div class="metric"><strong>{v}</strong><span>{escape(k)}</span></div>' for k, v in metrics)
    graphs = [
        ("Players by age group", charts["bar"](ages, 230)),
        ("Juvenile membership trend", charts["line"](growth)),
        ("Parish catchment", charts["donut"](parish, subtitle="players")),
        ("Schools represented", charts["horizontal"](schools)),
    ]
    panels = "".join(f'<section class="panel"><h3>{escape(title)}</h3>{graph}</section>' for title, graph in graphs)
    css = """<style>
    .report-tools{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
    .report-page{background:#fff;color:#064630;max-width:840px;min-height:1080px;margin:20px auto;box-shadow:0 5px 25px #0002;overflow:hidden}
    .report-accent{height:22px;background:linear-gradient(110deg,#005638 0 65%,#ffca28 65% 80%,#005638 80%)}
    .report-identity{display:flex;justify-content:space-evenly;align-items:center;gap:25px;padding:38px 35px 18px;text-align:center}
    .report-identity img{width:154px;height:155px;object-fit:contain}.report-identity p{font-weight:800;letter-spacing:1px;font-size:12px;margin:6px 0}.report-mini-identity{display:flex;align-items:center;gap:12px}.report-mini-identity img{width:56px;height:64px;object-fit:contain}.report-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:18px}.report-heading h2{margin:0}.report-heading p{margin:4px 0;color:#527566}
    .report-cover-title{text-align:center;padding:18px 20px 28px}
    .report-cover-title h1{font-size:clamp(42px,7vw,64px);line-height:1.1;color:#004b32;margin:0}
    .report-cover-title h2{font-size:38px;color:#004b32}
    .report-cover-title p{font-size:20px;font-style:italic}
    .report-photo{height:445px;background:linear-gradient(0deg,#003e2baa,transparent 65%),url('/report-pitch.png') center/cover no-repeat}
    .report-jersey{height:200px;background:url('/report-jersey.jpg') center/contain no-repeat}
    .report-footer{background:#005638;color:#fff;text-align:center;padding:16px;letter-spacing:2px;font-size:12px;font-weight:700}
    .report-body{padding:26px 28px 20px}.report-body h2{color:#004b32}
    .report-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
    .metric{text-align:center;background:#edf5ef;padding:17px 5px;border-top:4px solid #ffca28}
    .metric strong{display:block;font-size:32px}.metric span{font-size:12px;font-weight:800;text-transform:uppercase}
    .report-charts{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:20px}
    .panel{border:1px solid #d8e5de;padding:12px;border-radius:7px;overflow:hidden;min-height:215px}
    .panel h3{font-size:16px;color:#005638}.panel svg{width:100%;height:auto}
    @media(max-width:650px){.report-metrics,.report-charts{grid-template-columns:1fr 1fr}.report-identity{padding:20px}}
    @media print{@page{size:A4;margin:0}.sidebar,.topbar,.report-tools{display:none!important}
    .report-page{width:210mm;height:297mm;min-height:297mm;max-width:none;box-shadow:none;margin:0;break-after:page;page-break-after:always}.report-page:last-of-type{break-after:auto;page-break-after:auto}
    *{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
    </style>"""
    # Asset URLs are supplied by the main application when the official files are installed.
    identity = '<div class="report-identity"><div><img src="/report-eastern-gaels.jpg" alt="Eastern Gaels club crest"><p>EASTERN GAELS</p></div><div><img src="/report-meath.png" alt="Meath GAA county crest"><p>MEATH GAA</p></div></div>'
    footer = '<div class="report-footer">AN MHÍ | EASTERN GAELS | TOGETHER WE GROW</div>'
    cover = '<section class="report-page"><div class="report-accent"></div>' + identity + '<div class="report-cover-title"><h1>Demographics<br>Report</h1><h2>' + escape(year) + '</h2><p>Our People | Our Club | Our Community</p></div><div class="report-photo"></div>' + footer + '</section>'
    data = '<section class="report-page"><div class="report-accent"></div><div class="report-body"><div class="report-heading"><div><h2>DEMOGRAPHICS REPORT ' + escape(year) + '</h2><p>Our People | Our Club | Our Community</p></div><div class="report-mini-identity"><img src="/report-eastern-gaels.jpg" alt="Eastern Gaels crest"><img src="/report-meath.png" alt="Meath GAA crest"></div></div><div class="report-metrics">' + tiles + '</div><div class="report-charts">' + panels + '</div><p>Source: Eastern Gaels dashboard demographics dataset. Juvenile growth is distinct from total club membership.</p></div>' + footer + '</section>'
    return css + '<div class="report-tools"><a class="btn" href="/reports">Back to Reports</a> <button class="btn" onclick="window.print()">Print / Save PDF</button></div>' + cover + data
