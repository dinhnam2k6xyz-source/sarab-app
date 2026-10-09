import io
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Query, Response, status
import httpx
from app.core.security import validate_url_ssrf

from typing import Optional

from app.image_translator.bubble_translator import translate_comic_image

router = APIRouter()


@router.get("/proxy/image")
async def proxy_image(
    url: str = Query(..., description="Image URL to proxy"),
    referer: Optional[str] = Query(default=None, description="Optional custom referer header"),
    translate: bool = Query(default=True, description="Whether to translate speech bubbles inside comic panels"),
):
    """
    Image proxy to bypass CDN anti-hotlinking / referer protection (such as Webtoons, Naver CDN),
    translate speech bubbles inside comic panels into Vietnamese, and ensure 100% of images load in reader.
    """
    # 0. Fast disk-cache check by URL hash to return translated panel in 0ms
    import hashlib
    import os
    from app.image_translator.bubble_translator import CACHE_DIR
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    url_cache_path = os.path.join(CACHE_DIR, f"url_{url_hash}.jpg")
    if translate and os.path.exists(url_cache_path):
        try:
            with open(url_cache_path, "rb") as f:
                cached_data = f.read()
            return Response(
                content=cached_data,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except Exception:
            pass

    # 1. SSRF Security check (only needed when downloading from network)
    is_safe, error_msg = validate_url_ssrf(url)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SSRF_BLOCKED", "message": error_msg},
        )

    parsed = urlparse(url)
    domain = parsed.hostname or ""

    # Determine required Referer based on domain
    req_referer = referer if isinstance(referer, str) and referer else ""
    if not req_referer:
        if "webtoon" in domain or "pstatic.net" in domain:
            req_referer = "https://www.webtoons.com/"
        elif "syosetu" in domain:
            req_referer = "https://syosetu.com/"
        elif "royalroad" in domain:
            req_referer = "https://www.royalroad.com/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    if req_referer:
        headers["Referer"] = req_referer

    try:
        async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Failed to fetch image from CDN: status {resp.status_code}",
                )

            image_data = resp.content
            was_translated = False
            # If translation is enabled, translate speech bubbles directly inside the comic panel
            if translate:
                try:
                    from app.image_translator.bubble_translator import translate_comic_image_with_status
                    import asyncio
                    image_data, was_translated = await asyncio.wait_for(
                        translate_comic_image_with_status(image_data, url),
                        timeout=40.0,
                    )
                except Exception as trans_err:
                    import logging
                    logging.getLogger("novel_translator").warning(
                        f"Bubble translation failed or timed out for {url}: {trans_err}"
                    )

            if translate and was_translated:
                try:
                    with open(url_cache_path, "wb") as f_out:
                        f_out.write(image_data)
                except Exception:
                    pass

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            cache_header = "public, max-age=604800, immutable" if was_translated else "no-cache, no-store, must-revalidate"
            return Response(
                content=image_data,
                media_type=content_type,
                headers={
                    "Cache-Control": cache_header,
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Proxy error: {str(exc)}",
        )
