from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from pathlib import Path


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
    def content_hash(self):
        locator = (
            f"{self.page_start}|{self.sheet_name}|{self.cell_range}|"
            f"{self.paragraph_start}|{self.slide_number}"
        )
        return sha256((locator + "|" + self.raw_text).encode()).hexdigest()


class AnchorCollector:
    def __init__(self, max_anchors: int, max_text_chars: int):
        self.max_anchors = max_anchors
        self.max_text_chars = max_text_chars
        self.text_chars = 0
        self.items: list[AnchorData] = []

    def add(self, anchor: AnchorData) -> None:
        next_count = len(self.items) + 1
        next_chars = self.text_chars + len(anchor.raw_text)
        if next_count > self.max_anchors:
            raise ValueError(f"Document exceeds maximum anchor count ({self.max_anchors})")
        if next_chars > self.max_text_chars:
            raise ValueError(f"Document exceeds maximum extracted text size ({self.max_text_chars})")
        self.items.append(anchor)
        self.text_chars = next_chars


def parse_xlsx(
    data: bytes,
    max_anchors: int = 20000,
    max_text_chars: int = 10_000_000,
) -> list[AnchorData]:
    import openpyxl

    workbook = openpyxl.load_workbook(
        BytesIO(data),
        data_only=False,
        read_only=True,
        keep_links=False,
    )
    collector = AnchorCollector(max_anchors, max_text_chars)
    try:
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows():
                values = [cell.value for cell in row]
                row_context = [str(value) for value in values if value is not None][:20]
                for cell in row:
                    if cell.value is None:
                        continue
                    text = str(cell.value).strip()
                    if not text:
                        continue
                    collector.add(
                        AnchorData(
                            "EXCEL_CELL",
                            text,
                            sheet_name=worksheet.title,
                            cell_range=cell.coordinate,
                            metadata={"row_context": row_context},
                        )
                    )
    finally:
        workbook.close()
    return collector.items


def parse_docx(
    data: bytes,
    max_anchors: int = 20000,
    max_text_chars: int = 10_000_000,
) -> list[AnchorData]:
    from docx import Document

    document = Document(BytesIO(data))
    collector = AnchorCollector(max_anchors, max_text_chars)
    headings: list[str] = []
    for index, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style and paragraph.style.name.startswith("Heading"):
            try:
                level = int(paragraph.style.name.split()[-1])
            except (TypeError, ValueError):
                level = 1
            headings = headings[: level - 1] + [text]
        collector.add(
            AnchorData(
                "DOCX_PARAGRAPH",
                text,
                heading_path=list(headings),
                paragraph_start=index,
            )
        )
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows):
            values = [cell.text.strip() for cell in row.cells]
            for col_index, value in enumerate(values):
                if not value:
                    continue
                collector.add(
                    AnchorData(
                        "DOCX_TABLE_CELL",
                        value,
                        metadata={
                            "table_index": table_index,
                            "row_index": row_index,
                            "column_index": col_index,
                            "row_context": values[:20],
                        },
                    )
                )
    return collector.items


def parse_pdf(
    data: bytes,
    max_anchors: int = 20000,
    max_text_chars: int = 10_000_000,
) -> list[AnchorData]:
    import fitz

    document = fitz.open(stream=data, filetype="pdf")
    collector = AnchorCollector(max_anchors, max_text_chars)
    try:
        for page_number, page in enumerate(document):
            for block in page.get_text("blocks"):
                text = (block[4] or "").strip()
                if not text:
                    continue
                collector.add(
                    AnchorData(
                        "PDF_TEXT",
                        text,
                        page_start=page_number + 1,
                        page_end=page_number + 1,
                        bbox={
                            "x0": block[0],
                            "y0": block[1],
                            "x1": block[2],
                            "y1": block[3],
                        },
                    )
                )
    finally:
        document.close()
    return collector.items


def parse_pptx(
    data: bytes,
    max_anchors: int = 20000,
    max_text_chars: int = 10_000_000,
) -> list[AnchorData]:
    from pptx import Presentation

    presentation = Presentation(BytesIO(data))
    collector = AnchorCollector(max_anchors, max_text_chars)
    for slide_number, slide in enumerate(presentation.slides, start=1):
        for shape_index, shape in enumerate(slide.shapes):
            text = getattr(shape, "text", "")
            text = text.strip() if text else ""
            if not text:
                continue
            collector.add(
                AnchorData(
                    "PPTX_TEXT",
                    text,
                    slide_number=slide_number,
                    metadata={"shape_index": shape_index},
                )
            )
    return collector.items


def parse_plain_text(
    data: bytes,
    max_anchors: int = 20000,
    max_text_chars: int = 10_000_000,
) -> list[AnchorData]:
    text = data.decode("utf-8-sig", errors="replace")
    collector = AnchorCollector(max_anchors, max_text_chars)
    for index, line in enumerate(text.splitlines()):
        value = line.strip()
        if value:
            collector.add(AnchorData("PLAIN_TEXT", value, paragraph_start=index))
    if not collector.items and text:
        collector.add(AnchorData("PLAIN_TEXT", text))
    return collector.items


def parse_document(
    filename: str,
    data: bytes,
    max_anchors: int = 20000,
    max_text_chars: int = 10_000_000,
) -> list[AnchorData]:
    extension = Path(filename).suffix.lower()
    kwargs = {"max_anchors": max_anchors, "max_text_chars": max_text_chars}
    if extension in {".xlsx", ".xlsm"}:
        return parse_xlsx(data, **kwargs)
    if extension == ".docx":
        return parse_docx(data, **kwargs)
    if extension == ".pdf":
        return parse_pdf(data, **kwargs)
    if extension == ".pptx":
        return parse_pptx(data, **kwargs)
    if extension in {".txt", ".md", ".csv"}:
        return parse_plain_text(data, **kwargs)
    raise ValueError(f"Unsupported file type: {extension}")
