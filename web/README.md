# ESG Report Agent Web

Next.js frontend foundation for the evidence-grounded ESG report workspace.

## Stack

- Next.js 16.3.8
- React 19
- TypeScript
- Astryx 0.6.3
- Tailwind CSS 4.3
- TanStack Query
- Zustand

Astryx is the primary design system. Tailwind is used for layout and domain composition rather than rebuilding primitive controls.

## Run

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

The root page is currently a **Foundation Showcase**, not a product feature page. It verifies the persistent shell and the first ESG domain components before route development begins.

## Quality gates

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npm run astryx -- component Button --json
```

## Astryx

All stable Astryx packages are pinned to the same exact version.

Use the locally installed CLI:

```bash
npm run astryx -- search evidence
npm run astryx -- component Button
npm run astryx -- component Card
npm run astryx -- template --list
```

Do not use an unrelated bare `npx astryx` before `@astryxdesign/cli` is installed.

## Domain components

- EvidenceCard
- FactCard
- GRICoverage
- MissingItemCard
- CitationMarker
- AIAction

These components are the first layer of the project's ESG-specific design system.

## Backend

Set:

```text
NEXT_PUBLIC_SERVICE_BASE_URL=http://localhost:8000
```

The current foundation exposes an API client abstraction but does not yet implement the product login route or feature pages.
