from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
class FactCandidate(BaseModel):
    fact_type:str='METRIC'; metric_code:str|None=None; name:str; value_type:str; number_value:Decimal|None=None; text_value:str|None=None; boolean_value:bool|None=None; raw_value:str|None=None; unit:str|None=None; period_start:date|None=None; period_end:date|None=None; entity_scope:str|None=None; dimensions:dict=Field(default_factory=dict); anchor_ids:list[UUID]; confidence:float=0.5
class FactExtractionResult(BaseModel): facts:list[FactCandidate]
class SectionPlan(BaseModel): goal:str; recommended_structure:list[str]=Field(default_factory=list); key_messages:list[str]=Field(default_factory=list); disclosure_ids:list[UUID]=Field(default_factory=list); requirement_ids:list[UUID]=Field(default_factory=list); fact_ids:list[UUID]=Field(default_factory=list); evidence_anchor_ids:list[UUID]=Field(default_factory=list); missing_item_ids:list[UUID]=Field(default_factory=list); missing_items:list[str]=Field(default_factory=list); warnings:list[str]=Field(default_factory=list)
class ClaimDraft(BaseModel): text:str; claim_type:str='FACTUAL'; risk_level:str='MEDIUM'; fact_ids:list[UUID]=Field(default_factory=list)
class DraftBlock(BaseModel): type:str='PARAGRAPH'; content:str; claims:list[ClaimDraft]=Field(default_factory=list)
class SectionDraft(BaseModel): blocks:list[DraftBlock]; warnings:list[str]=Field(default_factory=list)
