from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Vacancy:
    id: str
    title: str
    company: str
    salary: str
    location: str
    url: str
    description: str
    tags: list[str] = field(default_factory=list)
    date: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


@dataclass(slots=True)
class SearchParams:
    tech: str
    salary: Optional[int] = None
    location: Optional[str] = None


@dataclass(slots=True)
class Subscription:
    id: int
    user_id: int
    tech: str
    salary: Optional[int]
    location: Optional[str]
    is_active: bool = True


@dataclass(slots=True)
class Stats:
    saved: int = 0
    applied: int = 0
    interview: int = 0
    offer: int = 0
    rejected: int = 0

    @property
    def total(self) -> int:
        return (
            self.saved
            + self.applied
            + self.interview
            + self.offer
            + self.rejected
        )

    @property
    def conversion_rate(self) -> int:
        if not self.applied:
            return 0
        return min(100, round(self.interview / self.applied * 100))


@dataclass(slots=True)
class UserProfile:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    company: Optional[str] = None
    created_at: Optional[str] = None
    last_seen_at: Optional[str] = None


@dataclass(slots=True)
class UserLink:
    id: int
    user_id: int
    url: str
    added_at: str


@dataclass(slots=True)
class UserSettings:
    user_id: int
    notify_hour: int = 10
    language: str = "ru"