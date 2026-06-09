from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ThesisCreate(BaseModel):
    ticker: str
    direction: str = Field(default="long", pattern="^(long|short)$")
    target_price: Optional[float] = None
    time_horizon_months: Optional[int] = None
    thesis_text: str = ""
    catalysts: list[str] = []
    risks: list[str] = []
    conviction: Optional[int] = Field(default=None, ge=1, le=10)
    entry_price: Optional[float] = None
    entry_date: Optional[date] = None


class ThesisUpdate(BaseModel):
    direction: Optional[str] = Field(default=None, pattern="^(long|short)$")
    target_price: Optional[float] = None
    time_horizon_months: Optional[int] = None
    thesis_text: Optional[str] = None
    catalysts: Optional[list[str]] = None
    risks: Optional[list[str]] = None
    conviction: Optional[int] = Field(default=None, ge=1, le=10)
    status: Optional[str] = Field(default=None, pattern="^(active|closed)$")
    entry_price: Optional[float] = None
    entry_date: Optional[date] = None


class ThesisOut(BaseModel):
    id: int
    ticker: str
    direction: str
    target_price: Optional[float]
    time_horizon_months: Optional[int]
    thesis_text: str
    catalysts: list
    risks: list
    conviction: Optional[int]
    status: str
    entry_price: Optional[float]
    entry_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ThesisDraftRequest(BaseModel):
    ticker: str
    direction: str = Field(default="long", pattern="^(long|short)$")
    notes: str = ""


class MemoOut(BaseModel):
    id: int
    ticker: str
    title: str
    content_md: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoGenerateRequest(BaseModel):
    ticker: str


class ChatRequest(BaseModel):
    messages: list[dict]  # [{role, content}] — content may be string or block list
