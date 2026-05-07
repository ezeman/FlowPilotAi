from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Post, PostAsset, User


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned[:48] or "post-image"


def _asset_dir() -> Path:
    settings = get_settings()
    target = Path(settings.generated_media_dir) / "generated"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _asset_url(filename: str) -> str:
    return f"/media/generated/{filename}"


def _placeholder_svg(post: Post, prompt: str, variant_index: int) -> bytes:
    title = html.escape(post.title)
    safe_prompt = html.escape(prompt[:180])
    palette = [
        ("#d7efe8", "#f5efe5", "#0f766e", "#cf7135"),
        ("#e0e7ff", "#f8fafc", "#4338ca", "#0891b2"),
        ("#fee2e2", "#fff7ed", "#be123c", "#ea580c"),
        ("#dcfce7", "#eff6ff", "#15803d", "#2563eb"),
    ][(variant_index - 1) % 4]
    bg1, bg2, accent1, accent2 = palette
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1200" viewBox="0 0 1200 1200">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
  </defs>
  <rect width="1200" height="1200" fill="url(#bg)" />
  <circle cx="940" cy="220" r="170" fill="{accent1}" fill-opacity="0.14" />
  <circle cx="220" cy="980" r="220" fill="{accent2}" fill-opacity="0.12" />
  <rect x="84" y="96" width="1032" height="1008" rx="36" fill="#fffaf2" stroke="#d7cbbf" />
  <text x="132" y="184" font-size="38" font-family="Arial, sans-serif" fill="{accent1}">Clean Air Studio</text>
  <text x="132" y="280" font-size="68" font-weight="700" font-family="Arial, sans-serif" fill="#1b1a16">{title}</text>
  <text x="132" y="330" font-size="24" font-family="Arial, sans-serif" fill="#62584d">Variant {variant_index}</text>
  <foreignObject x="132" y="360" width="936" height="430">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: Arial, sans-serif; font-size: 34px; line-height: 1.5; color: #62584d;">
      {safe_prompt}
    </div>
  </foreignObject>
  <text x="132" y="1028" font-size="28" font-family="Arial, sans-serif" fill="#62584d">Generated placeholder illustration</text>
</svg>
""".strip()
    return svg.encode("utf-8")


def _create_asset_record(
    db: Session,
    post: Post,
    actor: User,
    prompt: str,
    file_path: Path,
    variant_index: int,
    source: str,
    revised_prompt: str | None = None,
) -> None:
    metadata: dict[str, str | int] = {
        "created_by_user_id": actor.id,
        "prompt": prompt,
        "source": source,
        "variant_index": variant_index,
    }
    if revised_prompt:
        metadata["revised_prompt"] = revised_prompt

    asset = PostAsset(
        post_id=post.id,
        asset_type="image",
        asset_url=_asset_url(file_path.name),
        alt_text=f"{post.title} - variant {variant_index}",
        metadata_json=metadata,
    )
    db.add(asset)


def generate_post_illustrations(db: Session, post: Post, actor: User, variant_count: int = 1) -> Post:
    settings = get_settings()
    prompt = post.image_prompt or f"Thai educational Facebook illustration for {post.title}, clean air, editorial infographic style"
    asset_dir = _asset_dir()
    filename_stem = f"post-{post.id}-{_safe_stem(post.title)}"

    try:
        client = None if settings.mock_external_services or not settings.openai_api_key else OpenAI(api_key=settings.openai_api_key)
        for variant_index in range(1, variant_count + 1):
            variant_prompt = f"{prompt}. Create variant {variant_index} with a distinct composition."
            if client is None:
                file_path = asset_dir / f"{filename_stem}-{uuid4().hex[:8]}-v{variant_index}.svg"
                file_path.write_bytes(_placeholder_svg(post, variant_prompt, variant_index))
                _create_asset_record(db, post, actor, variant_prompt, file_path, variant_index, "placeholder")
            else:
                response = client.images.generate(
                    model=settings.openai_image_model,
                    prompt=variant_prompt,
                    size="1024x1024",
                )
                image_payload = response.data[0]
                b64_data = getattr(image_payload, "b64_json", None)
                if not b64_data:
                    raise ValueError("OpenAI image response did not include image data")
                file_path = asset_dir / f"{filename_stem}-{uuid4().hex[:8]}-v{variant_index}.png"
                file_path.write_bytes(base64.b64decode(b64_data))
                revised_prompt = getattr(image_payload, "revised_prompt", None)
                _create_asset_record(db, post, actor, variant_prompt, file_path, variant_index, "openai", revised_prompt)
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image generation failed: {exc}",
        ) from exc
