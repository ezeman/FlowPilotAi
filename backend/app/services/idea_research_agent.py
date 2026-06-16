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
from app.core.celery_app import celery_app
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
You are an editorial research agent for a Thai-language Facebook content team.
You will receive account page context and trusted source snippets.
Create practical, educational content ideas in Thai that fit each Facebook page's theme, audience, and content pillars.

Rules:
- Thai language only for title, topic, target_audience, tone, notes
- No sales copy
- Prioritize page context first, then use trusted sources for support and references
- Distribute ideas across available pages instead of concentrating in a single theme
- Return strict JSON with key "items"
- Each item must contain: title, topic, content_pillar, target_audience, tone, post_length, notes, source_name, source_url, page_id, viral_score
- content_pillar must be relevant to the selected page and should prefer that page's configured content_pillars
- post_length should be short, medium, or long
- Include 1 source only per item
- viral_score: integer 0-100 — honestly rate the idea's viral potential on Facebook (shareability, emotional hook, engagement likelihood)
""".strip()


@dataclass(frozen=True)
class TrustedSource:
    id: str
    name: str
    url: str
    content_pillar: str
    source_type: str = "official_web"


TRUSTED_SOURCES: list[TrustedSource] = []

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
        enforce_auto_idea_limit(account, config.count, db)

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
    headers = {"User-Agent": "ezeCraftAgent/1.0 (+https://localhost)"}
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


def _page_context_summaries(pages: list[Page]) -> list[dict]:
    page_summaries: list[dict] = []
    for page in pages:
        description = (page.description or "").strip()
        category = (page.page_category or "General").strip()
        pillars = page.content_pillars or ["General"]
        primary_pillar = pillars[0]
        page_summaries.append(
            {
                "id": f"page-{page.id}",
                "name": f"Page Context: {page.name}",
                "url": f"page://{page.id}",
                "content_pillar": primary_pillar,
                "title": f"{page.name} - {category}",
                "summary": description or f"Audience and themes for {page.name} in category {category}",
            }
        )
    return page_summaries


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
                "viral_score": 78,
            }
        )
    return items


def _normalize_items(raw_items: list[dict], fallback_sources: dict[str, dict]) -> list[AutoIdeaDiscoveryItem]:
    normalized: list[AutoIdeaDiscoveryItem] = []
    for raw_item in raw_items:
        source_url = str(raw_item.get("source_url") or "").strip()
        fallback = fallback_sources.get(source_url) or next(iter(fallback_sources.values()))
        try:
            viral_score = max(0, min(100, int(raw_item.get("viral_score") or 75)))
        except (TypeError, ValueError):
            viral_score = 75
        normalized.append(
            AutoIdeaDiscoveryItem(
                page_id=raw_item.get("page_id"),
                title=str(raw_item.get("title") or fallback["title"] or fallback["name"]).strip(),
                topic=str(raw_item.get("topic") or fallback["summary"] or fallback["title"] or fallback["name"]).strip(),
                content_pillar=str(raw_item.get("content_pillar") or fallback["content_pillar"]).strip(),
                target_audience=str(raw_item.get("target_audience") or "คนเมือง เจ้าของบ้าน และคนทำงานในอาคาร").strip(),
                tone=str(raw_item.get("tone") or "ให้ข้อมูลชัดเจน เชื่อถือได้ และนำไปใช้ได้จริง").strip(),
                post_length=str(raw_item.get("post_length") or "medium").strip(),
                notes=str(raw_item.get("notes") or f"อ้างอิงจาก {fallback['name']}").strip(),
                source_name=str(raw_item.get("source_name") or fallback["name"]).strip(),
                source_url=source_url or fallback["url"],
                viral_score=viral_score,
            )
        )
    return normalized


def _build_system_prompt(pages: list[Page]) -> str:
    if not pages:
        return IDEA_SYSTEM_PROMPT

    def _page_desc(page: Page) -> str:
        return page.description or page.page_category or "General"

    page_context = "\n".join(
        (
            f'- id={p.id} {p.name} ({p.page_category or "General"}): {_page_desc(p)}'
            f' Tone: {p.default_tone or "account default"}.'
            f' Content pillars: {", ".join(p.content_pillars or ["account default"])}.'
        )
        for p in pages
    )
    return (
        IDEA_SYSTEM_PROMPT
        + f"\n\nTarget Facebook pages for this account:\n{page_context}\n"
        + "Generate ideas that are relevant to the themes and audiences of these pages."
    )


def _mock_ideas_for_pages(summaries: list[dict], count: int, pages: list[Page]) -> list[dict]:
    if not pages:
        return _mock_ideas(summaries, count)

    items: list[dict] = []
    for i in range(count):
        source = summaries[i % len(summaries)]
        page = pages[i % len(pages)]
        selected_pillar = (page.content_pillars or [source["content_pillar"]])[0]
        page_hint = f" สำหรับเพจ {page.name}" if page else ""
        items.append(
            {
                "page_id": page.id,
                "title": f"ไอเดียคอนเทนต์ {selected_pillar}{page_hint}",
                "topic": page.description or source["title"] or source["summary"][:120] or source["name"],
                "content_pillar": selected_pillar,
                "target_audience": (page.description or "กลุ่มผู้ติดตามของเพจนี้")[:120],
                "tone": page.default_tone or "ให้ข้อมูลชัดเจน เชื่อถือได้ และนำไปใช้ได้จริง",
                "post_length": "medium",
                "notes": f"สรุปจากแหล่งทางการ {source['name']}: {source['summary'][:220]}",
                "source_name": source["name"],
                "source_url": source["url"],
                "viral_score": 78,
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
    normalized = _normalize_items(items[: request.count], {item["url"]: item for item in summaries})

    page_ids = {page.id for page in pages}
    for index, item in enumerate(normalized):
        if item.page_id in page_ids:
            continue
        item.page_id = pages[index % len(pages)].id if pages else None

    return normalized


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
        enforce_auto_idea_limit(account, request.count, db)
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
        summaries = _page_context_summaries(pages) + _collect_source_summaries()

        # Fallback: if no pages and no trusted sources, use a generic context
        # so idea generation can still proceed
        if not summaries:
            summaries = [
                {
                    "id": "generic-fallback",
                    "name": "เนื้อหาทั่วไป",
                    "url": "page://generic",
                    "content_pillar": "ไลฟ์สไตล์",
                    "title": "ไอเดียคอนเทนต์ Facebook",
                    "summary": (
                        "สร้างเนื้อหาที่น่าสนใจ มีคุณค่า และแชร์ได้สำหรับ Facebook "
                        "โดยเน้นประโยชน์แก่ผู้อ่าน ข้อมูลที่เป็นประโยชน์ และเรื่องราวที่สร้างแรงบันดาลใจ"
                    ),
                }
            ]

        VIRAL_THRESHOLD = 70
        MAX_RESEARCHER_RETRIES = 2

        items = _generate_ideas_from_sources(summaries, request, pages)
        items = _dedupe_against_existing(db, items)
        viral_items = [it for it in items if (it.viral_score or 0) >= VIRAL_THRESHOLD]

        # If no ideas pass viral threshold, retry with larger batches
        retry = 0
        while len(viral_items) < 1 and retry < MAX_RESEARCHER_RETRIES:
            retry += 1
            from app.schemas.content import AutoIdeaDiscoveryRequest as _Req
            more_items = _generate_ideas_from_sources(
                summaries, _Req(count=request.count * 2, save_to_calendar=False), pages
            )
            more_items = _dedupe_against_existing(db, more_items)
            viral_items.extend(it for it in more_items if (it.viral_score or 0) >= VIRAL_THRESHOLD)

        # If still none after retries, use best available sorted by viral_score
        if not viral_items:
            viral_items = sorted(items, key=lambda x: x.viral_score or 0, reverse=True)

        items = viral_items[: request.count]

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
                    page_id=item.page_id,
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
            # Trigger auto-pipeline for each saved idea
            for created_item in created_items:
                celery_app.send_task(
                    "app.workers.tasks.auto_pipeline_for_idea_job",
                    args=[created_item.id, account_id],
                )
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
