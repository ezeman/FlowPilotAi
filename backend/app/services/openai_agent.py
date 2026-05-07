from __future__ import annotations

import json
import re

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AIRun, Post, User
from app.schemas.content import GenerateContentRequest


SYSTEM_PROMPT = """
You are a Thai-language editorial AI for a Facebook fanpage named 'อากาศสะอาด'.
Write educational, trustworthy, non-salesy Facebook content about clean air, indoor air quality, environmental innovation, health, CO2, VOC, ventilation, mold, climate, and practical lifestyle tips.
Rules:
- Thai language only
- Professional but easy to understand
- No product selling
- No exaggerated medical claims
- Include practical advice
- Suitable for Facebook post
- Default length: 120-180 Thai words
- Return valid JSON with keys: title, caption, hashtags, image_prompt, reference_suggestions, quality_score
""".strip()


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        hashtag_matches = re.findall(r"#[^#\s,\n\r]+", value)
        if hashtag_matches:
            return hashtag_matches
        parts = re.split(r"[\n,]+", value)
        return [part.strip(" -\t\r") for part in parts if part.strip(" -\t\r")]
    return []


def _normalize_result(payload: GenerateContentRequest, result: dict) -> dict:
    normalized = dict(result)
    normalized["title"] = str(normalized.get("title") or payload.topic).strip()
    normalized["caption"] = str(normalized.get("caption") or "").strip()
    normalized["image_prompt"] = str(normalized.get("image_prompt") or "").strip()
    normalized["hashtags"] = _coerce_list(normalized.get("hashtags"))
    normalized["reference_suggestions"] = _coerce_list(normalized.get("reference_suggestions"))

    try:
        normalized["quality_score"] = int(normalized.get("quality_score", 0))
    except (TypeError, ValueError):
        normalized["quality_score"] = 0

    normalized["quality_score"] = max(0, min(100, normalized["quality_score"]))
    return normalized


def _mock_content(payload: GenerateContentRequest) -> dict:
    topic = payload.topic.strip()
    caption = (
        f"{topic} ไม่ได้เป็นเรื่องไกลตัวอย่างที่หลายคนคิด เพราะอากาศในบ้านและที่ทำงานมีผลต่อการใช้ชีวิตทุกวัน\n\n"
        f"ประเด็นสำคัญคือการสังเกตแหล่งสะสมมลพิษ การระบายอากาศ และพฤติกรรมเล็ก ๆ ที่ช่วยลดความเสี่ยงได้ เช่น เปิดพัดลมดูดอากาศเมื่อทำความสะอาด เลือกช่วงเวลาเปิดหน้าต่างที่อากาศภายนอกเหมาะสม และหมั่นเช็กความชื้นในห้อง\n\n"
        f"ลองเริ่มจากการสำรวจพื้นที่ที่ใช้งานบ่อยที่สุด แล้วจดว่ามีกลิ่นอับ อากาศนิ่ง หรือความชื้นสะสมตรงไหนบ้าง วิธีนี้จะช่วยให้แก้ปัญหาได้ตรงจุดและยั่งยืนกว่าเดิม"
    )
    return {
        "title": topic,
        "caption": caption,
        "hashtags": ["#อากาศสะอาด", "#คุณภาพอากาศ", "#IndoorAir", "#HealthyHome"],
        "image_prompt": f"Educational Thai Facebook graphic about {topic}, clean editorial layout, friendly icons, Thai infographic style",
        "reference_suggestions": [
            "WHO indoor air quality guidance",
            "ASHRAE ventilation references",
            "กรมอนามัย หรือหน่วยงานสาธารณสุขที่เกี่ยวข้อง",
        ],
        "quality_score": 82,
    }


def generate_content(db: Session, user: User, payload: GenerateContentRequest) -> dict:
    settings = get_settings()
    linked_post = None
    if payload.post_id:
        linked_post = db.query(Post).filter(Post.id == payload.post_id).first()

    ai_run = AIRun(
        account_id=linked_post.account_id if linked_post else user.account_id,
        post_id=linked_post.id if linked_post else None,
        run_type="generate_content",
        status="running",
        model_name=settings.openai_model,
        prompt_payload=payload.model_dump(),
        created_by_id=user.id,
    )
    db.add(ai_run)
    db.commit()
    db.refresh(ai_run)

    try:
        if settings.mock_external_services or not settings.openai_api_key:
            result = _mock_content(payload)
        else:
            client = OpenAI(api_key=settings.openai_api_key)
            completion = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "topic": payload.topic,
                                "content_pillar": payload.content_pillar,
                                "target_audience": payload.target_audience,
                                "tone": payload.tone,
                                "post_length": payload.post_length,
                                "reference_notes": payload.reference_notes,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            result = json.loads(completion.choices[0].message.content or "{}")

        result = _normalize_result(payload, result)

        ai_run.status = "completed"
        ai_run.output_payload = result
        ai_run.quality_score = int(result.get("quality_score", 0))
        db.commit()

        if linked_post:
            linked_post.title = result.get("title", linked_post.title)
            linked_post.caption = result.get("caption", linked_post.caption)
            linked_post.hashtags = result.get("hashtags", [])
            linked_post.image_prompt = result.get("image_prompt", linked_post.image_prompt)
            linked_post.quality_score = result.get("quality_score")
            linked_post.status = "draft"
            db.commit()

        return result
    except Exception as exc:
        ai_run.status = "failed"
        ai_run.error_message = str(exc)
        db.commit()
        raise
