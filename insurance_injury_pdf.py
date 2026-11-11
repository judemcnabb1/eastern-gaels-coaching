"""Downloadable committee insurance and injury report; read-only demographics snapshot."""
import io, os
from datetime import date
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, String, Ellipse

GREEN=colors.HexColor('#075438')
GOLD=colors.HexColor('#d9a62c')

def build_pdf(demo, base):
    groups=[('Senior Adult Ladies','Senior ladies'),('Senior Adult Mens','Senior men')]
    records=[(team,m) for team,key in groups for m in demo.get('adult_payment',{}).get(key,[]) if str(m.get('name','')).strip()]
    def status(m): return str(m.get('private_medical_insurance','')).strip().upper()
    yes=sum(status(m)=='YES' for _,m in records)
    no=sum(status(m)=='NO' for _,m in records)
    unknown=len(records)-yes-no
    known=yes+no
    def amount(v):
        try: return float(str(v or '').replace('€','').replace(',','').replace('EUR','').strip())
        except (ValueError,TypeError,OverflowError): return None
    claims=[]
    for team,m in records:
        injury=m.get('injury',{}) or {}
        vals=[str(injury.get(k,'') or '').strip() for k in ('description','date','claim_amount','shortfall_amount')]
        if any(vals): claims.append((team,str(m.get('name','')).strip(),*vals))
    claim_sum=sum(amount(r[4]) or 0 for r in claims)
    short_sum=sum(amount(r[5]) or 0 for r in claims)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='EGTitle',parent=styles['Title'],textColor=GREEN,fontSize=20,leading=25,spaceAfter=13))
    styles.add(ParagraphStyle(name='EGHeading',parent=styles['Heading2'],textColor=GREEN,spaceBefore=17,spaceAfter=9))
    styles.add(ParagraphStyle(name='EGSmall',parent=styles['Normal'],fontSize=8.3,leading=12))
    styles.add(ParagraphStyle(name='EGCell',parent=styles['Normal'],fontSize=7,leading=10))
    styles.add(ParagraphStyle(name='EGCellWhite',parent=styles['EGCell'],textColor=colors.white,fontName='Helvetica-Bold'))
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=35,bottomMargin=42,title='Eastern Gaels Insurance and Injury Claims Report')
    story=[]
    cover=os.path.join(base,'Insurance and Injury Claims.png')
    if os.path.isfile(cover):
        image=Image(cover)
        maxw,maxh=doc.width,620
        scale=min(maxw/image.imageWidth,maxh/image.imageHeight)
        image.drawWidth=image.imageWidth*scale
        image.drawHeight=image.imageHeight*scale
        story.extend([Spacer(1,50),image,PageBreak()])
    story.append(Paragraph('Insurance, Injury Claims &amp; Financial Exposure',styles['EGTitle']))
    story.append(Paragraph('Eastern Gaels | Senior Adult Ladies &amp; Senior Adult Mens | '+date.today().strftime('%d %B %Y'),styles['EGSmall']))
    story.append(Spacer(1,14))
    story.append(Paragraph('Insurance coverage overview',styles['EGHeading']))
    data=[['Senior players','Private cover: Yes','Private cover: No','Unknown'],[str(len(records)),str(yes),str(no),str(unknown)]]
    table=Table(data,colWidths=[doc.width/4]*4,rowHeights=[24,30])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ALIGN',(0,0),(-1,-1),'CENTER'),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#eef5f0')),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(table)
    exposure=100*no/known if known else 0
    story.append(Spacer(1,12))
    story.append(Paragraph(('Potential exposure: %.1f%% of recorded Yes/No responses report no private medical cover.'%exposure) if known else 'Potential exposure: awaiting recorded Yes/No responses.',styles['Normal']))
    story.append(Paragraph('Unknown responses are excluded from this percentage. This is not a probability of injury or confirmed club liability.',styles['EGSmall']))
    # Centred, vector insurance graphic on the first report-content page.
    # The approved cover remains a separate front page when available.
    story.append(Spacer(1,13))
    if known:
        from reportlab.graphics.charts.piecharts import Pie
        graphic=Drawing(360,205)
        pie=Pie()
        pie.x=99;pie.y=26;pie.width=162;pie.height=145
        pie.data=[yes,no]
        pie.labels=['','']
        pie.startAngle=90
        pie.slices[0].fillColor=colors.HexColor('#08764a')
        pie.slices[1].fillColor=colors.HexColor('#d58c22')
        pie.slices[0].strokeColor=colors.white
        pie.slices[1].strokeColor=colors.white
        pie.slices[0].strokeWidth=1.5
        pie.slices[1].strokeWidth=1.5
        graphic.add(Ellipse(180,31,81,19,fillColor=colors.HexColor('#c5d8cd'),strokeColor=None))
        graphic.add(pie)
        graphic.add(String(180,192,'PRIVATE MEDICAL INSURANCE',textAnchor='middle',fontName='Helvetica-Bold',fontSize=11,fillColor=GREEN))
        graphic.add(String(180,7,'Private cover: %d  |  No private cover: %d'%(yes,no),textAnchor='middle',fontSize=10,fillColor=GREEN))
        graphic.hAlign='CENTER'
        story.append(graphic)
    else:
        story.append(Paragraph('Insurance chart: awaiting Yes/No responses.',styles['EGSmall']))
    story.append(Spacer(1,6))
    story.append(Paragraph('Insurance status by team',styles['EGHeading']))
    rows=[['Team','Players','Yes','No','Unknown','Exposure']]
    for team,key in groups:
        subset=[m for t,m in records if t==team]
        y=sum(status(m)=='YES' for m in subset); n=sum(status(m)=='NO' for m in subset); k=y+n
        rows.append([team,str(len(subset)),str(y),str(n),str(len(subset)-k),('%.1f%%'%(100*n/k)) if k else 'N/A'])
    t=Table(rows,colWidths=[155,65,52,52,60,doc.width-384],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#eef5f0')]),('BOTTOMPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),9)]))
    story.append(t)
    story.append(Paragraph('Injury claims and recorded shortfalls',styles['EGHeading']))
    story.append(Paragraph('Players with injury records: %d | Recorded claims: EUR %s | Recorded shortfalls: EUR %s'%(len(claims),format(claim_sum,',.2f'),format(short_sum,',.2f')),styles['Normal']))
    story.append(Paragraph('Player injury claim register',styles['EGHeading']))
    def cell(v):return Paragraph(escape(str(v or 'Not recorded')),styles['EGCell'])
    def money(v):
        a=amount(v)
        return ('EUR '+format(a,',.2f')) if a is not None else 'Not recorded'
    claim_rows=[[Paragraph(escape(x),styles['EGCellWhite']) for x in ['Team','Player','Injury description','Date','Claim amount','Shortfall']]]
    for team,name,desc,dt,claim,short in claims:
        claim_rows.append([cell(x) for x in [team,name,desc,dt,money(claim),money(short)]])
    if len(claim_rows)==1:claim_rows.append([cell('No injury claims recorded'),'','','','',''])
    widths=[86,80,120,66,76,doc.width-428]
    t=Table(claim_rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#eef5f0')]),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),1,GOLD)]))
    story.append(t)
    story.append(Paragraph('Committee interpretation and data notes',styles['EGHeading']))
    for note in [
        'Coverage exposure is the share of recorded No responses; it does not establish club liability.',
        'Recorded shortfalls are potential exposure indicators, not automatic obligations to pay. GAA injury benefit and private insurance terms apply.',
        'Missing insurance responses are counted separately; missing claim amounts are excluded from totals, not assumed to be zero.',
        'Source: Eastern Gaels demographics workbook, Senior Adult Ladies and Senior Adult Mens. Figures reflect the latest successful dashboard synchronisation.',
        'Confidential: contains player personal and health-related information. Share only with authorised club personnel.'
    ]:story.append(Paragraph('• '+escape(note),styles['EGSmall']))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(GREEN)
        canvas.drawString(36,25,'EASTERN GAELS | CONFIDENTIAL COMMITTEE REPORT')
        canvas.drawRightString(A4[0]-36,25,'Page %d'%doc.page)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()
