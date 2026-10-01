# Tasks

- [x] Scaffold Next.js 16 frontend
- [x] Pin Astryx 0.6.3 packages
- [x] Configure Astryx + Tailwind CSS layer order
- [x] Configure Theme/Link/Query providers
- [x] Add ProductShell with Astryx AppShell + SideNav
- [x] Add API client foundation
- [x] Add auth/workspace local state foundation
- [x] Add EvidenceCard
- [x] Add FactCard
- [x] Add GRICoverage
- [x] Add MissingItemCard
- [x] Add CitationMarker
- [x] Add AIAction
- [x] Add foundation showcase page
- [x] Add web AGENTS.md
- [x] Add component/evidence-boundary tests
- [x] Add Web CI
- [x] Verify Astryx CLI
- [x] Verify production build
- [x] Publish acceptance report

## Accepted commands

```bash
npm ci
npm run astryx -- component Button --json
npm run lint
npm run typecheck
npm run test
npm run build
npm run start
```

The Web CI also performs an SSR smoke against the built root route and requires the
Foundation Showcase to render successfully.
