"""Fetch and parse content from scientific sources by URL.

Supported sources:
- researchgate.net
- elibrary.ru
- link.springer.com
- patents.google.com
- mdpi.com
- cyberleninka.ru
- onlinelibrary.wiley.com
- sciencedirect.com
- sci-hub.ru
"""

import re
from urllib.parse import urlparse

import httpx

SUPPORTED_DOMAINS = {
    "www.researchgate.net": "ResearchGate",
    "researchgate.net": "ResearchGate",
    "www.elibrary.ru": "eLibrary",
    "elibrary.ru": "eLibrary",
    "link.springer.com": "Springer",
    "patents.google.com": "Google Patents",
    "www.mdpi.com": "MDPI",
    "cyberleninka.ru": "CyberLeninka",
    "onlinelibrary.wiley.com": "Wiley",
    "www.sciencedirect.com": "ScienceDirect",
    "sciencedirect.com": "ScienceDirect",
    "sci-hub.ru": "Sci-Hub",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT = 30


def detect_source(url: str) -> str | None:
    """Return source provider name if URL is from a supported domain."""
    host = urlparse(url).hostname or ""
    return SUPPORTED_DOMAINS.get(host)


def is_supported_url(url: str) -> bool:
    """Check whether the URL is from a supported source."""
    return detect_source(url) is not None


def fetch_url_content(url: str) -> dict:
    """
    Fetch a URL and extract readable text content.

    Returns:
        {
            "url": str,
            "source_provider": str,
            "title": str,
            "text": str,
            "filename": str,
        }

    Raises:
        ValueError: if URL is unsupported or fetch fails.
    """
    source = detect_source(url)
    if not source:
        supported = ", ".join(sorted(set(SUPPORTED_DOMAINS.values())))
        raise ValueError(f"Неподдерживаемый источник. Поддерживаются: {supported}")

    try:
        with httpx.Client(follow_redirects=True, timeout=HTTP_TIMEOUT, headers=HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise ValueError(f"Таймаут при загрузке страницы: {url}")
    except httpx.HTTPStatusError as e:
        raise ValueError(f"Ошибка HTTP {e.response.status_code}: {url}")
    except Exception as e:
        raise ValueError(f"Ошибка загрузки: {e}")

    content_type = resp.headers.get("content-type", "")

    # If we got a PDF directly, treat it as binary
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return _handle_pdf_response(resp, url, source)

    html = resp.text
    text, title = _parse_html(html, url, source)

    if not text or len(text.strip()) < 50:
        raise ValueError("Не удалось извлечь текст из страницы. Возможно, контент требует авторизации.")

    safe_title = _safe_filename(title or _extract_title(html) or "page")
    filename = f"{safe_title}.txt"

    return {
        "url": url,
        "source_provider": source,
        "title": title,
        "text": text,
        "filename": filename,
    }


def _handle_pdf_response(resp: httpx.Response, url: str, source: str) -> dict:
    """Handle a direct PDF response."""
    filename = _pdf_filename_from_url(url)
    return {
        "url": url,
        "source_provider": source,
        "title": filename.replace(".pdf", ""),
        "text": "",  # will be handled by caller as raw bytes
        "filename": filename,
        "raw_pdf": resp.content,
    }


def _pdf_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = path.split("/")[-1].split("?")[0]
    if name and ".pdf" in name.lower():
        return _safe_filename(name)
    return "document.pdf"


def _safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:120].strip("_.")


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def _parse_html(html: str, url: str, source: str) -> tuple[str, str]:
    """Source-specific HTML parsing to extract article text."""
    if source == "ResearchGate":
        return _parse_researchgate(html)
    if source == "eLibrary":
        return _parse_elibrary(html)
    if source == "Springer":
        return _parse_springer(html)
    if source == "Google Patents":
        return _parse_patents(html)
    if source == "MDPI":
        return _parse_mdpi(html)
    if source == "CyberLeninka":
        return _parse_cyberleninka(html)
    if source == "Wiley":
        return _parse_wiley(html)
    if source == "ScienceDirect":
        return _parse_sciencedirect(html)
    if source == "Sci-Hub":
        return _parse_scihub(html)
    return _parse_generic(html)


def _strip_tags(html: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_from_selectors(html: str, selectors: list[str]) -> str:
    """Try to extract text content using regex-based CSS selector approximation."""
    for sel in selectors:
        # Simple tag extraction: e.g. "div.abstract" -> <div[^>]*class="[^"]*abstract[^"]*"[^>]*>...</div>
        parts = sel.split(".", 1)
        tag = parts[0]
        cls = parts[1] if len(parts) > 1 else None
        if cls:
            pattern = rf"<{tag}[^>]*class=\"[^\"]*{cls}[^\"]*\"[^>]*>(.*?)</{tag}>"
        else:
            pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if m:
            text = _strip_tags(m.group(1))
            if text and len(text) > 30:
                return text
    return ""


# ── Source-specific parsers ─────────────────────────────────

def _parse_researchgate(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, ["h1", "meta[property='og:title']"])
    abstract = _extract_from_selectors(html, [
        "div.abstract", "div[class*='abstract']", "div[data-testid='abstract']",
        "section.abstract", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div.nova-legacy-e-text", "div[class*='nova-legacy-e-text']",
        "article", "div.publication-content",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_elibrary(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, ["h1", "meta[name='citation_title']"])
    abstract = _extract_from_selectors(html, [
        "div.abstract", "div[itemprop='description']",
        "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div#annotation", "div.article-text", "div[itemprop='articleBody']",
        "article",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_springer(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, [
        "h1.c-article-title", "h1", "meta[name='citation_title']",
    ])
    abstract = _extract_from_selectors(html, [
        "div.c-article-section__content", "section#Abs1-content",
        "div#Abs1-content", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div.c-article-body", "div#Sec1-content",
        "article", "div.c-article-section",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_patents(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, [
        "span[itemprop='title']", "h1", "meta[name='title']",
    ])
    abstract = _extract_from_selectors(html, [
        "div.abstract", "section.abstract", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "section.description", "div.description", "article",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_mdpi(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, [
        "h1", "meta[name='citation_title']",
    ])
    abstract = _extract_from_selectors(html, [
        "div.html-abstract", "div#abstract", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div.html-body", "div#html-body",
        "article", "div.markdown-parser-holder",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_cyberleninka(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, [
        "h1", "meta[property='og:title']",
    ])
    abstract = _extract_from_selectors(html, [
        "div.abstract", "div.annotation", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div#article", "div.content", "article", "div.paper-body",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_wiley(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, [
        "h1.article-title", "h1", "meta[name='citation_title']",
    ])
    abstract = _extract_from_selectors(html, [
        "div.article-section__abstract", "div#abstract",
        "section.abstract", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div.article-section__content", "div#article-body",
        "article", "div.article-body",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_sciencedirect(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, [
        "h1.article-header-title", "h1", "meta[name='citation_title']",
    ])
    abstract = _extract_from_selectors(html, [
        "div.abstract", "div#abstracts", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div.article-body", "div#article-body",
        "article", "div.u-margin-l-top",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_scihub(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, ["h1", "meta[name='citation_title']"])
    abstract = _extract_from_selectors(html, [
        "div.abstract", "meta[name='description']",
    ])
    body = _extract_from_selectors(html, [
        "div#article", "div.content", "article",
        "iframe", "div.document",
    ])
    parts = [p for p in [title, abstract, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)


def _parse_generic(html: str) -> tuple[str, str]:
    title = _extract_from_selectors(html, ["h1", "meta[name='citation_title']"])
    body = _extract_from_selectors(html, [
        "article", "main", "div.content", "div#content",
    ])
    parts = [p for p in [title, body] if p]
    return "\n\n".join(parts), title or _extract_title(html)
