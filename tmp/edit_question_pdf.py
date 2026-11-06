from pathlib import Path
import re
import fitz

src = Path(r'C:\Users\acer-\Desktop\CLARA_100_Cardiovascular_Questions.pdf')
out = Path(r'C:\clara-system\output\pdf\CLARA_100_Cardiovascular_Questions_Reviewer_Copy.pdf')
original = fitz.open(src)
doc = fitz.open(src)
# Duplicate the introduction's page furniture to retain the exact house style.
doc.insert_pdf(original, from_page=1, to_page=1, start_at=1)
page = doc[1]
page.add_redact_annot(fitz.Rect(65, 65, 530, 775), fill=(1, 1, 1))
page.apply_redactions()
regular = r'C:\Windows\Fonts\times.ttf'
bold = r'C:\Windows\Fonts\timesbd.ttf'
ink = (32/255, 52/255, 67/255)

def box(page, text, rect, size=12, boldface=False, color=(0,0,0)):
    name = 'CLARABold' if boldface else 'CLARARegular'
    page.insert_font(fontname=name, fontfile=bold if boldface else regular)
    spare = page.insert_textbox(fitz.Rect(*rect), text, fontname=name,
                                fontsize=size, lineheight=1.35, color=color)
    if spare < 0:
        raise ValueError(f'Text does not fit: {text[:60]} ({spare})')

box(page, 'Answer relevancy: reviewer instructions', (78, 80, 520, 110), 17, True, ink)
box(page, 'Read each predefined question alongside its corresponding CLARA-generated answer. '
    'Assign one score from 1 to 5 using the criteria below. Rate how directly and completely '
    'the answer addresses the question, and whether it includes unnecessary content.',
    (78, 120, 517, 199))
box(page, 'Five-point answer relevancy scale', (78, 215, 517, 240), 12, True)
ratings = [
    'Does not address the question.',
    'Mostly unrelated; addresses only a small part.',
    'Partially addresses the question, with substantial omissions.',
    'Directly addresses most of the question, with minor omissions.',
    'Directly and fully addresses the question without unnecessary content.',
]
for i, text in enumerate(ratings, 1):
    y = 254 + (i-1)*49
    box(page, f'{i}:', (78,y,100,y+30), 12, True)
    box(page, text, (105,y,517,y+42))
box(page, 'How to record the assessment', (78, 519, 517, 544), 12, True)
box(page, 'Record the question number, relevance score, and a brief reason in the accompanying '
    'answer-review sheet. Flag clinical inaccuracies or safety concerns separately; a relevant '
    'answer is not necessarily medically correct.', (78, 549, 517, 624))
box(page, 'This researcher-developed ordinal scale measures clinician-rated answer relevancy. '
    'It is separate from the automated RAGAS Answer Relevancy metric. The rubric should be '
    'reviewed before scoring; this document does not establish that it is a validated instrument.',
    (78, 639, 517, 716))
box(page, 'Reviewer instructions added: 6 November 2026.', (78, 735, 517, 757), 10)

# Revise the original evaluation-status paragraph without disturbing its layout.
scope = doc[2]
scope.add_redact_annot(fitz.Rect(76,453,519,544),fill=(1,1,1))
scope.apply_redactions()
box(scope, 'Reference answers and evaluation scores are not included. CLARA responses will be '
    'reviewed using the answer relevancy rubric on the preceding page. Reference answers must '
    'be prepared from the relevant guideline PDFs and reviewed separately. Validation remains '
    'pending until the reviewer completes the final sign-off. Historical question wording is '
    'retained for traceability.', (78,456,517,545), 12)

last = doc[-1]
box(last, 'Validation statement - complete after review', (78,611,517,633), 12, True, ink)
box(last, 'By signing below, I confirm that I have reviewed the submitted dataset, selected '
    'questions, and accompanying CLARA-generated answers for their stated research purpose. '
    'My validation is limited to the materials reviewed and is subject to my recorded comments '
    'and required corrections.', (78,637,517,699), 10.5)
box(last, 'Validated by: Johnrey T. Pepito', (78,700,517,721), 11, True)
box(last, 'Team Manager\nNew Marketlink Pharmaceutical Corporation\nHealth & Wellness Segment',
    (78,720,517,767), 10.5)
box(last, 'Signature: _________________________    Date: __________________',
    (78,770,517,790), 10)

# Renumber the inserted page and all subsequent pages within the existing footer.
for i in range(1,len(doc)):
    p=doc[i]
    p.add_redact_annot(fitz.Rect(500,795,527,812),fill=(1,1,1))
    p.apply_redactions()
    p.insert_font(fontname='CLARARegular',fontfile=regular)
    p.insert_textbox(fitz.Rect(490,797,523.2756,814),str(i+1),fontname='CLARARegular',fontsize=9,color=ink,align=2)

out.parent.mkdir(parents=True,exist_ok=True)
doc.save(out,garbage=4,deflate=True)
doc.close()
check=fitz.open(out)
# Compare only the body, excluding changed page numbers: all question pages identical.
for old_index in range(2,12):
    before=original[old_index].get_text(clip=fitz.Rect(65,65,530,790))
    after=check[old_index+1].get_text(clip=fitz.Rect(65,65,530,790))
    assert before==after, f'Question text changed on original page {old_index+1}'
original_ids=re.findall(r'NQ\d{6}', ''.join(p.get_text() for p in original))
new_ids=re.findall(r'NQ\d{6}', ''.join(p.get_text() for p in check))
assert original_ids==new_ids and len(set(new_ids))==100
for i in [1,2,13]:
    check[i].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(f'C:/clara-system/tmp/reviewer-page-{i+1}.png')
print(f'Saved {out}; {len(check)} pages; all 100 question IDs and question bodies preserved.')



