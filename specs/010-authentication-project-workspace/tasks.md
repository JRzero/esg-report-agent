# Tasks

- [x] Add HttpOnly BFF session helper
- [x] Add login/logout/session routes
- [x] Add BFF companies/projects routes
- [x] Remove browser token state
- [x] Add Login page
- [x] Add session identity hook
- [x] Add Project List
- [x] Add Create Project
- [x] Add Project Overview
- [x] Add project workspace navigation
- [x] Add future-module placeholder routes
- [x] Add auth/project validation tests
- [x] Update SSR smoke
- [x] Run Web CI
- [x] Run Service CI
- [x] Publish acceptance report

## Accepted flow

```text
/login
  ↓
Next.js BFF HttpOnly session
  ↓
/projects
  ↓
/projects/new
  ↓
/projects/{projectId}
  ↓
project-scoped navigation
```

## Security invariant

FastAPI access and refresh tokens are not exposed to browser JavaScript state. They are managed by
Next.js Route Handlers using HttpOnly, SameSite=Lax cookies.
