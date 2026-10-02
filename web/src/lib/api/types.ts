export type SessionIdentity = {
  user: {
    id: string;
    email: string;
    name: string;
  };
  tenant: {
    id: string;
    name: string;
    code: string;
  };
  membership: {
    id: string;
    tenant_role: 'ADMIN' | 'MEMBER';
    member_type: 'INTERNAL' | 'CLIENT';
    company_id: string | null;
  };
};

export type Company = {
  id: string;
  tenant_id: string;
  name: string;
  short_name?: string | null;
  registration_no?: string | null;
  industry_code?: string | null;
  country?: string | null;
  region?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
};

export type Project = {
  id: string;
  tenant_id: string;
  company_id: string;
  name: string;
  report_year: number;
  period_start: string;
  period_end: string;
  source_project_id?: string | null;
  status: string;
  owner_membership_id: string;
  created_at: string;
  updated_at: string;
};

export type ProjectCreateInput = {
  company_id: string;
  name: string;
  report_year: number;
  period_start: string;
  period_end: string;
  source_project_id?: string | null;
};


export type DocumentSourceType =
  | 'EVIDENCE'
  | 'REFERENCE'
  | 'STANDARD'
  | 'HISTORICAL';

export type Document = {
  id: string;
  tenant_id: string;
  project_id: string;
  name: string;
  source_type: DocumentSourceType;
  category_code: string | null;
  status: string;
  sensitivity_level: string;
  inherited_from_document_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
};

export type DocumentVersion = {
  id: string;
  document_id: string;
  version_no: number;
  original_filename: string;
  mime_type: string | null;
  file_extension: string | null;
  file_size: number;
  sha256: string;
  validation_status: string;
  evidence_parse_status: string;
  context_status: string;
  classification_status: string;
  fact_extraction_status: string;
  parse_error: string | null;
  processing_started_at: string | null;
  uploaded_by: string;
  uploaded_at: string;
};

export type DocumentAnchor = {
  id: string;
  tenant_id: string;
  project_id: string;
  document_version_id: string;
  anchor_type: string;
  page_start: number | null;
  page_end: number | null;
  sheet_name: string | null;
  cell_range: string | null;
  heading_path: string[] | null;
  paragraph_start: number | null;
  paragraph_end: number | null;
  slide_number: number | null;
  bbox: Record<string, unknown> | null;
  raw_text: string;
  normalized_text: string | null;
  content_hash: string;
  metadata: Record<string, unknown>;
};

export type DocumentDetail = {
  document: Document;
  versions: DocumentVersion[];
};

export type AITask = {
  id: string;
  task_type: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED' | string;
  progress: string | number;
  stage: string | null;
  result_json: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
};

export type UploadDocumentResult = {
  document_id: string;
  version_id: string;
  status: string;
};

export type QueueTaskResult = {
  task_id: string;
  status: string;
};


export type FactStatus = 'PENDING' | 'CONFIRMED' | 'CONFLICT' | 'REJECTED';
export type FactValueType = 'NUMBER' | 'TEXT' | 'BOOLEAN' | 'DATE' | 'JSON';

export type Fact = {
  id: string;
  tenant_id: string;
  project_id: string;
  fact_type: string;
  metric_definition_id: string | null;
  semantic_key: string;
  name: string;
  value_type: FactValueType;
  number_value: string | number | null;
  text_value: string | null;
  boolean_value: boolean | null;
  date_value: string | null;
  json_value: Record<string, unknown> | null;
  raw_value: string | null;
  unit: string | null;
  period_start: string | null;
  period_end: string | null;
  entity_scope: string | null;
  dimensions: Record<string, unknown>;
  status: FactStatus;
  confidence: string | number | null;
  source_type: 'AI' | 'HUMAN' | string;
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FactUpdateInput = {
  name?: string;
  number_value?: number | null;
  text_value?: string | null;
  boolean_value?: boolean | null;
  date_value?: string | null;
  json_value?: Record<string, unknown> | null;
  raw_value?: string | null;
  unit?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  entity_scope?: string | null;
  dimensions?: Record<string, unknown>;
};

export type FactEvidenceTrace = {
  fact_evidence_id: string;
  evidence_role: string;
  confidence: string | number | null;
  anchor: {
    id: string;
    type: string;
    page_start: number | null;
    page_end: number | null;
    sheet_name: string | null;
    cell_range: string | null;
    heading_path: string[] | null;
    paragraph_start: number | null;
    paragraph_end: number | null;
    slide_number: number | null;
    bbox: Record<string, unknown> | null;
    raw_text: string;
    normalized_text: string | null;
    content_hash: string;
  };
  document: {
    id: string;
    name: string;
    source_type: DocumentSourceType;
    category_code: string | null;
    version_id: string;
    version_no: number;
    original_filename: string;
    sha256: string;
  };
};

export type FactRevision = {
  id: string;
  fact_id: string;
  revision_no: number;
  snapshot: Record<string, unknown>;
  change_type: string;
  changed_by: string | null;
  created_at: string;
};

export type FactConflictGroup = {
  id: string;
  tenant_id?: string;
  project_id: string;
  semantic_key: string;
  conflict_type: string;
  status: 'OPEN' | 'RESOLVED' | 'IGNORED' | string;
  resolved_fact_id: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FactConflictDetail = {
  group: FactConflictGroup;
  members: Fact[];
};


export type Standard = {
  id: string;
  code: string;
  name: string;
  publisher: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type StandardVersion = {
  id: string;
  standard_id: string;
  version_code: string;
  name: string;
  effective_date: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProjectStandardAttachment = {
  id: string;
  is_primary: boolean;
  standard: Pick<Standard, 'id' | 'code' | 'name' | 'publisher'>;
  version: {
    id: string;
    version_code: string;
    name: string;
    effective_date: string | null;
    status: string;
  };
};

export type ProjectDisclosureApplicability =
  | 'APPLICABLE'
  | 'NOT_APPLICABLE'
  | 'UNDETERMINED';

export type ProjectDisclosureCoverage = 'COVERED' | 'PARTIAL' | 'MISSING';

export type ProjectDisclosure = {
  id: string;
  disclosure_id: string;
  code: string;
  title: string;
  description: string | null;
  topic_code: string | null;
  applicability: ProjectDisclosureApplicability;
  coverage_status: ProjectDisclosureCoverage;
  notes: string | null;
};

export type ProjectRequirementStatusValue =
  | 'COVERED'
  | 'PARTIAL'
  | 'MISSING'
  | 'NOT_APPLICABLE';

export type ProjectRequirement = {
  id: string;
  requirement_id: string;
  disclosure_id: string;
  disclosure_code: string;
  disclosure_title: string;
  code: string;
  requirement_type: string;
  content: string;
  guidance: string | null;
  required_data_json: Record<string, unknown>;
  status: ProjectRequirementStatusValue;
  reason: string | null;
};

export type ProjectDisclosureDetail = {
  project_disclosure: ProjectDisclosure;
  requirements: Array<
    Omit<ProjectRequirement, 'disclosure_id' | 'disclosure_code' | 'disclosure_title'>
  >;
  fact_maps: Array<{
    id: string;
    mapping_type: string;
    confidence: string | number | null;
    source_type: string;
    confirmed: boolean;
    fact: Fact;
  }>;
};

export type ProjectDisclosureUpdateInput = {
  applicability?: ProjectDisclosureApplicability;
  notes?: string | null;
};

export type MissingItemStatus =
  | 'MISSING'
  | 'REQUESTED'
  | 'RECEIVED'
  | 'RESOLVED'
  | 'NOT_APPLICABLE';

export type MissingItemPriority = 'LOW' | 'MEDIUM' | 'HIGH';

export type MissingItem = {
  id: string;
  tenant_id: string;
  project_id: string;
  disclosure_id: string | null;
  requirement_id: string | null;
  section_id: string | null;
  name: string;
  description: string | null;
  missing_type: string;
  priority: MissingItemPriority;
  status: MissingItemStatus;
  suggested_material: string | null;
  created_at: string;
  updated_at: string;
};

export type MissingItemUpdateInput = {
  status?: MissingItemStatus;
  priority?: MissingItemPriority;
  suggested_material?: string | null;
};
