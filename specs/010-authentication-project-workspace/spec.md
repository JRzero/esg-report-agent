# Authentication & Project Workspace

## Intent
Deliver the first real frontend-to-service vertical slice after the accepted frontend foundation.

## User flow

```text
Login
  ↓
HttpOnly BFF Session
  ↓
Current User / Tenant
  ↓
Project List
  ↓
Create Project
  ↓
Project Overview
  ↓
Project Workspace Navigation
```

## Security boundary
- Browser JavaScript must not store FastAPI access or refresh tokens.
- Next.js Route Handlers act as a BFF.
- FastAPI tokens are stored in HttpOnly, SameSite=Lax cookies.
- BFF refreshes the access token through `/api/v1/auth/refresh` when required.
- Logout deletes both cookies.
- Client components call only same-origin `/api/*` BFF routes for this slice.

## Scope
- Login UI
- Session establishment/refresh/logout
- Current user/tenant identity
- Project list
- Company list for project creation
- Create project
- Project overview
- Project-level navigation shell

## Project navigation
- 概览
- 资料
- 事实
- 报告
- GRI
- 缺失资料
- 成员

Only Overview is functional in this spec. Other project sections render explicit placeholders for later specs; they must not invent business behavior.

## Acceptance criteria
1. Unauthenticated workspace routes redirect to `/login`.
2. Login never returns FastAPI tokens to browser JavaScript.
3. Session BFF stores tokens in HttpOnly cookies.
4. `/api/session/me` proxies the authenticated backend identity.
5. Project list consumes the real Service `GET /api/v1/projects` contract.
6. Create Project consumes real Company and Project contracts.
7. Project overview consumes `GET /api/v1/projects/{id}`.
8. Project navigation is project-scoped and stable.
9. Astryx primitives are used for forms, actions, cards, selectors, and navigation.
10. Web CI lint/typecheck/test/build/SSR smoke remains green.
