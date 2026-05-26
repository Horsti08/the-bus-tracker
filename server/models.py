import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_invite_code() -> str:
    return secrets.token_urlsafe(8)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    memberships: Mapped[list["SpeditionMember"]] = relationship(back_populates="user")
    trips: Mapped[list["Trip"]] = relationship(back_populates="user")
    bank_account: Mapped["BankAccount | None"] = relationship(
        back_populates="user", uselist=False, foreign_keys="BankAccount.user_id"
    )


class Spedition(Base):
    __tablename__ = "speditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, default=new_invite_code)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    members: Mapped[list["SpeditionMember"]] = relationship(
        back_populates="spedition", cascade="all, delete-orphan"
    )
    trips: Mapped[list["Trip"]] = relationship(back_populates="spedition")
    bank_account: Mapped["BankAccount | None"] = relationship(
        back_populates="spedition", uselist=False, foreign_keys="BankAccount.spedition_id"
    )


class SpeditionMember(Base):
    __tablename__ = "spedition_members"
    __table_args__ = (UniqueConstraint("spedition_id", "user_id", name="uq_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spedition_id: Mapped[int] = mapped_column(ForeignKey("speditions.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32), default="driver")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    spedition: Mapped["Spedition"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    spedition_id: Mapped[int | None] = mapped_column(ForeignKey("speditions.id"), nullable=True)
    vehicle_model: Mapped[str] = mapped_column(String(128), default="")
    line_name: Mapped[str] = mapped_column(String(64), default="")
    route_name: Mapped[str] = mapped_column(String(128), default="")
    level_name: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    max_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    avg_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    tickets_sold: Mapped[int] = mapped_column(Integer, default=0)
    revenue_eur: Mapped[float] = mapped_column(Float, default=0.0)
    stops_served: Mapped[int] = mapped_column(Integer, default=0)
    overspeed_events: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="trips")
    spedition: Mapped["Spedition | None"] = relationship(back_populates="trips")


class LiveStatus(Base):
    __tablename__ = "live_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    spedition_id: Mapped[int | None] = mapped_column(ForeignKey("speditions.id"), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    vehicle_model: Mapped[str] = mapped_column(String(128), default="")
    line_name: Mapped[str] = mapped_column(String(64), default="")
    level_name: Mapped[str] = mapped_column(String(128), default="")
    current_stop: Mapped[str] = mapped_column(String(128), default="")
    next_stop: Mapped[str] = mapped_column(String(128), default="")
    speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    allowed_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    pos_x: Mapped[float] = mapped_column(Float, default=0.0)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_session_eur: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_bank_user"),
        UniqueConstraint("spedition_id", name="uq_bank_spedition"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    spedition_id: Mapped[int | None] = mapped_column(ForeignKey("speditions.id"), nullable=True)
    balance_eur: Mapped[float] = mapped_column(Float, default=5000.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User | None"] = relationship(
        back_populates="bank_account", foreign_keys=[user_id]
    )
    spedition: Mapped["Spedition | None"] = relationship(
        back_populates="bank_account", foreign_keys=[spedition_id]
    )
