# Authentication & Project Workspace Acceptance Report

Date: 2026-10-02  
Scope: Authentication and the first frontend-to-service Project vertical slice.

## Result

**Spec 010 Acceptance: PASS**

PR validation runs:

- Web CI: **36942564131 — PASS**
- Service CI: **36942564129 — PASS**

Observed Web results:

- locked dependency install: PASS
- Astryx CLI contract: PASS
- ESLint: PASS
- TypeScript: PASS
- Vitest: **3 files / 6 tests passed**
- Next.js 16.3.8 production build: PASS
- unauthenticated SSR redirect smoke: PASS

Observed Service regression results:

- Ruff/compile/migrations: PASS
- pytest: **37 passed**
- Agent Eval: **1.0**
- ESG Scenario Eval: **1.0**
- performance smoke p50: **13.69 ms**
- performance smoke p95: **67.65 ms**
- service image build: PASS
- non-root container verification: PASS

The performance figures are CI regression guards, not production capacity claims.

## Authentication architecture

```text
Browser
  ↓ same-origin
Next.js Route Handler BFF
  ↓ Authorization: Bearer <access>
FastAPI Service
```

The browser never receives FastAPI access/refresh tokens in application JavaScript.

The BFF stores:

- access token → HttpOnly cookie
- refresh token → HttpOnly cookie

Cookie policy:

- HttpOnly
- SameSite=Lax
- Secure in production
- Path=/

When the Service returns 401 for an authenticated BFF request:

```text
access rejected
   ↓
refresh token
   ↓
POST /api/v1/auth/refresh
   ↓
rotate cookies
   ↓
retry original request
```

If refresh fails, the BFF deletes the session cookies and returns 401.

## Implemented BFF routes

```text
POST /api/session/login
POST /api/session/logout
GET  /api/session/me

GET  /api/companies

GET  /api/projects
POST /api/projects
GET  /api/projects/{projectId}
```

## Login

Implemented route:

```text
/login
```

The login form uses Astryx:

- TextInput
- Button
- Card

On success it creates the HttpOnly BFF session and navigates to `/projects`.

The frontend Zustand store now contains only non-secret display identity. Token state was removed.

## Workspace guard

Authenticated product routes live under a workspace route group.

If neither access nor refresh cookie exists, the server layout redirects to:

```text
/login
```

Web CI starts the production build and verifies that a request to the root workspace ultimately
renders the login page when no session exists.

## Project list

Implemented:

```text
/projects
```

It consumes the real Service contracts:

```text
GET /api/v1/projects
GET /api/v1/companies
```

The UI displays:

- project name
- company name
- report year
- reporting period
- non-default project status

The empty state provides a direct Create Project action.

## Create Project

Implemented:

```text
/projects/new
```

The form consumes the real Service `ProjectCreate` contract:

- company_id
- name
- report_year
- period_start
- period_end

Frontend validation mirrors backend structural rules:

- company required
- name required
- report year 2000–2200
- ISO reporting dates
- start date must not exceed end date

The Company selector is populated from the real tenant Company API.

## Project Overview

Implemented:

```text
/projects/{projectId}
```

It consumes:

```text
GET /api/v1/projects/{projectId}
```

and displays the project/company/reporting-period boundary that all later ESG modules use.

## Project navigation

The stable project-level navigation is now:

```text
概览
资料
事实
报告
GRI
缺失资料
成员
```

Current routes:

```text
/projects/{id}
/projects/{id}/materials
/projects/{id}/facts
/projects/{id}/reports
/projects/{id}/gri
/projects/{id}/missing
/projects/{id}/members
```

Only Overview is functional in Spec 010.

The other routes intentionally render explicit Astryx EmptyState placeholders. No fake Material,
Fact, GRI, Report or Member business behavior is implemented.

## Product shell

The global SideNav has been simplified to application-level destinations:

- Projects
- Foundation

Project business navigation is no longer incorrectly mixed into global navigation.

The SideNav footer displays the current user/tenant identity and supports Logout.

## Tests

The frontend suite now includes:

- Evidence vs Reference boundary tests
- ESG domain component smoke tests
- ProjectCreate contract/period validation tests

SSR smoke additionally checks the unauthenticated redirect path in the production Next.js server.

## Explicit exclusions

Not implemented in Spec 010:

- Company administration UI
- Material Center
- document upload/preview
- Fact Center
- GRI workspace
- Missing Data workflow
- Project Member management UI
- Report Workspace
- Tiptap editor

These are subsequent vertical slices.

## Conclusion

The application now has its first real authenticated vertical slice:

```text
User
 ↓
Session
 ↓
Tenant
 ↓
Project
 ↓
Project Workspace
```

The next product slice can start at the project's **Materials** route without redesigning authentication,
navigation or project scoping.
