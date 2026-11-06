import json
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

root=Path('C:/clara-system')
data=json.loads((root/'tmp/word_question_content.json').read_text())
d=Document()
s=d.sections[0]
s.page_width=Inches(8.2677);s.page_height=Inches(11.6929)
s.top_margin=s.bottom_margin=Inches(.85)
s.left_margin=s.right_margin=Inches(1)
for name in ['Normal','Title','Heading 1','Heading 2']:
 st=d.styles[name];st.font.name='Times New Roman';st.font.color.rgb=RGBColor.from_string('203443' if name.startswith('Heading') else '000000')
d.styles['Normal'].font.size=Pt(12)
d.styles['Normal'].paragraph_format.space_after=Pt(8)
d.styles['Normal'].paragraph_format.line_spacing=1.15
for name in ['Normal','Title','Heading 1','Heading 2']:
 st=d.styles[name]
 fonts=st.element.get_or_add_rPr().find(qn('w:rFonts'))
 for attr in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme']:
  fonts.attrib.pop(qn('w:'+attr),None)
 for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
d.styles['Title'].font.size=Pt(28)
d.styles['Heading 1'].font.size=Pt(17)
d.styles['Heading 2'].font.size=Pt(13)
h=s.header.paragraphs[0];h.text='CLARA | Cardiovascular Question Bank';h.runs[0].font.size=Pt(9)
f=s.footer.paragraphs[0];f.text='CLARA Research Documentation | Reviewer copy     '
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');f._p.append(field)
for r in f.runs:r.font.size=Pt(9)

def p(text='',bold=False,keep=False):
 x=d.add_paragraph();x.add_run(text).bold=bold
 x.paragraph_format.keep_with_next=keep
 return x

d.add_paragraph('CLARA Cardiovascular Clinical Question Bank',style='Title')
p('100 Selected Questions from the NLM Clinical Questions Collection',True)
p('Research and Development Evaluation Material')
p('Editable reviewer copy | 6 November 2026')
p('Paste each CLARA-generated answer beneath its question, then ask the reviewer to enter one answer relevancy score in the box provided. The response paragraphs expand normally in Word.')
d.add_heading('Answer relevancy rating instructions',level=1)
p('Read each question alongside its corresponding CLARA-generated answer. Rate how directly and completely the answer addresses the question and whether it includes unnecessary content.')
ratings=['Does not address the question.','Mostly unrelated; addresses only a small part.','Partially addresses the question, with substantial omissions.','Directly addresses most of the question, with minor omissions.','Directly and fully addresses the question without unnecessary content.']
for i,t in enumerate(ratings,1):
 x=p();x.add_run(f'{i}: ').bold=True;x.add_run(t)
p('This researcher-developed scale measures clinician-rated answer relevancy separately from automated RAGAS Answer Relevancy. Review the rubric before scoring. Record clinical inaccuracies, safety concerns, and reasons for scores separately using the question number; relevance does not establish medical correctness.')
d.add_page_break()
scope=data['scope']
status=next(t for t in scope if t.startswith('Reference answers and evaluation scores'))
scope.remove(status);scope.insert(scope.index('Evaluation status')+1,status)
for i,t in enumerate(scope):
 if i==0:d.add_heading(t,level=1)
 elif t in ['Selection and presentation','Evaluation status','Source citation']:d.add_heading(t,level=2)
 else:p(t.replace('on the preceding page','at the beginning of this document'))
d.add_page_break()
sections={1:'Hypertension: diagnosis, treatment, and monitoring',26:'Heart failure: assessment and treatment',41:'Lipids and cardiovascular prevention',51:'Coronary disease, chest pain, and cardiac testing',63:'Arrhythmias and conduction disorders',75:'Stroke, transient ischemic attack, and carotid disease',83:'Anticoagulation and thromboembolic disease',93:'Peripheral vascular disease and broader cardiovascular assessment'}
for n,q,label in data['items']:
 if n in sections:d.add_heading(sections[n],level=1)
 p(f'{n}. {q}',True,True)
 x=p(label,keep=True)
 for r in x.runs:r.font.size=Pt(10)
 p('CLARA response:',True,True)
 x=p();x.paragraph_format.keep_with_next=True
 x.paragraph_format.space_after=Pt(12)
 x=p('Clinician answer relevancy score (1-5):   ')
 r=x.add_run('\u00a0\u00a0\u00a0\u00a0\u00a0')
 border=OxmlElement('w:bdr');border.set(qn('w:val'),'single');border.set(qn('w:sz'),'6');border.set(qn('w:space'),'4');border.set(qn('w:color'),'203443')
 r._r.get_or_add_rPr().append(border)
 x.paragraph_format.space_after=Pt(22)
d.add_page_break()
for i,t in enumerate(data['references']):
 if i==0:d.add_heading(t,level=1)
 elif t in ['Attribution and traceability','Validation statement - complete after review']:d.add_heading(t,level=2)
 elif t.startswith('Validated by:'):p(t,True,True)
 elif t.startswith('Team Manager'):
  p('Team Manager',keep=True)
  p('New Marketlink Pharmaceutical Corporation',keep=True)
  p('Health & Wellness Segment',keep=True)
 else:p(t)
out=root/'output/docx/CLARA_100_Cardiovascular_Questions_Reviewer.docx'
out.parent.mkdir(exist_ok=True,parents=True)
d.save(out)
check=Document(out)
texts=[x.text for x in check.paragraphs]
assert texts.count('CLARA response:')==100
assert sum(t.startswith('Clinician answer relevancy score') for t in texts)==100
assert all(f'{n}. {q}' in texts for n,q,_ in data['items'])
print(out)
