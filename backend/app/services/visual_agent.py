from __future__ import annotations

import json

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AIRun, Page, Post, User


VISUAL_SYSTEM_PROMPT_BASE = """
You are a visual design specialist for a Thai Facebook fanpage.
Your job is to create a strong image-generation prompt for a square social post.

Rules:
- Respond in Thai
- Focus on educational editorial visuals, not product ads
- Avoid too much text inside the image
- Prefer clean composition, clear focal point, infographic-friendly layout
- Mention style, subject, composition, lighting/color mood, and objects to avoid
- Return strict JSON with keys: image_prompt, art_direction, alt_text
""".strip()


def _build_visual_system_prompt(page: Page | None) -> str:
    if page:
        pillars = ", ".join(page.content_pillars or []) if page.content_pillars else "general"
        category = page.page_category or "General"
        desc_line = f" \u2014 {page.description}" if page.description else ""
        return (
            f"You are a visual design specialist for the Thai Facebook fanpage '{page.name}' ({category}{desc_line}).\n"
            f"This page covers: {pillars}\n"
            "Your job is to create a strong image-generation prompt for a square social post.\n"
            "Rules:\n"
            "- Respond in Thai\n"
            "- Educational editorial visuals only, not product ads\n"
            "- Avoid too much text inside the image\n"
            "- Clean composition, clear focal point, infographic-friendly layout\n"
            "- Visuals must match the page theme and content pillar\n"
            "- Mention style, subject, composition, lighting/color mood, and objects to avoid\n"
            "- Return strict JSON with keys: image_prompt, art_direction, alt_text"
        )
    return VISUAL_SYSTEM_PROMPT_BASE


def _mock_visual_payload(post: Post) -> dict:
    return {
        "image_prompt": (
            f"ภาพประกอบสี่เหลี่ยมสำหรับโพสต์ Facebook เรื่อง {post.title} "
            "โทน editorial infographic สะอาด ทันสมัย "
            "มี focal point ชัดเจน สื่อแนวคิดสอดคล้องกับเนื้อหา "
            "หลีกเลี่ยงตัวหนังสือเยอะและหน้าคนที่ดูเป็น stock photo"
        ),
        "art_direction": "ภาพให้ความรู้ ดูน่าเชื่อถือ ใช้ layout ที่อ่านง่ายและมีพื้นที่สำหรับนำไปครอปบนโซเชียล",
        "alt_text": post.title,
    }


def create_visual_brief(db: Session, post: Post, actor: User) -> Post:
    settings = get_settings()
    page: Page | None = None
    if post.page_id:
        page = db.query(Page).filter(Page.id == post.page_id).first()
    system_prompt = _build_visual_system_prompt(page)
    ai_run = AIRun(
        account_id=post.account_id,
        post_id=post.id,
        run_type="generate_visual_brief",
        status="running",
        model_name=settings.openai_model,
        prompt_payload={
            "post_id": post.id,
            "title": post.title,
            "caption": post.caption,
            "content_pillar": post.content_pillar,
            "existing_image_prompt": post.image_prompt,
        },
        created_by_id=actor.id,
    )
    db.add(ai_run)
    db.commit()
    db.refresh(ai_run)

    try:
        if settings.mock_external_services or not settings.openai_api_key:
            payload = _mock_visual_payload(post)
        else:
            client = OpenAI(api_key=settings.openai_api_key)
            completion = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "title": post.title,
                                "caption": post.caption,
                                "content_pillar": post.content_pillar,
                                "target_audience": post.target_audience,
                                "tone": post.tone,
                                "existing_image_prompt": post.image_prompt,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            payload = json.loads(completion.choices[0].message.content or "{}")

        post.image_prompt = str(payload.get("image_prompt") or post.image_prompt or "").strip()
        ai_run.status = "completed"
        ai_run.output_payload = payload
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        ai_run.status = "failed"
        ai_run.error_message = str(exc)
        db.commit()
        raise
