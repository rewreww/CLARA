from pathlib import Path
from io import BytesIO
import re
import fitz
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from xml.sax.saxutils import escape
from pypdf import PdfReader, PdfWriter

ROOT=Path(r'C:\clara-system')
source=Path(r'C:\Users\acer-\Desktop\CLARA_100_Cardiovascular_Questions_Reviewer_Copy.pdf')
out=ROOT/'output/pdf/CLARA_100_Cardiovascular_Questions_Fillable.pdf'
scratch=ROOT/'tmp/pdfs'
scratch.mkdir(exist_ok=True)
doc=fitz.open(source)
text='\n'.join(p.get_text(clip=fitz.Rect(70,70,525,790)) for p in list(doc)[4:-1])
pattern=r'(?m)^(\d+)\. (.*?)\n(Source: NLM \| NQ\d{6} \| [^\n]+)'
matches=re.findall(pattern,text,re.S)
items=[]
for number,question,label in matches:
    # Section headings precede some questions and use their own numbering.
    candidates=list(re.finditer(r'(?m)^(\d+)\. ',number+'. '+question))
    last=candidates[-1]
    combined=number+'. '+question
    items.append((int(last.group(1)),' '.join(combined[last.end():].split()),label))
assert [n for n,_,_ in items]==list(range(1,101)), [n for n,_,_ in items]
sections=[(25,'Hypertension: diagnosis, treatment, and monitoring'),(40,'Heart failure: assessment and treatment'),(50,'Lipids and cardiovascular prevention'),(62,'Coronary disease, chest pain, and cardiac testing'),(74,'Arrhythmias and conduction disorders'),(82,'Stroke, transient ischemic attack, and carotid disease'),(92,'Anticoagulation and thromboembolic disease'),(100,'Peripheral vascular disease and broader cardiovascular assessment')]
for name,file in [('TNR','times.ttf'),('TNRBold','timesbd.ttf')]:
    pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file))
ink=HexColor('#203443')
line=HexColor('#B5C2CC')
W,H=595.2756,841.8898
buffer=BytesIO()
c=canvas.Canvas(buffer,pagesize=(W,H))
style=ParagraphStyle('question',fontName='TNRBold',fontSize=13,leading=18,textColor=ink)
small=ParagraphStyle('small',fontName='TNR',fontSize=10,leading=13,textColor=ink)
def para(text,x,top,width,style):
    p=Paragraph(escape(text),style)
    _,height=p.wrap(width,H)
    p.drawOn(c,x,top-height)
    return top-height
for n,q,label in items:
    c.setFillColor(ink);c.setFont('TNR',9)
    c.drawString(72,H-43,'CLARA | Cardiovascular Question Bank')
    c.drawRightString(W-72,H-43,'Answer review worksheet')
    c.setStrokeColor(line);c.line(72,H-50,W-72,H-50)
    category=next(title for limit,title in sections if n<=limit)
    top=para(category,78,H-80,W-156,small)-18
    top=para(f'{n}. {q}',78,top,W-156,style)-12
    top=para(label,78,top,W-156,small)
    assert top>H-230
    c.setFillColor(ink);c.setFont('TNRBold',12)
    c.drawString(78,H-250,'CLARA response')
    c.setFont('TNR',10)
    c.drawString(78,H-266,'Paste the complete answer into the field below.')
    c.acroForm.textfield(name=f'clara_response_{n:03}',tooltip=f'CLARA response to question {n}',
        x=78,y=145,width=W-156,height=H-425,fontName='Times-Roman',fontSize=11,
        textColor=ink,borderColor=line,fillColor=white,borderWidth=0.8,
        forceBorder=True,fieldFlags='multiline',maxlen=20000)
    c.setFont('TNRBold',12);c.setFillColor(ink)
    c.drawString(78,115,'Clinician answer relevancy score (1-5):')
    c.acroForm.textfield(name=f'clinician_score_{n:03}',tooltip=f'Question {n}: enter one score from 1 to 5',
        x=310,y=105,width=38,height=28,fontName='Times-Roman',fontSize=15,
        textColor=ink,borderColor=ink,fillColor=white,borderWidth=0.8,forceBorder=True,maxlen=1)
    c.setFont('TNR',9);c.drawString(78,84,'Use the rubric on page 2. Check that pasted text is fully visible before printing.')
    c.setStrokeColor(line);c.line(72,51,W-72,51)
    c.setFont('TNR',9);c.drawString(72,35,'CLARA Research Documentation | Reviewer worksheet | 6 November 2026')
    c.drawRightString(W-72,35,str(n+4))
    c.showPage()
c.save();buffer.seek(0)

# Update instructions to refer to the new fields, retaining all introductory pages.
p=doc[1]
p.add_redact_annot(fitz.Rect(76,547,519,627),fill=(1,1,1));p.apply_redactions()
p.insert_font(fontname='TNR',fontfile='C:/Windows/Fonts/times.ttf')
remaining=p.insert_textbox(fitz.Rect(78,549,517,627),
    'Paste each CLARA answer into its question page and enter one score (1-5) in the '
    'clinician score box. Record reasons and any clinical inaccuracies or safety concerns '
    'in a separate review log keyed to the question number. Relevance does not establish medical correctness.',
    fontname='TNR',fontsize=12,lineheight=1.35)
assert remaining>=0
last=doc[-1]
last.add_redact_annot(fitz.Rect(490,795,527,815),fill=(1,1,1));last.apply_redactions()
last.insert_font(fontname='TNR',fontfile='C:/Windows/Fonts/times.ttf')
last.insert_textbox(fitz.Rect(490,797,523.2756,814),'105',fontname='TNR',fontsize=9,color=(32/255,52/255,67/255),align=2)
edited=BytesIO(doc.tobytes(garbage=4,deflate=True))
reader=PdfReader(edited)
writer=PdfWriter()
writer.append(reader,pages=(0,4))
writer.append(PdfReader(buffer))
writer.append(reader,pages=[len(reader.pages)-1])
writer.add_metadata({'/Title':'CLARA 100 Cardiovascular Questions - Fillable Reviewer Worksheet'})
with out.open('wb') as f:writer.write(f)

check=PdfReader(out)
fields=check.get_fields()
expected={f'{kind}_{n:03}' for n in range(1,101) for kind in ['clara_response','clinician_score']}
assert set(fields)==expected and len(check.pages)==105
widgets=[]
for p in check.pages:
    for a in p.get('/Annots',[]):
        a=a.get_object()
        if a.get('/Subtype')=='/Widget':
            widgets.append(a)
            assert a.get('/AP',{}).get('/N') is not None
            assert str(a.get('/V',''))==str(fields[a['/T']].get('/V',''))
assert len(widgets)==200
render=fitz.open(out)
for i in [1,4,28,103,104]:
    render[i].get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(str(scratch/f'fillable-page-{i+1}.png'))
for i,(n,q,label) in enumerate(items):
    actual=' '.join(render[i+4].get_text().split())
    assert q in actual and label in actual, n
print(f'Created {out}: 105 pages, 100 unchanged questions, 100 multiline response fields, 100 score fields.')
