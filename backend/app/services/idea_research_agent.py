from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape

import httpx
from openai import OpenAI
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AIRun, Account, ContentCalendar, Page, Setting, User
from app.schemas.content import (
    AutoIdeaDiscoveryItem,
    AutoIdeaDiscoveryRequest,
    AutoIdeaScheduleConfig,
    AutoIdeaScheduleResponse,
    AutoIdeaScheduleState,
)
from app.services.account_scope import enforce_auto_idea_limit, require_account


IDEA_SYSTEM_PROMPT = """
You are an editorial research agent for a Thai-language Facebook content team about clean air, indoor air quality, health, ventilation, mold, climate, and pollution.
You will receive trusted source snippets from official organizations.
Create practical, educational content ideas in Thai.

Rules:
- Thai language only for title, topic, target_audience, tone, notes
- No sales copy
- Stay close to the provided sources
- Prefer timely, useful, public-health-oriented ideas
- Return strict JSON with key "items"
- Each item must contain: title, topic, content_pillar, target_audience, tone, post_length, notes, source_name, source_url
- content_pillar should be one of: Indoor Air, Outdoor Air, Health, CO2, VOC, Mold, Ventilation, Climate, Lifestyle
- post_length should be short, medium, or long
- Include 1 source only per item
""".strip()


@dataclass(frozen=True)
class TrustedSource:
    id: str
    name: str
    url: str
    content_pillar: str
    source_type: str = "official_web"


TRUSTED_SOURCES: list[TrustedSource] = [
    TrustedSource(
        id="who-air-pollution",
        name="WHO Air Pollution Newsroom",
        url="https://www.who.int/news-room/air-pollution",
        content_pillar="Health",
    ),
    TrustedSource(
        id="epa-indoor-air-quality",
        name="US EPA Indoor Air Quality",
        url="https://www.epa.gov/indoor-air-quality-iaq",
        content_pillar="Indoor Air",
    ),
    TrustedSource(
        id="cdc-air-quality",
        name="CDC Air Quality",
        url="https://www.cdc.gov/air-quality/about/index.html",
        content_pillar="Outdoor Air",
    ),
    TrustedSource(
        id="nih-news-air-pollution",
        name="NIH News in Health",
        url="https://newsinhealth.nih.gov/2026/04/protect-against-air-pollution",
        content_pillar="Health",
    ),
    TrustedSource(
        id="niehs-air-pollution",
        name="NIEHS Air Pollution and Your Health",
        url="https://www.niehs.nih.gov/health/topics/agents/air-pollution",
        content_pillar="Health",
    ),
]

AUTO_IDEA_SCHEDULE_KEY = "auto_idea_generation_schedule"
AUTO_IDEA_STATE_KEY = "auto_idea_generation_state"


def get_default_schedule_config() -> AutoIdeaScheduleConfig:
    return AutoIdeaScheduleConfig()


def get_auto_idea_schedule(db: Session, account_id: int) -> AutoIdeaScheduleResponse:
    schedule_setting = db.query(Setting).filter(Setting.account_id == account_id, Setting.key == AUTO_IDEA_SCHEDULE_KEY).first()
    state_setting = db.query(Setting).filter(Setting.account_id == account_id, Setting.key == AUTO_IDEA_STATE_KEY).first()

    config_payload = schedule_setting.value_json if schedule_setting and isinstance(schedule_setting.value_json, dict) else {}
    state_payload = state_setting.value_json if state_setting and isinstance(state_setting.value_json, dict) else {}

    return AutoIdeaScheduleResponse(
        config=AutoIdeaScheduleConfig.model_validate(config_payload or get_default_schedule_config().model_dump()),
        state=AutoIdeaScheduleState.model_validate(state_payload or {}),
    )


def update_auto_idea_schedule(db: Session, actor: User, config: AutoIdeaScheduleConfig) -> AutoIdeaScheduleResponse:
    account_id = require_account(actor)
    account = db.query(Account).filter(Account.id == account_id).first()
    if account:
        enforce_auto_idea_limit(account, config.count)

    schedule_setting = db.query(Setting).filter(Setting.account_id == account_id, Setting.key == AUTO_IDEA_SCHEDULE_KEY).first()
    if not schedule_setting:
        schedule_setting = Setting(account_id=account_id, key=AUTO_IDEA_SCHEDULE_KEY)
        db.add(schedule_setting)

    schedule_setting.value_json = config.model_dump()
    schedule_setting.value_text = None
    schedule_setting.is_encrypted = False
    schedule_setting.description = "Daily automatic idea generation schedule"
    schedule_setting.updated_by_id = actor.id
    db.commit()
    return get_auto_idea_schedule(db, account_id)


def mark_auto_idea_schedule_run(db: Session, account_id: int, local_date: str) -> None:
    state_setting = db.query(Setting).filter(Setting.account_id == account_id, Setting.key == AUTO_IDEA_STATE_KEY).first()
    if not state_setting:
        state_setting = Setting(account_id=account_id, key=AUTO_IDEA_STATE_KEY)
        db.add(state_setting)
    state_setting.value_json = {"last_run_local_date": local_date}
    state_setting.value_text = None
    state_setting.is_encrypted = False
    state_setting.description = "Last successful automatic idea generation run date"
    db.commit()


def should_run_auto_idea_schedule(db: Session, account_id: int, now: datetime) -> tuple[bool, AutoIdeaScheduleConfig]:
    schedule = get_auto_idea_schedule(db, account_id)
    config = schedule.config
    state = schedule.state
    if not config.enabled:
        return False, config

    hour, minute = [int(part) for part in config.time_local.split(":")]
    if (now.hour, now.minute) < (hour, minute):
        return False, config

    local_date = now.strftime("%Y-%m-%d")
    if state.last_run_local_date == local_date:
        return False, config

    return True, config


def list_trusted_sources() -> list[dict]:
    return [asdict(source) for source in TRUSTED_SOURCES]


def _extract_title(html: str) -> str:
    patterns = [
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r'<meta[^>]+name="title"[^>]+content="([^"]+)"',
        r"<title>(.*?)</title>",
        r"<h1[^>]*>(.*?)</h1>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _cleanup_html(match.group(1))
    return ""


def _extract_description(html: str) -> str:
    patterns = [
        r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
        r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
        r"<p[^>]*>(.*?)</p>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            text = _cleanup_html(match.group(1))
            if text:
                return text
    return ""


def _cleanup_html(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", value)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _fetch_source_summary(source: TrustedSource) -> dict:
    headers = {"User-Agent": "FlowPilotAgent/1.0 (+https://localhost)"}
    with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
        response = client.get(source.url)
        response.raise_for_status()
    html = response.text
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "content_pillar": source.content_pillar,
        "title": _extract_title(html),
        "summary": _extract_description(html),
    }


def _collect_source_summaries() -> list[dict]:
    summaries: list[dict] = []
    for source in TRUSTED_SOURCES:
        try:
            summaries.append(_fetch_source_summary(source))
        except Exception:
            continue
    return summaries


def _mock_ideas(summaries: list[dict], count: int) -> list[dict]:
    items: list[dict] = []
    for source in summaries[:count]:
        items.append(
            {
                "title": f"ชวนคุยจาก {source['name']}: สิ่งที่ควรรู้เรื่อง{source['content_pillar'].lower()}",
                "topic": source["title"] or source["summary"][:120] or source["name"],
                "content_pillar": source["content_pillar"],
                "target_audience": "คนเมือง เจ้าของบ้าน และคนทำงานในอาคาร",
                "tone": "ให้ข้อมูลชัดเจน เชื่อถือได้ และนำไปใช้ได้จริง",
                "post_length": "medium",
                "notes": f"สรุปจากแหล่งทางการ {source['name']}: {source['summary'][:220]}",
                "source_name": source["name"],
                "source_url": source["url"],
            }
        )
    return items


def _normalize_items(raw_items: list[dict], fallback_sources: dict[str, dict]) -> list[AutoIdeaDiscoveryItem]:
    normalized: list[AutoIdeaDiscoveryItem] = []
    for raw_item in raw_items:
        source_url = str(raw_item.get("source_url") or "").strip()
        fallback = fallback_sources.get(source_url) or next(iter(fallback_sources.values()))
        normalized.append(
            AutoIdeaDiscoveryItem(
                title=str(raw_item.get("title") or fallback["title"] or fallback["name"]).strip(),
                topic=str(raw_item.get("topic") or fallback["summary"] or fallback["title"] or fallback["name"]).strip(),
                content_pillar=str(raw_item.get("content_pillar") or fallback["content_pillar"]).strip(),
                target_audience=str(raw_item.get("target_audience") or "คนเมือง เจ้าของบ้าน และคนทำงานในอาคาร").strip(),
                tone=str(raw_item.get("tone") or "ให้ข้อมูลชัดเจน เชื่อถือได้ และนำไปใช้ได้จริง").strip(),
                post_length=str(raw_item.get("post_length") or "medium").strip(),
                notes=str(raw_item.get("notes") or f"อ้างอิงจาก {fallback['name']}").strip(),
                source_name=str(raw_item.get("source_name") or fallback["name"]).strip(),
                source_url=source_url or fallback["url"],
            )
        )
    return normalized


def _build_system_prompt(pages: list[Page]) -> str:
    pages_with_desc = [p for p in pages if p.description]
    if not pages_with_desc:
        return IDEA_SYSTEM_PROMPT
    page_context = "\n".join(
        f'- {p.name} ({p.page_category or "General"}): {p.description}'
        for p in pages_with_desc
    )
    return (
        IDEA_SYSTEM_PROMPT
        + f"\n\nTarget Facebook pages for this account:\n{page_context}\n"
        + "Generate ideas that are relevant to the themes and audiences of these pages."
    )


def _mock_ideas_for_pages(summaries: list[dict], count: int, pages: list[Page]) -> list[dict]:
    pages_with_desc = [p for p in pages if p.description]
    items: list[dict] = []
    for i, source in enumerate(summaries[:count]):
        page = pages_with_desc[i % len(pages_with_desc)] if pages_with_desc else None
        page_hint = f" สำหรับเพจ {page.name}" if page else ""
        items.append(
            {
                "title": f"ชวนคุยจาก {source['name']}: สิ่งที่ควรรู้เรื่อง{source['content_pillar'].lower()}{page_hint}",
                "topic": source["title"] or source["summary"][:120] or source["name"],
                "content_pillar": source["content_pillar"],
                "target_audience": page.description[:120] if page and page.description else "คนเมือง เจ้าของบ้าน และคนทำงานในอาคาร",
                "tone": "ให้ข้อมูลชัดเจน เชื่อถือได้ และนำไปใช้ได้จริง",
                "post_length": "medium",
                "notes": f"สรุปจากแหล่งทางการ {source['name']}: {source['summary'][:220]}",
                "source_name": source["name"],
                "source_url": source["url"],
            }
        )
    return items


def _generate_ideas_from_sources(summaries: list[dict], request: AutoIdeaDiscoveryRequest, pages: list[Page]) -> list[AutoIdeaDiscoveryItem]:
    settings = get_settings()
    if settings.mock_external_services or not settings.openai_api_key:
        mock = _mock_ideas_for_pages(summaries, request.count, pages) if pages else _mock_ideas(summaries, request.count)
        return _normalize_items(mock, {item["url"]: item for item in summaries})

    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = _build_system_prompt(pages)
    completion = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"count": request.count, "trusted_sources": summaries},
                    ensure_ascii=False,
                ),
            },
        ],
    )
    payload = json.loads(completion.choices[0].message.content or "{}")
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    return _normalize_items(items[: request.count], {item["url"]: item for item in summaries})


def _dedupe_against_existing(db: Session, items: list[AutoIdeaDiscoveryItem]) -> list[AutoIdeaDiscoveryItem]:
    deduped: list[AutoIdeaDiscoveryItem] = []
    seen_topics: set[str] = set()
    for item in items:
        topic_key = item.topic.casefold()
        title_key = item.title.casefold()
        if topic_key in seen_topics or title_key in seen_topics:
            continue
        exists = (
            db.query(ContentCalendar)
            .filter(
                or_(
                    ContentCalendar.title.ilike(item.title),
                    ContentCalendar.topic.ilike(item.topic),
                )
            )
            .first()
        )
        if exists:
            continue
        seen_topics.add(topic_key)
        seen_topics.add(title_key)
        deduped.append(item)
    return deduped


def discover_and_optionally_save_ideas(
    db: Session,
    user: User,
    request: AutoIdeaDiscoveryRequest,
) -> tuple[list[ContentCalendar | AutoIdeaDiscoveryItem], list[dict]]:
    account_id = require_account(user)
    account = db.query(Account).filter(Account.id == account_id).first()
    if account:
        enforce_auto_idea_limit(account, request.count)
    settings = get_settings()
    ai_run = AIRun(
        account_id=account_id,
        run_type="discover_ideas",
        status="running",
        model_name=settings.openai_model,
        prompt_payload=request.model_dump(),
        created_by_id=user.id,
    )
    db.add(ai_run)
    db.commit()
    db.refresh(ai_run)

    try:
        pages = db.query(Page).filter(Page.account_id == account_id, Page.is_active.is_(True)).all()
        summaries = _collect_source_summaries()
        if not summaries:
            raise RuntimeError("Could not fetch any trusted sources for idea discovery")
        items = _generate_ideas_from_sources(summaries, request, pages)
        items = _dedupe_against_existing(db, items)
        items = items[: request.count]

        if request.save_to_calendar:
            created_items: list[ContentCalendar] = []
            for item in items:
                note = (
                    f"{item.notes}\n\n"
                    f"Source: {item.source_name}\n"
                    f"URL: {item.source_url}"
                )
                calendar_item = ContentCalendar(
                    account_id=account_id,
                    title=item.title,
                    topic=item.topic,
                    content_pillar=item.content_pillar,
                    target_audience=item.target_audience,
                    tone=item.tone,
                    post_length=item.post_length,
                    status="idea",
                    notes=note,
                    created_by_id=user.id,
                )
                db.add(calendar_item)
                created_items.append(calendar_item)
            db.commit()
            for created_item in created_items:
                db.refresh(created_item)
            ai_run.status = "completed"
            ai_run.output_payload = {"created_count": len(created_items), "sources_checked": summaries}
            db.commit()
            return created_items, list_trusted_sources()

        ai_run.status = "completed"
        ai_run.output_payload = {"preview_count": len(items), "sources_checked": summaries}
        db.commit()
        return items, list_trusted_sources()
    except Exception as exc:
        ai_run.status = "failed"
        ai_run.error_message = str(exc)
        db.commit()
        raise
