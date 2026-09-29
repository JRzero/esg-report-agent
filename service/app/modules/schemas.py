from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ORMModel(BaseModel):
    model_config=ConfigDict(from_attributes=True)
class Page(BaseModel):
    items:list
    page:int
    page_size:int
    total:int
class LoginRequest(BaseModel): email: EmailStr; password: str
class TokenResponse(BaseModel): access_token:str; refresh_token:str; token_type:str='bearer'; expires_in:int
class CompanyCreate(BaseModel):
    name:str; short_name:str|None=None; registration_no:str|None=None; industry_code:str|None=None; country:str|None=None; region:str|None=None; description:str|None=None
class CompanyRead(CompanyCreate, ORMModel): id:UUID; tenant_id:UUID; created_at:datetime; updated_at:datetime
class ProjectCreate(BaseModel):
    company_id:UUID; name:str; report_year:int; period_start:date; period_end:date; source_project_id:UUID|None=None
class ProjectRead(ProjectCreate, ORMModel): id:UUID; tenant_id:UUID; status:str; owner_membership_id:UUID; created_at:datetime; updated_at:datetime
class ProjectMemberCreate(BaseModel): membership_id:UUID; project_role:str
class ProjectMemberRead(ProjectMemberCreate, ORMModel): id:UUID; project_id:UUID; tenant_id:UUID; status:str
class FactCreate(BaseModel):
    fact_type:str='METRIC'; metric_definition_id:UUID|None=None; metric_code:str|None=None; name:str; value_type:str; number_value:Decimal|None=None; text_value:str|None=None; boolean_value:bool|None=None; date_value:date|None=None; json_value:dict|None=None; raw_value:str|None=None; unit:str|None=None; period_start:date|None=None; period_end:date|None=None; entity_scope:str|None=None; dimensions:dict=Field(default_factory=dict); anchor_ids:list[UUID]=Field(default_factory=list); source_type:str='HUMAN'
class FactRead(FactCreate, ORMModel): id:UUID; tenant_id:UUID; project_id:UUID; semantic_key:str; status:str; confidence:Decimal|None=None; confirmed_by:UUID|None=None; confirmed_at:datetime|None=None
class ReportCreate(BaseModel): title:str; template_version_id:UUID|None=None; language:str='zh-CN'
class ReportRead(ReportCreate, ORMModel): id:UUID; tenant_id:UUID; project_id:UUID; status:str
class SectionCreate(BaseModel): title:str; parent_id:UUID|None=None; level:int=1; sort_order:int=0; description:str|None=None
class SectionRead(SectionCreate, ORMModel): id:UUID; report_id:UUID; project_id:UUID; status:str; writing_plan:dict
class TaskRead(ORMModel): id:UUID; task_type:str; status:str; progress:Decimal; stage:str|None=None; result_json:dict; error_code:str|None=None; error_message:str|None=None

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    member_type: str = 'INTERNAL'
    tenant_role: str = 'MEMBER'
    company_id: UUID | None = None
class UserRead(ORMModel):
    id: UUID
    email: EmailStr
    name: str
    status: str
class MembershipRead(ORMModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    member_type: str
    tenant_role: str
    company_id: UUID | None
    status: str
class RefreshRequest(BaseModel):
    refresh_token: str


class CompanyUpdate(BaseModel):
    name:str|None=None
    short_name:str|None=None
    registration_no:str|None=None
    industry_code:str|None=None
    country:str|None=None
    region:str|None=None
    description:str|None=None

class MembershipUpdate(BaseModel):
    tenant_role:str|None=None
    member_type:str|None=None
    company_id:UUID|None=None
    status:str|None=None

class ProjectUpdate(BaseModel):
    name:str|None=None
    report_year:int|None=None
    period_start:date|None=None
    period_end:date|None=None
    status:str|None=None

class ProjectMemberUpdate(BaseModel):
    project_role:str

class TransferOwnerRequest(BaseModel):
    membership_id:UUID

class FactUpdate(BaseModel):
    name:str|None=None
    value_type:str|None=None
    number_value:Decimal|None=None
    text_value:str|None=None
    boolean_value:bool|None=None
    date_value:date|None=None
    json_value:dict|None=None
    raw_value:str|None=None
    unit:str|None=None
    period_start:date|None=None
    period_end:date|None=None
    entity_scope:str|None=None
    dimensions:dict|None=None

class FactRejectRequest(BaseModel):
    reason:str=Field(min_length=1,max_length=1000)

class FactEvidenceCreate(BaseModel):
    anchor_id:UUID
    evidence_role:str='PRIMARY'

class ConflictResolveRequest(BaseModel):
    fact_id:UUID
    reason:str|None=None

class MissingItemUpdate(BaseModel):
    status:str|None=None
    priority:str|None=None
    suggested_material:str|None=None

class ReportTemplateCreate(BaseModel):
    name:str
    description:str|None=None

class ReportTemplateVersionCreate(BaseModel):
    source_type:str='MANUAL'
    source_document_id:UUID|None=None

class TemplateSectionCreate(BaseModel):
    title:str
    parent_id:UUID|None=None
    description:str|None=None
    level:int=1
    sort_order:int=0
    writing_guidance:str|None=None

class ReportUpdate(BaseModel):
    title:str|None=None
    language:str|None=None
    status:str|None=None

class SectionUpdate(BaseModel):
    title:str|None=None
    parent_id:UUID|None=None
    description:str|None=None
    level:int|None=None
    sort_order:int|None=None
    status:str|None=None

class SectionReorderItem(BaseModel):
    section_id:UUID
    parent_id:UUID|None=None
    sort_order:int

class SectionReorderRequest(BaseModel):
    items:list[SectionReorderItem]

class SectionDisclosureCreate(BaseModel):
    disclosure_id:UUID
    mapping_type:str='DIRECT'

class BlockCreate(BaseModel):
    block_type:str='PARAGRAPH'
    sort_order:int=0
    content:str=''
    content_json:dict=Field(default_factory=dict)

class BlockUpdate(BaseModel):
    content:str
    content_json:dict=Field(default_factory=dict)
    change_reason:str|None=None

class CommentCreate(BaseModel):
    body:str=Field(min_length=1,max_length=10000)
    section_id:UUID|None=None
    block_id:UUID|None=None
    parent_id:UUID|None=None

class ExportRequest(BaseModel):
    format:str='DOCX'
