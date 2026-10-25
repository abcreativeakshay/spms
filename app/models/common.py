"""Shared schema primitives."""

from __future__ import annotations

from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

IsoDate = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]

T = TypeVar("T")


class CamelModel(BaseModel):
    """snake_case in Python, camelCase on the wire and in Firestore."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
    )


class PageResponse(CamelModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


class MessageResponse(CamelModel):
    message: str
    details: dict[str, Any] | None = None


class ListResponse(CamelModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None


class Links(CamelModel):
    github: str | None = None
    linkedin: str | None = None
    portfolio: str | None = None


class Project(CamelModel):
    title: str
    description: str | None = None
    url: str | None = None
    tech: list[str] = Field(default_factory=list)


class Certification(CamelModel):
    name: str
    issuer: str | None = None
    year: int | None = None
    url: str | None = None


class Eligibility(CamelModel):
    min_cgpa: float = Field(default=0.0, ge=0, le=10)
    min_attendance: float = Field(default=0.0, ge=0, le=100)
    min_assessment_avg: float = Field(default=0.0, ge=0, le=100)
    batch_ids: list[str] = Field(default_factory=list)
    college_ids: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)


class Round(CamelModel):
    name: str
    date: IsoDate | None = None
    description: str | None = None


class RoundResult(CamelModel):
    round_name: str
    status: str
    score: float | None = None
    remarks: str | None = None
    recorded_by: str | None = None
    recorded_by_name: str | None = None
    recorded_at: str | None = None


class Offer(CamelModel):
    ctc: float | None = Field(default=None, ge=0)
    letter_path: str | None = None
    letter_url: str | None = None
    joined: bool | None = None
    offer_date: IsoDate | None = None


class Ratings(CamelModel):
    technical: int = Field(ge=1, le=5)
    communication: int = Field(ge=1, le=5)
    problem_solving: int = Field(ge=1, le=5)
    attitude: int = Field(ge=1, le=5)

    @property
    def average(self) -> float:
        return round(
            (self.technical + self.communication + self.problem_solving + self.attitude) / 4, 2
        )
