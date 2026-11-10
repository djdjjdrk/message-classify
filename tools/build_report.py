# -*- coding: utf-8 -*-
"""在模板第四部分填入“实验运行过程及分析”和“运行结果”，其余内容保持原样。"""

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

TEMPLATE = Path(r"C:\Users\zz\Desktop\py实验报告\Word_template_stable.docx")
OUTPUT = Path(r"C:\Users\zz\Desktop\py实验报告\校园留言分类与垃圾信息识别系统_实验报告_完成版.docx")
FIGS = Path(__file__).resolve().parent / "figs"

CN_FONT = "宋体"
EN_FONT = "Times New Roman"
CODE_FONT = "Consolas"

PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
    "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
    "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN",
    "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing",
    "mirrorIndents", "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange",
]
TCPR_ORDER = [
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap",
    "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark", "headers", "cellIns",
    "cellDel", "cellMerge", "tcPrChange",
]
TRPR_ORDER = [
    "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter", "cantSplit",
    "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden", "ins", "del", "trPrChange",
]


def insert_ordered(parent, element, order):
    tag = element.tag.split("}")[1]
    index = order.index(tag)
    for child in list(parent):
        child_tag = child.tag.split("}")[1]
        if child_tag in order and order.index(child_tag) > index:
            child.addprevious(element)
            return element
    parent.append(element)
    return element


def style_run(run, *, size=12, bold=False, cn=CN_FONT, en=EN_FONT, color=None):
    if size is not None:
        run.font.size = Pt(size)
    if bold:
        run.font.bold = True
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), cn)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    if color is not None:
        run.font.color.rgb = RGBColor(*color)


def base_paragraph(cell, *, space_before=2, space_after=2, line=1.5, align=None,
                   first_indent=True, keep_next=False):
    p = cell.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line
    if first_indent:
        pf.first_line_indent = Cm(0.95)
    if align is not None:
        p.alignment = align
    if keep_next:
        pf.keep_with_next = True
    return p


def add_body(cell, text):
    p = base_paragraph(cell, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    style_run(p.add_run(text), size=12)
    return p


def add_h3(cell, text, space_before=6):
    p = base_paragraph(cell, space_before=space_before, space_after=3, keep_next=True)
    style_run(p.add_run(text), size=12, bold=True)
    return p


def add_code(cell, text):
    p = base_paragraph(cell, space_before=3, space_after=3, line=1.15,
                       first_indent=False)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.keep_together = True
    pf = p.paragraph_format
    pf.left_indent = Cm(0.6)
    pf.right_indent = Cm(0.2)
    run = p.add_run(text)
    style_run(run, size=9, cn=CN_FONT, en=CODE_FONT)
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F5F7")
    insert_ordered(ppr, shd, PPR_ORDER)
    return p


def add_caption(cell, text, *, after_figure=False):
    p = base_paragraph(cell, space_before=4 if not after_figure else 3,
                       space_after=6 if after_figure else 4,
                       first_indent=False, keep_next=not after_figure)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(p.add_run(text), size=10.5, bold=True)
    return p


def add_figure(cell, path, width_cm, caption):
    p = cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    add_caption(cell, caption, after_figure=True)


def shade_cell(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    insert_ordered(tcpr, shd, TCPR_ORDER)


def set_cell_text(cell, text, *, bold=False, size=10, align="center"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = {
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "left": WD_ALIGN_PARAGRAPH.LEFT,
    }[align]
    pf = p.paragraph_format
    pf.space_before = Pt(1)
    pf.space_after = Pt(1)
    pf.line_spacing = 1.0
    pf.first_line_indent = Cm(0)
    run = p.add_run(text)
    style_run(run, size=size, bold=bold)


def atomic_block(cell, width_cm=14.9):
    """把表格、图、代码块放进单行无边框表格，使其不跨页拆分。"""
    table = cell.add_table(rows=1, cols=1)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.columns[0].width = Cm(width_cm)
    row = table.rows[0]
    inner = row.cells[0]
    inner.width = Cm(width_cm)

    trpr = row._tr.get_or_add_trPr()
    insert_ordered(trpr, OxmlElement("w:cantSplit"), TRPR_ORDER)

    tcpr = inner._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{side}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    insert_ordered(tcpr, borders, TCPR_ORDER)

    margins = OxmlElement("w:tcMar")
    for side in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{side}")
        element.set(qn("w:w"), "0")
        element.set(qn("w:type"), "dxa")
        margins.append(element)
    insert_ordered(tcpr, margins, TCPR_ORDER)

    tail = cell.paragraphs[-1]
    if not tail.text.strip():
        tail.paragraph_format.space_before = Pt(0)
        tail.paragraph_format.space_after = Pt(0)
        tail.paragraph_format.line_spacing = Pt(2)
    return inner


def add_table(cell, spec):
    header, rows, widths = spec["header"], spec["rows"], spec["widths"]
    aligns = spec.get("aligns", ["center"] * len(header))
    add_caption(cell, spec["caption"])
    table = cell.add_table(rows=len(rows) + 1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for j, width in enumerate(widths):
        table.columns[j].width = Cm(width)
        for row in table.rows:
            row.cells[j].width = Cm(width)

    for j, text in enumerate(header):
        c = table.rows[0].cells[j]
        set_cell_text(c, text, bold=True, size=10)
        shade_cell(c, "DCE6F1")
    for i, row_values in enumerate(rows, start=1):
        for j, text in enumerate(row_values):
            set_cell_text(table.rows[i].cells[j], text, size=10, align=aligns[j])

    for i, row in enumerate(table.rows):
        trpr = row._tr.get_or_add_trPr()
        insert_ordered(trpr, OxmlElement("w:cantSplit"), TRPR_ORDER)
        if i == 0:
            insert_ordered(trpr, OxmlElement("w:tblHeader"), TRPR_ORDER)
        if i < len(table.rows) - 1:
            for cell_obj in row.cells:
                for paragraph in cell_obj.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True

    # python-docx 在表格后补了一个空段落，这里压缩掉多余行高。
    tail = cell.paragraphs[-1]
    if not tail.text.strip():
        tail.paragraph_format.space_before = Pt(0)
        tail.paragraph_format.space_after = Pt(0)
        tail.paragraph_format.line_spacing = Pt(4)
    return table


# ----------------------------- 正文内容 -----------------------------

INTRO = (
    "本实验完成校园留言分类与垃圾信息识别系统。后端采用 FastAPI 提供接口，SQLAlchemy 2.x 完成对象关系映射，"
    "业务数据保存在 MySQL 8 中；前端采用 Vue 3 与 Vite 实现页面；垃圾信息识别使用 jieba 分词、词级 TF-IDF "
    "特征和自行实现的多项式朴素贝叶斯。前端只承担交互与展示，输入校验、权限判断、预测调用、审核流转和统计"
    "口径全部由后端实现，下面以一次留言从发布到审核、统计与人工纠正的过程为主线说明运行过程。"
    "系统按前后端分离方式部署，接口统一返回 JSON 结构。"
)

SECTION_1 = [
    ("h3", "（1）系统结构与一次留言的处理流程", 26),
    ("p", "系统按职责分为前端展示层、接口层、业务服务层、数据访问层和数据库五部分，机器学习模块作为业务服务层的"
          "支撑组件单独组织，各层的文件位置与职责见表4-1，调用关系如图4-1所示。图左侧自上而下是请求方向，右侧是"
          "模型组件，业务服务层在发布、预测和重训时调用它。"),
    ("table", {
        "caption": "表4-1 各模块的职责划分",
        "header": ["层次", "主要文件", "职责"],
        "rows": [
            ["前端展示层", "frontend/src/views、components", "登录注册与四类业务页面，提交表单、展示列表、预测结果与操作提示"],
            ["接口层", "backend/app/api/*.py", "解析请求参数、注入当前用户与数据库会话、统一响应与异常处理"],
            ["业务服务层", "backend/app/service/*.py", "发布、检索、删除、审核、标注、统计的业务规则与事务"],
            ["数据模型层", "backend/app/models/*.py", "四张表的 ORM 映射、字段约束与表间关联"],
            ["机器学习模块", "backend/app/ml/*.py", "文本预处理、TF-IDF 特征、朴素贝叶斯、训练、评估与在线预测"],
            ["命令行工具", "backend/app/commands/*.py", "建库建表、数据准备、人工标注重训与迁移脚本"],
        ],
        "widths": [2.6, 4.6, 7.6],
        "aligns": ["center", "left", "left"],
    }),
    ("fig", FIGS / "fig_pipeline.png", 12.4, "图4-1 系统分层结构与模块调用关系"),
    ("p", "一次留言发布依次经过以下步骤：前端提交正文，接口层校验 JWT 令牌并取得当前用户；Pydantic 模型去除正文"
          "首尾空白后检查长度在 1 至 2000 字之间；业务服务调用 predict_text，得到预测状态、预测标签、垃圾概率、"
          "模型名和最多五个贡献词；审核规则根据预测结果决定自动通过还是保持待审核；最后在同一事务中写入留言与"
          "审核记录，返回“留言发布成功，已自动通过审核”或“留言发布成功，等待审核”。"),
    ("p", "接口层只负责参数解析、依赖注入和统一响应包装，业务规则集中在 service 层，数据库读写集中在模型层。统一"
          "异常处理器把业务异常转换为 {code, message, data} 结构：未登录返回 401，越权返回 403，参数不合法返回 422，"
          "已审核留言再次提交返回 409，数据库异常则回滚事务并返回 500。由于规则只有一份，网页、接口文档和自动化"
          "测试看到的行为一致。"),

    ("h3", "（2）数据库设计与数据持久化"),
    ("p", "数据库设计四张有业务关联的表：用户表 users、留言表 messages、标注记录表 annotation_records 和审核记录表"
          " review_records，主要字段与约束见表4-2。四张表都以 BIGINT 自增列作为主键；留言通过 author_id 关联发布者；"
          "标注与审核记录通过 message_id 关联留言，并分别通过 annotator_id、reviewer_id 关联操作人；外键统一设置为"
          " ON DELETE RESTRICT，避免删除用户时丢失历史。用户名设置唯一约束，正文用 CHECK 约束限定 1 至 2000 字，"
          "垃圾概率限定在 0 至 1 之间，标签与状态使用 ENUM 限定取值，预测依据以 JSON 保存。留言删除采用软删除，"
          "只写入 deleted_at，列表、统计和审核查询都排除已删除记录，标注与审核历史因此可以长期保留。"),
    ("table", {
        "caption": "表4-2 四张业务表及主要字段",
        "header": ["表名", "主要字段", "约束与作用"],
        "rows": [
            ["users", "id、username、nickname、password_hash、role、created_at", "username 唯一，role 取 student 或 admin，密码只保存 Argon2 哈希"],
            ["messages", "id、author_id、content、predicted_label、prediction_status、predicted_probability、prediction_explanation、manual_label、review_status、deleted_at", "外键关联用户；正文 1 至 2000 字，概率 0 至 1；预测依据存为 JSON，删除只写时间"],
            ["annotation_records", "id、message_id、annotator_id、previous_label、new_label、reason、created_at", "记录每次人工纠正的原标签、新标签与原因"],
            ["review_records", "id、message_id、reviewer_id、review_source、decision、label_snapshot、comment", "区分自动与人工审核，保存模型名、概率与阈值快照"],
        ],
        "widths": [3.7, 6.1, 5.0],
        "aligns": ["center", "left", "left"],
    }),
    ("p", "以用户表为例，id 使用 BIGINT 自增主键，username 设为唯一约束，password_hash 保存 Argon2 哈希，"
          "role 用 ENUM 限定为学生或管理员；留言表、标注表和审核表按同样的方式定义外键与 CHECK 约束。"),
    ("p", "建表由命令 python -m backend.app.commands.init_db 完成，内部调用 Base.metadata.create_all 创建缺失的表，"
          "可重复执行；加 --seed-users 参数可同时创建学生与管理员账号。服务重启后数据仍在 MySQL 中，列表与统计接口"
          "直接读取，不依赖内存状态。"),

    ("h3", "（3）文本预处理与特征提取"),
    ("p", "训练与在线预测共用 TextPreprocessor 和 tokenize_with_signals，保证两端文本处理一致，这是题目要求检查的"
          "重点之一。预处理先做 NFKC 规范化，统一全角与半角字符，去掉零宽字符等格式控制符，并把连续空白合并为一个"
          "空格；随后用 jieba 精确模式分词，过滤空白和纯标点，保留英文大小写与数字。除正常词以外，还按联系方式、"
          "收益承诺、代办服务、医疗美容、博彩充值五类规则生成内部广告信号 token（例如 __ad_money__），每类最多"
          "累加三次，使“加微信”“日赚”“扫码”这类搭配能够作为独立特征参与训练。"),
    ("code", "class TextPreprocessor:\n"
             "    def normalize(self, content: str) -> str:\n"
             "        return normalize_content(content)      # NFKC、去控制符、合并空白\n"
             "\n"
             "    def tokenize(self, content: str) -> list[str]:\n"
             "        return [\n"
             "            word for word in jieba.lcut(self.normalize(content))\n"
             "            if any(char.isalnum() for char in word)\n"
             "        ]\n"
             "\n"
             "def tokenize_with_signals(content):\n"
             "    words = tokenize(content)\n"
             "    if not words:                              # 空文本不生成信号\n"
             "        return []\n"
             "    return words + ad_signal_tokens(content)   # 五类信号，每类最多 3 个"),
    ("p", "特征采用词级 TF-IDF，min_df=2 过滤只在单条样本中出现的词，sublinear_tf 抑制长文本的词频放大，避免长"
          "留言仅凭词数多而占据更高权重。向量器只用训练集正文拟合，测试集、来源留出集和在线预测一律调用 transform，"
          "词表与 IDF 不会接触评估数据，测试结果不会因信息穿越而虚高。"),

    ("h3", "（4）训练数据划分与朴素贝叶斯训练"),
    ("p", "训练语料由三个公开来源整理而成，标签统一为 0 表示正常留言、1 表示垃圾广告或诈骗引流，各来源条数见"
          "表4-3。三个来源合并、去重并统一格式后共 4184 条。"),
    ("table", {
        "caption": "表4-3 训练语料的来源与规模",
        "header": ["数据来源", "条数", "标签", "用途"],
        "rows": [
            ["人大校园树洞（RUC 2025）", "2588", "正常 2585 / 垃圾 3", "正常留言主体"],
            ["ChineseHarm-Bench", "1500", "垃圾 1500", "广告、引流与欺诈语料"],
            ["IAD-dataset 第一部分", "96", "垃圾 96", "整体留出，做来源压力测试"],
            ["合并去重后合计", "4184", "正常 2585 / 垃圾 1599", "分组划分训练集与测试集"],
        ],
        "widths": [6.0, 1.8, 3.9, 3.1],
        "aligns": ["left", "center", "center", "left"],
    }),
    ("p", "为避免同一模板或近似重复的留言同时出现在训练集和测试集，划分前先用字符 2 至 4 gram 的 TF-IDF 余弦"
          "相似度（阈值 0.70）与序列相似度（阈值 0.90）构建近似重复组，再按固定种子 42 做分组五折，取第一折作为"
          "测试集。IAD 的 96 条广告数量少且来源独立，整体留出作为来源压力测试集，不参与训练和阈值选择。划分结果"
          "为训练集 3271 条（正常 2068、垃圾 1203）、同分布测试集 817 条（正常 517、垃圾 300）。"),
    ("p", "最终模型在固定训练集之外，又从 ChineseHarm 原始语料中按规则补充 1551 条弱标注广告，并对 649 条校园交易"
          "类正常样本各额外重复两次，用来提供带“出售”“自取”“元”等词的困难负样本，训练输入共 6120 条。弱标注由"
          "关键词规则筛选，尚未逐条人工复核，属于含噪声的训练数据；固定测试集与 IAD 留出集都没有参与这次扩充。"),
    ("p", "分类器是自行实现的多项式朴素贝叶斯，不调用 sklearn 的分类器。训练时按类别累加特征权重，使用 α=1 的"
          "拉普拉斯平滑计算词条件概率，并把两类先验都设为 0.5，使模型不依赖训练集中垃圾样本的比例。"),
    ("code", "for label in (0, 1):\n"
             "    counts = np.asarray(X[y == label].sum(axis=0)).ravel()\n"
             "    self.feature_count_[label] = counts\n"
             "    total = counts.sum() + self.alpha * word_count\n"
             "    for word_index in range(word_count):\n"
             "        numerator = counts[word_index] + self.alpha\n"
             "        self.feature_log_prob_[label, word_index] = (\n"
             "            math.log(numerator) - math.log(total)\n"
             "        )"),
    ("p", "预测时把先验对数与各词的条件概率对数加权求和，减去两类最大得分后再归一化，避免长文本连乘下溢。分类"
          "阈值在训练集内部按模板组切出的 965 条验证数据上选择：先要求垃圾精确率不低于 95%，再取 F2 最大者，最终"
          "阈值为 0.36，对应验证集精确率 97.69%、召回率 99.64%、F2 为 0.9924。选择完成后，固定测试集与 IAD 留出集"
          "只用于最终评估。"),

    ("h3", "（5）在线预测与自动审核"),
    ("p", "在线预测由 predict_text 完成。函数加载 pipeline.joblib 中保存的向量器、分类器和模型名，对正文执行与训练"
          "相同的分词和信号生成后只调用 transform；得到垃圾概率后与阈值 0.36 比较得到标签，再按“TF-IDF 权重乘以"
          "两类对数条件概率之差”的绝对值排序，输出支持当前判断的五个贡献词。内部信号 token 只参与打分，不作为可读"
          "依据展示。"),
    ("code", "row = vectorizer.transform([content]).tocsr()\n"
             "if row.nnz == 0:                      # 词表未覆盖任何词\n"
             "    return PredictionResult(status=\"no_features\", model_name=model_name)\n"
             "probability = float(model.predict_proba(row)[0, 1])\n"
             "label = int(probability >= model.threshold)"),
    ("p", "边界输入按三种情况处理：正文只有空白时由参数校验直接拒绝；部分词不在词表中时由 transform 忽略未见部分，"
          "仍按已有词计算；全部词都不在词表中时返回 no_features，不给出猜测标签，直接进入人工审核。这一约定同样"
          "适用于测试集和线上请求，离线评估时全未知词按类别先验预测并单独记录条数，两种口径分别说明。"),
    ("p", "留言发布后是否公开由审核规则决定：只有预测成功、标签为正常、垃圾概率不超过 0.25 三条同时满足时才自动"
          "通过，并写入一条 review_source 为 automatic 的审核记录，快照保存模型名、垃圾概率和阈值，便于事后核对；"
          "其余留言保持待审核，由管理员通过或驳回，驳回必须填写原因。分类阈值 0.36 与自动通过上限 0.25 分开设置，"
          "前者是模型判定垃圾的界限，后者为直接公开留出更严格的余量。"),

    ("h3", "（6）人工纠正、统计与重新训练"),
    ("p", "管理员可以在分类标注页给出人工标签并填写原因。标注服务把标签写入 manual_label，同时新增一条标注记录，"
          "保存原标签（没有人工标签时取模型预测）、新标签、操作人与原因；标签与历史在同一事务中提交，任一写入失败"
          "就一起回滚。重复提交相同人工标签不会重复写历史，但首次确认模型结果时仍会记录一条从模型标签到人工标签的"
          "变更。人工标签只纠正分类，不改变审核状态，也不覆盖模型原始预测，因此页面可以同时显示“模型判为垃圾、人工"
          "判为正常”这样的对照。"),
    ("p", "统计接口在一次聚合查询中返回留言总数、正常数、垃圾数、未分类数以及待审核、通过、驳回数量，统一排除软"
          "删除记录。分类统计优先采用人工标签，其次采用预测成功的模型标签，预测失败或缺少模型的留言计入未分类，"
          "两个维度的合计都等于总数，避免页面之间数字对不上。"),
    ("p", "人工标签还可通过 retrain_from_annotations 命令用于离线重训：脚本读取人工标签，按规范化正文去重，排除与"
          "固定测试集、来源留出集关联的正文、模板和近似重复组，用同一测试集同时评估原模型与新模型，新模型和纠正"
          "快照保存在独立目录，不自动替换线上模型。只有积累到足够的人工纠正数据，重训结果才具有比较意义。"),

    ("h3", "（7）前端页面"),
    ("p", "前端使用 Vue 3 与 Vue Router 构建单页应用，路由采用 hash 模式，包含登录、注册、留言管理、分类标注、"
          "留言审核和留言统计六个页面，其中后三个页面由路由守卫按角色限制，后端接口再校验一次身份与权限。请求模块"
          "统一携带令牌并处理 401 与超时重试，页面负责列表展示、表单提交和操作提示，同时显示预测标签、垃圾概率与"
          "贡献词。前端不含业务规则，只负责调用与展示，这里不再展开。"),
]

SECTION_2 = [
    ("h3", "（1）运行环境与启动过程"),
    ("p", "实验在 Windows 11、Python 3.12.13、MySQL 8、Node.js 24 环境下完成，后端依赖由 uv 管理，数据库连接、"
          "JWT 密钥和模型路径通过 .env 配置。启动分为安装依赖、初始化数据库、启动服务三步，前端安装依赖后以 Vite "
          "开发服务器启动。"),
    ("code", "uv sync --project backend --group dev\n"
             "uv run --project backend python -m backend.app.commands.init_db --seed-users\n"
             "uv run --project backend uvicorn backend.app.main:app --reload --port 8000\n"
             "cd frontend; npm ci; npm run dev          # http://127.0.0.1:5173"),
    ("p", "本次实际启动后端时的控制台输出如下，服务启动后持续运行，直到手动结束进程。"),
    ("code", "INFO:     Started server process [36916]\n"
             "INFO:     Waiting for application startup.\n"
             "INFO:     Application startup complete.\n"
             "INFO:     Uvicorn running on http://127.0.0.1:8123 (Press CTRL+C to quit)"),
    ("p", "随后访问 /openapi.json 与 /docs 均返回 200，接口文档列出认证、留言、分类标注、审核、统计共 6 组 14 个接口；"
          "未携带令牌访问 /api/v1/messages/public 返回 401 和统一错误体 "
          "{\"code\":401,\"message\":\"登录已失效，请重新登录\",\"data\":null}，说明鉴权在业务查询之前生效。"),
    ("h3", "（2）接口运行结果"),
    ("p", "主要接口的运行情况见表4-4，各接口均在自动化测试中以真实请求调用，返回码与业务规则一致。"),
    ("table", {
        "caption": "表4-4 主要接口与运行情况",
        "header": ["接口", "功能", "运行情况"],
        "rows": [
            ["POST /auth/register、/auth/login", "注册账号、登录并签发 JWT", "成功返回用户信息与令牌，重复账号 409，密码错误 401"],
            ["POST /messages", "发布留言、调用模型并自动审核", "正常且概率不超过 0.25 自动通过，其余待审核"],
            ["GET /messages/public", "公开留言列表", "只返回审核通过且未删除的留言"],
            ["DELETE /messages/{id}", "删除留言", "本人或管理员可删，重复删除返回 404"],
            ["POST /reviews/messages/{id}", "人工通过或驳回", "驳回必须填写原因，重复审核返回 409"],
            ["POST /classification/messages/{id}/annotations", "人工标注", "写入标签与历史，重复标签不重复写"],
            ["GET /statistics", "数量、类别与审核统计", "两个维度合计均等于总数"],
        ],
        "widths": [4.9, 4.3, 5.6],
        "aligns": ["left", "left", "left"],
    }),
    ("p", "公开列表经过“审核通过”和“未删除”两次过滤，被驳回的广告和已删除的留言都不会出现在前台；统计接口排除"
          "软删除记录，因此删除留言后总数、类别分布与审核数量同时减少，三个页面的数字保持一致。"),
    ("h3", "（3）单条留言预测结果"),
    ("p", "用保存的 campus_spam_final_v1 模型对 6 条自拟文本调用 predict_text，实际输出见表4-5，垃圾概率保留两位"
          "小数，贡献词只列前三个。"),
    ("table", {
        "caption": "表4-5 单条文本的预测结果",
        "header": ["编号", "输入正文", "预测", "垃圾概率", "主要贡献词"],
        "rows": [
            ["1", "请问图书馆今晚几点关门？想去看书。", "正常", "0.01", "请问、图书馆、几点"],
            ["2", "有没有人一起拼车去高铁站，周日下午三点出发。", "正常", "0.03", "拼车、周日、出发"],
            ["3", "出一本高等数学教材，九成新，30 元，信息楼自取。", "正常", "0.06", "教材、一本、自取"],
            ["4", "兼职刷单日赚三百，加微信 13800000000 详聊。", "垃圾", "0.99", "兼职、赚、刷"],
            ["5", "低价代发各类广告，扫码进群领取名额。", "垃圾", "0.99", "代发、广告、扫码"],
            ["6", "zxqv 8492 hjkl", "无特征", "—", "返回 no_features"],
        ],
        "widths": [1.2, 6.4, 1.8, 1.8, 3.6],
        "aligns": ["center", "left", "center", "center", "left"],
    }),
    ("p", "三条正常留言的垃圾概率都在 0.06 以下，两条广告接近 0.99，区分明显。二手教材属于校园交易，正文含“出”"
          "“自取”“30 元”等容易被误判的表达，实际仍判为正常，贡献词“教材”“一本”“自取”都支持正常类别，说明困难"
          "负样本起了作用。随机字母输入返回 no_features；空白正文在参数校验阶段被拒绝，提示“留言内容不能为空”。"
          "垃圾概率是后验输出，未经校准，只能用于排序和阈值比较，不能当作真实正确率。"),
    ("h3", "（4）模型评估结果"),
    ("p", "最终模型在固定测试集和 IAD 来源压力测试集上的指标见表4-6，混淆矩阵见图4-2。两组评估都直接加载保存的"
          "模型与向量器，不重新训练，测试样本不参与词表拟合和阈值选择。"),
    ("table", {
        "caption": "表4-6 两种评估口径的指标",
        "header": ["评估口径", "样本数", "准确率", "平衡准确率", "垃圾精确率", "垃圾召回率", "垃圾 F1"],
        "rows": [
            ["同分布测试集", "817", "98.16%", "98.55%", "95.24%", "100.00%", "97.56%"],
            ["IAD 来源压力测试集", "613", "94.29%", "88.13%", "83.52%", "79.17%", "81.28%"],
        ],
        "widths": [3.0, 1.5, 1.8, 2.2, 2.2, 2.2, 1.7],
        "aligns": ["left", "center", "center", "center", "center", "center", "center"],
    }),
    ("fig", FIGS / "fig_confusion.png", 13.2, "图4-2 两种评估口径的混淆矩阵"),
    ("p", "同分布测试中 300 条垃圾信息全部被判为垃圾，召回率 100%；15 条正常留言被误判为垃圾，因此垃圾精确率为"
          " 95.24%，正常召回率为 97.10%，准确率 98.16%，平衡准确率 98.55%。IAD 来源压力测试使用同一批 517 条正常"
          "留言与整体留出的 96 条 IAD 广告，广告检出 76 条、漏判 20 条，召回率降到 79.17%，垃圾精确率 83.52%，"
          "平衡准确率 88.13%，比同分布测试低 10.42 个百分点。"),
    ("p", "两组评估共享 517 条正常留言，指标不能合并计算，也不能当作完全独立的双类别外部测试。来源压力测试反映"
          "广告来源与表达风格变化时的表现，其中 20.83% 的广告被漏判，说明模型对未见过的广告写法仍不稳定；同分布"
          "测试的召回达到 100%，则说明在训练语料覆盖的写法上，这些广告都被识别了出来。"),
    ("h3", "（5）自动化测试结果"),
    ("p", "后端使用 pytest 在内存 SQLite 上运行单元与接口测试，测试开始前替换数据库连接、JWT 密钥和模型路径，"
          "因此不依赖本地 MySQL 与模型文件；前端使用 Node.js 内置测试运行器验证请求封装、分页、统计刷新和分类"
          "展示逻辑。本次完整执行的输出如下。"),
    ("code", "$ python -m pytest -q\n"
             "........................................................................ [ 86%]\n"
             "............................................                             [100%]\n"
             "332 passed, 1 warning in 43.32s\n"
             "\n"
             "$ node --test tests/*.test.js\n"
             "tests 22\n"
             "pass 22\n"
             "fail 0"),
    ("table", {
        "caption": "表4-7 自动化测试的覆盖情况",
        "header": ["测试模块", "代表性用例", "结果"],
        "rows": [
            ["认证与权限", "注册重名、密码错误、无令牌访问、非管理员访问", "通过"],
            ["留言管理", "发布长度边界、空正文、分页、关键词检索、软删除", "通过"],
            ["分类标注", "首次标注、重复标注、标注历史、无效标签", "通过"],
            ["审核", "自动通过阈值、人工通过、驳回必填原因、重复审核", "通过"],
            ["统计", "排除软删除、人工标签优先、维度合计", "通过"],
            ["模型处理", "模型缺失、全未知词、预测异常、阈值比较", "通过"],
            ["前端逻辑", "请求封装与重试、分页、统计刷新、分类展示", "通过"],
        ],
        "widths": [2.8, 9.0, 3.0],
        "aligns": ["center", "left", "center"],
    }),
    ("p", "332 项后端测试覆盖参数校验、权限、事务回滚、软删除、重复审核冲突、模型缺失与预测异常等分支，22 项前端"
          "测试覆盖请求重试、分页与统计的竞态处理；唯一警告来自 Starlette 测试客户端对 httpx 的弃用提示，不影响"
          "测试结果。"),
    ("h3", "（6）结果分析与改进方向"),
    ("p", "同分布测试准确率 98.16%，但不能直接理解为真实校园场景的准确率。正常留言主要来自校园树洞，垃圾信息来自"
          "公开广告语料，两类文本在来源、长度和用词上差异明显，模型容易学到来源风格而不是垃圾意图。划分阶段已经"
          "按模板和近似重复组分隔，训练与测试的精确正文、模板组交叉均为 0，但仅靠去重无法消除来源偏差；IAD 广告"
          "整体留出后召回率降到 79.17%，就是来源变化带来的直接损失。"),
    ("p", "15 条正常留言被误判为垃圾，属于边界样本，可能包含“兼职”“免费”“出售”等正常语境下也会出现的词；系统把"
          "自动通过条件收紧到垃圾概率不超过 0.25，这些样本会留在待审核列表由管理员判断，不会直接公开。被漏判的"
          " 20 条 IAD 广告则会进入公开列表或待审核，需要人工纠正后再训练。分类阈值 0.36 以精确率优先、F2 最大选出，"
          "调低阈值可以提高召回率但会增加误判，调高则相反，实际部署时应按漏判与误判的代价重新权衡。"),
    ("p", "后续可以收集真实校园留言并逐条人工复核，替换目前由规则筛选的弱标注数据；在词特征之外加入字符 n-gram，"
          "缓解未登录词与变形写法的问题；利用人工纠正记录定期重训，并在同一测试集上比较新旧模型的准确率、平衡"
          "准确率与 F1；对垃圾概率做校准，使页面展示的数值更接近真实出错比例。当前模型只作为辅助判断，留言是否"
          "公开最终仍由审核规则和管理员决定。"),
]


def main():
    doc = Document(TEMPLATE)
    cell = doc.tables[3].rows[0].cells[0]

    # 保留“3、心得体会”标题和黄色提示段落，其余段落与表格清空。
    keep_heading = None
    keep_placeholder = None
    for p in cell.paragraphs:
        if p.text.strip() == "3、心得体会":
            keep_heading = deepcopy(p._p)
        elif "写课程和实验报告的心得体会" in p.text:
            keep_placeholder = deepcopy(p._p)

    tc = cell._tc
    for child in list(tc):
        if child.tag in (qn("w:p"), qn("w:tbl")):
            tc.remove(child)

    # 一级、二级标题按模板原有样式创建。
    p = cell.add_paragraph()
    p.style = doc.styles["报告一级标题"]
    style_run(p.add_run("四、实验结果及分析"), size=None, bold=True, cn="黑体")

    p = cell.add_paragraph()
    p.style = doc.styles["报告二级标题"]
    p.add_run("1、实验运行过程及分析")

    add_body(cell, INTRO)
    for block in SECTION_1:
        kind = block[0]
        if kind == "p":
            add_body(cell, block[1])
        elif kind == "h3":
            add_h3(cell, block[1], block[2] if len(block) > 2 else False)
        elif kind == "code":
            add_code(cell, block[1])
        elif kind == "table":
            add_table(cell, block[1])
        elif kind == "fig":
            add_figure(cell, block[1], block[2], block[3])

    p = cell.add_paragraph()
    p.style = doc.styles["报告二级标题（2字符）"]
    p.add_run(" 2、运行结果")
    for block in SECTION_2:
        kind = block[0]
        if kind == "p":
            add_body(cell, block[1])
        elif kind == "h3":
            add_h3(cell, block[1], block[2] if len(block) > 2 else False)
        elif kind == "code":
            add_code(cell, block[1])
        elif kind == "table":
            add_table(cell, block[1])
        elif kind == "fig":
            add_figure(cell, block[1], block[2], block[3])

    if keep_heading is not None:
        tc.append(keep_heading)
    if keep_placeholder is not None:
        tc.append(keep_placeholder)

    doc.save(OUTPUT)
    print("saved", OUTPUT)


if __name__ == "__main__":
    main()
