'use client';

import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {browserRequest} from './browser';
import type {
  Company,
  Project,
  ProjectCreateInput,
  SessionIdentity,
} from './types';
import {queryKeys} from '@/lib/query/query-keys';

export function useSessionIdentity() {
  return useQuery({
    queryKey: ['session', 'me'],
    queryFn: () => browserRequest<SessionIdentity>('/api/session/me'),
    staleTime: 60_000,
    retry: false,
  });
}

export function useCompanies() {
  return useQuery({
    queryKey: ['companies'],
    queryFn: () => browserRequest<Company[]>('/api/companies'),
  });
}

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: () => browserRequest<Project[]>('/api/projects'),
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => browserRequest<Project>(`/api/projects/${projectId}`),
    enabled: Boolean(projectId),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ProjectCreateInput) =>
      browserRequest<Project>('/api/projects', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: (project) => {
      queryClient.setQueryData(queryKeys.project(project.id), project);
      void queryClient.invalidateQueries({queryKey: queryKeys.projects});
    },
  });
}
