"""The Bus Tracker API – virtuelle Bus-Speditionen."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from server import models
from server.auth import create_access_token, decode_token, hash_password, verify_password
from server.database import get_db, init_db
from shared import APP_VERSION, COMMUNITY_SERVER_NAME
from server.bank_service import (
    credit_trip_revenue,
    ensure_spedition_bank,
    ensure_user_bank,
)
from server.schemas import (
    BankResponse,
    JoinSpeditionRequest,
    LiveDriverResponse,
    LiveUpdateRequest,
    LoginRequest,
    MemberResponse,
    RankingEntry,
    RegisterRequest,
    SpeditionCreate,
    SpeditionResponse,
    TokenResponse,
    TripResponse,
    TripSubmitRequest,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="The Bus Tracker API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Nicht angemeldet")
    payload = decode_token(authorization[7:])
    if not payload:
        raise HTTPException(401, "Ungültiges Token")
    user = db.get(models.User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "Benutzer nicht gefunden")
    return user


def _web_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def invite_link(code: str, web_base: str = "") -> str:
    if web_base:
        return f"{web_base.rstrip('/')}/join/{code}"
    return f"bus-tracker://join/{code}"


@app.get("/")
def root():
    return {
        "app": "The Bus Tracker Community API",
        "version": APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "info": "/app/info",
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION, "mode": "community"}


@app.get("/app/info")
def app_info(request: Request, db: Session = Depends(get_db)):
    base = str(request.base_url).rstrip("/")
    online = (
        db.query(models.LiveStatus)
        .filter(models.LiveStatus.is_online == True)  # noqa: E712
        .count()
    )
    users = db.query(models.User).count()
    speditions = db.query(models.Spedition).filter(models.Spedition.is_active == True).count()  # noqa: E712
    return {
        "server_name": COMMUNITY_SERVER_NAME,
        "version": APP_VERSION,
        "community_api_url": base,
        "players_online": online,
        "registered_users": users,
        "active_speditions": speditions,
        "invite_web_base": base,
    }


@app.get("/app/version")
def app_version(request: Request):
    base = str(request.base_url).rstrip("/")
    return {
        "version": APP_VERSION,
        "app": "The Bus Tracker",
        "download_url": "",
        "changelog": "Fix Spedition/Join, UI flüssiger, Auto-Update",
        "community_api_url": base,
        "community_api_urls": [base],
    }


@app.get("/join/{invite_code}")
def join_info(invite_code: str, db: Session = Depends(get_db)):
    sp = (
        db.query(models.Spedition)
        .filter(
            models.Spedition.invite_code == invite_code,
            models.Spedition.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not sp:
        raise HTTPException(400, "Einladung ungültig")
    return {
        "spedition": sp.name,
        "invite_code": invite_code,
        "message": "Öffne The Bus Tracker und gib den Code unter Spedition → Beitreten ein.",
    }


@app.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(400, "Benutzername bereits vergeben")
    user = models.User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
    )
    db.add(user)
    db.flush()
    ensure_user_bank(db, user.id)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
    )


@app.get("/auth/me")
def me(user: models.User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
    }


@app.post("/speditions", response_model=SpeditionResponse)
def create_spedition(
    body: SpeditionCreate,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(models.Spedition).filter(models.Spedition.name == body.name).first():
        raise HTTPException(400, "Spedition existiert bereits")
    sp = models.Spedition(name=body.name, description=body.description, owner_id=user.id)
    db.add(sp)
    db.flush()
    db.add(models.SpeditionMember(spedition_id=sp.id, user_id=user.id, role="owner"))
    ensure_spedition_bank(db, sp.id)
    ensure_user_bank(db, user.id)
    db.commit()
    db.refresh(sp)
    return SpeditionResponse(
        id=sp.id,
        name=sp.name,
        description=sp.description,
        owner_id=sp.owner_id,
        invite_code=sp.invite_code,
        invite_link=invite_link(sp.invite_code, _web_base(request)),
        member_count=1,
        is_owner=True,
    )


@app.get("/speditions", response_model=list[SpeditionResponse])
def list_speditions(
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(models.Spedition, func.count(models.SpeditionMember.id))
        .join(models.SpeditionMember, models.SpeditionMember.spedition_id == models.Spedition.id)
        .filter(
            models.SpeditionMember.user_id == user.id,
            models.Spedition.is_active == True,  # noqa: E712
        )
        .group_by(models.Spedition.id)
        .all()
    )
    result = []
    for sp, count in memberships:
        result.append(
            SpeditionResponse(
                id=sp.id,
                name=sp.name,
                description=sp.description,
                owner_id=sp.owner_id,
                invite_code=sp.invite_code,
                invite_link=invite_link(sp.invite_code, _web_base(request)),
                member_count=count,
                is_owner=sp.owner_id == user.id,
            )
        )
    return result


@app.post("/speditions/join", response_model=SpeditionResponse)
def join_spedition(
    body: JoinSpeditionRequest,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sp = (
        db.query(models.Spedition)
        .filter(
            models.Spedition.invite_code == body.invite_code,
            models.Spedition.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not sp:
        raise HTTPException(400, "Einladung ungültig – Code prüfen")
    existing = (
        db.query(models.SpeditionMember)
        .filter(
            models.SpeditionMember.spedition_id == sp.id,
            models.SpeditionMember.user_id == user.id,
        )
        .first()
    )
    if not existing:
        db.add(models.SpeditionMember(spedition_id=sp.id, user_id=user.id, role="driver"))
        ensure_user_bank(db, user.id)
        db.commit()
    count = db.query(models.SpeditionMember).filter(models.SpeditionMember.spedition_id == sp.id).count()
    return SpeditionResponse(
        id=sp.id,
        name=sp.name,
        description=sp.description,
        owner_id=sp.owner_id,
        invite_code=sp.invite_code,
        invite_link=invite_link(sp.invite_code, _web_base(request)),
        member_count=count,
        is_owner=sp.owner_id == user.id,
    )


@app.post("/join", response_model=SpeditionResponse)
def join_spedition_alias(
    body: JoinSpeditionRequest,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias – falls /speditions/join auf altem Deploy fehlt."""
    return join_spedition(body, request, user, db)


@app.delete("/speditions/{spedition_id}")
def delete_spedition(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sp = db.get(models.Spedition, spedition_id)
    if not sp:
        raise HTTPException(404, "Spedition nicht gefunden")
    if sp.owner_id != user.id:
        raise HTTPException(403, "Nur der Besitzer kann die Spedition löschen")
    sp.is_active = False
    db.query(models.LiveStatus).filter(models.LiveStatus.spedition_id == spedition_id).update(
        {"is_online": False, "spedition_id": None}
    )
    db.commit()
    return {"ok": True}


@app.post("/speditions/{spedition_id}/regenerate-invite")
def regenerate_invite(
    spedition_id: int,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sp = db.get(models.Spedition, spedition_id)
    if not sp or sp.owner_id != user.id:
        raise HTTPException(403, "Keine Berechtigung")
    sp.invite_code = models.new_invite_code()
    db.commit()
    return {
        "invite_code": sp.invite_code,
        "invite_link": invite_link(sp.invite_code, _web_base(request)),
    }


@app.post("/live")
def update_live(
    body: LiveUpdateRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status = db.query(models.LiveStatus).filter(models.LiveStatus.user_id == user.id).first()
    if not status:
        status = models.LiveStatus(user_id=user.id)
        db.add(status)
    status.spedition_id = body.spedition_id
    status.is_online = body.is_online
    status.vehicle_model = body.vehicle_model
    status.line_name = body.line_name
    status.level_name = body.level_name
    status.current_stop = body.current_stop
    status.next_stop = body.next_stop
    status.speed_kmh = body.speed_kmh
    status.allowed_speed_kmh = body.allowed_speed_kmh
    status.latitude = body.latitude
    status.longitude = body.longitude
    status.pos_x = body.pos_x
    status.pos_y = body.pos_y
    status.revenue_session_eur = body.revenue_session_eur
    status.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@app.get("/speditions/{spedition_id}/live", response_model=list[LiveDriverResponse])
def get_live_drivers(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = (
        db.query(models.SpeditionMember)
        .filter(
            models.SpeditionMember.spedition_id == spedition_id,
            models.SpeditionMember.user_id == user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(403, "Kein Mitglied dieser Spedition")

    cutoff = datetime.now(timezone.utc)
    rows = (
        db.query(models.LiveStatus, models.User)
        .join(models.User, models.User.id == models.LiveStatus.user_id)
        .filter(
            models.LiveStatus.spedition_id == spedition_id,
            models.LiveStatus.is_online == True,  # noqa: E712
        )
        .all()
    )
    drivers = []
    for status, u in rows:
        overspeed = (
            status.allowed_speed_kmh > 0
            and status.speed_kmh > status.allowed_speed_kmh + 3
        )
        drivers.append(
            LiveDriverResponse(
                user_id=u.id,
                display_name=u.display_name,
                username=u.username,
                vehicle_model=status.vehicle_model,
                line_name=status.line_name,
                level_name=status.level_name,
                current_stop=status.current_stop,
                next_stop=status.next_stop,
                speed_kmh=status.speed_kmh,
                allowed_speed_kmh=status.allowed_speed_kmh,
                is_overspeed=overspeed,
                revenue_session_eur=status.revenue_session_eur,
                pos_x=status.pos_x,
                pos_y=status.pos_y,
                updated_at=status.updated_at,
            )
        )
    return drivers


@app.get("/users/me/bank", response_model=BankResponse)
def my_bank(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    acc = ensure_user_bank(db, user.id)
    db.commit()
    return BankResponse(
        balance_eur=round(acc.balance_eur, 2),
        account_type="driver",
        label=user.display_name,
    )


@app.get("/speditions/{spedition_id}/bank", response_model=BankResponse)
def spedition_bank(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_member(db, spedition_id, user.id):
        raise HTTPException(403, "Kein Mitglied")
    sp = db.get(models.Spedition, spedition_id)
    acc = ensure_spedition_bank(db, spedition_id)
    db.commit()
    return BankResponse(
        balance_eur=round(acc.balance_eur, 2),
        account_type="spedition",
        label=sp.name if sp else "",
    )


def _is_member(db: Session, spedition_id: int, user_id: int) -> bool:
    return (
        db.query(models.SpeditionMember)
        .filter(
            models.SpeditionMember.spedition_id == spedition_id,
            models.SpeditionMember.user_id == user_id,
        )
        .first()
        is not None
    )


@app.get("/speditions/{spedition_id}/members", response_model=list[MemberResponse])
def spedition_members(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_member(db, spedition_id, user.id):
        raise HTTPException(403, "Kein Mitglied")

    members = (
        db.query(models.SpeditionMember, models.User)
        .join(models.User, models.User.id == models.SpeditionMember.user_id)
        .filter(models.SpeditionMember.spedition_id == spedition_id)
        .all()
    )
    result: list[MemberResponse] = []
    for m, u in members:
        agg = (
            db.query(
                func.coalesce(func.sum(models.Trip.revenue_eur), 0.0),
                func.count(models.Trip.id),
            )
            .filter(
                models.Trip.user_id == u.id,
                models.Trip.spedition_id == spedition_id,
            )
            .one()
        )
        acc = ensure_user_bank(db, u.id)
        live = db.query(models.LiveStatus).filter(models.LiveStatus.user_id == u.id).first()
        online = bool(live and live.is_online and live.spedition_id == spedition_id)
        result.append(
            MemberResponse(
                user_id=u.id,
                display_name=u.display_name,
                username=u.username,
                role=m.role,
                is_online=online,
                balance_eur=round(acc.balance_eur, 2),
                total_revenue_eur=round(float(agg[0]), 2),
                trip_count=int(agg[1]),
            )
        )
    result.sort(key=lambda x: x.total_revenue_eur, reverse=True)
    ranked = [m.model_copy(update={"rank": i}) for i, m in enumerate(result, 1)]
    db.commit()
    return ranked


@app.get("/speditions/{spedition_id}/ranking", response_model=list[RankingEntry])
def spedition_ranking(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_member(db, spedition_id, user.id):
        raise HTTPException(403, "Kein Mitglied")

    rows = (
        db.query(
            models.User.id,
            models.User.display_name,
            func.coalesce(func.sum(models.Trip.revenue_eur), 0.0),
            func.count(models.Trip.id),
            func.coalesce(func.sum(models.Trip.distance_km), 0.0),
        )
        .join(models.SpeditionMember, models.SpeditionMember.user_id == models.User.id)
        .outerjoin(
            models.Trip,
            (models.Trip.user_id == models.User.id)
            & (models.Trip.spedition_id == spedition_id),
        )
        .filter(models.SpeditionMember.spedition_id == spedition_id)
        .group_by(models.User.id, models.User.display_name)
        .order_by(func.coalesce(func.sum(models.Trip.revenue_eur), 0.0).desc())
        .all()
    )
    ranking: list[RankingEntry] = []
    for i, (uid, name, rev, trips, dist) in enumerate(rows, 1):
        acc = ensure_user_bank(db, uid)
        ranking.append(
            RankingEntry(
                rank=i,
                user_id=uid,
                display_name=name,
                total_revenue_eur=round(float(rev), 2),
                trip_count=int(trips),
                total_distance_km=round(float(dist), 2),
                balance_eur=round(acc.balance_eur, 2),
            )
        )
    db.commit()
    return ranking


@app.post("/trips", response_model=TripResponse)
def submit_trip(
    body: TripSubmitRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = models.Trip(
        user_id=user.id,
        spedition_id=body.spedition_id,
        vehicle_model=body.vehicle_model,
        line_name=body.line_name,
        route_name=body.route_name,
        level_name=body.level_name,
        started_at=body.started_at,
        ended_at=body.ended_at,
        distance_km=body.distance_km,
        max_speed_kmh=body.max_speed_kmh,
        avg_speed_kmh=body.avg_speed_kmh,
        tickets_sold=body.tickets_sold,
        revenue_eur=body.revenue_eur,
        stops_served=body.stops_served,
        overspeed_events=body.overspeed_events,
    )
    db.add(trip)
    db.flush()
    credit_trip_revenue(db, user.id, body.spedition_id, body.revenue_eur)
    db.commit()
    db.refresh(trip)
    return TripResponse(
        id=trip.id,
        vehicle_model=trip.vehicle_model,
        line_name=trip.line_name,
        route_name=trip.route_name,
        level_name=trip.level_name,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        max_speed_kmh=trip.max_speed_kmh,
        avg_speed_kmh=trip.avg_speed_kmh,
        tickets_sold=trip.tickets_sold,
        revenue_eur=trip.revenue_eur,
        stops_served=trip.stops_served,
        overspeed_events=trip.overspeed_events,
        driver_name=user.display_name,
    )


@app.get("/speditions/{spedition_id}/trips", response_model=list[TripResponse])
def spedition_trips(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = (
        db.query(models.SpeditionMember)
        .filter(
            models.SpeditionMember.spedition_id == spedition_id,
            models.SpeditionMember.user_id == user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(403, "Kein Mitglied")

    rows = (
        db.query(models.Trip, models.User)
        .join(models.User, models.User.id == models.Trip.user_id)
        .filter(models.Trip.spedition_id == spedition_id)
        .order_by(models.Trip.started_at.desc())
        .limit(100)
        .all()
    )
    return [
        TripResponse(
            id=t.id,
            vehicle_model=t.vehicle_model,
            line_name=t.line_name,
            route_name=t.route_name,
            level_name=t.level_name,
            started_at=t.started_at,
            ended_at=t.ended_at,
            distance_km=t.distance_km,
            max_speed_kmh=t.max_speed_kmh,
            avg_speed_kmh=t.avg_speed_kmh,
            tickets_sold=t.tickets_sold,
            revenue_eur=t.revenue_eur,
            stops_served=t.stops_served,
            overspeed_events=t.overspeed_events,
            driver_name=u.display_name,
        )
        for t, u in rows
    ]


@app.get("/speditions/{spedition_id}/stats")
def spedition_stats(
    spedition_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = (
        db.query(models.SpeditionMember)
        .filter(
            models.SpeditionMember.spedition_id == spedition_id,
            models.SpeditionMember.user_id == user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(403, "Kein Mitglied")

    agg = (
        db.query(
            func.count(models.Trip.id),
            func.coalesce(func.sum(models.Trip.revenue_eur), 0.0),
            func.coalesce(func.sum(models.Trip.distance_km), 0.0),
            func.coalesce(func.sum(models.Trip.tickets_sold), 0),
        )
        .filter(models.Trip.spedition_id == spedition_id)
        .one()
    )
    return {
        "total_trips": agg[0],
        "total_revenue_eur": round(float(agg[1]), 2),
        "total_distance_km": round(float(agg[2]), 2),
        "total_tickets": int(agg[3]),
    }
