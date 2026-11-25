"""SSRF-protected polite multi-page URL ingestor with human-in-the-loop CAPTCHA recovery (§8.3)."""

from __future__ import annotations

import base64
import http.client
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from html.parser import HTMLParser
from typing import IO, Literal, Protocol, cast
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.document_parser import parse_document_bytes
from app.ingestion.models import (
    CaptchaPauseReport,
    DocumentSection,
    ExtractedTable,
    IngestionStagingJob,
    ParsedDocument,
    PoliteFetchPolicy,
    SubpageDiscoveryCandidate,
    SubpageFetchRecord,
    canonical_sha256,
)
from app.ruleset_vm.rng import DeterministicRngStream

_NON_CONTENT_TOKENS: tuple[str, ...] = (
    "/login",
    "/signin",
    "/signup",
    "/register",
    "/logout",
    "/auth",
    "/search",
    "/feed",
    "/rss",
    "action=edit",
    "printable=yes",
    "sort=",
    "filter=",
    "page=",
)
_BINARY_ASSET_EXTS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".zip",
    ".tar",
    ".gz",
    ".mp3",
    ".mp4",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
)
_REDIRECT_CODES: frozenset[int] = frozenset({301, 302, 303, 307, 308})


class SsrfBlockedError(Exception):
    """Raised when a URL resolves to a forbidden network scheme, host, or private/loopback IP."""


class UrlFetchError(Exception):
    """Raised on HTTP transport errors, disallowed robots rules, or response size overflows."""


class HttpFetchResponse(BaseModel):
    """Immutable HTTP response payload produced by default transport or test fake."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: bytes = b""


DnsResolverFn = Callable[[str, int], Sequence[str]]
HttpFetchFn = Callable[[str, Mapping[str, str], float, int], HttpFetchResponse]
SleepFn = Callable[[float], None]


def _is_disallowed_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return _is_disallowed_ip(addr.ipv4_mapped)
    return False


def _default_dns_resolver(hostname: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlFetchError(f"DNS lookup failed for '{hostname}': {exc}") from exc
    return [str(info[4][0]) for info in infos if info[4]]


def validate_url_target(
    url: str,
    *,
    dns_resolver: DnsResolverFn | None = None,
) -> str:
    """Validate URL scheme, credentials, hostname, and resolved IP addresses against SSRF."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise SsrfBlockedError(f"Blocked non-HTTP(S) URL scheme '{scheme or 'empty'}' in {url!r}.")
    if parsed.username is not None or parsed.password is not None:
        raise SsrfBlockedError("Blocked URL containing embedded user credentials.")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise SsrfBlockedError(f"Blocked URL without valid hostname: {url!r}.")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise SsrfBlockedError(f"Blocked loopback hostname '{hostname}'.")

    clean_host = hostname.split("%", 1)[0]
    try:
        literal_ip = ipaddress.ip_address(clean_host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_disallowed_ip(literal_ip):
            raise SsrfBlockedError(f"Blocked non-public IP literal '{literal_ip}'.")
        return urldefrag(url.strip()).url

    port = parsed.port or (443 if scheme == "https" else 80)
    resolver = dns_resolver or _default_dns_resolver
    resolved_ips = list(resolver(hostname, port))
    if not resolved_ips:
        raise UrlFetchError(f"Host '{hostname}' did not resolve to any IP addresses.")

    for raw_ip in resolved_ips:
        ip_no_scope = raw_ip.split("%", 1)[0]
        try:
            addr = ipaddress.ip_address(ip_no_scope)
        except ValueError as exc:
            raise SsrfBlockedError(f"Blocked invalid resolved address {raw_ip!r}.") from exc
        if _is_disallowed_ip(addr):
            raise SsrfBlockedError(
                f"Blocked SSRF target: host '{hostname}' resolved to disallowed IP '{addr}'."
            )

    return urldefrag(url.strip()).url


def detect_anti_bot_challenge(response: HttpFetchResponse) -> CaptchaPauseReport | None:
    """Detect Cloudflare, Turnstile, hCaptcha, reCAPTCHA, Altcha, or human-verify gates."""
    headers_l = {k.lower(): v.lower() for k, v in response.headers.items()}
    body_sample = response.body[:131072].decode("utf-8", errors="replace").lower()

    if headers_l.get("cf-mitigated") == "challenge" or any(
        marker in body_sample
        for marker in (
            "challenges.cloudflare.com",
            "cf-turnstile",
            "cf-challenge",
            "attention required! | cloudflare",
            "just a moment...",
        )
    ):
        return CaptchaPauseReport(
            paused_url=response.url,
            challenge_vendor="cloudflare_turnstile",
            http_status=response.status_code,
            reason="Detected Cloudflare anti-bot challenge; queue paused for human verification.",
        )

    if any(
        marker in body_sample
        for marker in ("hcaptcha.com/1/api.js", "h-captcha", "data-hcaptcha-sitekey")
    ):
        return CaptchaPauseReport(
            paused_url=response.url,
            challenge_vendor="hcaptcha",
            http_status=response.status_code,
            reason="Detected hCaptcha challenge; queue paused for human verification.",
        )

    if any(
        marker in body_sample
        for marker in ("google.com/recaptcha", "gstatic.com/recaptcha", "g-recaptcha")
    ):
        return CaptchaPauseReport(
            paused_url=response.url,
            challenge_vendor="recaptcha",
            http_status=response.status_code,
            reason="Detected reCAPTCHA challenge; queue paused for human verification.",
        )

    if any(marker in body_sample for marker in ("altcha-widget", "altcha.org")):
        return CaptchaPauseReport(
            paused_url=response.url,
            challenge_vendor="altcha",
            http_status=response.status_code,
            reason="Detected Altcha challenge; queue paused for human verification.",
        )

    if response.status_code in {403, 429, 503} and any(
        marker in body_sample
        for marker in (
            "verify you are human",
            "human verification",
            "are you a robot",
            "bot protection",
            "captcha",
        )
    ):
        return CaptchaPauseReport(
            paused_url=response.url,
            challenge_vendor="generic_anti_bot_gate",
            http_status=response.status_code,
            reason="Detected anti-bot verification gate; queue paused for human recovery.",
        )

    return None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> None:
        return None


class _ReadableStream(Protocol):
    def read(self, n: int = ..., /) -> bytes: ...


def _read_bounded_bytes(stream: _ReadableStream | IO[bytes], max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UrlFetchError(f"Response exceeded max size limit of {max_bytes} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)


def _default_http_fetch(
    url: str,
    headers: Mapping[str, str],
    timeout_seconds: float,
    max_bytes: int,
) -> HttpFetchResponse:
    req = urllib.request.Request(url, headers=dict(headers), method="GET")
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(req, timeout=timeout_seconds) as resp:
            body = _read_bounded_bytes(resp, max_bytes)
            hdrs = dict(resp.headers.items())
            return HttpFetchResponse(url=url, status_code=int(resp.status), headers=hdrs, body=body)
    except urllib.error.HTTPError as exc:
        body = _read_bounded_bytes(exc.fp, max_bytes) if exc.fp is not None else b""
        hdrs = dict(exc.headers.items()) if exc.headers is not None else {}
        return HttpFetchResponse(url=url, status_code=int(exc.code), headers=hdrs, body=body)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UrlFetchError(f"HTTP fetch error for '{url}': {exc}") from exc


class _DiscoveryHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.noindex = False
        self.nofollow = False
        self.links: list[tuple[str, str]] = []
        self._in_a = False
        self._current_href: str | None = None
        self._text_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        attr_map = {k.lower(): v or "" for k, v in attrs}
        if lower == "meta" and attr_map.get("name", "").strip().lower() == "robots":
            content_tokens = {
                tok.strip().lower() for tok in re.split(r"[,;\s]+", attr_map.get("content", ""))
            }
            if "noindex" in content_tokens:
                self.noindex = True
            if "nofollow" in content_tokens:
                self.nofollow = True
        elif lower == "a" and attr_map.get("href"):
            self._in_a = True
            self._current_href = attr_map["href"].strip()
            self._text_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._in_a and self._current_href:
            absolute = urljoin(self.base_url, self._current_href)
            label = " ".join("".join(self._text_buf).split())
            self.links.append((absolute, label))
            self._in_a = False
            self._current_href = None
            self._text_buf = []

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._text_buf.append(data)


def _scope_prefix_for_index(index_url: str) -> str:
    path = urlparse(index_url).path or "/"
    if path.endswith("/"):
        return path
    last_seg = path.rsplit("/", 1)[-1]
    if "." in last_seg:
        parent = path.rsplit("/", 1)[0]
        return f"{parent}/" if parent else "/"
    return path


def _is_within_scope(candidate_url: str, index_origin: tuple[str, str], scope_prefix: str) -> bool:
    parsed = urlparse(candidate_url)
    if (parsed.scheme.lower(), parsed.netloc.lower()) != index_origin:
        return False
    cand_path = parsed.path or "/"
    if scope_prefix == "/":
        return cand_path.startswith("/")
    if scope_prefix.endswith("/"):
        return cand_path.startswith(scope_prefix)
    return cand_path == scope_prefix or cand_path.startswith(f"{scope_prefix}/")


def _is_non_content_url(url: str) -> bool:
    parsed = urlparse(url)
    lower_path = parsed.path.lower()
    lower_full = f"{lower_path}?{parsed.query.lower()}"
    if any(lower_path.endswith(ext) for ext in _BINARY_ASSET_EXTS):
        return True
    return any(tok in lower_full for tok in _NON_CONTENT_TOKENS)


def _chapter_group_for_url(candidate_url: str, scope_prefix: str) -> str:
    path = urlparse(candidate_url).path or "/"
    rel = path[len(scope_prefix) :] if path.startswith(scope_prefix) else path
    parts = [p for p in rel.strip("/").split("/") if p]
    if len(parts) >= 2:
        return parts[0]
    if parts:
        stem = parts[0].rsplit(".", 1)[0]
        return stem or "root"
    return "root"


def _infer_content_kind(
    headers: Mapping[str, str], url: str
) -> Literal["html", "markdown", "txt", "pdf"]:
    hdrs = {k.lower(): v.lower() for k, v in headers.items()}
    ctype = hdrs.get("content-type", "")
    lower_path = urlparse(url).path.lower()
    if "application/pdf" in ctype or lower_path.endswith(".pdf"):
        return "pdf"
    if "text/markdown" in ctype or lower_path.endswith((".md", ".markdown")):
        return "markdown"
    if "text/plain" in ctype or lower_path.endswith(".txt"):
        return "txt"
    return "html"


def _header_value(headers: Mapping[str, str], key: str) -> str | None:
    target = key.lower()
    for k, v in headers.items():
        if k.lower() == target:
            return v
    return None


def _parse_retry_after(headers: Mapping[str, str], fallback_delay: float) -> float:
    raw = _header_value(headers, "retry-after")
    if raw is None:
        return fallback_delay
    try:
        parsed = float(raw.strip())
    except ValueError:
        return fallback_delay
    return min(60.0, max(fallback_delay, parsed))


def _encode_subpage_content(
    body: bytes | str,
    content_kind: Literal["html", "markdown", "txt", "pdf"],
) -> str:
    if isinstance(body, str):
        return body
    if content_kind == "pdf":
        return "b64:" + base64.b64encode(body).decode("ascii")
    return body.decode("utf-8", errors="replace")


def _decode_subpage_bytes(
    raw_content: str,
    content_kind: Literal["html", "markdown", "txt", "pdf"],
) -> bytes:
    if content_kind == "pdf" and raw_content.startswith("b64:"):
        return base64.b64decode(raw_content.removeprefix("b64:").encode("ascii"))
    if content_kind == "pdf":
        return raw_content.encode("latin-1", errors="replace")
    return raw_content.encode("utf-8")


class PoliteUrlIngestor:
    """Polite single-concurrency URL discoverer and queue with CAPTCHA pause recovery."""

    def __init__(
        self,
        policy: PoliteFetchPolicy | None = None,
        *,
        http_fetch_fn: HttpFetchFn | None = None,
        dns_resolver: DnsResolverFn | None = None,
        sleep_fn: SleepFn | None = None,
    ) -> None:
        self.policy = policy or PoliteFetchPolicy()
        self._http_fetch_fn: HttpFetchFn = http_fetch_fn or _default_http_fetch
        self._dns_resolver: DnsResolverFn | None = dns_resolver
        self._sleep_fn: SleepFn = sleep_fn or time.sleep
        self._rng = DeterministicRngStream(self.policy.rng_seed, "polite_delay")
        self._robots_cache: dict[str, tuple[RobotFileParser | None, float | None]] = {}

    def _next_delay_seconds(
        self,
        robots_crawl_delay: float | None,
        min_delay_override: float | None = None,
    ) -> float:
        floor = max(
            self.policy.min_delay_seconds,
            min_delay_override or 0.0,
            robots_crawl_delay or 0.0,
        )
        ceiling = max(floor, self.policy.max_delay_seconds, robots_crawl_delay or 0.0)
        mid = (floor + ceiling) / 2.0
        half_span = max(0.0, (ceiling - floor) / 2.0) + self.policy.jitter_seconds
        unit = self._rng.next_u64() / float(1 << 64)
        return max(floor, round(mid + ((2.0 * unit) - 1.0) * half_span, 3))

    def _fetch_with_ssrf_and_redirects(
        self,
        url: str,
        *,
        request_headers: Mapping[str, str] | None = None,
    ) -> HttpFetchResponse:
        current = url
        hdrs = dict(request_headers or {})
        hdrs.setdefault("User-Agent", self.policy.user_agent)

        for hop in range(self.policy.max_redirects + 1):
            clean_url = validate_url_target(current, dns_resolver=self._dns_resolver)
            resp = self._http_fetch_fn(
                clean_url,
                hdrs,
                self.policy.request_timeout_seconds,
                self.policy.max_response_bytes,
            )
            if len(resp.body) > self.policy.max_response_bytes:
                raise UrlFetchError(
                    f"Response from '{clean_url}' exceeded max size "
                    f"({self.policy.max_response_bytes} bytes)."
                )
            if resp.status_code in _REDIRECT_CODES:
                location = _header_value(resp.headers, "location")
                if not location:
                    return resp
                if hop >= self.policy.max_redirects:
                    raise UrlFetchError(
                        f"Exceeded max redirects ({self.policy.max_redirects}) from '{url}'."
                    )
                current = urljoin(clean_url, location)
                continue
            return resp
        raise UrlFetchError(f"Exceeded max redirects ({self.policy.max_redirects}) for '{url}'.")

    def _get_robots_policy(self, origin_base: str) -> tuple[RobotFileParser | None, float | None]:
        cached = self._robots_cache.get(origin_base)
        if cached is not None:
            return cached

        validate_url_target(origin_base, dns_resolver=self._dns_resolver)
        robots_url = f"{origin_base}/robots.txt"
        try:
            resp = self._fetch_with_ssrf_and_redirects(robots_url)
        except SsrfBlockedError:
            raise
        except UrlFetchError:
            self._robots_cache[origin_base] = (None, None)
            return None, None

        if resp.status_code >= 400:
            self._robots_cache[origin_base] = (None, None)
            return None, None

        parser = RobotFileParser()
        parser.parse(resp.body.decode("utf-8", errors="replace").splitlines())
        delay_val = parser.crawl_delay(self.policy.user_agent) or parser.crawl_delay("*")
        crawl_delay = float(delay_val) if isinstance(delay_val, (int, float)) else None
        result = (parser, crawl_delay)
        self._robots_cache[origin_base] = result
        return result

    def _fetch_one_page_polite(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        crawl_delay: float | None = None,
        min_delay_override: float | None = None,
        apply_delay: bool = False,
    ) -> HttpFetchResponse:
        if apply_delay:
            delay = self._next_delay_seconds(crawl_delay, min_delay_override=min_delay_override)
            if delay > 0.0:
                self._sleep_fn(delay)

        req_headers: dict[str, str] = {"User-Agent": self.policy.user_agent}
        if etag:
            req_headers["If-None-Match"] = etag
        if last_modified:
            req_headers["If-Modified-Since"] = last_modified

        for attempt in range(self.policy.max_rate_limit_retries + 1):
            resp = self._fetch_with_ssrf_and_redirects(url, request_headers=req_headers)
            if detect_anti_bot_challenge(resp) is not None:
                return resp
            if resp.status_code in {429, 503} and attempt < self.policy.max_rate_limit_retries:
                base_wait = max(
                    self.policy.min_delay_seconds, crawl_delay or 0.0, 2.0 ** (attempt + 1)
                )
                wait_sec = _parse_retry_after(resp.headers, base_wait)
                if wait_sec > 0.0:
                    self._sleep_fn(wait_sec)
                continue
            return resp

        raise UrlFetchError(f"Failed fetching '{url}' after rate-limit retries.")

    def discover_scoped_subpages(
        self,
        index_url: str,
        *,
        max_depth: int | None = None,
    ) -> tuple[SubpageDiscoveryCandidate, ...]:
        """Fetch index URL (+ robots.txt), extract scoped same-origin links & check nofollow."""
        clean_index = validate_url_target(index_url, dns_resolver=self._dns_resolver)
        parsed_index = urlparse(clean_index)
        origin_tuple = (parsed_index.scheme.lower(), parsed_index.netloc.lower())
        origin_base = f"{origin_tuple[0]}://{origin_tuple[1]}"
        scope_prefix = _scope_prefix_for_index(clean_index)

        robots_parser, crawl_delay = self._get_robots_policy(origin_base)
        if robots_parser is not None and not robots_parser.can_fetch(
            self.policy.user_agent, clean_index
        ):
            raise UrlFetchError(f"robots.txt disallowed discovery on '{clean_index}'.")

        index_resp = self._fetch_one_page_polite(
            clean_index, crawl_delay=crawl_delay, apply_delay=False
        )
        challenge = detect_anti_bot_challenge(index_resp)
        if challenge is not None:
            raise UrlFetchError(
                f"Anti-bot challenge ({challenge.challenge_vendor}) on index '{clean_index}'."
            )
        if index_resp.status_code >= 400:
            raise UrlFetchError(
                f"Index URL '{clean_index}' returned HTTP {index_resp.status_code}."
            )

        bounded_depth = min(
            2, max(1, max_depth if max_depth is not None else self.policy.max_discovery_depth)
        )
        candidates: list[SubpageDiscoveryCandidate] = []
        seen_urls: set[str] = {clean_index}

        def _extract_links(
            page_url: str, html_bytes: bytes, depth: int
        ) -> list[SubpageDiscoveryCandidate]:
            link_parser = _DiscoveryHtmlParser(page_url)
            link_parser.feed(html_bytes.decode("utf-8", errors="replace"))
            link_parser.close()
            if link_parser.nofollow:
                return []

            found: list[SubpageDiscoveryCandidate] = []
            for abs_url, link_label in link_parser.links:
                defragged = urldefrag(abs_url).url
                if defragged in seen_urls:
                    continue
                if not _is_within_scope(defragged, origin_tuple, scope_prefix):
                    continue
                if _is_non_content_url(defragged):
                    continue
                if robots_parser is not None and not robots_parser.can_fetch(
                    self.policy.user_agent, defragged
                ):
                    continue
                seen_urls.add(defragged)
                found.append(
                    SubpageDiscoveryCandidate(
                        url=defragged,
                        title=link_label or _chapter_group_for_url(defragged, scope_prefix),
                        chapter_group=_chapter_group_for_url(defragged, scope_prefix),
                        depth=cast(Literal[1, 2], depth),
                        selected=True,
                    )
                )
                if len(candidates) + len(found) >= self.policy.max_pages_per_job:
                    break
            return found

        depth1 = _extract_links(clean_index, index_resp.body, 1)
        candidates.extend(depth1)

        if bounded_depth == 2 and len(candidates) < self.policy.max_pages_per_job:
            for item in depth1:
                if len(candidates) >= self.policy.max_pages_per_job:
                    break
                child_resp = self._fetch_one_page_polite(
                    item.url, crawl_delay=crawl_delay, apply_delay=True
                )
                if (
                    detect_anti_bot_challenge(child_resp) is not None
                    or child_resp.status_code >= 400
                ):
                    continue
                depth2 = _extract_links(item.url, child_resp.body, 2)
                candidates.extend(depth2)

        return tuple(candidates[: self.policy.max_pages_per_job])

    def create_multipage_job(
        self,
        index_url: str,
        selected_candidates: Sequence[SubpageDiscoveryCandidate],
        *,
        job_id: str,
    ) -> IngestionStagingJob:
        """Create an ordered StagingJob containing only user-selected subpages."""
        clean_index = validate_url_target(index_url, dns_resolver=self._dns_resolver)
        records: list[SubpageFetchRecord] = []
        seen: set[str] = set()

        for cand in selected_candidates:
            if not cand.selected:
                continue
            defragged = urldefrag(cand.url).url
            if defragged in seen:
                continue
            seen.add(defragged)
            records.append(
                SubpageFetchRecord(
                    url=defragged,
                    title=cand.title,
                    chapter_group=cand.chapter_group,
                    status="pending",
                )
            )
            if len(records) >= self.policy.max_pages_per_job:
                break

        return IngestionStagingJob(
            job_id=job_id,
            source_name=clean_index,
            source_kind="url",
            status="staging",
            subpages=tuple(records),
        )

    def fetch_job_sequentially(
        self,
        job: IngestionStagingJob,
        *,
        min_delay_override: float | None = None,
    ) -> IngestionStagingJob:
        """Sequentially fetch pending subpages (concurrency=1), pausing on CAPTCHA."""
        updated = list(job.subpages)
        warnings = list(job.warnings)
        network_fetches = 0

        for idx, rec in enumerate(updated):
            if rec.status not in {"pending", "paused_captcha"}:
                continue

            clean_url = validate_url_target(rec.url, dns_resolver=self._dns_resolver)
            parsed = urlparse(clean_url)
            origin_base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
            robots_parser, crawl_delay = self._get_robots_policy(origin_base)
            if robots_parser is not None and not robots_parser.can_fetch(
                self.policy.user_agent, clean_url
            ):
                updated[idx] = rec.model_copy(
                    update={
                        "status": "blocked_robots",
                        "error_message": "Disallowed by robots.txt",
                    }
                )
                continue

            resp = self._fetch_one_page_polite(
                clean_url,
                etag=rec.etag,
                last_modified=rec.last_modified,
                crawl_delay=crawl_delay,
                min_delay_override=min_delay_override,
                apply_delay=(network_fetches > 0),
            )
            network_fetches += 1

            challenge = detect_anti_bot_challenge(resp)
            if challenge is not None:
                updated[idx] = rec.model_copy(
                    update={
                        "status": "paused_captcha",
                        "challenge_vendor": challenge.challenge_vendor,
                        "error_message": challenge.reason,
                    }
                )
                return job.model_copy(
                    update={
                        "status": "paused_captcha",
                        "subpages": tuple(updated),
                        "captcha_pause": challenge,
                        "warnings": tuple(warnings),
                    }
                )

            if resp.status_code == 304:
                updated[idx] = rec.model_copy(
                    update={
                        "status": "not_modified",
                        "challenge_vendor": None,
                        "error_message": None,
                    }
                )
                continue

            if resp.status_code >= 400:
                updated[idx] = rec.model_copy(
                    update={
                        "status": "failed",
                        "challenge_vendor": None,
                        "error_message": f"HTTP {resp.status_code}",
                    }
                )
                warnings.append(f"Failed fetching '{clean_url}': HTTP {resp.status_code}")
                continue

            kind = _infer_content_kind(resp.headers, resp.url)
            if kind == "html":
                meta_probe = _DiscoveryHtmlParser(resp.url)
                meta_probe.feed(resp.body.decode("utf-8", errors="replace"))
                meta_probe.close()
                if meta_probe.noindex:
                    warnings.append(f"Page '{resp.url}' carries meta robots noindex directive.")

            encoded_body = _encode_subpage_content(resp.body, kind)
            updated[idx] = rec.model_copy(
                update={
                    "status": "fetched",
                    "etag": _header_value(resp.headers, "etag") or rec.etag,
                    "last_modified": _header_value(resp.headers, "last-modified")
                    or rec.last_modified,
                    "content_hash": canonical_sha256(resp.body),
                    "raw_content": encoded_body,
                    "content_kind": kind,
                    "challenge_vendor": None,
                    "error_message": None,
                }
            )

        return job.model_copy(
            update={
                "status": "ready_for_review",
                "subpages": tuple(updated),
                "captcha_pause": None,
                "warnings": tuple(warnings),
            }
        )

    def _update_subpage_record(
        self,
        job: IngestionStagingJob,
        url: str,
        update_fields: Mapping[str, object],
    ) -> IngestionStagingJob:
        target = urldefrag(url.strip()).url
        updated = list(job.subpages)
        matched = False
        for idx, rec in enumerate(updated):
            if urldefrag(rec.url).url == target:
                updated[idx] = rec.model_copy(update=dict(update_fields))
                matched = True
                break
        if not matched:
            raise KeyError(f"URL '{url}' not found in staging job '{job.job_id}'.")
        return job.model_copy(update={"subpages": tuple(updated), "captcha_pause": None})

    def resume_from_user_browser_capture(
        self,
        job: IngestionStagingJob,
        *,
        url: str,
        captured_html: str,
        continue_queue: bool = True,
        min_delay_override: float | None = None,
    ) -> IngestionStagingJob:
        """Option A recovery: ingest HTML verified directly by the user and resume queue."""
        updated = self._update_subpage_record(
            job,
            url,
            {
                "status": "fetched",
                "raw_content": captured_html,
                "content_kind": "html",
                "content_hash": canonical_sha256(captured_html),
                "challenge_vendor": None,
                "error_message": None,
            },
        )
        if continue_queue:
            return self.fetch_job_sequentially(updated, min_delay_override=min_delay_override)
        return updated.model_copy(update={"status": "ready_for_review"})

    def submit_manual_subpage_content(
        self,
        job: IngestionStagingJob,
        *,
        url: str,
        raw_content: str | bytes,
        content_kind: Literal["html", "markdown", "txt", "pdf"] = "html",
        continue_queue: bool = True,
        min_delay_override: float | None = None,
    ) -> IngestionStagingJob:
        """Option B recovery: accept user-pasted text/HTML or dropped file for a paused row."""
        encoded = _encode_subpage_content(raw_content, content_kind)
        digest = canonical_sha256(raw_content)
        updated = self._update_subpage_record(
            job,
            url,
            {
                "status": "manual_submitted",
                "raw_content": encoded,
                "content_kind": content_kind,
                "content_hash": digest,
                "challenge_vendor": None,
                "error_message": None,
            },
        )
        if continue_queue:
            return self.fetch_job_sequentially(updated, min_delay_override=min_delay_override)
        return updated.model_copy(update={"status": "ready_for_review"})

    def skip_paused_subpage(
        self,
        job: IngestionStagingJob,
        *,
        url: str,
        continue_queue: bool = True,
        min_delay_override: float | None = None,
    ) -> IngestionStagingJob:
        """Option C recovery: mark blocked subpage as skipped and resume remaining queue."""
        updated = self._update_subpage_record(
            job,
            url,
            {
                "status": "skipped",
                "challenge_vendor": None,
                "error_message": "Skipped by user.",
            },
        )
        if continue_queue:
            return self.fetch_job_sequentially(updated, min_delay_override=min_delay_override)
        return updated.model_copy(update={"status": "ready_for_review"})

    def merge_fetched_subpages(
        self,
        job: IngestionStagingJob,
        *,
        sandboxed: bool = False,
    ) -> ParsedDocument:
        """Normalize and merge all fetched/submitted subpages into a single ToC-ordered AST."""
        merged_sections: list[DocumentSection] = []
        merged_tables: list[ExtractedTable] = []
        raw_parts: list[str] = []
        warnings = list(job.warnings)
        sec_counter = 0
        tbl_counter = 0

        for rec in job.subpages:
            if rec.status not in {"fetched", "not_modified", "manual_submitted"}:
                continue
            if not rec.raw_content:
                continue

            sub_bytes = _decode_subpage_bytes(rec.raw_content, rec.content_kind)
            parsed = parse_document_bytes(
                sub_bytes,
                source_name=rec.title or rec.url,
                source_kind=rec.content_kind,
                url=rec.url,
                max_bytes=self.policy.max_response_bytes,
                timeout_seconds=self.policy.request_timeout_seconds,
                sandboxed=sandboxed,
            )
            warnings.extend(parsed.warnings)
            if parsed.raw_text:
                raw_parts.append(parsed.raw_text)

            page_tables_remap: dict[str, ExtractedTable] = {}
            for tbl in parsed.tables:
                tbl_counter += 1
                new_tbl = tbl.model_copy(
                    update={
                        "table_id": f"tbl_{tbl_counter:04d}",
                        "citation": tbl.citation.model_copy(update={"url": rec.url}),
                    }
                )
                page_tables_remap[tbl.table_id] = new_tbl
                merged_tables.append(new_tbl)

            for sec in parsed.sections:
                sec_counter += 1
                remapped_sec_tables = tuple(
                    page_tables_remap.get(t.table_id, t) for t in sec.tables
                )
                merged_sections.append(
                    sec.model_copy(
                        update={
                            "section_id": f"sec_{sec_counter:04d}",
                            "url": rec.url,
                            "tables": remapped_sec_tables,
                        }
                    )
                )

        merged_raw = "\n\n".join(raw_parts)
        return ParsedDocument(
            doc_id=f"doc_{canonical_sha256((job.job_id, merged_raw))[:12]}",
            source_name=job.source_name,
            source_kind="url",
            title=job.subpages[0].title
            if job.subpages and job.subpages[0].title
            else job.source_name,
            raw_text=merged_raw,
            sections=tuple(merged_sections),
            tables=tuple(merged_tables),
            content_hash=canonical_sha256(merged_raw),
            warnings=tuple(warnings),
        )
