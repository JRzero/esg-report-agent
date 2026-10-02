# Material Center & Evidence Viewer

## Intent
Replace the Project Materials placeholder with the first evidence-centric production workspace.

## Core flow

```text
Project
  ↓
Material Center
  ↓
Upload Document
  ↓
Document Version
  ↓
Evidence Parse
  ↓
Document Anchor
  ↓
Evidence Viewer
  ↓
Fact Extraction Task
```

## Source boundaries
- EVIDENCE: may substantiate enterprise Facts.
- REFERENCE: style/structure only; must never be presented as enterprise factual evidence.
- STANDARD: reporting rules, not enterprise facts.
- HISTORICAL: prior-period context; requires period awareness.

The UI must preserve these boundaries visually and in action availability.

## Scope
- Project material list
- Upload PDF, DOCX, XLSX/XLSM, PPTX, TXT, MD, CSV
- Source type and optional category
- Document detail
- Version list
- parse/context/classification/fact-extraction status
- DocumentAnchor viewer
- PDF page / Excel sheet-cell / Word paragraph / PPT slide locator presentation
- Reprocess current version
- Download original
- Trigger Fact Extraction
- Project AI task visibility for extraction
- Explicit Reference warning

## Evidence Viewer rule
The browser must not independently derive authoritative source coordinates from the binary file.
Authoritative evidence coordinates come from backend `DocumentAnchor`.

This spec therefore implements an Anchor Viewer rather than a second browser-side parser.

## Acceptance criteria
1. Materials route consumes real document list/upload Service contracts.
2. Upload accepts only formats supported by the Service.
3. Source type is explicit before upload.
4. Reference and Standard documents cannot visually masquerade as enterprise Evidence.
5. Document detail consumes real versions and anchors.
6. Anchor locator renders correctly for PDF, Excel, Word and PPT coordinates.
7. Reprocess and Fact Extraction invoke real Service commands.
8. Fact Extraction is unavailable for REFERENCE and STANDARD source types in the UI.
9. Project tasks expose extraction status/result/failure.
10. Web and Service CI stay green.
