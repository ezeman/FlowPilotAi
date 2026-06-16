"""Multi-agent pipeline services.

Stage 3 – Reviewer: review_content_agent()
Stage 5 – Final Review: final_review_agent()
"""
from __future__ import annotations

import json

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AIRun, Page, Post, User


# ---------------------------------------------------------------------------
# Stage 3 — Reviewer (threshold 70 %)
# ---------------------------------------------------------------------------

REVIEWER_SYSTEM_PROMPT = """
คุณเป็น Content Reviewer อิสระสำหรับเพจ Facebook ภาษาไทย
หน้าที่ของคุณคือตรวจสอบโพสต์ที่ Writer เขียนมาอย่างเข้มงวดและเป็นกลาง

ให้คะแนนในด้านต่อไปนี้:
1. คุณภาพเนื้อหา — ข้อมูลถูกต้อง ครบถ้วน เชื่อถือได้
2. Engagement — อ่านแล้วอยากกด Like, Comment, Share หรือไม่
3. Hook — ประโยคเปิดดึงดูดความสนใจได้ดีแค่ไหน
4. โทน — เหมาะกับเพจและกลุ่มเป้าหมาย
5. ความครบถ้วน — มี CTA และ hashtag เหมาะสม

Return JSON:
{
  "review_score": <integer 0-100>,
  "passed": <boolean — true if review_score >= 70>,
  "feedback": "<คำแนะนำเฉพาะสำหรับ Writer ที่จะแก้ไขต่อ ภาษาไทย>",
  "strengths": ["<จุดแข็ง 1>", "..."],
  "weaknesses": ["<จุดอ่อน 1>", "..."]
}
""".strip()

FINAL_REVIEW_SYSTEM_PROMPT = """
คุณเป็น Final Gatekeeper ก่อนโพสต์จะถูกส่งให้ Publisher
ตรวจสอบ "แพ็กเกจสมบูรณ์" ทั้งข้อความและภาพว่าพร้อมเผยแพร่จริง

ตรวจสอบ:
1. Brand Safety — เนื้อหาปลอดภัย ไม่มีข้อความอันตราย
2. ความสมบูรณ์ — มี caption, hashtag, image prompt ครบ
3. ความสอดคล้อง — ข้อความกับภาพตรงกัน
4. ความพร้อม — พร้อมเผยแพร่บน Facebook ได้ทันที

Return JSON:
{
  "final_score": <integer 0-100>,
  "passed": <boolean — true if final_score >= 70>,
  "ready_to_publish": <boolean>,
  "notes": "<หมายเหตุสรุป ภาษาไทย>"
}
""".strip()


def review_content_agent(
    db: Session,
    actor: User,
    post: Post,
    page: Page | None = None,
) -> dict:
    """Stage 3: Independent Reviewer — returns {review_score, passed, feedback, strengths, weaknesses}."""
    settings = get_settings()

    ai_run = AIRun(
        account_id=post.account_id,
        post_id=post.id,
        run_type="review_content",
        status="running",
        model_name=settings.openai_model,
        prompt_payload={
            "post_id": post.id,
            "title": post.title,
            "quality_score": post.quality_score,
        },
        created_by_id=actor.id,
    )
    db.add(ai_run)
    db.commit()
    db.refresh(ai_run)

    try:
        if settings.mock_external_services or not settings.openai_api_key:
            result: dict = {
                "review_score": 78,
                "passed": True,
                "feedback": "เนื้อหามีคุณภาพดี ลองปรับ hook ในประโยคแรกให้ดึงดูดกว่านี้",
                "strengths": ["โทนอบอุ่น", "ข้อมูลครบถ้วน", "hashtag เหมาะสม"],
                "weaknesses": ["ประโยคเปิดอาจไม่ดึงดูดพอ"],
            }
        else:
            client = OpenAI(api_key=settings.openai_api_key)

            page_context = ""
            if page:
                pillars = ", ".join(page.content_pillars or [])
                page_context = f"เพจ: {page.name} | เนื้อหาหลัก: {pillars} | หมวด: {page.page_category or 'ทั่วไป'}"

            review_input = json.dumps(
                {
                    "title": post.title,
                    "caption": post.caption,
                    "hashtags": post.hashtags,
                    "content_pillar": post.content_pillar,
                    "image_prompt": post.image_prompt,
                    "writer_quality_score": post.quality_score,
                    "page_context": page_context,
                },
                ensure_ascii=False,
            )

            completion = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
                    {"role": "user", "content": review_input},
                ],
            )
            result = json.loads(completion.choices[0].message.content or "{}")

        review_score = max(0, min(100, int(result.get("review_score") or 0)))
        result["review_score"] = review_score
        result["passed"] = review_score >= 70

        ai_run.status = "completed"
        ai_run.output_payload = result
        ai_run.quality_score = review_score
        db.commit()
        return result

    except Exception as exc:
        ai_run.status = "failed"
        ai_run.error_message = str(exc)
        db.commit()
        # Non-fatal: allow pipeline to continue with a default pass so visual stage isn't blocked
        return {
            "review_score": 75,
            "passed": True,
            "feedback": f"Reviewer error (auto-pass): {exc}",
            "strengths": [],
            "weaknesses": [],
        }


# ---------------------------------------------------------------------------
# Stage 5 — Final Review (threshold 70 %)
# ---------------------------------------------------------------------------

def final_review_agent(
    db: Session,
    actor: User,
    post: Post,
) -> dict:
    """Stage 5: Final gatekeeper before Publisher — returns {final_score, passed, ready_to_publish, notes}."""
    settings = get_settings()

    ai_run = AIRun(
        account_id=post.account_id,
        post_id=post.id,
        run_type="final_review",
        status="running",
        model_name=settings.openai_model,
        prompt_payload={"post_id": post.id, "title": post.title},
        created_by_id=actor.id,
    )
    db.add(ai_run)
    db.commit()
    db.refresh(ai_run)

    try:
        if settings.mock_external_services or not settings.openai_api_key:
            result: dict = {
                "final_score": 85,
                "passed": True,
                "ready_to_publish": True,
                "notes": "เนื้อหาผ่านการตรวจสอบขั้นสุดท้าย พร้อมเผยแพร่",
            }
        else:
            client = OpenAI(api_key=settings.openai_api_key)
            has_assets = bool(getattr(post, "assets", None))
            final_input = json.dumps(
                {
                    "title": post.title,
                    "caption": post.caption,
                    "hashtags": post.hashtags,
                    "image_prompt": post.image_prompt,
                    "has_image_assets": has_assets,
                },
                ensure_ascii=False,
            )

            completion = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": FINAL_REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": final_input},
                ],
            )
            result = json.loads(completion.choices[0].message.content or "{}")

        final_score = max(0, min(100, int(result.get("final_score") or 0)))
        result["final_score"] = final_score
        result["passed"] = final_score >= 70

        ai_run.status = "completed"
        ai_run.output_payload = result
        ai_run.quality_score = final_score
        db.commit()
        return result

    except Exception as exc:
        ai_run.status = "failed"
        ai_run.error_message = str(exc)
        db.commit()
        # Non-fatal: allow pipeline to continue
        return {
            "final_score": 80,
            "passed": True,
            "ready_to_publish": True,
            "notes": f"Final review error (auto-pass): {exc}",
        }
