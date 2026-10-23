"""Printable Eastern Gaels demographics report, using the dashboard's live DEMO data."""
from html import escape

def age_group_3d(ages):
    items = [(str(k), max(0, int(v or 0))) for k, v in ages.items()]
    if not items:
        return '<p>No age-group figures available.</p>'
    maximum = max(1, *(v for _, v in items))
    step = 600 / len(items)
    width = min(48, step * .55)
    shapes = ['<svg class="report-3d-bars" viewBox="0 0 660 290" role="img" aria-label="Players by age group">']
    for i, (label, value) in enumerate(items):
        x = 38 + i * step + (step - width) / 2
        h = 170 * value / maximum
        y = 228 - h
        front = '#087f4a' if i % 2 == 0 else '#e8ae25'
        side = '#005b37' if i % 2 == 0 else '#a77b0c'
        top = '#57c891' if i % 2 == 0 else '#f8d86b'
        shapes.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{h:.1f}" fill="{front}"/>')
        shapes.append(f'<polygon points="{x+width:.1f},{y:.1f} {x+width+12:.1f},{y-12:.1f} {x+width+12:.1f},216 {x+width:.1f},228" fill="{side}"/>')
        shapes.append(f'<polygon points="{x:.1f},{y:.1f} {x+12:.1f},{y-12:.1f} {x+width+12:.1f},{y-12:.1f} {x+width:.1f},{y:.1f}" fill="{top}"/>')
        shapes.append(f'<text x="{x+width/2:.1f}" y="{max(15,y-17):.1f}" text-anchor="middle" font-size="17" font-weight="800" fill="#005638">{value}</text>')
        shapes.append(f'<text x="{x+width/2:.1f}" y="257" text-anchor="middle" font-size="14" font-weight="700" fill="#285440">{escape(label)}</text>')
    return ''.join(shapes) + '</svg>'

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
    gender = demo.get("juvenile_gender", {}) or {}
    boys = int(gender.get("Boys", 0) or 0)
    girls = int(gender.get("Girls", 0) or 0)
    gender_chart = charts["donut"]({"Boys": boys, "Girls": girls}, subtitle="juvenile players") if boys + girls else '<p class="report-no-data">Juvenile boys/girls totals are not available in the current dataset.</p>'
    parish_counts = {str(k): int(v or 0) for k, v in parish.items()} if isinstance(parish, dict) else {}
    parish_total = sum(v for v in parish_counts.values() if v > 0)
    parish_legend = ('<div class="report-parish-counts">' + ''.join(f'<div><span>{escape(name)}</span><strong>{count} · {count/parish_total:.0%}</strong></div>' for name, count in sorted(parish_counts.items(), key=lambda item: -item[1]) if count > 0) + '</div>') if parish_total else '<p class="report-no-data">No parish catchment data available.</p>'
    graphs = [
        ("Juvenile boys & girls", gender_chart),
        ("Players by age group — 3D bars", age_group_3d(ages)),
        ("Juvenile membership trend", charts["line"](growth)),
        ("Parish catchment — players by area", charts["donut"](parish_counts, subtitle="players") + parish_legend),
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
    .metric{text-align:center;background:linear-gradient(145deg,#f8fff9,#d9efe2);padding:17px 5px;border:1px solid #cbded1;border-top:5px solid #ffca28;border-radius:12px;box-shadow:0 5px 12px #003e2b20}.metric:nth-child(2){background:linear-gradient(145deg,#e5f5e8,#bfe4d0)}.metric:nth-child(3){background:linear-gradient(145deg,#fff9e6,#f4e2b4)}.metric:nth-child(4){background:linear-gradient(145deg,#e5f4f1,#cde8e0)}.report-3d-bars{width:100%;height:auto;display:block}
    .metric strong{display:block;font-size:40px;line-height:1.15;font-weight:900;letter-spacing:-1px;color:#004d32}.metric span{font-size:12px;font-weight:800;text-transform:uppercase}
    .report-charts{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:20px}
    .panel{border:1px solid #d8e5de;padding:12px;border-radius:7px;overflow:hidden;min-height:215px}
    .report-parish-counts{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;margin-top:10px;font-size:11px}.report-parish-counts>div{display:flex;justify-content:space-between;gap:5px;border-bottom:1px solid #e6eee9;padding:3px 0}.report-parish-counts strong{white-space:nowrap;color:#005638}.report-no-data{font-size:14px;color:#567369;padding:30px 8px}.panel h3{font-size:16px;color:#005638}.panel svg{width:100%;height:auto}
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
