# -*- coding: utf-8 -*-
"""对比模板与成稿：确认除第四部分外内容未改动，并检查成稿结构。"""
from docx import Document

TEMPLATE = r"C:\Users\zz\Desktop\py实验报告\Word_template_stable.docx"
OUTPUT = r"C:\Users\zz\Desktop\py实验报告\校园留言分类与垃圾信息识别系统_实验报告（按评分表）.docx"

tpl = Document(TEMPLATE)
out = Document(OUTPUT)

# 1. 正文段落（封面、标题页）逐段比较
tpl_paras = [p.text for p in tpl.paragraphs]
out_paras = [p.text for p in out.paragraphs]
print("正文段落数 模板/成稿:", len(tpl_paras), len(out_paras))
print("正文字段完全一致:", tpl_paras == out_paras)
if tpl_paras != out_paras:
    for i, (a, b) in enumerate(zip(tpl_paras, out_paras)):
        if a != b:
            print("差异段落", i, repr(a[:40]), repr(b[:40]))

# 2. 前三张表比较（班级表、实验题目表、实验内容表）
for i in range(3):
    a = [[c.text for c in r.cells] for r in tpl.tables[i].rows]
    b = [[c.text for c in r.cells] for r in out.tables[i].rows]
    print(f"表{i} 一致:", a == b)

# 3. 第四部分结构
cell = out.tables[3].rows[0].cells[0]
print("四部分段落数:", len(cell.paragraphs))
print("四部分内表格数:", len(cell.tables))
print("首段:", repr(cell.paragraphs[0].text), "样式:", cell.paragraphs[0].style.name)
print("图片数:", len(out.inline_shapes))
texts = [p.text for p in cell.paragraphs]
for key in ["四、实验结果及分析", "1、实验运行过程及分析", "2、运行结果", "3、心得体会"]:
    print(key, "出现次数:", sum(1 for t in texts if t.strip() == key))
placeholder = [p for p in cell.paragraphs if "写课程和实验报告的心得体会" in p.text]
print("黄色提示保留:", len(placeholder) == 1,
      "高亮:", placeholder[0].runs[0].font.highlight_color if placeholder else None)
print("最后两段:", repr(texts[-2:]))

# 4. 字数统计（第四部分）
body_text = "".join(t for t in texts)
print("四部分正文/代码合计字符数:", len(body_text))
print("表格字符数:", sum(len(c.text) for t in cell.tables for r in t.rows for c in r.cells))
