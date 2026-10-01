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
