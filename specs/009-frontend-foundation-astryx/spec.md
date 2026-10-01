# Frontend Foundation & ESG Design System

## Intent
Create the frontend foundation only after the backend contract and evaluation gates are stable.

## Stack
- Next.js 16.3.8 App Router
- React 19
- TypeScript
- Astryx 0.6.3 as the primary design system
- Tailwind CSS 4 for layout/composition
- TanStack Query for server state
- Zustand for local workspace/auth state

## Architectural rules
1. Astryx owns primitive UI language. Do not add shadcn/ui, Radix-based general UI kits, or duplicate primitive libraries.
2. Tailwind is for layout and domain composition, not reimplementing Button/Input/Dialog/Badge/Card primitives.
3. ESG concepts live under `src/components/domain`.
4. Do not wrap every Astryx primitive. Isolation happens at the ESG domain-component layer.
5. Do not swizzle Astryx without a dedicated architectural reason and spec update.
6. Evidence, Reference, Standard, and Historical sources must remain visually and semantically distinct.
7. A Reference source must never be presented as enterprise Evidence.
8. Frontend state never becomes business truth; confirmed Facts and provenance come from the Service API.
9. Report editing is not part of this spec; Tiptap is introduced in a later Report Workspace spec.
10. Package versions for Astryx are pinned exactly because Astryx is pre-1.0.

## Deliverables
- Next.js application foundation under `web/`
- Astryx + Tailwind layer setup
- Theme/provider setup
- Product AppShell + SideNav
- API client foundation
- Query provider
- local auth/workspace store
- six domain components:
  - EvidenceCard
  - FactCard
  - GRICoverage
  - MissingItemCard
  - CitationMarker
  - AIAction
- Foundation showcase page
- frontend AGENTS.md
- lint/typecheck/test/build CI

## Acceptance criteria
- Next production build succeeds.
- TypeScript strict mode succeeds.
- Frontend tests succeed.
- Astryx CLI can resolve installed component docs.
- No shadcn/ui dependency exists.
- Foundation page renders all six ESG domain components.
- EvidenceCard explicitly distinguishes Evidence from Reference.
- Product shell uses Astryx AppShell/SideNav.
