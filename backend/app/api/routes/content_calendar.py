from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import ContentCalendar, User
from app.schemas.content import (
    AutoIdeaDiscoveryRequest,
    AutoIdeaDiscoveryResponse,
    AutoIdeaScheduleConfig,
    AutoIdeaScheduleResponse,
    CalendarCreate,
    CalendarRead,
    CalendarUpdate,
    TrustedSourceRead,
)
from app.services.idea_research_agent import (
    discover_and_optionally_save_ideas,
    get_auto_idea_schedule,
    list_trusted_sources,
    update_auto_idea_schedule,
)
from app.services.account_scope import ensure_account_access, require_account, scope_query
from app.workers.tasks import auto_generate_daily_ideas_job

router = APIRouter()


@router.get("", response_model=list[CalendarRead])
def list_calendar(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[ContentCalendar]:
    return scope_query(db.query(ContentCalendar), ContentCalendar, current_user).order_by(
        ContentCalendar.scheduled_date.asc().nullslast(),
        ContentCalendar.created_at.desc(),
    ).all()


@router.get("/sources", response_model=list[TrustedSourceRead])
def list_auto_idea_sources(
    _: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[dict]:
    return list_trusted_sources()


@router.post("/auto-ideas", response_model=AutoIdeaDiscoveryResponse, status_code=status.HTTP_201_CREATED)
def auto_discover_ideas(
    payload: AutoIdeaDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> AutoIdeaDiscoveryResponse:
    items, sources_checked = discover_and_optionally_save_ideas(db, current_user, payload)
    return AutoIdeaDiscoveryResponse(items=items, sources_checked=sources_checked)


@router.get("/auto-ideas/schedule", response_model=AutoIdeaScheduleResponse)
def get_auto_idea_schedule_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> AutoIdeaScheduleResponse:
    return get_auto_idea_schedule(db, require_account(current_user))


@router.put("/auto-ideas/schedule", response_model=AutoIdeaScheduleResponse)
def put_auto_idea_schedule_config(
    payload: AutoIdeaScheduleConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> AutoIdeaScheduleResponse:
    return update_auto_idea_schedule(db, current_user, payload)


@router.post("/auto-ideas/run", status_code=status.HTTP_202_ACCEPTED)
def trigger_auto_idea_run(
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> dict[str, str]:
    task = auto_generate_daily_ideas_job.delay(current_user.id, True)
    return {"task_id": task.id, "message": "Automatic idea generation queued"}


@router.post("", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
def create_calendar(
    payload: CalendarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> ContentCalendar:
    item = ContentCalendar(**payload.model_dump(exclude={"account_id"}), account_id=require_account(current_user), created_by_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{calendar_id}", response_model=CalendarRead)
def get_calendar(
    calendar_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> ContentCalendar:
    item = db.query(ContentCalendar).filter(ContentCalendar.id == calendar_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar item not found")
    ensure_account_access(item, current_user)
    return item


@router.put("/{calendar_id}", response_model=CalendarRead)
def update_calendar(
    calendar_id: int,
    payload: CalendarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> ContentCalendar:
    item = db.query(ContentCalendar).filter(ContentCalendar.id == calendar_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar item not found")
    ensure_account_access(item, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "account_id":
            continue
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_calendar(
    calendar_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> Response:
    item = db.query(ContentCalendar).filter(ContentCalendar.id == calendar_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar item not found")
    ensure_account_access(item, current_user)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
