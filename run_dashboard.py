"""Eastern Gaels app launcher with integrated Demographics Report."""
import os
import threading
from http.server import ThreadingHTTPServer
import eastern_gaels_v7 as app
from demographics_report import render

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
