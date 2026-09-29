from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".xlsx", ".xlsm", ".docx", ".pdf", ".pptx", ".txt", ".md", ".csv",
    ".png", ".jpg", ".jpeg", ".webp",
}


@dataclass
class AnchorData:
    anchor_type: str
    raw_text: str
    page_start: int | None = None
    page_end: int | None = None
    sheet_name: str | None = None
    cell_range: str | None = None
    heading_path: list[str] | None = None
    paragraph_start: int | None = None
    slide_number: int | None = None
    bbox: dict | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        locator = (
            f"{self.anchor_type}|{self.page_start}|{self.sheet_name}|{self.cell_range}|"
            f"{self.paragraph_start}|{self.slide_number}"
        )
        return sha256((locator + "|" + self.raw_text).encode()).hexdigest()


def parse_xlsx(data: bytes) -> list[AnchorData]:
    import openpyxl

    wb = openpyxl.load_workbook(BytesIO(data), data_only=False, read_only=True)
    out: list[AnchorData] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            vals = [c.value for c in row]
            context = [str(x) for x in vals if x is not None][:20]
            for cell in row:
                if cell.value is None:
                    continue
                text = str(cell.value).strip()
                if text:
                    out.append(
                        AnchorData(
                            "EXCEL_CELL",
                            text,
                            sheet_name=ws.title,
                            cell_range=cell.coordinate,
                            metadata={"row_context": context},
                        )
                    )
    return out


def parse_docx(data: bytes) -> list[AnchorData]:
    from docx import Document

    doc = Document(BytesIO(data))
    headings: list[str] = []
    out: list[AnchorData] = []
    for index, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style and paragraph.style.name.startswith("Heading"):
            try:
                level = int(paragraph.style.name.split()[-1])
            except (TypeError, ValueError):
                level = 1
            headings = headings[: max(level - 1, 0)] + [text]
        out.append(
            AnchorData(
                "DOCX_PARAGRAPH",
                text,
                heading_path=list(headings),
                paragraph_start=index,
            )
        )
    for table_index, table in enumerate(doc.tables):
        for row_index, row in enumerate(table.rows):
            values = [cell.text.strip() for cell in row.cells]
            text = " | ".join(v for v in values if v)
            if text:
                out.append(
                    AnchorData(
                        "DOCX_TABLE_ROW",
                        text,
                        metadata={"table_index": table_index, "row_index": row_index},
                    )
                )
    return out


def parse_pdf(data: bytes) -> list[AnchorData]:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    out: list[AnchorData] = []
    for page_no, page in enumerate(doc):
        for block in page.get_text("blocks"):
            text = (block[4] or "").strip()
            if text:
                out.append(
                    AnchorData(
                        "PDF_TEXT",
                        text,
                        page_start=page_no + 1,
                        page_end=page_no + 1,
                        bbox={"x0": block[0], "y0": block[1], "x1": block[2], "y1": block[3]},
                    )
                )
    return out


def parse_pptx(data: bytes) -> list[AnchorData]:
    from pptx import Presentation

    presentation = Presentation(BytesIO(data))
    out: list[AnchorData] = []
    for slide_no, slide in enumerate(presentation.slides, start=1):
        for shape_index, shape in enumerate(slide.shapes):
            text = getattr(shape, "text", "").strip()
            if text:
                out.append(
                    AnchorData(
                        "PPTX_TEXT",
                        text,
                        slide_number=slide_no,
                        metadata={"shape_index": shape_index},
                    )
                )
            if getattr(shape, "has_table", False):
                for row_index, row in enumerate(shape.table.rows):
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        out.append(
                            AnchorData(
                                "PPTX_TABLE_ROW",
                                row_text,
                                slide_number=slide_no,
                                metadata={"shape_index": shape_index, "row_index": row_index},
                            )
                        )
    return out


def parse_document(filename: str, data: bytes) -> list[AnchorData]:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")
    if ext in {".xlsx", ".xlsm"}:
        return parse_xlsx(data)
    if ext == ".docx":
        return parse_docx(data)
    if ext == ".pdf":
        return parse_pdf(data)
    if ext == ".pptx":
        return parse_pptx(data)
    if ext in {".txt", ".md", ".csv"}:
        return [AnchorData("PLAIN_TEXT", data.decode("utf-8", errors="replace"))]
    # Native images are accepted and retained as immutable evidence/context resources.
    # They deliberately do not fabricate OCR text. A future vision skill can produce
    # derived visual anchors while preserving this original file anchor.
    return [AnchorData("IMAGE_FILE", "", metadata={"filename": filename, "requires_vision": True})]
