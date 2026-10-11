"""Polite HTTP fetching: robots.txt check, retries with backoff."""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from collections.abc import Callable
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

# Worth retrying: the server is overloaded or the request timed out.
# Any other 4xx (403, 404, 410...) will not fix itself, so fail at once.
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class FetchError(Exception):
    pass


class RobotsDisallowed(FetchError):
    pass


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 2.0,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_agent = user_agent
        # robots.txt groups are matched on the product token, not the full UA
        self.robots_token = user_agent.split("/")[0].strip()
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
            }
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _request(self, url: str) -> requests.Response:
        """GET with up to ``retries`` retries on network errors and RETRY_STATUSES."""
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code not in RETRY_STATUSES:
                    return resp
                last_error = FetchError(f"HTTP {resp.status_code}")
            except requests.RequestException as exc:
                last_error = exc
            if attempt < self.retries:
                delay = self.backoff * 2**attempt
                log.warning("%s: %s; retry %d/%d in %.0fs", url, last_error, attempt + 1, self.retries, delay)
                self.sleep(delay)
        raise FetchError(f"{url}: failed after {self.retries + 1} attempts: {last_error}") from last_error

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = urllib.robotparser.RobotFileParser(origin + "/robots.txt")
            try:
                resp = self._request(origin + "/robots.txt")
                status = resp.status_code
            except FetchError as exc:
                log.warning("%s/robots.txt unreachable (%s); treating site as disallowed", origin, exc)
                status = None
            # RFC 9309: a 4xx means "no rules"; an unreachable file means "disallow all".
            if status == 200:
                parser.parse(resp.text.splitlines())
            elif status is not None and 400 <= status < 500:
                parser.allow_all = True
            else:
                parser.disallow_all = True
            self._robots[origin] = parser
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.robots_token, url)

    def fetch_feed(self, url: str) -> bytes:
        """Return the raw feed bytes; raise FetchError / RobotsDisallowed."""
        if not self.allowed(url):
            raise RobotsDisallowed(f"{url}: disallowed by robots.txt")
        resp = self._request(url)
        if resp.status_code != 200:
            raise FetchError(f"{url}: HTTP {resp.status_code}")
        return resp.content
