"""Synthetic mode: Polymarket's answers from files, never from Polymarket.

A developer's setting (`synthetic`, shown only on a development deployment)
turns it on. The client asks exactly as it asks Polymarket, keeps each answer
as a raw record and reads it the same way; only the transport differs:

- `Synthetic`: the synthetic exchanges this package carries (`synthetic/`),
  shaped exactly as Polymarket documents and sends its answers -- Gamma's
  markets with their outcomes and token IDs as JSON arrays inside strings,
  the order book's prices and sizes as text, a last trade's price and side
  -- with invented markets, invented token IDs and invented values. They
  are what CI and `make e2e` replay.
- `Recorded`: a developer's own recorded exchanges -- the raw records a
  plugin kept of Polymarket's real answers to its public reads -- replayed
  by `make e2e-recorded` from a directory that is never committed (the
  plan's Q11).
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from .venue import Response

_HEADERS = {"cache-control": "no-store"}
_FILES = ("markets", "book", "last-trade")
#: Kept only where a directory states events (contract v26).
_OPTIONAL = ("events",)


def _found(body: Any) -> Response:
    return Response(200, dict(_HEADERS), json.dumps(body).encode("utf-8"))


def _no_book() -> Response:
    return Response(
        404, dict(_HEADERS), b'{"error":"No orderbook exists for the requested token id"}'
    )


def _asked(url: str) -> tuple[str, str] | None:
    """Which call a request is, and of which token."""
    split = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(split.query))
    if split.path.rstrip("/") == "/markets" and query.get("clob_token_ids"):
        return "markets", query["clob_token_ids"]
    if split.path.rstrip("/") == "/markets" and query.get("condition_ids"):
        return "condition", query["condition_ids"]
    if split.path.startswith("/events/slug/"):
        return "events", urllib.parse.unquote(split.path[len("/events/slug/") :].rstrip("/"))
    if split.path.rstrip("/") == "/book" and query.get("token_id"):
        return "book", query["token_id"]
    if split.path.rstrip("/") == "/last-trade-price" and query.get("token_id"):
        return "last-trade", query["token_id"]
    return None


def _missing() -> Response:
    return Response(404, dict(_HEADERS), b'{"type":"not found error","error":"not found"}')


def _never_traded() -> Response:
    """Polymarket's answer for a token it states no trade of."""
    return Response(200, dict(_HEADERS), b'{"price":"0.5","side":""}')


class Synthetic:
    """Answers from a directory of synthetic exchanges: `markets.json`, Gamma's
    answer per token, `book.json`, the order book's per token, and
    `last-trade.json`, its last trade's per token; and `events.json`,
    Gamma's answer per event slug, where it has one. A condition's market
    is the one `markets.json` holds by that condition ID."""

    def __init__(self, directory: Path | None = None) -> None:
        root = directory or Path(str(resources.files("polymarket") / "synthetic"))
        self.held: dict[str, dict[str, Any]] = {
            name: json.loads((root / f"{name}.json").read_text(encoding="utf-8")) for name in _FILES
        }
        for name in _OPTIONAL:
            path = root / f"{name}.json"
            self.held[name] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def __call__(self, url: str, headers: Mapping[str, str]) -> Response:
        asked = _asked(url)
        if asked is None:
            return _no_book()
        call, token = asked
        if call == "condition":
            return _found(
                next(
                    (
                        m
                        for m in self.held["markets"].values()
                        if m and m[0].get("conditionId") == token
                    ),
                    [],
                )
            )
        if call == "events":
            event = self.held["events"].get(token)
            return _found(event) if event is not None else _missing()
        body = self.held[call].get(token)
        if call == "markets":
            return _found(body if body is not None else [])
        if call == "last-trade":
            return _found(body) if body is not None else _never_traded()
        return _found(body) if body is not None else _no_book()


class Recorded:
    """Answers from a developer's recorded raw records (`meridian.edge.RawStore`'s files under a
    `responses/` directory): the latest answer kept for each call and token,
    a 404 among them."""

    def __init__(self, directory: Path) -> None:
        self.latest: dict[tuple[str, str], tuple[int, int, str]] = {}
        for path in sorted(directory.rglob("*")):
            if path.suffix == ".json":
                records = [json.loads(path.read_text(encoding="utf-8"))]
            elif path.suffix == ".jsonl":
                records = [
                    json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                ]
            else:
                continue
            for record in records:
                status = int(record.get("status", 0))
                asked = _asked(str(record.get("request", {}).get("url", "")))
                if asked is None or status not in (200, 404):
                    continue
                at = int(record.get("received_at_ns", 0))
                held = self.latest.get(asked)
                if held is None or at >= held[0]:
                    self.latest[asked] = (at, status, str(record["body"]))

    def calls(self) -> set[tuple[str, str]]:
        """Each call and token the recording answers."""
        return set(self.latest)

    def __call__(self, url: str, headers: Mapping[str, str]) -> Response:
        asked = _asked(url)
        held = self.latest.get(asked) if asked else None
        if held is None:
            if asked and asked[0] in ("markets", "condition"):
                return _found([])
            if asked and asked[0] == "events":
                return _missing()
            return _never_traded() if asked and asked[0] == "last-trade" else _no_book()
        return Response(held[1], dict(_HEADERS), held[2].encode("utf-8"))
