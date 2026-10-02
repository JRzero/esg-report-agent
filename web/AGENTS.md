# ESG Report Agent Web — Agent Rules

## Stack
- Next.js App Router
- React 19
- TypeScript strict mode
- Astryx is the primary design system
- Tailwind CSS is primarily for layout and domain composition
- TanStack Query owns server state
- Zustand is limited to local workspace/session UI state

## Before editing UI
1. Read the relevant `../specs/<id>/spec.md`, `plan.md`, and `tasks.md`.
2. Search Astryx before implementing a primitive:
   - `npm run astryx -- search <term>`
   - `npm run astryx -- component <Name>`
   - `npm run astryx -- template --list`
3. Prefer an Astryx primitive/template over a custom primitive.
4. Run lint, typecheck, test, and build before marking a task complete.

## UI rules
- Do not introduce shadcn/ui or another general-purpose primitive component library.
- Do not recreate Button, Input, Selector, Dialog, Tabs, Tooltip, Badge, Card, Table, or navigation primitives with Tailwind.
- Do not wrap every Astryx primitive. Build ESG domain components that compose Astryx.
- Prefer Astryx Theme/tokens/className before swizzling.
- Do not swizzle Astryx without an explicit spec decision.
- Keep Astryx packages pinned to the same exact version.
- Use Tailwind for grid/flex/gap/width/height and domain-specific composition.
- Avoid hard-coded brand colors. Let Astryx theme tokens own the visual language.

## ESG domain invariants
- `EVIDENCE` may substantiate enterprise Facts.
- `REFERENCE` is style/structure context only and must never be presented as factual Evidence.
- `STANDARD` describes reporting requirements, not enterprise facts.
- `HISTORICAL` requires period awareness and must not silently appear as current-year truth.
- A displayed factual Claim should eventually resolve to Confirmed Fact → FactEvidence → DocumentAnchor.
- Frontend cached state is never business truth.

## Report editor
Do not add a general rich-text editor in Spec 009. The Report Workspace gets a dedicated spec and will use the backend ReportBlock model as its source of structure.


## Authentication/BFF
- Browser code must not persist FastAPI access or refresh tokens in localStorage, sessionStorage, Zustand, or IndexedDB.
- Authentication tokens belong to HttpOnly cookies managed by Next.js Route Handlers.
- Client components call same-origin BFF routes under `/api/*`.
- Service API authentication/refresh logic belongs under `src/lib/server`, not feature components.
- A client-side identity store may cache non-secret user/tenant display data only.


## Evidence Viewer
- Original file binaries live in Service object storage; the browser is not a second source-of-truth parser.
- Treat Service `DocumentAnchor` coordinates as authoritative for Fact/Citation provenance.
- REFERENCE and STANDARD source types must never expose Fact Extraction actions.
- HISTORICAL material may produce candidates only with period awareness and human confirmation.
- Do not transform a Reference card into an Evidence card based on UI context.
- New file revisions create immutable DocumentVersion records; never imply in-place replacement.


## Fact Center
- AI-created Facts are candidates, not business truth.
- Only PENDING Facts may use ordinary Confirm/Reject actions.
- CONFLICT Facts must be resolved through the conflict-group endpoint; never synthesize or auto-select a winner in the UI.
- CONFIRMED Facts are immutable through ordinary PATCH.
- PENDING Facts may edit semantic-key fields; CONFLICT candidates may edit value/unit only.
- Fact Evidence must display and link to the exact Service DocumentVersion + DocumentAnchor.
- Fact Revision history is read-only/append-only.
- Do not infer Evidence from Reference or Standard material.


## GRI / Missing Data
- Requirement coverage is derived from confirmed Facts plus explicit project applicability.
- PENDING, CONFLICT and REJECTED Facts must never be presented as satisfying GRI coverage.
- NOT_APPLICABLE is a human project decision; do not infer or auto-select it in the UI.
- Missing Item workflow state is operational follow-up state, not disclosure coverage.
- RECEIVED or RESOLVED Missing Item does not imply COVERED Requirement.
- Link mapped Facts back to Fact Center rather than duplicating fact editing inside GRI.
- After Fact Mapping/applicability changes, invalidate Disclosure, Requirement and detail queries.
