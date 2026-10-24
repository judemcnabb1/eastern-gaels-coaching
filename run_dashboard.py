"""Eastern Gaels app launcher with integrated Demographics Report."""
import os
import threading
from http.server import ThreadingHTTPServer
import eastern_gaels_v7 as app
from demographics_report import render
from demographics_pdf import build_pdf
from demographics_styled_pdf import build_styled_pdf
from schools_report import summary as schools_summary, render as render_schools, pdf as schools_pdf

_original_page = app.page

def page_with_reports(title, body, user=None):
    if title == "Dashboard" and user:
        body = '<div class="actions"><a class="btn" href="/reports/demographics">Open Demographics Report →</a></div>' + body
    if title == 'Reports' and user:
        body = '<div class="actions"><a class="btn" href="/reports/demographics">Open Demographics Report →</a></div>' + body
    html = _original_page(title, body, user)
    if user:
        html = html.replace('<span>Reports</span></a>', '<span>Reports Centre</span></a>')
    return html

app.page = page_with_reports

class ReportHandler(app.H):
    def do_GET(self):
        path = app.urlparse(self.path).path
        report_assets = {
            '/report-pitch.png': ('EG Pitch .png', 'image/png'),
            '/report-demographics-cover.png': ('demographics-cover.png', 'image/png'),
            '/report-final-cover.webp': ('demographics-cover-final-web.webp', 'image/webp'),
            '/report-cover-2026.png': ('demographics-cover-2026.png', 'image/png'),
            '/report-eastern-gaels.jpg': ('Eastern Gaels .jpg', 'image/jpeg'),
            '/report-meath.png': ('Meath Logo.png', 'image/png'),
        }
        if path in report_assets:
            name, mime = report_assets[path]
            filename = os.path.join(app.BASE, name)
            if not os.path.isfile(filename):
                self.send_error(404, 'Report asset not yet uploaded')
                return
            with open(filename, 'rb') as stream:
                data = stream.read()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(data)
            return
        if path == '/reports/demographics/styled.pdf':
            user = self.need()
            if not user:
                return
            charts = {
                'bar': app.svg_bar_chart,
                'line': app.svg_line_area,
                'donut': app.donut_chart,
                'horizontal': app.hbar_chart,
            }
            try:
                data = build_styled_pdf(app.DEMO, charts, app.BASE)
            except Exception as exc:
                self.send_error(503, 'Styled PDF generation unavailable: ' + str(exc)[:140])
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', 'attachment; filename="Eastern-Gaels-Demographics-Styled.pdf"')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return
        if path == '/reports/demographics/download.pdf':
            user = self.need()
            if not user:
                return
            data = build_pdf(app.DEMO, app.BASE)
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', 'attachment; filename="Eastern-Gaels-Demographics-Report.pdf"')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return
        if path == '/reports/demographics/print':
            user = self.need()
            if not user:
                return
            charts = {
                'bar': app.svg_bar_chart,
                'line': app.svg_line_area,
                'donut': app.donut_chart,
                'horizontal': app.hbar_chart,
            }
            report = render(app.DEMO, charts)
            # Render in an isolated document: the dashboard shell has a fixed
            # sidebar/header and screen layout that can leak into Chrome PDF.
            isolated = """<!doctype html><html><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Eastern Gaels Demographics Report — Print</title>
            <style>
            *{box-sizing:border-box}
            html,body{margin:0;padding:0;background:#e9efeb;font-family:Arial,sans-serif}
            .report-page{margin:18px auto}
            @media print{
              @page{size:A4;margin:0}
              html,body{width:210mm!important;margin:0!important;padding:0!important;background:white!important}
              .report-tools{display:none!important}
              .report-page{display:block!important;position:relative!important;box-sizing:border-box!important;
                width:210mm!important;max-width:210mm!important;height:297mm!important;
                min-height:297mm!important;max-height:297mm!important;margin:0!important;
                padding:12mm!important;overflow:hidden!important;box-shadow:none!important;
                break-inside:avoid!important;page-break-inside:avoid!important;
                break-after:page!important;page-break-after:always!important}
              .report-page:last-of-type{break-after:auto!important;page-break-after:auto!important}
              .report-accent{height:5mm!important}
              .report-final-cover{height:calc(273mm - 5mm)!important;min-height:0!important;max-height:none!important}
              .report-final-cover img{width:100%!important;max-width:100%!important;height:auto!important}
              .report-body{width:100%!important;max-width:100%!important;overflow:hidden!important}
              .report-metrics,.report-charts{width:100%!important;max-width:100%!important}
              .report-charts{grid-template-columns:repeat(2,minmax(0,1fr))!important}
              .report-metrics{grid-template-columns:repeat(4,minmax(0,1fr))!important}
            }
            </style></head><body>""" + report.replace("</style>", "</style>" + """<style media="print">\n            @page{size:A4;margin:0!important}\n            .report-page{width:210mm!important;max-width:210mm!important;height:297mm!important;min-height:297mm!important;max-height:297mm!important;margin:0!important;padding:12mm!important;break-after:page!important;page-break-after:always!important}\n            .report-page:last-of-type{break-after:auto!important;page-break-after:auto!important}\n            .report-final-cover{height:268mm!important;min-height:0!important;max-height:268mm!important}\n            .report-final-cover img{width:100%!important;max-width:100%!important}\n            </style>""", 1) + "</body></html>"
            return self.out(isolated)
        if path == '/reports/demographics':
            user = self.need()
            if not user:
                return
            charts = {
                'bar': app.svg_bar_chart,
                'line': app.svg_line_area,
                'donut': app.donut_chart,
                'horizontal': app.hbar_chart,
            }
            return self.out(app.page('Demographics Report', render(app.DEMO, charts), user))
        if path == '/report-jersey.jpg':
            self.path = '/club-jersey.png'
        return super().do_GET()

if __name__ == '__main__':
    app.init()
    bundled = os.path.join(app.BASE, 'eastern gaels demographics (26).xlsx')
    if os.path.exists(bundled) and not os.path.exists(app.DEMO_FILE):
        try:
            fresh = app.parse_demographics_xlsx(bundled)
            integrated = fresh.pop('coaching', None)
            with open(app.DEMO_FILE, 'w', encoding='utf8') as stream:
                app.json.dump(fresh, stream, indent=2, ensure_ascii=False)
            if integrated:
                with open(app.COACH_FILE, 'w', encoding='utf8') as stream:
                    app.json.dump(integrated, stream, indent=2, ensure_ascii=False)
            app.DEMO = app.load_demo()
            app.COACHING = app.load_coaching()
        except Exception as exc:
            print('Workbook preload warning:', exc)
    if app.GOOGLE_SYNC_ENABLED:
        threading.Thread(target=app.google_sync_loop, name='google-drive-sync', daemon=True).start()
    port = int(os.environ.get('PORT', '8010'))
    print('Eastern Gaels dashboard with Demographics Report')
    ThreadingHTTPServer(('0.0.0.0', port), ReportHandler).serve_forever()
