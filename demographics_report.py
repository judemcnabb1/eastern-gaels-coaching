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
    .report-identity{display:flex;justify-content:space-around;align-items:center;gap:25px;padding:45px 35px;text-align:center}
    .report-identity img{max-width:180px;max-height:170px;object-fit:contain}
    .rpt-county{border:4px solid #ffc72c;padding:28px;color:#005638;font-size:25px;font-weight:900}.report-cover-title{text-align:center;padding:45px 20px}
    .report-cover-title h1{font-size:clamp(42px,7vw,70px);line-height:1.1;color:#004b32;margin:0}
    .report-cover-title h2{font-size:38px;color:#004b32}
    .report-cover-title p{font-size:20px;font-style:italic}
    .report-photo{height:385px;background:linear-gradient(0deg,#003e2baa,transparent 65%),url('/report-pitch.png') center/cover no-repeat}
    .report-jersey{height:200px;background:url('/report-jersey.jpg') center/contain no-repeat}
    .report-footer{background:#005638;color:#fff;text-align:center;padding:16px;letter-spacing:2px;font-size:12px;font-weight:700}
    .report-body{padding:26px}.report-body h2{color:#004b32}
    .report-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
    .metric{text-align:center;background:#edf5ef;padding:17px 5px;border-top:4px solid #ffca28}
    .metric strong{display:block;font-size:32px}.metric span{font-size:12px;font-weight:800;text-transform:uppercase}
    .report-charts{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:20px}
    .panel{border:1px solid #d8e5de;padding:12px;border-radius:7px;overflow:hidden}
    .panel h3{font-size:16px;color:#005638}.panel svg{width:100%;height:auto}
    @media(max-width:650px){.report-metrics,.report-charts{grid-template-columns:1fr 1fr}.report-identity{padding:20px}}
    @media print{@page{size:A4;margin:0}.sidebar,.topbar,.report-tools{display:none!important}
    .report-page{width:210mm;height:297mm;min-height:297mm;max-width:none;box-shadow:none;margin:0;break-after:page;page-break-after:always}
    *{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
    </style>"""
    # Asset URLs are supplied by the main application when the official files are installed.
    identity = '<div class="report-identity"><div><img src="/club-jersey.png" alt="Eastern Gaels official crest"><p>EASTERN GAELS</p></div><div class="rpt-county"><strong>MEATH GAA</strong><p>AN MHÍ</p></div></div>'
    footer = '<div class="report-footer">AN MHÍ | EASTERN GAELS | TOGETHER WE GROW</div>'
    cover = '<section class="report-page"><div class="report-accent"></div>' + identity + '<div class="report-cover-title"><h1>Demographics<br>Report</h1><h2>' + escape(year) + '</h2><p>Our People | Our Club | Our Community</p></div><div class="report-photo"></div>' + footer + '</section>'
    data = '<section class="report-page"><div class="report-accent"></div><div class="report-body"><h2>DEMOGRAPHICS REPORT ' + escape(year) + '</h2><p>Live dashboard data</p><div class="report-metrics">' + tiles + '</div><div class="report-charts">' + panels + '</div><p>Source: Eastern Gaels dashboard demographics dataset. Juvenile growth is distinct from total club membership.</p></div>' + footer + '</section>'
    return css + '<div class="report-tools"><a class="btn" href="/reports">Back to Reports</a> <button class="btn" onclick="window.print()">Print / Save PDF</button></div>' + cover + data
