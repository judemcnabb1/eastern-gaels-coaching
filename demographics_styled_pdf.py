"""Render the original dashboard report HTML directly into an A4 PDF."""
import os
import re
from html import escape
from pathlib import Path

def build_styled_pdf(demo, charts, base):
    from weasyprint import HTML
    from demographics_report import render
    report = render(demo, charts)
    schools = [(str(k), int(v or 0)) for k, v in (demo.get("school_totals", {}) or {}).items()]
    schools.sort(key=lambda item: (-item[1], item[0]))
    midpoint = (len(schools) + 1) // 2
    school_columns = []
    for group in (schools[:midpoint], schools[midpoint:]):
        rows = ''.join('<div class="school-pdf-row"><span>' + escape(name) +
                       '</span><strong>' + str(count) + '</strong></div>'
                       for name, count in group)
        school_columns.append('<div class="school-pdf-col">' + rows + '</div>')
    school_html = '<div class="school-pdf-grid">' + ''.join(school_columns) + '</div>'
    pattern = r'(<section class="panel"><h3>Schools represented</h3>).*?(</section>)'
    report, replaced = re.subn(pattern, lambda m: m.group(1) + school_html + m.group(2),
                               report, count=1, flags=re.S)
    if replaced != 1:
        raise ValueError("Schools panel not found")
    # Keep the dashboard's original chart markup, SVGs, colours and typography.
    report = re.sub(r'<div class="report-tools">.*?</div>', '', report, count=1, flags=re.S)
    for url, filename in {
        '/report-cover-2026.png': 'demographics-cover-2026.png',
        '/report-eastern-gaels.jpg': 'Eastern Gaels .jpg',
        '/report-meath.png': 'Meath Logo.png',
    }.items():
        report = report.replace('src="'+url+'"', 'src="'+Path(base,filename).as_uri()+'"')
    # This stylesheet follows the report stylesheet and wins its print overrides.
    extra = """
    <style>
    @page {size:A4; margin:0}
    html,body {margin:0!important;padding:0!important;width:210mm!important;
      background:white!important;font-family:Arial,sans-serif}
    * {box-sizing:border-box!important}
    .report-tools {display:none!important}
    .report-page {display:block!important;position:relative!important;
      width:210mm!important;max-width:210mm!important;
      height:297mm!important;min-height:297mm!important;max-height:297mm!important;
      margin:0!important;padding:12mm!important;overflow:hidden!important;
      box-shadow:none!important;break-after:page!important;page-break-after:always!important}
    .report-page:last-of-type {break-after:auto!important;page-break-after:auto!important}
    .report-accent {height:5mm!important}
    .report-final-cover {height:268mm!important;min-height:0!important;max-height:268mm!important}
    .report-final-art {width:100%!important}
    .report-final-cover img {width:100%!important;max-width:100%!important;height:auto!important}
    .report-final-cover::before,.report-final-cover::after {display:none!important}
    .report-body {width:100%!important;max-width:100%!important;padding:9px 11px!important}
    .report-metrics {display:flex!important;width:100%!important;gap:6px!important}
    .report-metrics>.metric {width:25%!important;min-width:0!important}
    .report-charts {display:block!important;width:100%!important;font-size:0!important}
    .report-charts>.panel {display:inline-block!important;vertical-align:top!important;
      width:calc(50% - 4px)!important;height:204px!important;min-height:0!important;
      margin:0 4px 7px 0!important;padding:6px!important;overflow:hidden!important;
      font-size:11px!important;break-inside:avoid!important}
    .report-charts>.panel:nth-child(even) {margin-right:0!important}
    .report-heading h2 {font-size:18px!important}
    .report-heading {margin-bottom:8px!important}
    .report-mini-identity img {width:36px!important;height:44px!important}
    /* Fit the pie and every legend item side by side, not stacked off the panel bottom. */
    .catchment-pie-layout {display:flex!important;flex-direction:row!important;
      align-items:center!important;gap:7px!important;width:100%!important}
    .catchment-pie-layout svg {width:42%!important;max-width:108px!important;
      min-width:0!important;flex:0 0 42%!important;transform:none!important}
    .catchment-pie-key {width:56%!important;min-width:0!important;font-size:9px!important}
    .catchment-area {min-width:0!important;overflow-wrap:anywhere!important}
    .catchment-legend-row {gap:3px!important;font-size:9px!important}
    .catchment-swatch {width:7px!important;height:7px!important}
    .catchment-total {font-size:9px!important;padding-top:2px!important}
    .report-charts {margin-top:9px!important}
    .report-footer {margin-top:3px!important}
    /* School chart is a long horizontal-bar SVG: show the entire chart
       instead of clipping it to the fixed panel height. */
    .school-pdf-grid {display:flex!important;gap:7px!important;width:100%!important;margin-top:5px!important}
    .school-pdf-col {width:50%!important;min-width:0!important}
    .school-pdf-row {display:flex!important;justify-content:space-between!important;gap:3px!important;
      border-bottom:1px solid #e0ece5!important;padding:3px 0!important;
      min-height:14px!important;font-size:8px!important;line-height:1.1!important;color:#005638!important}
    .school-pdf-row span {overflow-wrap:anywhere!important;min-width:0!important}
    .school-pdf-row strong {flex:none!important;font-size:9px!important}
    .report-charts>.panel:last-child {overflow:hidden!important}
    .report-charts>.panel:last-child svg {width:100%!important;height:auto!important;
      max-height:155px!important;display:block!important}
    .report-charts>.panel:last-child h3 {margin-bottom:1px!important}
    .report-charts>.panel:last-child {padding:4px!important}
    .report-charts>.panel:nth-last-child(2) {padding:4px!important}
    .catchment-legend-row {padding:2px 0!important}
    .panel h3 {font-size:11px!important;margin:2px 0!important}
    .report-trend-svg,.report-3d-bars {max-height:125px!important}
    .metric {padding:6px 2px!important}
    .metric strong {font-size:25px!important}
    .metric span {font-size:9px!important}
    .report-footer {padding:8px!important;font-size:9px!important}
    </style>
    """
    html = '<!doctype html><html><head><meta charset="utf-8"></head><body>' + report + extra + '</body></html>'
    return HTML(string=html,base_url=Path(base).as_uri()+'/').write_pdf()
