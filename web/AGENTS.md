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
