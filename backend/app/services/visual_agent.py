from __future__ import annotations

import json

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AIRun, Post, User


VISUAL_SYSTEM_PROMPT = """
You are a visual design specialist for a Thai educational Facebook page about clean air, health, ventilation, mold, climate, CO2 and indoor air quality.
Your job is to create a strong image-generation prompt for a square social post.

Rules:
- Respond in Thai
- Focus on educational editorial visuals, not product ads
- Avoid too much text inside the image
- Prefer clean composition, clear focal point, infographic-friendly layout
- Mention style, subject, composition, lighting/color mood, and objects to avoid
- Return strict JSON with keys: image_prompt, art_direction, alt_text
""".strip()


def _mock_visual_payload(post: Post) -> dict:
    return {
        "image_prompt": (
            f"ภาพประกอบสี่เหลี่ยมสำหรับโพสต์ Facebook เรื่อง {post.title} "
            "โทน editorial infographic สะอาด ทันสมัย ใช้สี indigo, slate และ cyan "
            "มี focal point ชัดเจน สื่อแนวคิดคุณภาพอากาศ การระบายอากาศ และสุขภาพ "
            "หลีกเลี่ยงตัวหนังสือเยอะและหน้าคนที่ดูเป็น stock photo"
        ),
        "art_direction": "ภาพให้ความรู้ ดูน่าเชื่อถือ ใช้ layout ที่อ่านง่ายและมีพื้นที่สำหรับนำไปครอปบนโซเชียล",
        "alt_text": post.title,
    }


def create_visual_brief(db: Session, post: Post, actor: User) -> Post:
    settings = get_settings()
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
                    {"role": "system", "content": VISUAL_SYSTEM_PROMPT},
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
