# -*- coding: utf-8 -*-
"""打印模板第四部分单元格中各类段落的 pPr/rPr，便于复刻格式。"""
import re
import sys
from docx import Document
from lxml import etree

path = r"C:\Users\zz\Desktop\py实验报告\Word_template_stable.docx"
doc = Document(path)
cell = doc.tables[3].rows[0].cells[0]


def clean(el):
    s = etree.tostring(el, encoding="unicode")
    s = re.sub(r'\s+xmlns:[a-zA-Z0-9]+="[^"]*"', "", s)
    s = re.sub(r"\s+", " ", s)
    return s


for i, p in enumerate(cell.paragraphs):
    print(f"### para {i} style={p.style.name!r} text={p.text[:30]!r}")
    ppr = p._p.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr")
    print("  pPr:", clean(ppr) if ppr is not None else None)
    for j, r in enumerate(p.runs):
        rpr = r._r.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
        print(f"  run{j}:", clean(rpr) if rpr is not None else None, "|", repr(r.text[:20]))
