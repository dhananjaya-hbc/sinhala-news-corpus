"""Fetcher tests with a fake session; no network access."""

import pytest
import requests

from collector.fetch import Fetcher, FetchError, RobotsDisallowed

UA = "sinhala-news-corpus/1.0 (+https://github.com/dhananjaya-hbc/sinhala-news-corpus)"


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")


class FakeSession:
    """Returns queued responses (or raises queued exceptions) per URL."""

    def __init__(self, routes):
        self.routes = {url: list(items) for url, items in routes.items()}
        self.headers = {}
        self.calls = []

    def get(self, url, timeout):
        self.calls.append(url)
        item = self.routes[url].pop(0) if len(self.routes[url]) > 1 else self.routes[url][0]
        if isinstance(item, Exception):
            raise item
        return item


def make(routes, retries=3):
    sleeps = []
    fetcher = Fetcher(UA, retries=retries, session=FakeSession(routes), sleep=sleeps.append)
    return fetcher, sleeps


FEED = "https://news.example.lk/feed/"
ROBOTS = "https://news.example.lk/robots.txt"


def test_fetch_ok_and_user_agent_set():
    fetcher, _ = make({ROBOTS: [FakeResponse(200, "User-agent: *\nDisallow:")], FEED: [FakeResponse(200, "<rss/>")]})
    assert fetcher.fetch_feed(FEED) == b"<rss/>"
    assert fetcher.session.headers["User-Agent"] == UA


def test_retries_three_times_then_succeeds():
    fetcher, sleeps = make(
        {
            ROBOTS: [FakeResponse(404)],
            FEED: [requests.ConnectionError("down"), FakeResponse(503), FakeResponse(429), FakeResponse(200, "<rss/>")],
        }
    )
    assert fetcher.fetch_feed(FEED) == b"<rss/>"
    assert sleeps == [2.0, 4.0, 8.0]


def test_gives_up_after_three_retries():
    fetcher, sleeps = make({ROBOTS: [FakeResponse(404)], FEED: [requests.Timeout("slow")]})
    with pytest.raises(FetchError, match="4 attempts"):
        fetcher.fetch_feed(FEED)
    assert fetcher.session.calls.count(FEED) == 4
    assert len(sleeps) == 3


def test_permanent_error_not_retried():
    fetcher, sleeps = make({ROBOTS: [FakeResponse(404)], FEED: [FakeResponse(403)]})
    with pytest.raises(FetchError, match="HTTP 403"):
        fetcher.fetch_feed(FEED)
    assert fetcher.session.calls.count(FEED) == 1
    assert sleeps == []


def test_robots_disallow_for_our_bot_is_respected():
    robots = "User-agent: sinhala-news-corpus\nDisallow: /feed/\n\nUser-agent: *\nDisallow:"
    fetcher, _ = make({ROBOTS: [FakeResponse(200, robots)], FEED: [FakeResponse(200, "<rss/>")]})
    with pytest.raises(RobotsDisallowed):
        fetcher.fetch_feed(FEED)
    assert FEED not in fetcher.session.calls


def test_robots_disallow_for_everyone_is_respected():
    fetcher, _ = make({ROBOTS: [FakeResponse(200, "User-agent: *\nDisallow: /")], FEED: [FakeResponse(200)]})
    with pytest.raises(RobotsDisallowed):
        fetcher.fetch_feed(FEED)


def test_rules_for_other_bots_do_not_block_us():
    # Ada Derana's real robots.txt blocks only Bytespider
    fetcher, _ = make({ROBOTS: [FakeResponse(200, "User-agent: Bytespider\nDisallow: /")], FEED: [FakeResponse(200, "x")]})
    assert fetcher.fetch_feed(FEED) == b"x"


def test_unreachable_robots_means_disallow():
    fetcher, _ = make({ROBOTS: [requests.ConnectionError("dns")], FEED: [FakeResponse(200)]}, retries=0)
    with pytest.raises(RobotsDisallowed):
        fetcher.fetch_feed(FEED)


def test_robots_fetched_once_per_host():
    other = "https://news.example.lk/category/sports/feed/"
    fetcher, _ = make({ROBOTS: [FakeResponse(404)], FEED: [FakeResponse(200, "a")], other: [FakeResponse(200, "b")]})
    fetcher.fetch_feed(FEED)
    fetcher.fetch_feed(other)
    assert fetcher.session.calls.count(ROBOTS) == 1
