from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.core.config import settings
from app.models import ReportVersion, Task


def render_report_pdf(task: Task, report: ReportVersion) -> Path:
    output_dir = settings.storage_root / "tasks" / str(task.id) / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"report_v{report.version_no}.pdf"
    font_name = "OpinionChinese"
    font_candidates = [
        (Path("/System/Library/Fonts/STHeiti Medium.ttc"), 1),
        (Path("/System/Library/Fonts/Supplemental/Songti.ttc"), 0),
        (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 0),
    ]
    font_match = next(((path, index) for path, index in font_candidates if path.exists()), None)
    if font_match:
        try:
            font_path, subfont_index = font_match
            pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=subfont_index))
        except Exception:
            font_name = "Helvetica"
    else:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(
        str(output), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm,
        title=f"{task.name}-舆情分析报告",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleCN", parent=styles["Title"], fontName=font_name, fontSize=25, leading=38, textColor=colors.HexColor("#092759"), alignment=TA_CENTER)
    subtitle = ParagraphStyle("SubtitleCN", parent=styles["Normal"], fontName=font_name, fontSize=11, leading=20, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER)
    body = ParagraphStyle("BodyCN", parent=styles["BodyText"], fontName=font_name, fontSize=10.5, leading=19, textColor=colors.HexColor("#24344d"), spaceAfter=5)
    heading = ParagraphStyle("HeadingCN", parent=body, fontSize=15, leading=26, textColor=colors.HexColor("#0f62bd"), spaceBefore=10, spaceAfter=8)
    story = [
        Spacer(1, 58 * mm),
        Paragraph("舆情智析平台", subtitle),
        Spacer(1, 10 * mm),
        Paragraph(task.name, title),
        Paragraph("舆情分析与处置报告", title),
        Spacer(1, 18 * mm),
        Paragraph(f"报告版本：V{report.version_no}", subtitle),
        Paragraph("AI生成 · 人工已审核" if report.is_manually_edited else "AI智能生成", subtitle),
        Paragraph(report.created_at.strftime("%Y年%m月%d日 %H:%M"), subtitle),
        PageBreak(),
    ]
    for line in report.content.splitlines():
        text = line.strip()
        if not text:
            story.append(Spacer(1, 3 * mm))
        elif text.startswith(("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、")) or text.startswith("#"):
            story.append(Paragraph(escape(text.lstrip("# ")), heading))
        else:
            story.append(Paragraph(escape(text), body))

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"第 {document.page} 页")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output
