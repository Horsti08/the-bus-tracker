from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    display_name: str = Field(default="", max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    display_name: str


class SpeditionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    description: str = ""


class SpeditionResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    invite_code: str
    invite_link: str
    member_count: int
    is_owner: bool


class JoinSpeditionRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=64)


class LiveUpdateRequest(BaseModel):
    spedition_id: int | None = None
    is_online: bool = True
    vehicle_model: str = ""
    line_name: str = ""
    level_name: str = ""
    current_stop: str = ""
    next_stop: str = ""
    speed_kmh: float = 0.0
    allowed_speed_kmh: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0
    revenue_session_eur: float = 0.0


class LiveDriverResponse(BaseModel):
    user_id: int
    display_name: str
    username: str
    vehicle_model: str
    line_name: str
    level_name: str = ""
    current_stop: str
    next_stop: str
    speed_kmh: float
    allowed_speed_kmh: float
    is_overspeed: bool
    revenue_session_eur: float
    updated_at: datetime


class TripSubmitRequest(BaseModel):
    spedition_id: int | None = None
    vehicle_model: str = ""
    line_name: str = ""
    route_name: str = ""
    level_name: str = ""
    started_at: datetime
    ended_at: datetime | None = None
    distance_km: float = 0.0
    max_speed_kmh: float = 0.0
    avg_speed_kmh: float = 0.0
    tickets_sold: int = 0
    revenue_eur: float = 0.0
    stops_served: int = 0
    overspeed_events: int = 0


class TripResponse(BaseModel):
    id: int
    vehicle_model: str
    line_name: str
    route_name: str
    level_name: str
    started_at: datetime
    ended_at: datetime | None
    distance_km: float
    max_speed_kmh: float
    avg_speed_kmh: float
    tickets_sold: int
    revenue_eur: float
    stops_served: int
    overspeed_events: int
    driver_name: str = ""
