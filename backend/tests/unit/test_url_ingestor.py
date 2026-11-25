"""Offline unit tests for SSRF-protected polite multi-page URL ingestor (§8.3 / §1.2)."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.ingestion import (
    HttpFetchResponse,
    PoliteFetchPolicy,
    PoliteUrlIngestor,
    SsrfBlockedError,
    UrlFetchError,
    detect_anti_bot_challenge,
    validate_url_target,
)


def _public_dns(hostname: str, port: int) -> list[str]:
    _ = port
    if hostname == "internal.srd.test":
        return ["10.0.0.42"]
    return ["93.184.216.34"]


@pytest.mark.zero_ai
def test_ssrf_blocking_on_schemes_literals_dns_and_redirects() -> None:
    """Block non-HTTP schemes, loopback/private/link-local IPs, DNS SSRF & redirect SSRF."""
    assert validate_url_target("https://srd.example.com/rules#intro", dns_resolver=_public_dns) == (
        "https://srd.example.com/rules"
    )

    blocked_targets = (
        "file:///etc/passwd",
        "ftp://srd.example.com/rules.md",
        "https://user:secret@srd.example.com/rules",
        "http://localhost:8000/admin",
        "http://sub.localhost/secret",
        "http://127.0.0.1/status",
        "http://[::1]/status",
        "http://169.254.169.254/latest/meta-data/",
        "http://[fe80::1]/local",
        "http://10.1.2.3/private",
        "http://172.16.0.5/private",
        "http://192.168.1.10/router",
        "http://[fc00::1]/ula",
        "http://[::ffff:127.0.0.1]/mapped",
        "https://internal.srd.test/rules",
    )
    for bad_url in blocked_targets:
        with pytest.raises(SsrfBlockedError):
            validate_url_target(bad_url, dns_resolver=_public_dns)

    # Redirect hop to private DNS target is caught and blocked before connecting
    def _redirect_fetch(
        url: str, headers: Mapping[str, str], timeout: float, max_bytes: int
    ) -> HttpFetchResponse:
        _ = (headers, timeout, max_bytes)
        if url == "https://srd.example.com/hop":
            return HttpFetchResponse(
                url=url,
                status_code=302,
                headers={"Location": "http://internal.srd.test/secret"},
            )
        return HttpFetchResponse(
            url=url,
            status_code=302,
            headers={"Location": "https://srd.example.com/loop"},
        )

    ingestor = PoliteUrlIngestor(
        PoliteFetchPolicy(max_redirects=2),
        http_fetch_fn=_redirect_fetch,
        dns_resolver=_public_dns,
        sleep_fn=lambda _sec: None,
    )
    with pytest.raises(SsrfBlockedError):
        ingestor._fetch_with_ssrf_and_redirects("https://srd.example.com/hop")
    with pytest.raises(UrlFetchError, match="Exceeded max redirects"):
        ingestor._fetch_with_ssrf_and_redirects("https://srd.example.com/loop")


@pytest.mark.zero_ai
def test_scoped_discovery_robots_respect_and_polite_queue_headers() -> None:
    """Verify same-origin prefix scoping, robots.txt Crawl-delay, ETag 304 & Retry-After."""
    attempt_counts: dict[str, int] = {}
    recorded_delays: list[float] = []

    pages: dict[str, HttpFetchResponse] = {
        "https://srd.example.com/robots.txt": HttpFetchResponse(
            url="https://srd.example.com/robots.txt",
            status_code=200,
            body=b"User-agent: *\nDisallow: /rules/private\nCrawl-delay: 2\n",
        ),
        "https://srd.example.com/rules/index.html": HttpFetchResponse(
            url="https://srd.example.com/rules/index.html",
            status_code=200,
            body=(
                b"<html><body>"
                b"<a href='/rules/combat.html#melee'>Combat</a>"
                b"<a href='/rules/combat.html#ranged'>Ranged Dup</a>"
                b"<a href='/rules/magic.html'>Magic</a>"
                b"<a href='/rules/private/secret.html'>Secret</a>"
                b"<a href='/rules/login'>Login</a>"
                b"<a href='/rules/map.png'>PNG</a>"
                b"<a href='/about.html'>Out Of Prefix</a>"
                b"<a href='https://other.org/rules/ext.html'>Other Origin</a>"
                b"</body></html>"
            ),
        ),
        "https://srd.example.com/rules/combat.html": HttpFetchResponse(
            url="https://srd.example.com/rules/combat.html",
            status_code=200,
            headers={"ETag": '"etag-v1"', "Last-Modified": "Wed, 25 Nov 2026 10:00:00 GMT"},
            body=b"<h1>Combat Mechanics</h1><p>Roll 1d20 + agility mod.</p>",
        ),
        "https://srd.example.com/rules/magic.html": HttpFetchResponse(
            url="https://srd.example.com/rules/magic.html",
            status_code=200,
            body=b"<h1>Arcane Arts</h1><p>Expend focus pools.</p>",
        ),
    }

    def _fake_fetch(
        url: str, headers: Mapping[str, str], timeout: float, max_bytes: int
    ) -> HttpFetchResponse:
        _ = (timeout, max_bytes)
        count = attempt_counts.get(url, 0) + 1
        attempt_counts[url] = count

        # Simulate conditional 304 on ETag match for combat page
        if (
            url == "https://srd.example.com/rules/combat.html"
            and headers.get("If-None-Match") == '"etag-v1"'
        ):
            return HttpFetchResponse(url=url, status_code=304)

        # Simulate transient 429 Retry-After on magic page
        if url == "https://srd.example.com/rules/magic.html" and count == 1:
            return HttpFetchResponse(
                url=url,
                status_code=429,
                headers={"Retry-After": "3"},
                body=b"Rate limited",
            )

        return pages[url]

    ingestor = PoliteUrlIngestor(
        PoliteFetchPolicy(min_delay_seconds=1.5, max_delay_seconds=2.5, max_pages_per_job=10),
        http_fetch_fn=_fake_fetch,
        dns_resolver=_public_dns,
        sleep_fn=recorded_delays.append,
    )

    candidates = ingestor.discover_scoped_subpages("https://srd.example.com/rules/index.html")
    assert [cand.url for cand in candidates] == [
        "https://srd.example.com/rules/combat.html",
        "https://srd.example.com/rules/magic.html",
    ]

    job = ingestor.create_multipage_job(
        "https://srd.example.com/rules/index.html", candidates, job_id="job_srd_01"
    )
    fetched = ingestor.fetch_job_sequentially(job)
    assert fetched.status == "ready_for_review"
    assert [rec.status for rec in fetched.subpages] == ["fetched", "fetched"]
    assert fetched.subpages[0].etag == '"etag-v1"'
    # At least one inter-page delay >= robots Crawl-delay (2.0s) and Retry-After (3.0s)
    assert any(delay >= 2.0 for delay in recorded_delays)
    assert 3.0 in recorded_delays

    # Re-running conditional cache returns 304 Not Modified cleanly preserving raw_content
    recheck = fetched.model_copy(
        update={
            "subpages": tuple(
                rec.model_copy(update={"status": "pending"}) if idx == 0 else rec
                for idx, rec in enumerate(fetched.subpages)
            )
        }
    )
    rechecked = ingestor.fetch_job_sequentially(recheck)
    assert rechecked.subpages[0].status == "not_modified"
    assert "Combat Mechanics" in rechecked.subpages[0].raw_content

    # Depth-2 discovery & nofollow guard + max_response_bytes guard
    depth_pages: dict[str, HttpFetchResponse] = {
        "https://srd.example.com/robots.txt": HttpFetchResponse(
            url="https://srd.example.com/robots.txt", status_code=404
        ),
        "https://srd.example.com/rules/index.html": HttpFetchResponse(
            url="https://srd.example.com/rules/index.html",
            status_code=200,
            body=b"<a href='/rules/ch1.html'>Ch1</a><a href='/rules/blocked_nf.html'>NF</a>",
        ),
        "https://srd.example.com/rules/ch1.html": HttpFetchResponse(
            url="https://srd.example.com/rules/ch1.html",
            status_code=200,
            body=b"<a href='/rules/ch1_sub.html'>Sub</a>",
        ),
        "https://srd.example.com/rules/blocked_nf.html": HttpFetchResponse(
            url="https://srd.example.com/rules/blocked_nf.html",
            status_code=200,
            body=b"<meta name='robots' content='nofollow'><a href='/rules/hidden_nf.html'>H</a>",
        ),
        "https://srd.example.com/rules/oversize.html": HttpFetchResponse(
            url="https://srd.example.com/rules/oversize.html",
            status_code=200,
            body=b"X" * 512,
        ),
    }
    depth_ingestor = PoliteUrlIngestor(
        PoliteFetchPolicy(
            min_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter_seconds=0.0,
            max_response_bytes=128,
            max_discovery_depth=2,
        ),
        http_fetch_fn=lambda url, _h, _t, _m: depth_pages[url],
        dns_resolver=_public_dns,
        sleep_fn=lambda _s: None,
    )
    deep_cands = depth_ingestor.discover_scoped_subpages(
        "https://srd.example.com/rules/index.html", max_depth=2
    )
    deep_urls = [c.url for c in deep_cands]
    assert "https://srd.example.com/rules/ch1_sub.html" in deep_urls
    assert "https://srd.example.com/rules/hidden_nf.html" not in deep_urls

    with pytest.raises(UrlFetchError, match="exceeded max size"):
        depth_ingestor._fetch_with_ssrf_and_redirects("https://srd.example.com/rules/oversize.html")


@pytest.mark.zero_ai
def test_captcha_pause_and_three_graceful_human_recovery_paths() -> None:
    """Verify CAPTCHA pause preserves fetched pages and supports Browser, Paste/Drop & Skip."""
    turnstile_resp = HttpFetchResponse(
        url="https://srd.example.com/rules/p2.html",
        status_code=403,
        headers={"cf-mitigated": "challenge"},
        body=b"<html><body><div class='cf-turnstile'>Just a moment...</div></body></html>",
    )
    pause_report = detect_anti_bot_challenge(turnstile_resp)
    assert pause_report is not None
    assert pause_report.challenge_vendor == "cloudflare_turnstile"

    def _fake_fetch(
        url: str, headers: Mapping[str, str], timeout: float, max_bytes: int
    ) -> HttpFetchResponse:
        _ = (headers, timeout, max_bytes)
        if url.endswith("/robots.txt"):
            return HttpFetchResponse(url=url, status_code=404)
        if url.endswith("/index.html"):
            return HttpFetchResponse(
                url=url,
                status_code=200,
                body=(
                    b"<a href='/rules/p1.html'>P1</a>"
                    b"<a href='/rules/p2.html'>P2</a>"
                    b"<a href='/rules/p3.html'>P3</a>"
                ),
            )
        if url.endswith("/p1.html"):
            return HttpFetchResponse(
                url=url, status_code=200, body=b"<h1 id='ch1'>Chapter One</h1><p>Loaded safely.</p>"
            )
        if url.endswith("/p2.html"):
            return turnstile_resp
        if url.endswith("/p3.html"):
            return HttpFetchResponse(
                url=url, status_code=200, body=b"<h1 id='ch3'>Chapter Three</h1><p>Final rules.</p>"
            )
        return HttpFetchResponse(url=url, status_code=404)

    ingestor = PoliteUrlIngestor(
        PoliteFetchPolicy(min_delay_seconds=0.0, max_delay_seconds=0.0, jitter_seconds=0.0),
        http_fetch_fn=_fake_fetch,
        dns_resolver=_public_dns,
        sleep_fn=lambda _s: None,
    )
    candidates = ingestor.discover_scoped_subpages("https://srd.example.com/rules/index.html")
    base_job = ingestor.create_multipage_job(
        "https://srd.example.com/rules/index.html", candidates, job_id="job_captcha_01"
    )

    paused_job = ingestor.fetch_job_sequentially(base_job)
    assert paused_job.status == "paused_captcha"
    assert paused_job.captcha_pause is not None
    assert paused_job.captcha_pause.paused_url == "https://srd.example.com/rules/p2.html"
    assert [r.status for r in paused_job.subpages] == ["fetched", "paused_captcha", "pending"]

    # Option A: Visible browser verification capture completes paused page & resumes queue to P3
    opt_a = ingestor.resume_from_user_browser_capture(
        paused_job,
        url="https://srd.example.com/rules/p2.html",
        captured_html="<h1 id='ch2'>Chapter Two</h1><p>User verified content.</p>",
    )
    assert opt_a.status == "ready_for_review"
    assert [r.status for r in opt_a.subpages] == ["fetched", "fetched", "fetched"]
    merged = ingestor.merge_fetched_subpages(opt_a)
    assert [sec.url for sec in merged.sections] == [
        "https://srd.example.com/rules/p1.html",
        "https://srd.example.com/rules/p2.html",
        "https://srd.example.com/rules/p3.html",
    ]
    assert [sec.anchor for sec in merged.sections] == ["ch1", "ch2", "ch3"]

    # Option B: Inline paste / file drop recovery (including dropped PDF bytes)
    opt_b = ingestor.submit_manual_subpage_content(
        paused_job,
        url="https://srd.example.com/rules/p2.html",
        raw_content="# Chapter Two Markdown\nManually dropped file content.",
        content_kind="markdown",
    )
    assert opt_b.status == "ready_for_review"
    assert [r.status for r in opt_b.subpages] == ["fetched", "manual_submitted", "fetched"]
    merged_b = ingestor.merge_fetched_subpages(opt_b)
    assert "Manually dropped file content." in merged_b.raw_text

    pdf_payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Page /Contents 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Length 28 >>\nstream\nBT\n(Dropped PDF Page) Tj\nET\n\nendstream\nendobj\n"
        b"%%EOF\n"
    )
    opt_b_pdf = ingestor.submit_manual_subpage_content(
        paused_job,
        url="https://srd.example.com/rules/p2.html",
        raw_content=pdf_payload,
        content_kind="pdf",
    )
    merged_pdf = ingestor.merge_fetched_subpages(opt_b_pdf)
    assert "Dropped PDF Page" in merged_pdf.raw_text

    # Option C: Skip paused page and finish P3
    opt_c = ingestor.skip_paused_subpage(paused_job, url="https://srd.example.com/rules/p2.html")
    assert opt_c.status == "ready_for_review"
    assert [r.status for r in opt_c.subpages] == ["fetched", "skipped", "fetched"]
    merged_c = ingestor.merge_fetched_subpages(opt_c)
    assert len(merged_c.sections) == 2
