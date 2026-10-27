"""Downloadable Paid Membership 2026 report built from current imported records."""
from collections import Counter
from html import escape
from io import BytesIO
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.graphics.shapes import Drawing, Wedge, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.platypus import Image

GREEN=colors.HexColor('#075438')
GOLD=colors.HexColor('#e7b83e')
ORANGE=colors.HexColor('#e8a63b')
GREY=colors.HexColor('#cbd5d1')

def build_pdf(demo, base):
    juvenile=demo.get('players_by_age', {})
    adults=demo.get('adult_payment', {})
    age_keys=sorted(juvenile, key=lambda v:(int(v[1:]) if v[1:].isdigit() else 999,str(v)))
    groups=[(('U13' if str(name).strip().upper()=='U1' else name),juvenile[name]) for name in age_keys]+list(adults.items())
    members=[m for _, group in groups for m in group]
    counts=Counter(m.get('paid') for m in members)
    paid=counts['YES']; unpaid=counts['NO']; unknown=len(members)-paid-unpaid
    known=paid+unpaid
    out=BytesIO()
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='EGTitle',parent=styles['Title'],fontSize=27,leading=34,textColor=GREEN,spaceAfter=15))
    styles.add(ParagraphStyle(name='EGSection',parent=styles['Heading2'],fontSize=17,leading=22,textColor=GREEN,spaceBefore=18,spaceAfter=10))
    styles.add(ParagraphStyle(name='EGSmall',parent=styles['BodyText'],fontSize=9,leading=13))
    styles.add(ParagraphStyle(name='EGCover',parent=styles['Title'],fontSize=34,leading=43,textColor=colors.white,alignment=TA_CENTER))
    story=[]
    # A dedicated cover sheet. Uses the approved club pitch photograph already in the app.
    photo=Path(base,'report-pitch.png')
    story.append(Spacer(1,1))
    story.append(PageBreak())
    story.append(Paragraph('Paid Membership 2026',styles['EGTitle']))
    pct=f'{100*paid/known:.1f}%' if known else 'N/A'
    summary=[['Total member records','Paid','Not paid','Not recorded'],[str(len(members)),str(paid),str(unpaid),str(unknown)]]
    t=Table(summary,colWidths=[130,100,100,110],rowHeights=[32,42])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('TEXTCOLOR',(0,0),(-1,0),colors.white),('TEXTCOLOR',(0,1),(-1,1),GREEN),('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),('FONTSIZE',(0,1),(-1,1),18),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,-1),(-1,-1),4,GOLD),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#eaf4ed'))]))
    story.append(t)
    story.append(Spacer(1,16))
    story.append(Paragraph(f'<b>{pct}</b> of members with a recorded YES/NO payment status are paid.',styles['BodyText']))
    story.append(Paragraph(f'{unknown} members have no confirmed payment status and are not counted as unpaid. These are member counts, not euro amounts.',styles['EGSmall']))
    for name,group in groups:
        cc=Counter(m.get('paid') for m in group)
        yes=cc['YES']; no=cc['NO']; other=len(group)-yes-no
        section=[Paragraph('◆  '+escape(str(name))+'  |  MEMBERSHIP STATUS',styles['EGSection'])]
        pie=Pie()
        pie.x=5;pie.y=5;pie.width=120;pie.height=120
        pie.data=[yes,no,other] if len(group) else [1]
        pie.labels=[f'{100*v/len(group):.1f}%' if v else '' for v in (yes,no,other)] if len(group) else ['']
        pie.sideLabels=False
        pie.simpleLabels=False
        pie.slices.strokeColor=colors.white
        pie.slices.strokeWidth=1.5
        for i,col in enumerate((GREEN,ORANGE,GREY)):
            if i<len(pie.data):pie.slices[i].fillColor=col
        drawing=Drawing(140,145)
        from reportlab.graphics.shapes import Ellipse
        drawing.add(Ellipse(7,0,118,17,fillColor=colors.HexColor('#d0ded5'),strokeColor=None))
        drawing.add(pie)
        details=Paragraph(f'<b>Members:</b> {len(group)}<br/><font color="#075438">Paid: {yes}</font><br/><font color="#9d6718">Not paid: {no}</font><br/>Not recorded: {other}',styles['BodyText'])
        panel=Table([[drawing,details]],colWidths=[160,290]);panel.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#eff7f1')),('BOX',(0,0),(-1,-1),1,colors.HexColor('#bed8c5')),('LEFTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]));section.append(panel)
        names=[str(m.get('name') or 'Name not recorded') for m in group if m.get('paid')=='NO']
        section.append(Paragraph('<b>Members recorded as not paid:</b>',styles['EGSmall']))
        if names:
            for i in range(0,len(names),3):
                section.append(Paragraph(' • '.join(escape(n) for n in names[i:i+3]),styles['EGSmall']))
        else:
            section.append(Paragraph('No unpaid members recorded.',styles['EGSmall']))
        story.extend(section)
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=48,bottomMargin=45,title='Eastern Gaels Paid Membership 2026')
    def draw_cover(canvas, document):
        photo=Path(base,'paid-membership-cover.png')
        if photo.exists():
            canvas.drawImage(str(photo),0,0,width=A4[0],height=A4[1],preserveAspectRatio=False,mask='auto')
        else:
            canvas.setFillColor(GREEN)
            canvas.rect(0,0,A4[0],A4[1],fill=1,stroke=0)
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold',28)
            canvas.drawCentredString(A4[0]/2,A4[1]/2,'PAID MEMBERSHIP 2026')
    doc.build(story,onFirstPage=draw_cover)
    return out.getvalue()
