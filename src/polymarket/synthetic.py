"""Synthetic mode: Polymarket's answers from files, never from Polymarket.

A developer's setting (`synthetic`, shown only on a development deployment)
turns it on. The client asks exactly as it asks Polymarket, keeps each answer
as a raw record and reads it the same way; only the transport differs:

- `Synthetic`: the synthetic exchanges this package carries (`synthetic/`),
  shaped exactly as Polymarket documents and sends its answers -- Gamma's
  markets with their outcomes and token IDs as JSON arrays inside strings,
  the order book's prices and sizes as text, a last trade's price and side
  -- with invented markets, invented token IDs and invented values. They
  are what CI and `make e2e` replay. From 0.11.0 they hold a market's
  trades (`trades.json`, the data API's page, its wallets and names
  invented) and UMA's oracle on chain (`chain.json`, answered by
  `SyntheticChain` in the ABI's words, as Polygon's RPC answers).
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
#: Kept only where a directory states them: events (contract v26), and
#: from 0.11.0 trades.
_OPTIONAL = ("events", "trades")


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
    if split.path.rstrip("/") == "/v2/trades" and query.get("condition"):
        return "trades", query["condition"] + ("#" + query["cursor"] if "cursor" in query else "")
    return None


def _missing() -> Response:
    return Response(404, dict(_HEADERS), b'{"type":"not found error","error":"not found"}')


#: The data API's answer for a market it states no trade of.
_NO_TRADES: dict[str, Any] = {
    "data": [],
    "pagination": {"limit": 1000, "offset": 0, "has_more": False, "next_cursor": None},
}


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
        if call == "trades":
            page = self.held["trades"].get(token)
            return _found(page if page is not None else _NO_TRADES)
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
            if asked and asked[0] == "trades":
                return _found(_NO_TRADES)
            if asked and asked[0] == "events":
                return _missing()
            return _never_traded() if asked and asked[0] == "last-trade" else _no_book()
        return Response(held[1], dict(_HEADERS), held[2].encode("utf-8"))


# ── UMA's oracle on chain (0.11.0) ──────────────────────────────────────────


def _w(value: int) -> str:
    return format(value % (1 << 256), "064x")


def _address_word(address: str) -> str:
    return address[2:].lower().rjust(64, "0")


def _rpc(result: str, asked: Mapping[str, Any]) -> Response:
    body = {"jsonrpc": "2.0", "id": asked.get("id", 1), "result": "0x" + result}
    return Response(200, {}, json.dumps(body).encode("utf-8"))


def _question_words(question: Mapping[str, Any]) -> str:
    """The adapter's `getQuestion` answer: its QuestionData, a tuple holding
    bytes, so led by its offset."""
    data = str(question.get("ancillary", "")).encode("utf-8")
    padded = data.hex() + "0" * ((64 - len(data.hex()) % 64) % 64)
    head = [
        int(question.get("requested", 0)),
        int(question.get("reward", 0)),
        int(question.get("bond", 0)),
        int(question.get("liveness", 0)),
        0,
        int(bool(question.get("resolved"))),
        0,
        int(bool(question.get("reset"))),
        0,
    ]
    words = [_w(32)] + [_w(v) for v in head]
    words += [_address_word("0x" + "00" * 20), _address_word("0x" + "00" * 20), _w(12 * 32)]
    return "".join(words) + _w(len(data)) + padded


def _request_words(request: Mapping[str, Any], managed: bool) -> str:
    """The oracle's `getRequest` answer: its Request, every field static;
    a managed oracle's one word longer, as Polygon's answers it."""
    zero = "0x" + "00" * 20
    words = [
        _address_word(str(request.get("proposer", zero))),
        _address_word(str(request.get("disputer", zero))),
        _address_word(zero),
        _w(int(bool(request.get("settled")))),
        _w(1), _w(0), _w(0), _w(1), _w(0),
        _w(int(request.get("bond", 0))),
        _w(int(request.get("customLiveness", 0))),
        _w(int(str(request.get("price", 0)))),
        _w(0),
        _w(int(request.get("expires", 0))),
        _w(0),
        _w(0),
    ]  # fmt: skip
    return "".join(words) + (_w(0) if managed else "")


class SyntheticChain:
    """Polygon's RPC as UMA's adapters and oracles answer `eth_call`, from
    `chain.json`: each adapter's oracle and questions -- each question's
    request time, liveness, ancillary data and the oracle's request for it
    -- and each oracle's default liveness. A call it holds no answer for is
    answered as the chain answers an unknown question: zeros."""

    def __init__(self, directory: Path | None = None) -> None:
        root = directory or Path(str(resources.files("polymarket") / "synthetic"))
        path = root / "chain.json"
        self.held: dict[str, Any] = (
            json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        )

    def _adapter(self, to: str) -> Mapping[str, Any]:
        adapters = self.held.get("adapters", {})
        return next((a for k, a in adapters.items() if k.lower() == to), {})

    def __call__(self, url: str, headers: Mapping[str, str], body: bytes) -> Response:
        asked = json.loads(body)
        call = asked["params"][0]
        to, data = str(call["to"]).lower(), str(call["data"])[2:]
        selector, args = data[:8], data[8:]
        adapter = self._adapter(to)
        if selector == "22302922":  # optimisticOracle()
            return _rpc(_address_word(str(adapter.get("oracle", "0x" + "00" * 20))), asked)
        if selector == "58c039cd":  # getQuestion(bytes32)
            held = adapter.get("questions", {}).get("0x" + args[:64], {})
            return _rpc(_question_words(held), asked)
        oracles = {k.lower(): v for k, v in self.held.get("oracles", {}).items()}
        oracle = oracles.get(to, {})
        if selector == "fe4e1983":  # defaultLiveness()
            return _rpc(_w(int(oracle.get("defaultLiveness", 0))), asked)
        if selector == "a9904f9b":  # getRequest(address,bytes32,uint256,bytes)
            requester = "0x" + args[24:64]
            question: Mapping[str, Any] = next(
                (q for q in self._adapter(requester).get("questions", {}).values()
                 if format(int(q.get("requested", 0)), "064x") == args[128:192]),
                {},
            )  # fmt: skip
            return _rpc(_request_words(question.get("request", {}), bool(oracle.get("managed"))),
                        asked)  # fmt: skip
        return _rpc("", asked)


class RecordedChain:
    """Polygon's RPC as a developer's recorded raw records answered it: the
    latest answer kept for each call's address and data."""

    def __init__(self, directory: Path) -> None:
        self.latest: dict[tuple[str, str], tuple[int, str]] = {}
        for path in sorted(directory.rglob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("call") != "rpc" or int(record.get("status", 0)) != 200:
                continue
            sent = record.get("request", {}).get("body", {})
            params = sent.get("params") if isinstance(sent, dict) else None
            if not params:
                continue
            key = (str(params[0].get("to", "")).lower(), str(params[0].get("data", "")))
            at = int(record.get("received_at_ns", 0))
            if key not in self.latest or at >= self.latest[key][0]:
                self.latest[key] = (at, str(record["body"]))

    def __call__(self, url: str, headers: Mapping[str, str], body: bytes) -> Response:
        asked = json.loads(body)
        call = asked["params"][0]
        held = self.latest.get((str(call["to"]).lower(), str(call["data"])))
        if held is None:
            return _rpc("", asked)
        return Response(200, {}, held[1].encode("utf-8"))
