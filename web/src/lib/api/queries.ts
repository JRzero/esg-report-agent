'use client';

import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {browserRequest} from './browser';
import type {
  AITask,
  Company,
  Document,
  DocumentAnchor,
  DocumentDetail,
  Fact,
  FactConflictDetail,
  FactConflictGroup,
  FactEvidenceTrace,
  FactRevision,
  FactUpdateInput,
  MissingItem,
  MissingItemUpdateInput,
  Project,
  ProjectCreateInput,
  Report,
  ReportCreateInput,
  ReportSection,
  SectionCreateInput,
  SectionDisclosureMapping,
  SectionPlanningContext,
  SectionUpdateInput,
  SectionWritingPlan,
  SectionWritingPlanInput,
  ProjectDisclosure,
  ProjectDisclosureDetail,
  ProjectDisclosureUpdateInput,
  ProjectRequirement,
  ProjectStandardAttachment,
  QueueTaskResult,
  SessionIdentity,
  Standard,
  StandardVersion,
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


export function useFacts(projectId: string) {
  return useQuery({
    queryKey: queryKeys.facts(projectId),
    queryFn: () => browserRequest<Fact[]>(`/api/projects/${projectId}/facts`),
    enabled: Boolean(projectId),
  });
}

export function useFact(factId: string) {
  return useQuery({
    queryKey: queryKeys.fact(factId),
    queryFn: () => browserRequest<Fact>(`/api/facts/${factId}`),
    enabled: Boolean(factId),
  });
}

export function useFactEvidence(factId: string) {
  return useQuery({
    queryKey: queryKeys.factEvidence(factId),
    queryFn: () =>
      browserRequest<FactEvidenceTrace[]>(`/api/facts/${factId}/evidence`),
    enabled: Boolean(factId),
  });
}

export function useFactRevisions(factId: string) {
  return useQuery({
    queryKey: queryKeys.factRevisions(factId),
    queryFn: () =>
      browserRequest<FactRevision[]>(`/api/facts/${factId}/revisions`),
    enabled: Boolean(factId),
  });
}

export function useFactConflicts(projectId: string) {
  return useQuery({
    queryKey: queryKeys.factConflicts(projectId),
    queryFn: () =>
      browserRequest<FactConflictGroup[]>(
        `/api/projects/${projectId}/fact-conflicts`,
      ),
    enabled: Boolean(projectId),
  });
}

export function useFactConflict(groupId: string) {
  return useQuery({
    queryKey: queryKeys.factConflict(groupId),
    queryFn: () =>
      browserRequest<FactConflictDetail>(`/api/fact-conflicts/${groupId}`),
    enabled: Boolean(groupId),
  });
}

export function useUpdateFact(projectId: string, factId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: FactUpdateInput) =>
      browserRequest<Fact>(`/api/facts/${factId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: (fact) => {
      queryClient.setQueryData(queryKeys.fact(factId), fact);
      void queryClient.invalidateQueries({queryKey: queryKeys.facts(projectId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factRevisions(factId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factConflicts(projectId)});
    },
  });
}

export function useConfirmFact(projectId: string, factId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      browserRequest<Fact>(`/api/facts/${factId}/confirm`, {method: 'POST'}),
    onSuccess: (fact) => {
      queryClient.setQueryData(queryKeys.fact(factId), fact);
      void queryClient.invalidateQueries({queryKey: queryKeys.facts(projectId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factRevisions(factId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factConflicts(projectId)});
    },
  });
}

export function useRejectFact(projectId: string, factId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      browserRequest<Fact>(`/api/facts/${factId}/reject`, {
        method: 'POST',
        body: JSON.stringify({reason}),
      }),
    onSuccess: (fact) => {
      queryClient.setQueryData(queryKeys.fact(factId), fact);
      void queryClient.invalidateQueries({queryKey: queryKeys.facts(projectId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factRevisions(factId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factConflicts(projectId)});
    },
  });
}

export function useResolveFactConflict(projectId: string, groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (factId: string) =>
      browserRequest<FactConflictGroup>(
        `/api/fact-conflicts/${groupId}/resolve`,
        {method: 'POST', body: JSON.stringify({fact_id: factId})},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: queryKeys.facts(projectId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factConflicts(projectId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.factConflict(groupId)});
    },
  });
}


export function useStandards() {
  return useQuery({
    queryKey: queryKeys.standards,
    queryFn: () => browserRequest<Standard[]>('/api/standards'),
  });
}

export function useStandardVersions(standardId: string) {
  return useQuery({
    queryKey: queryKeys.standardVersions(standardId),
    queryFn: () =>
      browserRequest<StandardVersion[]>(
        `/api/standards/${standardId}/versions`,
      ),
    enabled: Boolean(standardId),
  });
}

export function useProjectStandards(projectId: string) {
  return useQuery({
    queryKey: queryKeys.projectStandards(projectId),
    queryFn: () =>
      browserRequest<ProjectStandardAttachment[]>(
        `/api/projects/${projectId}/standards`,
      ),
    enabled: Boolean(projectId),
  });
}

export function useAttachStandard(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      browserRequest<{id: string}>(
        `/api/projects/${projectId}/standards/${versionId}`,
        {method: 'POST'},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectStandards(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.disclosures(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.requirements(projectId),
      });
    },
  });
}

export function useProjectDisclosures(projectId: string) {
  return useQuery({
    queryKey: queryKeys.disclosures(projectId),
    queryFn: () =>
      browserRequest<ProjectDisclosure[]>(
        `/api/projects/${projectId}/disclosures`,
      ),
    enabled: Boolean(projectId),
  });
}

export function useProjectDisclosure(
  projectId: string,
  projectDisclosureId: string,
) {
  return useQuery({
    queryKey: queryKeys.disclosure(projectId, projectDisclosureId),
    queryFn: () =>
      browserRequest<ProjectDisclosureDetail>(
        `/api/projects/${projectId}/disclosures/${projectDisclosureId}`,
      ),
    enabled: Boolean(projectId && projectDisclosureId),
  });
}

export function useProjectRequirements(projectId: string) {
  return useQuery({
    queryKey: queryKeys.requirements(projectId),
    queryFn: () =>
      browserRequest<ProjectRequirement[]>(
        `/api/projects/${projectId}/requirements`,
      ),
    enabled: Boolean(projectId),
  });
}

export function useRunDisclosureMapping(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      browserRequest<{status: string; mappings_created: number}>(
        `/api/projects/${projectId}/gri/disclosure-mapping`,
        {method: 'POST'},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.disclosures(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.requirements(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'disclosures'],
      });
    },
  });
}

export function useUpdateProjectDisclosure(
  projectId: string,
  projectDisclosureId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProjectDisclosureUpdateInput) =>
      browserRequest<ProjectDisclosure>(
        `/api/projects/${projectId}/disclosures/${projectDisclosureId}`,
        {method: 'PATCH', body: JSON.stringify(input)},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.disclosures(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.disclosure(projectId, projectDisclosureId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.requirements(projectId),
      });
    },
  });
}

export function useMissingItems(projectId: string) {
  return useQuery({
    queryKey: queryKeys.missingItems(projectId),
    queryFn: () =>
      browserRequest<MissingItem[]>(
        `/api/projects/${projectId}/missing-items`,
      ),
    enabled: Boolean(projectId),
  });
}

export function useRunMissingAnalysis(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      browserRequest<{status: string; missing_items_created: number}>(
        `/api/projects/${projectId}/missing-analysis`,
        {method: 'POST'},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.missingItems(projectId),
      });
    },
  });
}

export function useUpdateMissingItem(projectId: string, itemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: MissingItemUpdateInput) =>
      browserRequest<MissingItem>(`/api/missing-items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.missingItems(projectId),
      });
    },
  });
}


export function useReports(projectId: string) {
  return useQuery({
    queryKey: queryKeys.reports(projectId),
    queryFn: () => browserRequest<Report[]>(`/api/projects/${projectId}/reports`),
    enabled: Boolean(projectId),
  });
}

export function useCreateReport(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReportCreateInput) =>
      browserRequest<Report>(`/api/projects/${projectId}/reports`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: (report) => {
      queryClient.setQueryData(queryKeys.report(report.id), report);
      void queryClient.invalidateQueries({queryKey: queryKeys.reports(projectId)});
    },
  });
}

export function useReport(reportId: string) {
  return useQuery({
    queryKey: queryKeys.report(reportId),
    queryFn: () => browserRequest<Report>(`/api/reports/${reportId}`),
    enabled: Boolean(reportId),
  });
}

export function useSections(reportId: string) {
  return useQuery({
    queryKey: queryKeys.sections(reportId),
    queryFn: () => browserRequest<ReportSection[]>(`/api/reports/${reportId}/sections`),
    enabled: Boolean(reportId),
  });
}

export function useCreateSection(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SectionCreateInput) =>
      browserRequest<ReportSection>(`/api/reports/${reportId}/sections`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: queryKeys.sections(reportId)});
    },
  });
}

export function useSection(sectionId: string) {
  return useQuery({
    queryKey: queryKeys.section(sectionId),
    queryFn: () => browserRequest<ReportSection>(`/api/sections/${sectionId}`),
    enabled: Boolean(sectionId),
    refetchInterval: (query) =>
      query.state.data?.status === 'GENERATING' ? 2000 : false,
  });
}

export function useUpdateSection(reportId: string, sectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SectionUpdateInput) =>
      browserRequest<ReportSection>(`/api/sections/${sectionId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: (section) => {
      queryClient.setQueryData(queryKeys.section(sectionId), section);
      void queryClient.invalidateQueries({queryKey: queryKeys.sections(reportId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sectionPlanningContext(sectionId)});
    },
  });
}

export function useSectionDisclosures(sectionId: string) {
  return useQuery({
    queryKey: queryKeys.sectionDisclosures(sectionId),
    queryFn: () =>
      browserRequest<SectionDisclosureMapping[]>(
        `/api/sections/${sectionId}/disclosures`,
      ),
    enabled: Boolean(sectionId),
  });
}

export function useMapSectionDisclosure(reportId: string, sectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (disclosureId: string) =>
      browserRequest<{id: string}>(
        `/api/sections/${sectionId}/disclosures/${disclosureId}`,
        {method: 'POST'},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: queryKeys.sectionDisclosures(sectionId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.section(sectionId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sections(reportId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sectionPlanningContext(sectionId)});
    },
  });
}

export function useUnmapSectionDisclosure(reportId: string, sectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (disclosureId: string) =>
      browserRequest<void>(
        `/api/sections/${sectionId}/disclosures/${disclosureId}`,
        {method: 'DELETE'},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: queryKeys.sectionDisclosures(sectionId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.section(sectionId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sections(reportId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sectionPlanningContext(sectionId)});
    },
  });
}

export function useSectionPlanningContext(sectionId: string) {
  return useQuery({
    queryKey: queryKeys.sectionPlanningContext(sectionId),
    queryFn: () =>
      browserRequest<SectionPlanningContext>(
        `/api/sections/${sectionId}/planning-context`,
      ),
    enabled: Boolean(sectionId),
  });
}

export function useGenerateSectionPlan(
  projectId: string,
  reportId: string,
  sectionId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      browserRequest<QueueTaskResult>(
        `/api/sections/${sectionId}/ai/writing-plan`,
        {
          method: 'POST',
          headers: {'Idempotency-Key': `section-plan:${sectionId}:${Date.now()}`},
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: queryKeys.section(sectionId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sections(reportId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.tasks(projectId)});
    },
  });
}

export function useSaveSectionPlan(
  reportId: string,
  sectionId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SectionWritingPlanInput) =>
      browserRequest<SectionWritingPlan>(
        `/api/sections/${sectionId}/writing-plan`,
        {method: 'PUT', body: JSON.stringify(input)},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: queryKeys.section(sectionId)});
      void queryClient.invalidateQueries({queryKey: queryKeys.sections(reportId)});
    },
  });
}
