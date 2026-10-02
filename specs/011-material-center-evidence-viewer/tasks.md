# Tasks

- [x] Add document BFF routes
- [x] Add document/version/anchor/task types
- [x] Add material query hooks
- [x] Add upload workflow
- [x] Add Material Center
- [x] Add Document detail route
- [x] Add Version status panel
- [x] Add Anchor Viewer
- [x] Add source locator formatter
- [x] Add original download action
- [x] Add reprocess action
- [x] Add Fact Extraction action
- [x] Disable Fact Extraction for Reference/Standard
- [x] Add task polling
- [x] Add tests
- [x] Run Web CI
- [x] Run Service CI
- [x] Publish acceptance report

## Accepted flow

```text
Project
  ↓
Materials
  ↓
Upload
  ↓
Document / immutable Version
  ↓
Service Parse
  ↓
DocumentAnchor
  ↓
Evidence Viewer
  ↓
Fact Extraction Task
```

## Evidence invariant

The frontend does not create authoritative source coordinates by reparsing documents in the browser.
`DocumentAnchor` from the Service remains the provenance source of truth.
