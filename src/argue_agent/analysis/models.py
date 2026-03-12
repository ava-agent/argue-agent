from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    FACTUAL = "factual"
    STATISTICAL = "statistical"
    CAUSAL = "causal"
    QUOTE = "quote"


class VerdictLevel(str, Enum):
    VERIFIED = "verified"
    MOSTLY_TRUE = "mostly_true"
    QUESTIONABLE = "questionable"
    MOSTLY_FALSE = "mostly_false"
    FALSE = "false"
    UNVERIFIABLE = "unverifiable"


class TranscriptSegment(BaseModel):
    text: str
    is_final: bool = False
    confidence: float = 0.0
    speaker: int | None = None


class Utterance(BaseModel):
    text: str
    speaker: str = "opponent"
    timestamp: datetime = Field(default_factory=datetime.now)


class Claim(BaseModel):
    original_text: str = Field(description="原始发言片段")
    normalized_claim: str = Field(description="规范化的论点表述")
    claim_type: ClaimType = Field(description="论点类型")
    search_queries: list[str] = Field(description="用于搜索验证的查询词，1-3个")
    confidence: float = Field(description="该论点可验证的置信度，0-1")


class ArgumentExtraction(BaseModel):
    claims: list[Claim] = Field(default_factory=list, description="提取的可验证论点")
    main_argument: str = Field(default="", description="对方的主要论点概括")


class Evidence(BaseModel):
    source_title: str
    source_url: str
    relevant_excerpt: str
    supports_claim: bool


class FactVerdict(BaseModel):
    claim: Claim
    verdict: VerdictLevel
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    summary: str = Field(description="一句话总结判定结果")
    suggested_rebuttal: str = Field(default="", description="反驳建议")
    timestamp: datetime = Field(default_factory=datetime.now)
