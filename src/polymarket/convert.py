"""Polymarket's answers, read into the venue's values (market.py): the one place
Polymarket's vocabulary is read.

- **The cash** is Polymarket's own USDC instrument, known by its code with
  `polymarket` as source: the venue states its prices and payouts in USDC
  without naming, for its data, which of the issuer's contracts it is, so it
  is the venue's own instrument (the product owner's ruling of 2026-10-03 on
  a venue's token), never the dollar and never a contract's CAIP-19. A
  stablecoin is a token, never its currency.
- **Two tokens, two contracts** (step 5's ruling of 2026-09-30). A Polymarket
  market has two outcomes, each traded as its own token (`clobTokenIds`), and
  each token is a binary event contract of its own, priced on its own book:
  it pays one USDC if its outcome is the market's result and nothing if it
  is not -- the Conditional Tokens design Polymarket documents, so its
  payout is one. A contract is known by its token's ID; its words are the
  market's `question` and the token's outcome; trading closes at the
  market's `endDate`; it trades while the market is `active`, not `closed`
  and accepting orders. A market Gamma answers with other than two outcomes
  is not taken as binary.
- **The book** is the token's own: its best bid the highest of `bids`, its
  best offer the lowest of `asks`, each with its size in tokens, prices in
  USDC as text; stated at the book's `timestamp` (milliseconds), its `hash`
  its identity.
- **The last trade** is `/last-trade-price`'s, the token's own price and the
  side that traded, which Polymarket states with no time: valid from when
  its answer first arrived. An answer naming no side is no trade (Polymarket
  answers a token that never traded with a price of 0.5 and an empty side),
  so no price. The book's own `last_trade_price` is not read: the CLOB
  states the same one on both tokens of a market.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from .market import (
    NANOS_PER_SECOND,
    Cash,
    Contract,
    Endpoint,
    Limits,
    Session,
    Tick,
    Top,
    Unread,
    number,
)
from .venue import BURST, CLOB, GAMMA, NOT_FOUND, RATE_PER_SECOND, Polymarket, VenueError

VENUE = "polymarket"
NAME = "Polymarket"
#: What the venue entitles this plugin to: its public market data, no key.
ENTITLED = "Public market data: a contract is read only for a subject the lake asked for"
#: What each outcome token is and pays, said on the Datasets page.
VENDOR_NOTE = (
    "Each outcome is its own token and contract, paying one USDC if it is the result: "
    "Polymarket's own USDC instrument, never a dollar."
)
#: Polymarket in the venue master: its own code, as a symbol.
VENUE_IDENTIFIERS: tuple[tuple[str, str, str], ...] = (("symbol", "polymarket", "polymarket"),)
CASH = Cash("USDC", "token", name="USD Coin at Polymarket")
#: What one outcome token pays if its outcome is the result: one USDC.
PAYOUT = Decimal("1")

LIMITS = Limits(
    allowed="Polymarket limits its API's requests; its market data needs no key",
    spent=f"At most {RATE_PER_SECOND:g} a second, bursts of {BURST}; a 429 waited out",
)

_RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})"
)


def rfc3339_ns(text: str) -> int:
    """An RFC 3339 time, to the nanosecond (datetime holds only six digits)."""
    match = _RFC3339.fullmatch(text)
    if match is None:
        raise ValueError(f"{text!r} is not an RFC 3339 time")
    year, month, day, hour, minute, second, fraction, zone = match.groups()
    offset = _dt.timedelta()
    if zone != "Z":
        sign = 1 if zone[0] == "+" else -1
        offset = sign * _dt.timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
    moment = _dt.datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second),
        tzinfo=_dt.timezone(offset),
    )  # fmt: skip
    return int(moment.timestamp()) * NANOS_PER_SECOND + int((fraction or "0").ljust(9, "0"))


def _when(text: object) -> int:
    try:
        return rfc3339_ns(str(text)) if text else 0
    except ValueError:
        return 0


def _listed(value: object) -> list[str]:
    """One of Gamma's lists, which it states as a JSON array in a string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [str(v) for v in value]
    return []


def contract(token: str, body: Mapping[str, Any], raw_key: str) -> Contract | None:
    """The outcome token `token` of one Gamma market, or None where the market
    holds no such token."""
    tokens, outcomes = _listed(body.get("clobTokenIds")), _listed(body.get("outcomes"))
    if token not in tokens:
        return None
    index = tokens.index(token)
    outcome = outcomes[index] if index < len(outcomes) else ""
    question = str(body.get("question") or "")
    closed = bool(body.get("closed"))
    trading = bool(body.get("active")) and not closed and body.get("acceptingOrders") is not False
    return Contract(
        code=token,
        title=f"{question} ({outcome})" if outcome else question,
        binary=len(tokens) == 2 and len(outcomes) == 2,
        payout=PAYOUT,
        closes_at_ns=_when(body.get("endDate")),
        tradable=trading,
        status="closed" if closed else "active" if trading else "not trading",
        market=str(body.get("conditionId") or ""),
        raw_key=raw_key,
    )


def _side(levels: object, side: str, best: Any, unread: list[Unread]) -> tuple[Any, Any]:
    """The best of a side's levels, `{price, size}` each, by `best` (max for
    bids, min for offers), and its size; a level that does not read kept as
    sent."""
    found: tuple[Decimal, Decimal | None] | None = None
    for level in levels if isinstance(levels, Sequence) and not isinstance(levels, str) else []:
        if not isinstance(level, Mapping):
            unread.append(Unread(f"book.{side}", str(level)))
            continue
        price, size = number(level.get("price")), number(level.get("size"))
        if price is None:
            unread.append(Unread(f"book.{side}.price", str(level.get("price"))))
            continue
        if size is None:
            unread.append(Unread(f"book.{side}.size", str(level.get("size"))))
        if found is None or best(price, found[0]) != found[0]:
            found = (price, size)
    return found if found is not None else (None, None)


def _stamp(body: Mapping[str, Any]) -> int:
    stated = body.get("timestamp")
    try:
        return int(str(stated)) * 1_000_000 if stated not in (None, "") else 0
    except ValueError:
        return 0


def top(of: Contract, body: Mapping[str, Any], raw_key: str, received_ns: int) -> Top:
    """The token's best bid and offer, each with its size."""
    unread: list[Unread] = []
    bid, bid_size = _side(body.get("bids"), "bids", max, unread)
    ask, ask_size = _side(body.get("asks"), "asks", min, unread)
    at = _stamp(body)
    return Top(
        code=of.code,
        bid=bid,
        ask=ask,
        bid_size=bid_size if bid is not None else None,
        ask_size=ask_size if ask is not None else None,
        at_ns=at or received_ns,
        stated=bool(at),
        ident=str(body.get("hash") or ""),
        raw_key=raw_key,
        unread=tuple(unread),
    )


def tick(of: Contract, body: Mapping[str, Any], raw_key: str, received_ns: int) -> Tick:
    """The token's last trade's price, with no time; none where Polymarket
    names no side that traded."""
    stated = body.get("price")
    traded = bool(body.get("side")) and stated not in (None, "")
    price = number(stated) if traded else None
    unread = (Unread("last-trade.price", str(stated)),) if traded and price is None else ()
    return Tick(code=of.code, price=price, at_ns=received_ns, stated=False, raw_key=raw_key,
                unread=unread)  # fmt: skip


class PolymarketMarket:
    """Polymarket's market data, as the shared data plugin's work asks for it."""

    venue = VENUE
    name = NAME
    venue_identifiers = VENUE_IDENTIFIERS
    cash = CASH

    def __init__(self, client: Polymarket, mode: str = "live") -> None:
        self.client = client
        live = mode == "live"
        elsewhere = f"{mode}: no call leaves the deployment"
        self.session = Session(
            mode=mode,
            endpoints=(
                Endpoint("Gamma", GAMMA if live else elsewhere, "the market a token belongs to"),
                Endpoint("CLOB", CLOB if live else elsewhere, "a token's book and last trade"),
            ),
            limits=LIMITS,
            health=client.health,
        )

    def contract(self, code: str) -> Contract | None:
        try:
            fetched = self.client.market(code)
        except VenueError as refused:
            if refused.status == NOT_FOUND:
                return None
            raise
        markets = fetched.value if isinstance(fetched.value, list) else []
        for body in markets:
            if isinstance(body, Mapping) and (read := contract(code, body, fetched.raw_key)):
                return read
        return None

    def last(self, of: Contract) -> Tick:
        fetched = self.client.last_trade(of.code)
        return tick(of, fetched.value, fetched.raw_key, fetched.received_at_ns)

    def top(self, of: Contract) -> Top:
        fetched = self.client.book(of.code)
        return top(of, fetched.value, fetched.raw_key, fetched.received_at_ns)
