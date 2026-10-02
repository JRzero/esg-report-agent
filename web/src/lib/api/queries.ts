'use client';

import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {browserRequest} from './browser';
import type {
  AITask,
  Company,
  Document,
  DocumentAnchor,
  DocumentDetail,
  Project,
  ProjectCreateInput,
  QueueTaskResult,
  SessionIdentity,
  UploadDocumentResult,
} from './types';
import {queryKeys} from '@/lib/query/query-keys';

export function useSessionIdentity() {
  return useQuery({
    queryKey: queryKeys.session,
    queryFn: () => browserRequest<SessionIdentity>('/api/session/me'),
    staleTime: 60_000,
    retry: false,
  });
}

export function useCompanies() {
  return useQuery({
    queryKey: queryKeys.companies,
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


export function useDocuments(projectId: string) {
  return useQuery({
    queryKey: queryKeys.documents(projectId),
    queryFn: () =>
      browserRequest<Document[]>(`/api/projects/${projectId}/documents`),
    enabled: Boolean(projectId),
  });
}

export function useDocument(documentId: string) {
  return useQuery({
    queryKey: queryKeys.document(documentId),
    queryFn: () =>
      browserRequest<DocumentDetail>(`/api/documents/${documentId}`),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const versions = query.state.data?.versions ?? [];
      return versions.some((version) =>
        [version.validation_status, version.evidence_parse_status, version.context_status]
          .some((status) => status === 'PENDING' || status === 'PROCESSING'),
      )
        ? 2000
        : false;
    },
  });
}

export function useDocumentAnchors(versionId: string) {
  return useQuery({
    queryKey: queryKeys.anchors(versionId),
    queryFn: () =>
      browserRequest<DocumentAnchor[]>(
        `/api/document-versions/${versionId}/anchors`,
      ),
    enabled: Boolean(versionId),
  });
}

export function useProjectTasks(projectId: string) {
  return useQuery({
    queryKey: queryKeys.tasks(projectId),
    queryFn: () =>
      browserRequest<AITask[]>(`/api/projects/${projectId}/tasks`),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const tasks = query.state.data;
      return tasks?.some(
        (task) => task.status === 'PENDING' || task.status === 'RUNNING',
      )
        ? 2000
        : false;
    },
  });
}

export function useUploadDocument(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) =>
      browserRequest<UploadDocumentResult>(
        `/api/projects/${projectId}/documents`,
        {method: 'POST', body: formData},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.documents(projectId),
      });
    },
  });
}

export function useUploadDocumentVersion(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.set('file', file);
      return browserRequest<UploadDocumentResult>(
        `/api/documents/${documentId}/versions`,
        {method: 'POST', body: formData},
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.document(documentId),
      });
    },
  });
}

export function useReprocessVersion(documentId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      browserRequest<{version_id: string; status: string}>(
        `/api/document-versions/${versionId}/reprocess`,
        {method: 'POST'},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.document(documentId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.anchors(versionId),
      });
    },
  });
}

export function useExtractFacts(projectId: string, documentId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      browserRequest<QueueTaskResult>(
        `/api/document-versions/${versionId}/extract-facts`,
        {
          method: 'POST',
          headers: {
            'Idempotency-Key': `fact-extraction:${versionId}`,
          },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.tasks(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.document(documentId),
      });
    },
  });
}

export async function getDocumentDownloadUrl(versionId: string) {
  return browserRequest<{download_url: string}>(
    `/api/document-versions/${versionId}/download`,
  );
}
