from __future__ import annotations

from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# List of selector tags to strip (noise elements)
NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "form"}
NOISE_CLASS_KEYWORDS = ["nav", "sidebar", "footer", "header", "menu", "advertisement", "广告"]

# Selectors for likely main content containers, ordered by priority
MAIN_SELECTORS = [
    ("article", None),
    ("main", None),
    ("div", {"class": "article"}),
    ("div", {"class": "content"}),
    ("div", {"class": "post"}),
    ("div", {"id": "content"}),
    ("div", {"id": "article"}),
    ("div", {"class": "main"}),
    ("div", {"id": "main"}),
    ("body", None),
]


async def extract_content(url: str, timeout: float = 15.0) -> dict:
    """Fetch a URL and extract clean content (Markdown + raw HTML).

    Returns:
        {"title": str, "content_md": str, "content_html": str, "error"?: str}
    """
    raw_url = url.strip()
    if not raw_url:
        return {"title": "", "content_md": "", "content_html": "", "error": "URL 不能为空"}

    if "://" not in raw_url:
        raw_url = "https://" + raw_url

    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            resp = await client.get(
                raw_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SpyLook-WebClip/1.0)"
                },
            )
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        parsed = urlparse(raw_url)
        return {
            "title": parsed.hostname or "",
            "content_md": "",
            "content_html": "",
            "error": str(e),
        }

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
        if not title:
            title = urlparse(raw_url).hostname or raw_url

        # Find main content container
        content_container = _find_main_content(soup)

        # Strip noise elements
        _strip_noise(content_container)

        # Serialize cleaned HTML
        content_html = str(content_container)

        # Convert to Markdown
        import html2text

        converter = html2text.HTML2Text()
        converter.body_width = 0  # no wrapping
        converter.ignore_links = False
        converter.ignore_images = False
        converter.ignore_emphasis = False
        converter.protect_links = True
        converter.unicode_snob = True
        content_md = converter.handle(content_html).strip()

        return {
            "title": title,
            "content_md": content_md,
            "content_html": content_html,
        }
    except Exception as e:
        return {
            "title": title if "title" in locals() else urlparse(raw_url).hostname or "",
            "content_md": "",
            "content_html": "",
            "error": f"解析失败: {e}",
        }


def _find_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Try to locate the main content container; fallback to <body>."""
    for tag, attrs in MAIN_SELECTORS:
        if attrs:
            container = soup.find(tag, attrs=attrs)
        else:
            container = soup.find(tag)
        if container:
            return container

    body = soup.find("body")
    return body if body else soup


def _strip_noise(tag: BeautifulSoup) -> None:
    """Remove noise elements from a BeautifulSoup tag in-place."""
    for selector in NOISE_TAGS:
        for el in tag.find_all(selector):
            el.decompose()

    # Remove elements with noise class keywords
    for el in tag.find_all(class_=True):
        cls = " ".join(el.get("class", []))
        if any(kw in cls.lower() for kw in NOISE_CLASS_KEYWORDS):
            el.decompose()
