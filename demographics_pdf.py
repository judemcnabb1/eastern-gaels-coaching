"""Server-generated two-page A4 demographics PDF; no browser print engine."""
import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

GREEN = HexColor("#005638")
GOLD = HexColor("#e7b83d")
PALE = HexColor("#eaf4ee")
W, H = A4

def build_pdf(demo, base):
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    c.setTitle("Eastern Gaels Demographics Report")
    # Page 1: preserve the approved cover image, proportionally fitted inside A4.
    cover = os.path.join(base, "demographics-cover-2026.png")
    c.setFillColor(GREEN)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    if os.path.exists(cover):
        img = ImageReader(cover)
        iw, ih = img.getSize()
        scale = min(W / iw, H / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(img, (W-dw)/2, (H-dh)/2, dw, dh, mask="auto")
    c.showPage()
    # Page 2: all content drawn within a fixed safe inset.
    margin = 35
    width = W - 2 * margin
    c.setFillColor(GREEN)
    c.rect(0, H-15, W, 15, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 19)
    c.drawString(margin, H-52, "DEMOGRAPHICS REPORT")
    growth = demo.get("growth", {}) or {}
    years = sorted((str(k) for k in growth if str(k).isdigit()), key=int)
    year = years[-1] if years else "Current"
    c.setFillColor(GOLD)
    c.drawRightString(W-margin, H-52, year)
    c.setFont("Helvetica", 9)
    c.setFillColor(GREEN)
    c.drawString(margin, H-69, "Our People  |  Our Club  |  Our Community")
    ages = demo.get("age_totals", {}) or {}
    juvenile = sum(int(v or 0) for v in ages.values())
    adult = sum(int(demo.get(k,0) or 0) for k in ("senior_adult_non_playing_count","senior_adult_ladies_count","senior_adult_mens_count"))
    metrics = [("TOTAL ACTIVE MEMBERS",juvenile+adult),("JUVENILE PLAYERS",juvenile),("ADULT MEMBERS",adult),("AGE GROUPS",len(ages))]
    gap = 8
    tw = (width-3*gap)/4
    for i,(name,value) in enumerate(metrics):
        x=margin+i*(tw+gap)
        c.setFillColor(PALE);c.roundRect(x,H-147,tw,59,7,fill=1,stroke=0)
        c.setFillColor(GOLD);c.rect(x,H-91,tw,3,fill=1,stroke=0)
        c.setFillColor(GREEN);c.setFont("Helvetica-Bold",23);c.drawCentredString(x+tw/2,H-119,str(value))
        c.setFont("Helvetica-Bold",6.8);c.drawCentredString(x+tw/2,H-136,name)
    # Six self-contained chart panels in a strict two-column, three-row grid.
    panel_gap=12
    pw=(width-panel_gap)/2
    ph=185
    tops=[H-169,H-169-ph-panel_gap,H-169-2*(ph+panel_gap)]
    def panel(col,row,title):
        x=margin+col*(pw+panel_gap);top=tops[row];bottom=top-ph
        c.setStrokeColor(HexColor("#d6e6db"));c.setFillColor(HexColor("#fbfdfb"))
        c.roundRect(x,bottom,pw,ph,6,stroke=1,fill=1)
        c.setFillColor(GREEN);c.setFont("Helvetica-Bold",10)
        c.drawString(x+10,top-18,title)
        return x,bottom,top
    def bars(items,x,y,top,limit=8):
        items=list(items)[:limit]
        if not items:return
        mx=max(1,max(v for _,v in items))
        chartw=pw-25
        bw=min(28,(chartw-10)/len(items)*.62)
        spacing=chartw/len(items)
        for i,(label,value) in enumerate(items):
            bx=x+13+i*spacing+(spacing-bw)/2
            bh=90*value/mx
            c.setFillColor(GREEN if i%2==0 else GOLD)
            c.roundRect(bx,y+40,bw,bh,2,fill=1,stroke=0)
            c.setFillColor(GREEN);c.setFont("Helvetica-Bold",7)
            c.drawCentredString(bx+bw/2,y+43+bh,str(value))
            c.setFont("Helvetica",6.2)
            c.drawCentredString(bx+bw/2,y+29,str(label)[:10])
    def breakdown(items,x,y,top):
        total=sum(v for _,v in items)
        for i,(name,value) in enumerate(items[:7]):
            yy=top-42-i*18
            c.setFillColor(GREEN if i%2==0 else GOLD)
            c.circle(x+17,yy+2,4,stroke=0,fill=1)
            c.setFillColor(GREEN);c.setFont("Helvetica",8)
            c.drawString(x+29,yy,str(name)[:26])
            c.setFont("Helvetica-Bold",8)
            pct=f" ({value/total:.0%})" if total else ""
            c.drawRightString(x+pw-12,yy,str(value)+pct)
        c.setFont("Helvetica-Bold",8);c.drawString(x+12,y+12,f"Total: {total}")
    def pie(items,x,y,top):
        import math
        items=[(name,int(value)) for name,value in items if int(value)>0]
        total=sum(value for _,value in items)
        if not total:
            return
        palette=[GREEN,GOLD,HexColor("#16a66a"),HexColor("#66b6a2"),HexColor("#b6811e"),HexColor("#7c9690")]
        cx=x+pw/2
        cy=top-74
        radius=44
        # Offset lower slices slightly to recreate the original 3D pie appearance.
        start=90
        for i,(name,value) in enumerate(items):
            extent=360*value/total
            c.setFillColor(HexColor("#365d4c") if i%2==0 else HexColor("#b28a28"))
            c.wedge(cx-radius,cy-radius-5,cx+radius,cy+radius-5,start,start+extent,stroke=0,fill=1)
            start+=extent
        start=90
        for i,(name,value) in enumerate(items):
            extent=360*value/total
            c.setFillColor(palette[i%len(palette)])
            c.wedge(cx-radius,cy-radius,cx+radius,cy+radius,start,start+extent,stroke=1,fill=1)
            angle=math.radians(start+extent/2)
            lx=cx+radius*.64*math.cos(angle)
            ly=cy+radius*.64*math.sin(angle)
            if extent>20:
                c.setFillColor(HexColor("#ffffff"))
                c.setFont("Helvetica-Bold",6)
                c.drawCentredString(lx,ly,f"{value/total:.0%}")
            start+=extent
        # Compact original-style area legend beneath the pie.
        c.setFillColor(GREEN);c.setFont("Helvetica-Bold",7)
        c.drawString(x+10,y+49,"AREA LEGEND")
        count=min(len(items),4)
        for i,(name,value) in enumerate(items[:count]):
            yy=y+36-i*10
            c.setFillColor(palette[i%len(palette)])
            c.rect(x+10,yy-1,6,6,stroke=0,fill=1)
            c.setFillColor(GREEN);c.setFont("Helvetica",6.6)
            c.drawString(x+20,yy,str(name)[:24])
            c.setFont("Helvetica-Bold",6.6)
            c.drawRightString(x+pw-9,yy,f"{value} ({value/total:.1%})")
        c.setFont("Helvetica-Bold",7)
        c.drawString(x+10,y+4,f"Total: {total} players")
    gender=demo.get("juvenile_gender",{}) or {}
    x,y,t=panel(0,0,"Juvenile boys & girls")
    pie([("Boys",int(gender.get("Boys",0) or 0)),("Girls",int(gender.get("Girls",0) or 0))],x,y,t)
    x,y,t=panel(1,0,"Senior adult men & women")
    pie([("Senior men",int(demo.get("senior_adult_mens_count",0) or 0)),("Senior women",int(demo.get("senior_adult_ladies_count",0) or 0))],x,y,t)
    x,y,t=panel(0,1,"Players by age group")
    bars([(str(k),int(v or 0)) for k,v in ages.items()],x,y,t,limit=12)
    x,y,t=panel(1,1,"Juvenile membership trend")
    bars([(str(k),int(growth[k] or 0)) for k in years],x,y,t)
    x,y,t=panel(0,2,"Parish catchment")
    parish=demo.get("catchment",{}) or {}
    pie(sorted([(str(k),int(v or 0)) for k,v in parish.items()],key=lambda p:-p[1]),x,y,t)
    x,y,t=panel(1,2,"Schools represented")
    schools=demo.get("school_totals",{}) or {}
    breakdown(sorted([(str(k),int(v or 0)) for k,v in schools.items()],key=lambda p:-p[1]),x,y,t)
    c.setFillColor(GREEN);c.setFont("Helvetica",7)
    c.drawString(margin,31,"Source: Eastern Gaels dashboard demographics dataset.")
    c.drawRightString(W-margin,31,"AN MHI  |  EASTERN GAELS")
    c.showPage();c.save()
    return output.getvalue()
