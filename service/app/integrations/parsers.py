from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from pathlib import Path
@dataclass
class AnchorData:
    anchor_type:str; raw_text:str; page_start:int|None=None; page_end:int|None=None; sheet_name:str|None=None; cell_range:str|None=None; heading_path:list[str]|None=None; paragraph_start:int|None=None; slide_number:int|None=None; bbox:dict|None=None; metadata:dict=field(default_factory=dict)
    @property
    def content_hash(self):
        locator=f'{self.page_start}|{self.sheet_name}|{self.cell_range}|{self.paragraph_start}|{self.slide_number}'
        return sha256((locator+'|'+self.raw_text).encode()).hexdigest()

def parse_xlsx(data:bytes)->list[AnchorData]:
    import openpyxl
    wb=openpyxl.load_workbook(BytesIO(data),data_only=False,read_only=True)
    out=[]
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            vals=[c.value for c in row]
            for c in row:
                if c.value is None: continue
                text=str(c.value).strip()
                if not text: continue
                out.append(AnchorData('EXCEL_CELL',text,sheet_name=ws.title,cell_range=c.coordinate,metadata={'row_context':[str(x) for x in vals if x is not None][:20]}))
    return out

def parse_docx(data:bytes)->list[AnchorData]:
    from docx import Document
    doc=Document(BytesIO(data)); headings=[]; out=[]
    for i,p in enumerate(doc.paragraphs):
        text=p.text.strip()
        if not text: continue
        if p.style and p.style.name.startswith('Heading'):
            try: level=int(p.style.name.split()[-1])
            except Exception: level=1
            headings=headings[:level-1]+[text]
        out.append(AnchorData('DOCX_PARAGRAPH',text,heading_path=list(headings),paragraph_start=i))
    return out

def parse_pdf(data:bytes)->list[AnchorData]:
    import fitz
    doc=fitz.open(stream=data,filetype='pdf'); out=[]
    for pno,page in enumerate(doc):
        for b in page.get_text('blocks'):
            text=(b[4] or '').strip()
            if text: out.append(AnchorData('PDF_TEXT',text,page_start=pno+1,page_end=pno+1,bbox={'x0':b[0],'y0':b[1],'x1':b[2],'y1':b[3]}))
    return out

def parse_document(filename:str,data:bytes)->list[AnchorData]:
    ext=Path(filename).suffix.lower()
    if ext in ('.xlsx','.xlsm'): return parse_xlsx(data)
    if ext=='.docx': return parse_docx(data)
    if ext=='.pdf': return parse_pdf(data)
    if ext in ('.txt','.md','.csv'): return [AnchorData('PLAIN_TEXT',data.decode('utf-8',errors='replace'))]
    raise ValueError(f'Unsupported file type: {ext}')
