"""Eastern Gaels app launcher with integrated Demographics Report."""
import os
import threading
from http.server import ThreadingHTTPServer
import eastern_gaels_v7 as app
from demographics_report import render
from demographics_pdf import build_pdf
from demographics_styled_pdf import build_styled_pdf
from schools_report import summary as schools_summary, render as render_schools, pdf as schools_pdf
from compliance_report import render as render_compliance, pdf as compliance_pdf
from dashboard_preview import render as render_dashboard_preview
from paid_membership_pdf import build_pdf as build_paid_membership_pdf

_original_page = app.page

def page_with_reports(title, body, user=None):
    if title == "Dashboard" and user:
        body = '<div class="actions"><a class="btn" href="/reports/demographics">Open Demographics Report →</a> <a class="btn" href="/reports/schools">Open Schools Demographics Report →</a> <a class="btn" href="/reports/compliance">Open Compliance Report →</a></div>' + body
    if title == 'Reports' and user:
        body = '<div class="actions"><a class="btn" href="/reports/demographics">Open Demographics Report →</a> <a class="btn" href="/reports/schools">Open Schools Demographics Report →</a> <a class="btn" href="/reports/compliance">Open Compliance Report →</a></div>' + body
    if title == 'Compliance' and user:
        # Display-only compliance centre: retain original charts and certificate upload forms.
        centre = render_dashboard_preview(app.COACHING.get('coaches', {}), app.compliance_records())
        marker = '<div class="card"><h3>Google Drive certificates</h3>'
        if marker in body:
            body = body.replace(marker, centre + '<h2>Certificate Management</h2>' + marker, 1)
    html = _original_page(title, body, user)
    if user:
        html = html.replace('<span>Reports</span></a>', '<span>Reports Centre</span></a>')
        html = html.replace('<span>Schools Schedule</span></a>', '<span>Schools Schedule</span></a><a href="/schools-coaching"><i>▦</i><span>Schools Coaching</span></a>', 1)
        # Dashboard 2.0: CSS-only shell refresh. Does not alter page logic or stored records.
        if title not in ('Demographics Report', 'Schools Demographics Report', 'Compliance Report'):
            html = html.replace('</head>', '<link rel="stylesheet" href="/dashboard-refresh.css?v=1"></head>', 1)
        # Compliance Centre is now on the main Compliance page; no preview sidebar link.
    return html

app.page = page_with_reports

class ReportHandler(app.H):
    def do_GET(self):
        path = app.urlparse(self.path).path
        report_assets = {
            '/report-schools-approved-cover.png': ('Eastern_Gaels_Schools_Demographics_Approved_Cover.png', 'image/png'),
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
        if path == '/dashboard-refresh.css':
            filename = os.path.join(app.BASE, 'dashboard_refresh.css')
            if not os.path.isfile(filename):
                return self.send_error(404)
            with open(filename, 'rb') as stream:
                data = stream.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/css; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=300')
            self.end_headers()
            self.wfile.write(data)
            return
        if path == '/compliance-cover.png':
            import mimetypes
            image_path = os.path.join(app.BASE, 'compliance-cover.png')
            if not os.path.isfile(image_path):
                return self.send_error(404)
            with open(image_path, 'rb') as stream:
                image_bytes = stream.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(image_bytes)))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(image_bytes)
            return
        if path == '/reports/paid-membership.pdf':
            user = self.need()
            if not user:
                return
            try:
                content = build_paid_membership_pdf(app.DEMO, app.BASE)
            except Exception as exc:
                self.send_error(503, 'Paid membership PDF unavailable: ' + str(exc)[:120])
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', 'attachment; filename="Eastern-Gaels-Paid-Membership-2026.pdf"')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
            return
        if path == '/reports/paid-membership':
            user = self.need()
            if not user:
                return
            from html import escape
            from demographics_report import catchment_pie
            demo = app.DEMO
            juvenile = demo.get('players_by_age', {})
            adults = demo.get('adult_payment', {})
            age_keys = sorted(juvenile, key=lambda v: (13 if str(v).strip().upper() == 'U1' else int(v[1:]) if v[1:].isdigit() else 999, str(v)))
            groups = [(('U13' if str(name).strip().upper() == 'U1' else name), juvenile[name]) for name in age_keys] + list(adults.items())
            members = [m for _, group in groups for m in group]
            paid = sum(m.get('paid') == 'YES' for m in members)
            unpaid = sum(m.get('paid') == 'NO' for m in members)
            unknown = len(members) - paid - unpaid
            known = paid + unpaid
            rate = round(100 * paid / known, 1) if known else 0
            cards = []
            for name, group in groups:
                yes = sum(m.get('paid') == 'YES' for m in group)
                no = sum(m.get('paid') == 'NO' for m in group)
                other = len(group) - yes - no
                total = len(group)
                yp = yes * 100 / total if total else 0
                np = (yes + no) * 100 / total if total else 0
                names = ''.join('<li>' + escape(str(m.get('name') or 'Name not recorded')) + '</li>' for m in group if m.get('paid') == 'NO')
                names = '<ul>' + names + '</ul>' if names else '<p class="pm-clear">No unpaid members recorded</p>'
                cards.append(f'<article class="pm-card"><h3>{escape(str(name))}</h3><div class="pm-card-body"><div class="pm-demographic-pie">{catchment_pie({"Paid":yes,"Not paid":no,"Not recorded":other})}</div></div><h4>Names not paid ({no})</h4>{names}</article>')
            content = f"""<style>
            .pm-report{{max-width:1220px;margin:15px auto 60px}}.pm-report h2{{font-size:32px;color:#064b34;margin:6px 0}}.pm-lead{{color:#5e7267;font-size:15px}}
            .pm-stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}}.pm-stat{{background:linear-gradient(145deg,#fff,#e8f3e9);border:1px solid #d4e6d9;border-radius:19px;padding:22px;box-shadow:0 11px 0 #bfd5c6,0 18px 28px #103e2626,inset 0 2px 1px #fff}}.pm-stat strong{{display:block;font-size:33px;color:#075a38}}.pm-stat span{{color:#5d7066;font-weight:650}}
            .pm-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.pm-card{{background:linear-gradient(155deg,#ffffff,#f1f8f2);border:1px solid #d1e3d6;border-radius:20px;padding:22px;box-shadow:0 9px 0 #c3d8ca,0 20px 32px #103e2624,inset 0 2px 1px white;margin-bottom:10px}}.pm-card h3{{font-size:20px;color:#075438;border-bottom:2px solid #f0c54b;padding-bottom:12px}}.pm-card h4{{margin:22px 0 8px;color:#203d2d}}.pm-card-body{{display:flex;align-items:center;gap:30px;flex-wrap:wrap}}.pm-pie{{width:170px;height:170px;flex:none;border-radius:50%;display:grid;place-items:center;box-shadow:0 10px 22px #0c3a221c}}.pm-pie>span{{width:102px;height:102px;border-radius:50%;background:white;display:flex;flex-direction:column;justify-content:center;align-items:center;font-size:29px;font-weight:850;color:#075438}}.pm-pie small{{font-size:11px;font-weight:500;color:#69766e}}.pm-numbers{{display:grid;gap:13px}}.pm-numbers b:nth-child(1){{color:#11834d}}.pm-numbers b:nth-child(2){{color:#a66b13}}.pm-numbers b:nth-child(3){{color:#6e7d76}}.pm-demographic-pie{{width:100%;max-width:460px;margin:auto}}.pm-demographic-pie .catchment-pie-layout{{display:flex;flex-direction:row;align-items:center;gap:14px}}.pm-demographic-pie .catchment-pie-layout svg{{width:52%;max-width:220px;filter:drop-shadow(0 8px 5px #003e2b35);transform:scaleY(.84)}}.pm-demographic-pie .catchment-pie-key{{flex:1;font-size:12px}}.pm-demographic-pie .catchment-legend-row{{display:flex;align-items:center;gap:7px;padding:6px 0;border-bottom:1px solid #e1ebe5}}.pm-demographic-pie .catchment-swatch{{width:12px;height:12px;border-radius:3px;flex:none}}.pm-demographic-pie .catchment-area{{flex:1}}.pm-demographic-pie .catchment-legend-heading{{font-weight:900;color:#075438}}.pm-demographic-pie .catchment-total{{margin-top:10px;font-weight:800}}.pm-card ul{{columns:2;padding-left:22px;line-height:1.9}}.pm-clear{{color:#11834d}}.pm-key{{display:flex;gap:20px;flex-wrap:wrap;margin:18px 0}}.pm-key span:before{{content:"";display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:7px;background:var(--c)}}@media(max-width:900px){{.pm-grid{{grid-template-columns:1fr}}.pm-stats{{grid-template-columns:repeat(2,1fr)}}}}@media print{{.sidebar,header,.pm-back{{display:none!important}}main{{margin:0!important}}.pm-card{{break-inside:avoid}}}}
            </style><section class="pm-report"><a class="pm-back" href="/reports">← Reports Centre</a> &nbsp; <a class="btn" href="/reports/paid-membership.pdf">⬇ Download PDF</a><p class="pm-lead">EASTERN GAELS · MEMBERSHIP REPORT</p><h2>Paid Membership Report</h2><p class="pm-lead">Payment status across imported active age-group, senior and non-playing membership records.</p>
            <div class="pm-stats"><div class="pm-stat"><strong>{len(members)}</strong><span>Total member records</span></div><div class="pm-stat"><strong>{paid}</strong><span>Paid members</span></div><div class="pm-stat"><strong>{unpaid}</strong><span>Not paid</span></div><div class="pm-stat"><strong>{rate}%</strong><span>Paid of recorded YES/NO statuses</span></div></div>
            <div class="pm-key"><span style="--c:#11834d">Paid</span><span style="--c:#e8a63b">Not paid</span><span style="--c:#cbd5d1">Not recorded</span></div>
            <p class="pm-lead">{unknown} records have no confirmed YES/NO status and are not classified as unpaid. Figures are counts of imported member records, not euro amounts.</p>
            <div class="pm-grid">{''.join(cards)}</div></section>"""
            return self.out(app.page('Paid Membership Report', content, user))
        if path == '/reports':
            user = self.need()
            if not user:
                return
            content = """<style>
            .eg-report-hub{max-width:1120px;margin:25px auto 50px;text-align:center}
            .eg-report-hub h2{font-size:34px;color:#064b34;margin:12px 0}
            .eg-report-hub p{color:#617568;font-size:15px}
            .eg-report-tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin:35px 0}
            .eg-report-tile{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:310px;padding:30px 18px;background:#fff;border:1px solid #d9e8df;border-top:7px solid #e6b62e;border-radius:20px;text-decoration:none;color:#074b34;box-shadow:0 12px 32px #103e2614;transition:transform .2s,box-shadow .2s}
            .eg-report-tile:hover{transform:translateY(-6px);box-shadow:0 18px 40px #103e2626}
            .eg-report-icon{width:105px;height:105px;border-radius:26px;display:grid;place-items:center;background:linear-gradient(135deg,#e3f7e9,#f8f1d9);font-size:55px;margin-bottom:25px}
            .eg-report-tile strong{font-size:21px;line-height:1.3}
            .eg-report-tile small{font-size:13px;color:#60756b;margin-top:12px}
            @media(max-width:900px){.eg-report-tiles{grid-template-columns:1fr}.eg-report-tile{min-height:230px}}
            </style><section class="eg-report-hub"><p>EASTERN GAELS · REPORTING</p><h2>Reports Centre</h2><p>Choose a report to explore the latest imported club data.</p>
            <div class="eg-report-tiles">
            <a class="eg-report-tile" href="/reports/demographics"><span class="eg-report-icon" aria-hidden="true">◉</span><strong>Demographics Report</strong><small>Club membership and population insights</small></a>
            <a class="eg-report-tile" href="/reports/schools"><span class="eg-report-icon" aria-hidden="true">▦</span><strong>Schools Demographics Report</strong><small>Schools and coaching programme insights</small></a>
            <a class="eg-report-tile" href="/reports/compliance"><span class="eg-report-icon" aria-hidden="true">✓</span><strong>Compliance Report</strong><small>Garda Vetting and Safeguarding</small></a>
            <a class="eg-report-tile" href="/reports/paid-membership"><span class="eg-report-icon" aria-hidden="true">€</span><strong>Paid Membership 2026</strong><small>Payment status by age group and unpaid member names</small></a>
            </div></section>"""
            return self.out(app.page('Reports Centre', content, user))
        if path == '/dashboard-preview':
            user = self.need()
            if not user:
                return
            return self.out(app.page('Dashboard Preview', render_dashboard_preview(app.COACHING.get('coaches', {}), app.compliance_records()), user))
        if path in ('/reports/compliance', '/reports/compliance.pdf'):
            user = self.need()
            if not user:
                return
            coaches = app.COACHING.get('coaches', {})
            records = app.compliance_records()
            if path.endswith('.pdf'):
                try:
                    content = compliance_pdf(coaches, records, app.BASE)
                except Exception as exc:
                    self.send_error(503, 'Compliance PDF unavailable: ' + str(exc)[:140])
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition', 'attachment; filename="Eastern-Gaels-Compliance-Report.pdf"')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(content)
                return
            return self.out(app.page('Compliance Report', render_compliance(coaches, records).replace('<article class="compliance-report"><div class="report-tools"><a class="btn" href="/reports">Back to Reports</a> <a class="btn" href="/reports/compliance.pdf">Download PDF</a></div>', '<article class="compliance-report">').replace('<section class="compliance-cover approved-compliance-cover">', '<div class="report-tools" style="max-width:900px;margin:14px auto;display:flex;gap:12px;justify-content:flex-start"><a class="btn" href="/reports">← Return to Reports</a><a class="btn" href="/reports/compliance.pdf">⬇ Download PDF</a></div><section class="compliance-cover approved-compliance-cover">'), user))
        if path in ('/reports/schools', '/reports/schools/styled.pdf'):
            user = self.need()
            if not user:
                return
            c = app.dbc()
            try:
                where, args = self.vis(user)
                rows = c.execute('select * from sessions ' + where + ' order by date,start', args).fetchall()
            finally:
                c.close()
            data = schools_summary(rows)
            if path.endswith('.pdf'):
                try:
                    content = schools_pdf(data, app.BASE, app.DEMO.get("school_totals", {}), sum(int(v or 0) for v in app.DEMO.get("age_totals", {}).values()))
                except Exception as exc:
                    self.send_error(503, 'Schools PDF unavailable: ' + str(exc)[:140])
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition', 'attachment; filename="Eastern-Gaels-Schools-Demographics-2026-2027.pdf"')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(content)
                return
            return self.out(app.page('Schools Demographics Report', render_schools(data, app.DEMO.get("school_totals", {}), sum(int(v or 0) for v in app.DEMO.get("age_totals", {}).values())), user))
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
