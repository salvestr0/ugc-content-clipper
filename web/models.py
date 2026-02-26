"""Pydantic request/response models."""

from pydantic import BaseModel
from typing import Optional


class JobCreate(BaseModel):
    url: str


class ClipUpdate(BaseModel):
    status: Optional[str] = None
    user_start_override: Optional[float] = None
    user_end_override: Optional[float] = None


class RerenderRequest(BaseModel):
    start_seconds: float
    end_seconds: float


class WatchlistCreate(BaseModel):
    channel_url: str
    channel_name: Optional[str] = None
