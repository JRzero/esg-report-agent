# API Contract Summary

Core groups: Auth, Companies, Projects, Project Members, Documents, Facts, Standards, Reports, AI Tasks.
All long-running AI operations return HTTP 202 with `task_id`. Project-bound endpoints must resolve ProjectMember authorization server-side.
