"""Load and validate sources.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from collector.categories import LABELS, build_category_map
from collector.sinhala_text import DEFAULT_MIN_SINHALA_RATIO


@dataclass(frozen=True)
class Settings:
    user_agent: str
    timeout: float = 30.0
    retries: int = 3
    backoff: float = 2.0
    min_sinhala_ratio: float = DEFAULT_MIN_SINHALA_RATIO


@dataclass(frozen=True)
class Feed:
    url: str
    default_category: str = "other"


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    homepage: str
    feeds: tuple[Feed, ...]
    category_map: dict[str, str] = field(default_factory=dict)
    title_suffixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    settings: Settings
    sources: tuple[Source, ...]


def _feed(raw: dict | str, source_id: str) -> Feed:
    if isinstance(raw, str):
        raw = {"url": raw}
    default = raw.get("default_category", "other")
    if default not in LABELS:
        raise ValueError(f"{source_id}: feed {raw['url']} has unknown default_category {default!r}")
    return Feed(url=raw["url"], default_category=default)


def _source(raw: dict) -> Source:
    source_id = raw["id"]
    feeds = tuple(_feed(f, source_id) for f in raw.get("feeds", []))
    if not feeds:
        raise ValueError(f"{source_id}: no feeds configured")
    return Source(
        id=source_id,
        name=raw.get("name", source_id),
        homepage=raw.get("homepage", ""),
        feeds=feeds,
        category_map=build_category_map(raw.get("category_map") or {}),
        title_suffixes=tuple(raw.get("title_suffixes") or ()),
    )


def load_config(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    settings = Settings(**raw["settings"])
    sources = tuple(_source(s) for s in raw["sources"] if s.get("enabled", True))
    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate source ids in {path}")
    return Config(settings=settings, sources=sources)
