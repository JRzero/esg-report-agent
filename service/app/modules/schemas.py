from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list
    page: int
    page_size: int
    total: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=256)
    member_type: Literal["INTERNAL", "CLIENT"] = "INTERNAL"
    tenant_role: Literal["ADMIN", "MEMBER"] = "MEMBER"
    company_id: UUID | None = None

    @model_validator(mode="after")
    def validate_client_company(self):
        if self.member_type == "CLIENT" and not self.company_id:
            raise ValueError("CLIENT member requires company_id")
        return self


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


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    short_name: str | None = Field(default=None, max_length=120)
    registration_no: str | None = Field(default=None, max_length=120)
    industry_code: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=20)
    region: str | None = Field(default=None, max_length=120)
    description: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    short_name: str | None = Field(default=None, max_length=120)
    registration_no: str | None = Field(default=None, max_length=120)
    industry_code: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=20)
    region: str | None = Field(default=None, max_length=120)
    description: str | None = None


class CompanyRead(CompanyCreate, ORMModel):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=240)
    report_year: int = Field(ge=2000, le=2200)
    period_start: date
    period_end: date
    source_project_id: UUID | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_start > self.period_end:
            raise ValueError("period_start must not exceed period_end")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    report_year: int | None = Field(default=None, ge=2000, le=2200)
    period_start: date | None = None
    period_end: date | None = None
    status: Literal["ACTIVE", "ARCHIVED"] | None = None


class ProjectRead(ProjectCreate, ORMModel):
    id: UUID
    tenant_id: UUID
    status: str
    owner_membership_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectMemberCreate(BaseModel):
    membership_id: UUID
    project_role: Literal["OWNER", "EDITOR", "REVIEWER", "CLIENT_MEMBER"]


class ProjectMemberUpdate(BaseModel):
    project_role: Literal["EDITOR", "REVIEWER", "CLIENT_MEMBER"]


class ProjectMemberRead(ProjectMemberCreate, ORMModel):
    id: UUID
    project_id: UUID
    tenant_id: UUID
    status: str


class TransferOwnerRequest(BaseModel):
    membership_id: UUID


class FactCreate(BaseModel):
    fact_type: str = "METRIC"
    metric_definition_id: UUID | None = None
    metric_code: str | None = None
    name: str = Field(min_length=1, max_length=300)
    value_type: Literal["NUMBER", "TEXT", "BOOLEAN", "DATE", "JSON"]
    number_value: Decimal | None = None
    text_value: str | None = None
    boolean_value: bool | None = None
    date_value: date | None = None
    json_value: dict | None = None
    raw_value: str | None = None
    unit: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    entity_scope: str | None = None
    dimensions: dict = Field(default_factory=dict)
    anchor_ids: list[UUID] = Field(default_factory=list)
    source_type: Literal["HUMAN", "AI"] = "HUMAN"

    @model_validator(mode="after")
    def validate_value(self):
        value_map = {
            "NUMBER": self.number_value,
            "TEXT": self.text_value,
            "BOOLEAN": self.boolean_value,
            "DATE": self.date_value,
            "JSON": self.json_value,
        }
        if value_map[self.value_type] is None:
            raise ValueError(f"{self.value_type} fact requires matching value field")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start must not exceed period_end")
        return self


class FactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    number_value: Decimal | None = None
    text_value: str | None = None
    boolean_value: bool | None = None
    date_value: date | None = None
    json_value: dict | None = None
    raw_value: str | None = None
    unit: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    entity_scope: str | None = None
    dimensions: dict | None = None


class FactRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class FactRead(FactCreate, ORMModel):
    id: UUID
    tenant_id: UUID
    project_id: UUID
    semantic_key: str
    status: str
    confidence: Decimal | None = None
    confirmed_by: UUID | None = None
    confirmed_at: datetime | None = None


class ProjectDisclosureUpdate(BaseModel):
    applicability: Literal["APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED"] | None = None
    notes: str | None = Field(default=None, max_length=4000)


class MissingItemUpdate(BaseModel):
    status: Literal[
        "MISSING",
        "REQUESTED",
        "RECEIVED",
        "RESOLVED",
        "NOT_APPLICABLE",
    ] | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    suggested_material: str | None = None


class ReportTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = None


class ReportTemplateVersionCreate(BaseModel):
    source_type: Literal["MANUAL", "CLONED", "EXTRACTED"] = "MANUAL"
    source_document_id: UUID | None = None


class TemplateSectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    parent_id: UUID | None = None
    level: int = Field(default=1, ge=1, le=9)
    sort_order: int = 0
    description: str | None = None
    writing_guidance: str | None = None


class ReportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    template_version_id: UUID | None = None
    language: str = "zh-CN"


class ReportRead(ReportCreate, ORMModel):
    id: UUID
    tenant_id: UUID
    project_id: UUID
    status: str


class SectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    parent_id: UUID | None = None
    level: int = Field(default=1, ge=1, le=9)
    sort_order: int = 0
    description: str | None = None


class SectionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    parent_id: UUID | None = None
    level: int | None = Field(default=None, ge=1, le=9)
    sort_order: int | None = None
    description: str | None = None
    status: Literal["NOT_STARTED", "GENERATING", "DRAFT", "COMPLETED"] | None = None


class SectionRead(SectionCreate, ORMModel):
    id: UUID
    report_id: UUID
    project_id: UUID
    status: str
    writing_plan: dict


class BlockCreate(BaseModel):
    block_type: Literal["PARAGRAPH", "HEADING", "TABLE", "KPI", "IMAGE"] = "PARAGRAPH"
    sort_order: int = 0
    content: str = ""
    content_json: dict = Field(default_factory=dict)


class BlockUpdate(BaseModel):
    content: str
    content_json: dict = Field(default_factory=dict)
    change_reason: str | None = None


class TaskRead(ORMModel):
    id: UUID
    task_type: str
    status: str
    progress: Decimal
    stage: str | None = None
    result_json: dict
    error_code: str | None = None
    error_message: str | None = None


class ClaimVerifyResponse(BaseModel):
    claim_id: UUID
    status: str
    reasons: list[str] = Field(default_factory=list)
