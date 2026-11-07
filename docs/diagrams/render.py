"""Render the repository's explanatory diagrams as SVG, PNG and vector PDF.

Optional authoring dependencies: Pillow and ReportLab. Not required for proof/test reproduction.
The diagrams encode logical assumptions, not validated deployment guarantees.
"""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont
import math

ROOT = Path(__file__).resolve().parent
W = 1200


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


class Diagram:
    def __init__(self, height, title):
        self.image = Image.new("RGB", (W, height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img"><title>{escape(title)}</title><rect width="100%" height="100%" fill="white"/>']

    def text(self, x, y, text, size=22, bold=False, color="#142c43", center=False):
        anchor = "mm" if center else "lm"
        self.draw.text((x, y), text, font=font(size, bold), fill=color, anchor=anchor)
        self.svg.append(f'<text x="{x}" y="{y}" dominant-baseline="middle" text-anchor="{"middle" if center else "start"}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{"700" if bold else "400"}" fill="{color}">{escape(text)}</text>')

    def rect(self, x, y, w, h, fill="#edf4fb", stroke="#52799d", width=2):
        self.draw.rounded_rectangle((x, y, x+w, y+h), radius=14, fill=fill, outline=stroke, width=width)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def box(self, x, y, w, h, title, lines=(), fill="#edf4fb"):
        self.rect(x,y,w,h,fill)
        self.text(x+w/2,y+31,title,23,True,center=True)
        for i,line in enumerate(lines):
            self.text(x+w/2,y+64+i*27,line,20,center=True)

    def arrow(self, points, color="#52799d"):
        self.draw.line(points,fill=color,width=3)
        self.svg.append(f'<polyline points="{" ".join(str(x)+","+str(y) for x,y in points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        a,b=points[-2:]; angle=math.atan2(b[1]-a[1],b[0]-a[0]); tip=[b]
        for delta in (-0.5,0.5):
            tip.append((b[0]-14*math.cos(angle+delta),b[1]-14*math.sin(angle+delta)))
        self.draw.polygon(tip,fill=color)
        self.svg.append(f'<polygon points="{" ".join(str(x)+","+str(y) for x,y in tip)}" fill="{color}"/>')

    def save(self,name):
        (ROOT/(name+".svg")).write_text("\n".join(self.svg)+"\n</svg>\n")
        self.image.save(ROOT/(name+".png"))
        # Vector PDF for manuscript inclusion; no on-upload SVG conversion needed.
        import xml.etree.ElementTree as ET
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.lib.colors import HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for bold in (False, True):
            pdfmetrics.registerFont(TTFont("DiagramBold" if bold else "DiagramRegular", font(20, bold).path))
        height = self.image.height
        pdf = Canvas(str(ROOT/(name+".pdf")), pagesize=(W, height), invariant=1)
        pdf.setTitle(name.replace("_", " ").title())
        pdf.setAuthor("")
        for element in ET.fromstring("\n".join(self.svg)+"</svg>"):
            tag = element.tag.split("}")[-1]; a = element.attrib
            if tag == "rect":
                if a.get("width") == "100%": continue
                pdf.setFillColor(HexColor(a["fill"])); pdf.setStrokeColor(HexColor(a["stroke"]))
                pdf.setLineWidth(float(a["stroke-width"]))
                pdf.roundRect(float(a["x"]), height-float(a["y"])-float(a["height"]), float(a["width"]), float(a["height"]), float(a["rx"]), fill=1, stroke=1)
            elif tag == "text":
                size = float(a["font-size"])
                pdf.setFillColor(HexColor(a["fill"]))
                pdf.setFont("DiagramBold" if a["font-weight"] == "700" else "DiagramRegular", size)
                draw = pdf.drawCentredString if a["text-anchor"] == "middle" else pdf.drawString
                draw(float(a["x"]), height-float(a["y"])-size*0.33, element.text or "")
            elif tag in ("polygon", "polyline"):
                points = [tuple(map(float, xy.split(","))) for xy in a["points"].split()]
                path = pdf.beginPath(); path.moveTo(points[0][0], height-points[0][1])
                for x, y in points[1:]: path.lineTo(x, height-y)
                if tag == "polygon":
                    path.close(); pdf.setFillColor(HexColor(a["fill"])); pdf.drawPath(path, fill=1, stroke=0)
                else:
                    pdf.setStrokeColor(HexColor(a["stroke"])); pdf.setLineWidth(float(a["stroke-width"])); pdf.drawPath(path, fill=0, stroke=1)
        pdf.showPage(); pdf.save()


def main():
    d=Diagram(820,"TrustBound trusted-service architecture")
    d.text(40,45,"TrustBound | trusted-service research scope",32,True)
    d.text(40,82,"Conceptual architecture. Placement does not establish isolation or complete mediation.",21)
    d.box(35,230,225,100,"Flight agent",["Request proposer"])
    d.box(35,380,225,100,"Hotel agent",["Request proposer"])
    d.rect(325,140,500,485,"#f7fafc","#52799d",3)
    d.text(575,175,"TRUSTED PAYMENT SERVICE",24,True,center=True)
    d.box(360,205,430,110,"Admission + serialized fence",["Record before granting authority","A1-A3 are deployment premises"])
    d.box(360,345,430,100,"Durable journal + dispatch",["Existing rights may survive the fence"])
    d.box(360,475,430,110,"Outcome reconciliation",["Unknown outcomes stay unresolved","No inference from silence alone"])
    d.arrow([(260,280),(310,280),(310,250),(360,250)])
    d.arrow([(260,430),(300,430),(300,280),(360,280)])
    d.arrow([(575,315),(575,345)])
    d.arrow([(575,445),(575,475)])
    d.box(900,275,265,175,"Processor",["Trusted outcomes / A4","All remaining effective","rights must be represented"])
    d.arrow([(790,380),(900,380)])
    d.text(845,345,"dispatch",17,center=True)
    d.arrow([(1030,450),(1030,530),(790,530)])
    d.text(1010,495,"qualified outcomes",17,center=True)
    d.box(360,675,430,100,"Auditor / researcher",["Faithful complete export assumed / A5"],"#edf7f0")
    d.arrow([(575,585),(575,675)])
    d.text(40,660,"No agent access to",20,True)
    d.text(40,690,"service keys, host",20)
    d.text(40,720,"or journal is assumed.",20)
    d.save("architecture")

    d=Diagram(750,"Premises for exact identity-level payment closure")
    d.text(40,45,"The payment completeness boundary",32,True)
    d.text(40,83,"Arrows show logical dependencies, not automatic progress or a completion deadline.",21)
    d.box(35,135,350,150,"Fixed covered population",["Reachable mediated journal J","Admission and grants fenced","No omitted in-scope routes"])
    d.box(425,135,350,150,"All rights discharged",["R is empty at the source","Includes in-flight / recovery","An empty client queue is not enough"])
    d.box(815,135,350,150,"Truthful outcome evidence",["Every journaled identity accounted","Faithful journal export","No missing past outcome"])
    d.arrow([(210,285),(210,350),(400,350)])
    d.arrow([(600,285),(600,320),(585,320),(585,350)])
    d.box(400,350,370,120,"Execution stopped",["No permitted continuation adds","a modeled attributable effect"],"#edf7f0")
    d.arrow([(585,470),(585,540)])
    d.arrow([(990,285),(990,600),(800,600)])
    d.box(375,540,425,125,"Exact identity-level closure",["Known effect identities + stable history","Both inputs are required"],"#edf7f0")
    d.text(40,710,"Conditional model result. No claim of real-world coverage, exact amounts or independent-issuer evidence.",20)
    d.save("completeness")


if __name__ == "__main__":
    main()
