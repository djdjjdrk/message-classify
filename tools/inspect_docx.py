# -*- coding: utf-8 -*-
import sys
from docx import Document
from docx.shared import Pt

path = sys.argv[1]
doc = Document(path)
print("=== SECTIONS ===")
for s in doc.sections:
    print("page", s.page_width, s.page_height, "margins", s.left_margin, s.right_margin, s.top_margin, s.bottom_margin)

print("=== BODY ===")
for i, p in enumerate(doc.paragraphs):
    txt = p.text
    runs = len(p.runs)
    sizes = {r.font.size.pt if r.font.size else None for r in p.runs}
    bold = {r.bold for r in p.runs}
    style = p.style.name
    print(f"[{i}] style={style!r} align={p.alignment} runs={runs} sz={sizes} bold={bold} | {txt!r}")

print("=== TABLES ===", len(doc.tables))
for ti, t in enumerate(doc.tables):
    print(f"--- table {ti}: rows={len(t.rows)} cols={len(t.columns)}")
    for ri, row in enumerate(t.rows):
        cells = [c.text.replace("\n", "\\n") for c in row.cells]
        print(f"  r{ri}: {cells}")
