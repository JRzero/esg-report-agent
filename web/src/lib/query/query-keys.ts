export const queryKeys = {
  session: ['session', 'me'] as const,
  companies: ['companies'] as const,
  projects: ['projects'] as const,
  project: (projectId: string) => ['projects', projectId] as const,
  documents: (projectId: string) => ['projects', projectId, 'documents'] as const,
  facts: (projectId: string) => ['projects', projectId, 'facts'] as const,
  disclosures: (projectId: string) => ['projects', projectId, 'disclosures'] as const,
  reports: (projectId: string) => ['projects', projectId, 'reports'] as const,
};
