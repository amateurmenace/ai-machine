"""
Web search and page fetching.

A local model's knowledge stops at its training cutoff and it cannot reach
anything on its own. These two tools are what let a community running Gemma
answer "what is the state deadline for this filing" without sending the
resident to a frontier provider.

**Network safety is the hard part, not the searching.** A model with a fetch
tool, running on a server that can reach `localhost:1234` and, on a cloud host,
`169.254.169.254`, is one crafted URL away from reading the inference server or
the instance's credentials. Every fetch therefore resolves the hostname first
and refuses private, loopback, link-local and cloud-metadata addresses, and
re-checks after each redirect. This is not optional hardening; it is the
difference between a safe deployment and a credential leak.

Four search backends, in the order a community should prefer them:

* ``searxng``    a SearXNG instance the community runs. No third party sees
                 residents' queries. The choice that matches the project.
* ``brave``      Brave Search API. A key, a bill, an independent index.
* ``tavily``     Tavily. A key; results are pre-summarized for models.
* ``duckduckgo`` no key, parses the public HTML endpoint. Convenient for
                 getting started and genuinely fragile: it is unofficial and
                 breaks when the markup changes. Do not build a town on it.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

from tools.base import Tool, ToolCitation, ToolResult

USER_AGENT = os.getenv(
    "COMMUNITY_USER_AGENT",
    "CommunityAI/0.2 (civic information assistant; +https://neighborhoodai.org)",
)

DEFAULT_TIMEOUT = 15.0
MAX_PAGE_CHARS = 20_000

# Cloud instance-metadata endpoints. On Google Cloud this address serves service
# account tokens to anything that can make an HTTP request from the instance.
_METADATA_HOSTS = {
    "169.254.169.254",      # GCP, AWS, Azure, DigitalOcean
    "metadata.google.internal",
    "metadata.goog",
    "fd00:ec2::254",
}


class BlockedURLError(ValueError):
    """Raised when a URL resolves somewhere the assistant must not reach."""


def _is_forbidden_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True  # unparseable is not provably safe
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or str(ip) in _METADATA_HOSTS
    )


def assert_public_url(url: str) -> str:
    """Validate a URL and confirm its host resolves to a public address.

    Resolution happens here rather than being left to the HTTP client because
    the check has to be about where the request actually lands. A hostname that
    looks innocuous can resolve to 127.0.0.1 or to the metadata service.
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise BlockedURLError(f"could not parse URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise BlockedURLError(
            f"only http and https are allowed, not {parsed.scheme or 'an empty scheme'}"
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise BlockedURLError("the URL has no hostname")

    if hostname in _METADATA_HOSTS or hostname.endswith(".internal"):
        raise BlockedURLError(f"{hostname} is an internal address")

    # A bare name with no dot is a local hostname.
    if "." not in hostname and hostname != "localhost":
        raise BlockedURLError(f"{hostname} is not a public hostname")
    if hostname == "localhost":
        raise BlockedURLError("localhost is not reachable from this tool")

    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise BlockedURLError(f"could not resolve {hostname}: {exc}") from exc

    for info in infos:
        address = info[4][0]
        if _is_forbidden_ip(address):
            raise BlockedURLError(
                f"{hostname} resolves to {address}, which is a private or "
                f"internal address this tool will not fetch"
            )

    return url


def _http_get(url: str, **kwargs: Any):
    import httpx

    headers = {"User-Agent": USER_AGENT}
    headers.update(kwargs.pop("headers", {}) or {})

    # Redirects are followed manually so each hop is re-validated. A redirect to
    # the metadata service would otherwise slip past the initial check.
    with httpx.Client(follow_redirects=False, timeout=DEFAULT_TIMEOUT) as client:
        current = assert_public_url(url)
        for _ in range(5):
            response = client.get(current, headers=headers, **kwargs)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    return response
                current = assert_public_url(str(httpx.URL(current).join(location)))
                continue
            return response
    raise BlockedURLError("too many redirects")


def _strip_html(html: str) -> str:
    """Extract readable text. Uses BeautifulSoup when present, regex otherwise."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()


# --- search backends ------------------------------------------------------


def _search_searxng(query: str, count: int, base_url: str,
                    api_key: Optional[str]) -> List[Dict[str, str]]:
    url = base_url.rstrip("/") + "/search"
    import httpx

    params = {"q": query, "format": "json", "safesearch": "1"}
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = httpx.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "snippet": r.get("content", "")}
        for r in response.json().get("results", [])[:count]
    ]


def _search_brave(query: str, count: int, api_key: str) -> List[Dict[str, str]]:
    import httpx

    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": count},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json",
                 "User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "snippet": r.get("description", "")}
        for r in response.json().get("web", {}).get("results", [])[:count]
    ]


def _search_tavily(query: str, count: int, api_key: str) -> List[Dict[str, str]]:
    import httpx

    response = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": count},
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "snippet": r.get("content", "")}
        for r in response.json().get("results", [])[:count]
    ]


_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r'.*?<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</a>',
    re.S,
)


def _search_duckduckgo(query: str, count: int) -> List[Dict[str, str]]:
    """Parse DuckDuckGo's HTML endpoint. No key, and no stability guarantee."""
    response = _http_get(
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    )
    response.raise_for_status()

    results = []
    for match in _DDG_RESULT_RE.finditer(response.text):
        url = match.group("url")
        # The HTML endpoint wraps targets in a redirector.
        redirect = re.search(r"uddg=([^&]+)", url)
        if redirect:
            from urllib.parse import unquote
            url = unquote(redirect.group(1))
        results.append({
            "title": _strip_html(match.group("title")),
            "url": url,
            "snippet": _strip_html(match.group("snippet")),
        })
        if len(results) >= count:
            break
    return results


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the public web for information that is not in this community's "
        "records: general facts, current events, state and federal rules, or "
        "anything outside this community. Returns titles, URLs and snippets. "
        "Follow up with fetch_url when a snippet is not enough."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
            "count": {"type": "integer", "description": "Results to return, 1-10.",
                      "default": 5},
        },
        "required": ["query"],
    }
    external = True

    def __init__(self, backend: str = "duckduckgo", base_url: Optional[str] = None,
                 api_key: Optional[str] = None) -> None:
        self.backend = (backend or "duckduckgo").lower()
        self.base_url = base_url
        self.api_key = api_key

    def run(self, query: str = "", count: int = 5, **_: Any) -> ToolResult:
        query = (query or "").strip()
        if not query:
            return ToolResult.failure("no search query was given")
        count = max(1, min(int(count or 5), 10))

        try:
            results = self._dispatch(query, count)
        except BlockedURLError as exc:
            return ToolResult.failure(str(exc))
        except Exception as exc:
            return ToolResult.failure(
                f"web search via {self.backend} failed: {type(exc).__name__}: {exc}"
            )

        if not results:
            return ToolResult(
                content=f"No web results for {query!r}.",
                meta={"backend": self.backend, "result_count": 0},
            )

        now = datetime.now().strftime("%Y-%m-%d")
        lines = [f"Web search results for {query!r} (via {self.backend}, {now}):", ""]
        citations = []
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result['title']}")
            lines.append(f"   {result['url']}")
            if result.get("snippet"):
                lines.append(f"   {result['snippet']}")
            lines.append("")
            citations.append(ToolCitation(
                title=result["title"] or result["url"],
                url=result["url"], kind="web",
                snippet=result.get("snippet", "")[:300], retrieved_at=now,
            ))

        return ToolResult(
            content="\n".join(lines).strip(),
            citations=citations,
            meta={"backend": self.backend, "result_count": len(results)},
        )

    def _dispatch(self, query: str, count: int) -> List[Dict[str, str]]:
        if self.backend == "searxng":
            if not self.base_url:
                raise ValueError(
                    "the searxng backend needs web_search_base_url set to the "
                    "community's SearXNG instance"
                )
            return _search_searxng(query, count, self.base_url, self.api_key)
        if self.backend == "brave":
            key = self.api_key or os.getenv("BRAVE_SEARCH_API_KEY")
            if not key:
                raise ValueError("the brave backend needs an API key")
            return _search_brave(query, count, key)
        if self.backend == "tavily":
            key = self.api_key or os.getenv("TAVILY_API_KEY")
            if not key:
                raise ValueError("the tavily backend needs an API key")
            return _search_tavily(query, count, key)
        return _search_duckduckgo(query, count)


class FetchURLTool(Tool):
    name = "fetch_url"
    description = (
        "Fetch a public web page and return its readable text. Use after "
        "web_search when a snippet is not enough, or when the resident gives "
        "you a URL. Only public pages; private and internal addresses are refused."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The full http(s) URL."},
            "max_chars": {"type": "integer",
                          "description": "Maximum characters to return.",
                          "default": 8000},
        },
        "required": ["url"],
    }
    external = True

    def __init__(self, allowed_domains: Optional[List[str]] = None) -> None:
        # An allowlist turns the tool from "the open web" into "these sources",
        # which some communities will want for a public-facing assistant.
        self.allowed_domains = [d.lower().lstrip(".") for d in (allowed_domains or [])]

    def run(self, url: str = "", max_chars: int = 8000, **_: Any) -> ToolResult:
        url = (url or "").strip()
        if not url:
            return ToolResult.failure("no URL was given")

        if self.allowed_domains:
            host = (urlparse(url).hostname or "").lower()
            if not any(host == d or host.endswith("." + d) for d in self.allowed_domains):
                return ToolResult.failure(
                    f"{host} is not in this deployment's allowed domains "
                    f"({', '.join(self.allowed_domains)})"
                )

        try:
            response = _http_get(url)
        except BlockedURLError as exc:
            return ToolResult.failure(str(exc))
        except Exception as exc:
            return ToolResult.failure(f"could not fetch {url}: {type(exc).__name__}: {exc}")

        if response.status_code >= 400:
            return ToolResult.failure(
                f"{url} returned HTTP {response.status_code}"
            )

        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            text = _strip_html(response.text)
        elif content_type.startswith("text/") or "json" in content_type:
            text = response.text
        else:
            return ToolResult.failure(
                f"{url} is {content_type or 'an unknown type'}, which this tool "
                f"cannot read as text"
            )

        limit = max(500, min(int(max_chars or 8000), MAX_PAGE_CHARS))
        truncated = len(text) > limit
        text = text[:limit]

        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", response.text)
        title = _strip_html(title_match.group(1)) if title_match else url

        now = datetime.now().strftime("%Y-%m-%d")
        body = f"Page: {title}\nURL: {url}\nRetrieved: {now}\n\n{text}"
        if truncated:
            body += "\n\n[truncated]"

        return ToolResult(
            content=body,
            citations=[ToolCitation(title=title, url=url, kind="page",
                                    snippet=text[:300], retrieved_at=now)],
            meta={"status": response.status_code, "truncated": truncated,
                  "chars": len(text)},
        )
