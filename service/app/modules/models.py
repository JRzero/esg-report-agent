from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.models import UUIDPKMixin, TimestampMixin, SoftDeleteMixin

JSON = JSONB().with_variant(__import__('sqlalchemy').JSON(), 'sqlite')

class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='app_user'
    email: Mapped[str]=mapped_column(String(320), unique=True, index=True)
    name: Mapped[str]=mapped_column(String(200))
    password_hash: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    is_system_admin: Mapped[bool]=mapped_column(Boolean, default=False)

class Tenant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='tenant'
    name: Mapped[str]=mapped_column(String(200))
    code: Mapped[str]=mapped_column(String(100), unique=True, index=True)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    settings: Mapped[dict]=mapped_column(JSON, default=dict)

class Company(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__='company'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    name: Mapped[str]=mapped_column(String(240), index=True)
    short_name: Mapped[str|None]=mapped_column(String(120), nullable=True)
    registration_no: Mapped[str|None]=mapped_column(String(120), nullable=True)
    industry_code: Mapped[str|None]=mapped_column(String(120), nullable=True)
    country: Mapped[str|None]=mapped_column(String(20), nullable=True)
    region: Mapped[str|None]=mapped_column(String(120), nullable=True)
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class TenantMembership(UUIDPKMixin, Base):
    __tablename__='tenant_membership'
    __table_args__=(UniqueConstraint('tenant_id','user_id'),)
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'), index=True)
    member_type: Mapped[str]=mapped_column(String(20), default='INTERNAL')
    tenant_role: Mapped[str]=mapped_column(String(20), default='MEMBER')
    company_id: Mapped[UUID|None]=mapped_column(ForeignKey('company.id'), nullable=True)
    status: Mapped[str]=mapped_column(String(20), default='ACTIVE')
    joined_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Project(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__='project'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    company_id: Mapped[UUID]=mapped_column(ForeignKey('company.id'), index=True)
    name: Mapped[str]=mapped_column(String(240))
    report_year: Mapped[int]=mapped_column(Integer)
    period_start: Mapped[date]=mapped_column(Date)
    period_end: Mapped[date]=mapped_column(Date)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    owner_membership_id: Mapped[UUID]=mapped_column(ForeignKey('tenant_membership.id'))
    source_project_id: Mapped[UUID|None]=mapped_column(ForeignKey('project.id'), nullable=True)
    settings: Mapped[dict]=mapped_column(JSON, default=dict)

class ProjectMember(UUIDPKMixin, Base):
    __tablename__='project_member'
    __table_args__=(UniqueConstraint('project_id','membership_id'),)
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    membership_id: Mapped[UUID]=mapped_column(ForeignKey('tenant_membership.id'), index=True)
    project_role: Mapped[str]=mapped_column(String(30))
    status: Mapped[str]=mapped_column(String(20), default='ACTIVE')
    joined_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Document(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__='document'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    name: Mapped[str]=mapped_column(String(300))
    source_type: Mapped[str]=mapped_column(String(30), default='EVIDENCE')
    category_code: Mapped[str|None]=mapped_column(String(120), nullable=True)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    sensitivity_level: Mapped[str]=mapped_column(String(30), default='INTERNAL')
    inherited_from_document_id: Mapped[UUID|None]=mapped_column(ForeignKey('document.id'), nullable=True)
    created_by: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'))

class DocumentVersion(UUIDPKMixin, Base):
    __tablename__='document_version'
    __table_args__=(UniqueConstraint('document_id','version_no'),)
    document_id: Mapped[UUID]=mapped_column(ForeignKey('document.id'), index=True)
    version_no: Mapped[int]=mapped_column(Integer)
    original_filename: Mapped[str]=mapped_column(String(300))
    mime_type: Mapped[str|None]=mapped_column(String(120), nullable=True)
    file_extension: Mapped[str|None]=mapped_column(String(30), nullable=True)
    file_size: Mapped[int]=mapped_column(Integer)
    object_key: Mapped[str]=mapped_column(String(800), unique=True)
    sha256: Mapped[str]=mapped_column(String(64), index=True)
    validation_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    evidence_parse_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    context_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    classification_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    fact_extraction_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    parse_error: Mapped[str|None]=mapped_column(Text, nullable=True)
    uploaded_by: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'))
    uploaded_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class DocumentAnchor(UUIDPKMixin, Base):
    __tablename__='document_anchor'
    __table_args__=(UniqueConstraint('document_version_id','content_hash'),)
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    document_version_id: Mapped[UUID]=mapped_column(ForeignKey('document_version.id'), index=True)
    anchor_type: Mapped[str]=mapped_column(String(40), index=True)
    page_start: Mapped[int|None]=mapped_column(Integer, nullable=True)
    page_end: Mapped[int|None]=mapped_column(Integer, nullable=True)
    sheet_name: Mapped[str|None]=mapped_column(String(200), nullable=True)
    cell_range: Mapped[str|None]=mapped_column(String(100), nullable=True)
    heading_path: Mapped[list|None]=mapped_column(JSON, nullable=True)
    paragraph_start: Mapped[int|None]=mapped_column(Integer, nullable=True)
    paragraph_end: Mapped[int|None]=mapped_column(Integer, nullable=True)
    slide_number: Mapped[int|None]=mapped_column(Integer, nullable=True)
    bbox: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    raw_text: Mapped[str]=mapped_column(Text)
    normalized_text: Mapped[str|None]=mapped_column(Text, nullable=True)
    content_hash: Mapped[str]=mapped_column(String(64), index=True)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class ContextBinding(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='context_binding'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID|None]=mapped_column(ForeignKey('project.id'), nullable=True, index=True)
    provider: Mapped[str]=mapped_column(String(40), default='OPENVIKING')
    resource_type: Mapped[str]=mapped_column(String(40))
    resource_id: Mapped[UUID]=mapped_column(index=True)
    uri: Mapped[str|None]=mapped_column(Text, nullable=True)
    processing_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    external_task_id: Mapped[str|None]=mapped_column(String(200), nullable=True)
    retry_count: Mapped[int]=mapped_column(Integer, default=0)
    last_error: Mapped[str|None]=mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class MetricDefinition(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='metric_definition'
    __table_args__=(UniqueConstraint('tenant_id','code'),)
    tenant_id: Mapped[UUID|None]=mapped_column(ForeignKey('tenant.id'), nullable=True)
    code: Mapped[str]=mapped_column(String(120), index=True)
    name: Mapped[str]=mapped_column(String(240))
    category: Mapped[str|None]=mapped_column(String(120), nullable=True)
    data_type: Mapped[str]=mapped_column(String(30))
    default_unit: Mapped[str|None]=mapped_column(String(40), nullable=True)
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class Fact(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__='fact'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    fact_type: Mapped[str]=mapped_column(String(40))
    metric_definition_id: Mapped[UUID|None]=mapped_column(ForeignKey('metric_definition.id'), nullable=True)
    semantic_key: Mapped[str]=mapped_column(String(500), index=True)
    name: Mapped[str]=mapped_column(String(300))
    value_type: Mapped[str]=mapped_column(String(20))
    number_value: Mapped[Decimal|None]=mapped_column(Numeric(30,10), nullable=True)
    text_value: Mapped[str|None]=mapped_column(Text, nullable=True)
    boolean_value: Mapped[bool|None]=mapped_column(Boolean, nullable=True)
    date_value: Mapped[date|None]=mapped_column(Date, nullable=True)
    json_value: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    raw_value: Mapped[str|None]=mapped_column(Text, nullable=True)
    unit: Mapped[str|None]=mapped_column(String(60), nullable=True)
    period_start: Mapped[date|None]=mapped_column(Date, nullable=True)
    period_end: Mapped[date|None]=mapped_column(Date, nullable=True)
    entity_scope: Mapped[str|None]=mapped_column(String(160), nullable=True)
    dimensions: Mapped[dict]=mapped_column(JSON, default=dict)
    status: Mapped[str]=mapped_column(String(30), default='PENDING', index=True)
    confidence: Mapped[Decimal|None]=mapped_column(Numeric(5,4), nullable=True)
    source_type: Mapped[str]=mapped_column(String(30), default='AI')
    confirmed_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    confirmed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

class FactEvidence(UUIDPKMixin, Base):
    __tablename__='fact_evidence'
    __table_args__=(UniqueConstraint('fact_id','document_anchor_id'),)
    fact_id: Mapped[UUID]=mapped_column(ForeignKey('fact.id'), index=True)
    document_anchor_id: Mapped[UUID]=mapped_column(ForeignKey('document_anchor.id'), index=True)
    evidence_role: Mapped[str]=mapped_column(String(30), default='PRIMARY')
    confidence: Mapped[Decimal|None]=mapped_column(Numeric(5,4), nullable=True)
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)

class FactRevision(UUIDPKMixin, Base):
    __tablename__='fact_revision'
    __table_args__=(UniqueConstraint('fact_id','revision_no'),)
    fact_id: Mapped[UUID]=mapped_column(ForeignKey('fact.id'), index=True)
    revision_no: Mapped[int]=mapped_column(Integer)
    snapshot: Mapped[dict]=mapped_column(JSON)
    change_type: Mapped[str]=mapped_column(String(40))
    changed_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FactConflictGroup(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='fact_conflict_group'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    semantic_key: Mapped[str]=mapped_column(String(500), index=True)
    conflict_type: Mapped[str]=mapped_column(String(30), default='VALUE')
    status: Mapped[str]=mapped_column(String(30), default='OPEN')
    resolved_fact_id: Mapped[UUID|None]=mapped_column(ForeignKey('fact.id'), nullable=True)
    resolved_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    resolved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

class FactConflictMember(Base):
    __tablename__='fact_conflict_member'
    conflict_group_id: Mapped[UUID]=mapped_column(ForeignKey('fact_conflict_group.id'), primary_key=True)
    fact_id: Mapped[UUID]=mapped_column(ForeignKey('fact.id'), primary_key=True)

class Standard(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='standard'
    code: Mapped[str]=mapped_column(String(60), unique=True)
    name: Mapped[str]=mapped_column(String(240))
    publisher: Mapped[str|None]=mapped_column(String(240), nullable=True)
    description: Mapped[str|None]=mapped_column(Text, nullable=True)

class StandardVersion(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='standard_version'
    standard_id: Mapped[UUID]=mapped_column(ForeignKey('standard.id'), index=True)
    version_code: Mapped[str]=mapped_column(String(80))
    name: Mapped[str]=mapped_column(String(240))
    effective_date: Mapped[date|None]=mapped_column(Date, nullable=True)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class Disclosure(UUIDPKMixin, Base):
    __tablename__='disclosure'
    standard_version_id: Mapped[UUID]=mapped_column(ForeignKey('standard_version.id'), index=True)
    code: Mapped[str]=mapped_column(String(80), index=True)
    title: Mapped[str]=mapped_column(String(500))
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    topic_code: Mapped[str|None]=mapped_column(String(100), nullable=True)
    sort_order: Mapped[int]=mapped_column(Integer, default=0)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class DisclosureRequirement(UUIDPKMixin, Base):
    __tablename__='disclosure_requirement'
    disclosure_id: Mapped[UUID]=mapped_column(ForeignKey('disclosure.id'), index=True)
    requirement_code: Mapped[str]=mapped_column(String(100))
    requirement_type: Mapped[str]=mapped_column(String(30), default='REQUIRED')
    content: Mapped[str]=mapped_column(Text)
    guidance: Mapped[str|None]=mapped_column(Text, nullable=True)
    required_data_json: Mapped[dict]=mapped_column(JSON, default=dict)
    sort_order: Mapped[int]=mapped_column(Integer, default=0)

class ProjectStandard(UUIDPKMixin, Base):
    __tablename__='project_standard'
    __table_args__=(UniqueConstraint('project_id','standard_version_id'),)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    standard_version_id: Mapped[UUID]=mapped_column(ForeignKey('standard_version.id'))
    is_primary: Mapped[bool]=mapped_column(Boolean, default=False)

class ProjectDisclosure(UUIDPKMixin, Base):
    __tablename__='project_disclosure'
    __table_args__=(UniqueConstraint('project_id','disclosure_id'),)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    disclosure_id: Mapped[UUID]=mapped_column(ForeignKey('disclosure.id'), index=True)
    applicability: Mapped[str]=mapped_column(String(30), default='UNDETERMINED')
    coverage_status: Mapped[str]=mapped_column(String(30), default='MISSING')
    notes: Mapped[str|None]=mapped_column(Text, nullable=True)

class ProjectRequirementStatus(UUIDPKMixin, Base):
    __tablename__='project_requirement_status'
    __table_args__=(UniqueConstraint('project_id','requirement_id'),)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    requirement_id: Mapped[UUID]=mapped_column(ForeignKey('disclosure_requirement.id'), index=True)
    status: Mapped[str]=mapped_column(String(30), default='MISSING')
    reason: Mapped[str|None]=mapped_column(Text, nullable=True)

class DisclosureFactMap(UUIDPKMixin, Base):
    __tablename__='disclosure_fact_map'
    __table_args__=(UniqueConstraint('project_id','disclosure_id','fact_id'),)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    disclosure_id: Mapped[UUID]=mapped_column(ForeignKey('disclosure.id'), index=True)
    fact_id: Mapped[UUID]=mapped_column(ForeignKey('fact.id'), index=True)
    mapping_type: Mapped[str]=mapped_column(String(30), default='DIRECT')
    confidence: Mapped[Decimal|None]=mapped_column(Numeric(5,4), nullable=True)
    source_type: Mapped[str]=mapped_column(String(30), default='RULE')
    confirmed: Mapped[bool]=mapped_column(Boolean, default=False)

class ReportTemplate(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='report_template'
    tenant_id: Mapped[UUID|None]=mapped_column(ForeignKey('tenant.id'), nullable=True, index=True)
    name: Mapped[str]=mapped_column(String(240))
    template_type: Mapped[str]=mapped_column(String(30), default='TENANT')
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)

class ReportTemplateVersion(UUIDPKMixin, Base):
    __tablename__='report_template_version'
    __table_args__=(UniqueConstraint('template_id','version_no'),)
    template_id: Mapped[UUID]=mapped_column(ForeignKey('report_template.id'), index=True)
    version_no: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    source_type: Mapped[str]=mapped_column(String(30), default='MANUAL')
    source_document_id: Mapped[UUID|None]=mapped_column(ForeignKey('document.id'), nullable=True)
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ReportTemplateSection(UUIDPKMixin, Base):
    __tablename__='report_template_section'
    template_version_id: Mapped[UUID]=mapped_column(ForeignKey('report_template_version.id'), index=True)
    parent_id: Mapped[UUID|None]=mapped_column(ForeignKey('report_template_section.id'), nullable=True)
    title: Mapped[str]=mapped_column(String(500))
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    level: Mapped[int]=mapped_column(Integer, default=1)
    sort_order: Mapped[int]=mapped_column(Integer, default=0)
    writing_guidance: Mapped[str|None]=mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class Report(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='report'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    template_version_id: Mapped[UUID|None]=mapped_column(ForeignKey('report_template_version.id'), nullable=True)
    title: Mapped[str]=mapped_column(String(500))
    language: Mapped[str]=mapped_column(String(20), default='zh-CN')
    status: Mapped[str]=mapped_column(String(30), default='DRAFT')
    created_by: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'))

class ReportSection(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='report_section'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    report_id: Mapped[UUID]=mapped_column(ForeignKey('report.id'), index=True)
    parent_id: Mapped[UUID|None]=mapped_column(ForeignKey('report_section.id'), nullable=True)
    source_template_section_id: Mapped[UUID|None]=mapped_column(ForeignKey('report_template_section.id'), nullable=True)
    title: Mapped[str]=mapped_column(String(500))
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    level: Mapped[int]=mapped_column(Integer, default=1)
    sort_order: Mapped[int]=mapped_column(Integer, default=0)
    status: Mapped[str]=mapped_column(String(30), default='NOT_STARTED')
    writing_plan: Mapped[dict]=mapped_column(JSON, default=dict)

class SectionDisclosureMap(UUIDPKMixin, Base):
    __tablename__='section_disclosure_map'
    __table_args__=(UniqueConstraint('section_id','disclosure_id'),)
    section_id: Mapped[UUID]=mapped_column(ForeignKey('report_section.id'), index=True)
    disclosure_id: Mapped[UUID]=mapped_column(ForeignKey('disclosure.id'), index=True)
    mapping_type: Mapped[str]=mapped_column(String(30), default='DIRECT')

class ReportBlock(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__='report_block'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    section_id: Mapped[UUID]=mapped_column(ForeignKey('report_section.id'), index=True)
    block_type: Mapped[str]=mapped_column(String(30), default='PARAGRAPH')
    sort_order: Mapped[int]=mapped_column(Integer, default=0)
    current_content: Mapped[str]=mapped_column(Text, default='')
    current_content_json: Mapped[dict]=mapped_column(JSON, default=dict)
    current_revision_no: Mapped[int]=mapped_column(Integer, default=0)
    source_type: Mapped[str]=mapped_column(String(30), default='HUMAN')
    created_by: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'))
    updated_by: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'))

class ReportBlockRevision(UUIDPKMixin, Base):
    __tablename__='report_block_revision'
    __table_args__=(UniqueConstraint('block_id','revision_no'),)
    block_id: Mapped[UUID]=mapped_column(ForeignKey('report_block.id'), index=True)
    revision_no: Mapped[int]=mapped_column(Integer)
    content: Mapped[str]=mapped_column(Text)
    content_json: Mapped[dict]=mapped_column(JSON, default=dict)
    source_type: Mapped[str]=mapped_column(String(30), default='AI')
    change_reason: Mapped[str|None]=mapped_column(Text, nullable=True)
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    ai_task_id: Mapped[UUID|None]=mapped_column(ForeignKey('ai_task.id', use_alter=True), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Claim(UUIDPKMixin, Base):
    __tablename__='claim'
    block_revision_id: Mapped[UUID]=mapped_column(ForeignKey('report_block_revision.id'), index=True)
    claim_text: Mapped[str]=mapped_column(Text)
    claim_type: Mapped[str]=mapped_column(String(30), default='FACTUAL')
    start_offset: Mapped[int|None]=mapped_column(Integer, nullable=True)
    end_offset: Mapped[int|None]=mapped_column(Integer, nullable=True)
    verification_status: Mapped[str]=mapped_column(String(30), default='PENDING')
    risk_level: Mapped[str]=mapped_column(String(20), default='MEDIUM')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Citation(UUIDPKMixin, Base):
    __tablename__='citation'
    claim_id: Mapped[UUID]=mapped_column(ForeignKey('claim.id'), index=True)
    citation_type: Mapped[str]=mapped_column(String(30), default='FACT')
    fact_id: Mapped[UUID|None]=mapped_column(ForeignKey('fact.id'), nullable=True)
    fact_evidence_id: Mapped[UUID|None]=mapped_column(ForeignKey('fact_evidence.id'), nullable=True)
    document_anchor_id: Mapped[UUID|None]=mapped_column(ForeignKey('document_anchor.id'), nullable=True)
    disclosure_requirement_id: Mapped[UUID|None]=mapped_column(ForeignKey('disclosure_requirement.id'), nullable=True)
    status: Mapped[str]=mapped_column(String(30), default='ACTIVE')
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MissingItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__='missing_item'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('project.id'), index=True)
    disclosure_id: Mapped[UUID|None]=mapped_column(ForeignKey('disclosure.id'), nullable=True)
    requirement_id: Mapped[UUID|None]=mapped_column(ForeignKey('disclosure_requirement.id'), nullable=True)
    section_id: Mapped[UUID|None]=mapped_column(ForeignKey('report_section.id'), nullable=True)
    name: Mapped[str]=mapped_column(String(500))
    description: Mapped[str|None]=mapped_column(Text, nullable=True)
    missing_type: Mapped[str]=mapped_column(String(30), default='DATA')
    priority: Mapped[str]=mapped_column(String(20), default='MEDIUM')
    status: Mapped[str]=mapped_column(String(30), default='MISSING')
    suggested_material: Mapped[str|None]=mapped_column(Text, nullable=True)

class AITask(UUIDPKMixin, Base):
    __tablename__='ai_task'
    __table_args__=(UniqueConstraint('tenant_id','idempotency_key'),)
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID|None]=mapped_column(ForeignKey('project.id'), nullable=True, index=True)
    task_type: Mapped[str]=mapped_column(String(60), index=True)
    target_type: Mapped[str|None]=mapped_column(String(60), nullable=True)
    target_id: Mapped[UUID|None]=mapped_column(nullable=True)
    status: Mapped[str]=mapped_column(String(30), default='PENDING', index=True)
    progress: Mapped[Decimal]=mapped_column(Numeric(5,4), default=0)
    stage: Mapped[str|None]=mapped_column(String(120), nullable=True)
    input_json: Mapped[dict]=mapped_column(JSON, default=dict)
    result_json: Mapped[dict]=mapped_column(JSON, default=dict)
    error_code: Mapped[str|None]=mapped_column(String(120), nullable=True)
    error_message: Mapped[str|None]=mapped_column(Text, nullable=True)
    trace_id: Mapped[str|None]=mapped_column(String(120), nullable=True, index=True)
    idempotency_key: Mapped[str|None]=mapped_column(String(500), nullable=True)
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

class AITrace(UUIDPKMixin, Base):
    __tablename__='ai_trace'
    ai_task_id: Mapped[UUID]=mapped_column(ForeignKey('ai_task.id'), index=True)
    skill_name: Mapped[str]=mapped_column(String(120))
    skill_version: Mapped[str]=mapped_column(String(40))
    prompt_version: Mapped[str]=mapped_column(String(40))
    model_provider: Mapped[str|None]=mapped_column(String(80), nullable=True)
    model_name: Mapped[str|None]=mapped_column(String(160), nullable=True)
    input_tokens: Mapped[int|None]=mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int|None]=mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal|None]=mapped_column(Numeric(18,8), nullable=True)
    latency_ms: Mapped[int|None]=mapped_column(Integer, nullable=True)
    result_status: Mapped[str]=mapped_column(String(30), default='SUCCESS')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AITraceContext(UUIDPKMixin, Base):
    __tablename__='ai_trace_context'
    trace_id: Mapped[UUID]=mapped_column(ForeignKey('ai_trace.id'), index=True)
    context_type: Mapped[str]=mapped_column(String(40))
    resource_type: Mapped[str]=mapped_column(String(60))
    resource_id: Mapped[UUID|None]=mapped_column(nullable=True)
    context_binding_id: Mapped[UUID|None]=mapped_column(ForeignKey('context_binding.id'), nullable=True)
    openviking_uri: Mapped[str|None]=mapped_column(Text, nullable=True)
    trust_level: Mapped[str]=mapped_column(String(40))
    rank: Mapped[int|None]=mapped_column(Integer, nullable=True)
    score: Mapped[Decimal|None]=mapped_column(Numeric(10,6), nullable=True)
    metadata_json: Mapped[dict]=mapped_column('metadata', JSON, default=dict)

class ReportExport(UUIDPKMixin, Base):
    __tablename__='report_export'
    report_id: Mapped[UUID]=mapped_column(ForeignKey('report.id'), index=True)
    format: Mapped[str]=mapped_column(String(20), default='DOCX')
    status: Mapped[str]=mapped_column(String(30), default='PENDING')
    object_key: Mapped[str|None]=mapped_column(String(800), nullable=True)
    template_config: Mapped[dict]=mapped_column(JSON, default=dict)
    created_by: Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id'), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

class AuditLog(UUIDPKMixin, Base):
    __tablename__='audit_log'
    tenant_id: Mapped[UUID]=mapped_column(ForeignKey('tenant.id'), index=True)
    project_id: Mapped[UUID|None]=mapped_column(ForeignKey('project.id'), nullable=True, index=True)
    user_id: Mapped[UUID]=mapped_column(ForeignKey('app_user.id'), index=True)
    action: Mapped[str]=mapped_column(String(80), index=True)
    resource_type: Mapped[str]=mapped_column(String(80))
    resource_id: Mapped[UUID|None]=mapped_column(nullable=True)
    before_data: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    after_data: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    request_id: Mapped[str|None]=mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
