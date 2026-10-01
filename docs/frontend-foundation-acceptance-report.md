# Frontend Foundation & ESG Design System Acceptance Report

Date: 2026-10-01  
Scope: Frontend foundation only. Product feature pages and report editor are excluded.

## Result

**Frontend Foundation Acceptance: PASS**

GitHub Actions Web CI run **36874514780** passed all configured gates.

Observed results:

- locked dependency install with `npm ci`: PASS
- Astryx CLI component contract: PASS
- ESLint: PASS
- TypeScript strict typecheck: PASS
- Vitest: **2 test files / 4 tests passed**
- Next.js production build: PASS
- Next.js version: **16.3.8**
- SSR root-route smoke: PASS

## Accepted stack

```text
Next.js 16.3.8
React 19.2
TypeScript
Astryx 0.6.3
Tailwind CSS 4.3
TanStack Query
Zustand
```

Astryx packages are pinned to the same exact version:

```text
@astryxdesign/core          0.6.3
@astryxdesign/theme-neutral 0.6.3
@astryxdesign/cli           0.6.3
```

The npm dependency graph is locked with `web/package-lock.json`.

## Architecture

```text
Next.js Application
        ↓
Product Shell
        ↓
ESG Domain Components
        ↓
Astryx primitives
        ↓
Astryx Theme / Tokens
```

Tailwind is used for layout/composition. It is not the primitive component system.

## Product shell

The persistent frame uses Astryx:

```text
AppShell
└── SideNav
    └── SideNavSection
        └── SideNavItem
```

The shell is prepared for the product navigation:

- Overview
- Projects
- Materials
- Facts
- GRI
- Reports

Those feature routes are intentionally not implemented in Spec 009.

## First ESG domain components

### EvidenceCard

Represents a source with explicit source type:

- EVIDENCE
- REFERENCE
- STANDARD
- HISTORICAL

A REFERENCE card renders a visible rule explaining that the source may be used for structure/style
but not as current-enterprise factual evidence.

This is covered by automated regression tests.

### FactCard

Displays:

- Fact name
- value/unit
- period
- entity scope
- Fact status
- Evidence count

### GRICoverage

Displays disclosure coverage state and requirement completion ratio.

### MissingItemCard

Displays missing-data requirement, priority, workflow state and suggested material.

### CitationMarker

Uses the Astryx Button primitive to represent an evidence/citation navigation affordance.

### AIAction

Uses Astryx actions for ESG writing commands such as:

- rewrite
- shorten
- regenerate from evidence
- consistency check

## Agent development contract

`web/AGENTS.md` now defines the frontend implementation rules.

Important rules include:

- Astryx is the primary primitive UI system.
- Do not introduce shadcn/ui or another competing primitive library.
- Search Astryx through its CLI before creating a primitive.
- Do not swizzle without a spec-level decision.
- Reference must never be presented as factual Evidence.
- Frontend state is never business truth.
- Report editor work is deferred to a dedicated spec.

## CSS integration

Astryx and Tailwind use an explicit cascade-layer order:

```text
reset
theme
base
astryx-base
astryx-theme
components
utilities
```

This follows the Astryx Tailwind-v4 coexistence model and prevents Tailwind preflight from silently
overriding the design-system theme.

## API/state foundation

The frontend includes:

- reusable `ApiClient`
- normalized `ApiError`
- access-token provider seam
- TanStack Query provider/default policy
- centralized query-key definitions
- small Zustand auth/workspace session store

Feature-specific queries are intentionally deferred until the first product route.

## Error boundaries

The App Router includes:

- `error.tsx`
- `not-found.tsx`

The error action uses an Astryx Button rather than a custom primitive.

## Explicit exclusions

Spec 009 does not implement:

- login UI
- project pages
- Material Center
- Fact Center page
- GRI page
- report workspace
- Tiptap
- PDF/Excel viewers
- real backend query hooks
- feature-level responsive behavior
- publication UI

These require later feature specs and are not acceptance defects.

## Conclusion

The frontend now has a stable implementation substrate:

```text
Spec + AGENTS
     ↓
Next.js
     ↓
Astryx Design System
     ↓
ESG Domain Components
     ↓
Service API contract
```

Feature development can now proceed without each page inventing its own UI language.
