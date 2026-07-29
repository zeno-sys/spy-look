from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


async def fetch_page_metadata(url: str, timeout: float = 8.0) -> dict:
    """Fetch page title and favicon URL from a web page.

    Returns:
        {"title": str, "favicon_url": str}
        On failure, includes "error" key with the exception message.
    """
    raw_url = url.strip()
    if not raw_url:
        return {"title": "", "favicon_url": "", "error": "URL 不能为空"}

    # Ensure scheme
    if "://" not in raw_url:
        raw_url = "https://" + raw_url

    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            resp = await client.get(
                raw_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SpyLook-Bookmark/1.0)"
                },
            )
            resp.raise_for_status()
            html = resp.text

            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                # Try og:title meta tag
                og_title = soup.find("meta", property="og:title")
                if og_title and og_title.get("content"):
                    title = og_title["content"].strip()
            if not title:
                title = urlparse(raw_url).hostname or raw_url

            # Extract favicon
            favicon_url = ""
            # Try <link rel="icon">, <link rel="shortcut icon">, <link rel="apple-touch-icon">
            for rel_name in ("icon", "shortcut icon", "apple-touch-icon"):
                icon_link = soup.find("link", rel=rel_name)
                if icon_link and icon_link.get("href"):
                    favicon_url = urljoin(raw_url, icon_link["href"])
                    break
            if not favicon_url:
                parsed = urlparse(raw_url)
                favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

            return {"title": title, "favicon_url": favicon_url}
    except Exception as e:
        parsed = urlparse(raw_url)
        return {
            "title": parsed.hostname or "",
            "favicon_url": f"{parsed.scheme}://{parsed.netloc}/favicon.ico",
            "error": str(e),
        }
