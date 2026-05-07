from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.encryption import decrypt_value
from app.models.entities import Page, Post, PublishLog


def publish_post_to_facebook(db: Session, post: Post) -> PublishLog:
    if post.status not in {"approved", "scheduled"}:
        raise ValueError("Post must be approved or scheduled before publishing")
    if not post.page_id:
        raise ValueError("Post must be assigned to a page")

    page = db.query(Page).filter(Page.id == post.page_id).first()
    if not page:
        raise ValueError("Facebook page configuration not found")

    settings = get_settings()
    payload = {"message": post.caption or "", "published": True}
    if post.scheduled_for:
        payload["scheduled_publish_time"] = int(post.scheduled_for.timestamp())
        payload["published"] = False

    log = PublishLog(
        account_id=post.account_id,
        post_id=post.id,
        page_id=page.id,
        status="publishing",
        request_payload=payload,
        response_payload={},
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        if settings.mock_external_services:
            response_payload = {
                "id": f"mock_{post.id}_{int(datetime.now(timezone.utc).timestamp())}",
                "message": "Mock publish completed",
            }
        else:
            access_token = decrypt_value(page.access_token_encrypted)
            if not access_token:
                raise ValueError("Missing or invalid page access token")
            graph_path = "photos" if post.assets else "feed"
            if post.assets:
                payload["url"] = post.assets[0].asset_url
                payload["caption"] = post.caption or ""
                payload.pop("message", None)
            url = f"https://graph.facebook.com/{settings.facebook_graph_api_version}/{page.facebook_page_id}/{graph_path}"
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, data={**payload, "access_token": access_token})
            response.raise_for_status()
            response_payload = response.json()

        post.status = "posted" if not post.scheduled_for else "scheduled"
        post.fb_post_id = response_payload.get("id")
        post.last_error = None
        log.status = "success"
        log.response_payload = response_payload
        log.fb_post_id = response_payload.get("id")
        db.commit()
        return log
    except Exception as exc:
        post.status = "failed"
        post.last_error = str(exc)
        log.status = "failed"
        log.error_message = str(exc)
        db.commit()
        return log
