"""Polymarket's answers, read into the venue's values (the SDK's
`meridian.roles.data.event_contracts`): the one place
Polymarket's vocabulary is read.

- **The cash** is pUSD, Polymarket's collateral (ruling 550, 2026-10-24):
  the token Polymarket documents as "the collateral token used for all
  trading" (docs.polymarket.com, "pUSD"), an ERC-20 on Polygon backed by
  USDC, known by its CAIP-19 (`eip155:137/erc20:0xc011...2dfb`, its
  contract as Polymarket's "Contracts" page lists it), which the platform's
  master holds as pUSD's record. Its code is `PUSD`, as the master names it
  at source `polymarket`. It replaces 0.8.0's "USDC" known by its code
  alone (the ruling of 2026-10-03), which no master record matched. A
  stablecoin is a token, never its currency: never the dollar.
- **Two tokens, two contracts** (step 5's ruling of 2026-09-30). A Polymarket
  market has two outcomes, each traded as its own token (`clobTokenIds`), and
  each token is a binary event contract of its own, priced on its own book:
  it pays one pUSD if its outcome is the market's result and nothing if it
  is not -- the Conditional Tokens design Polymarket documents, so its
  payout is one. A contract is known by its token's ID; its words are the
  market's `question` and the token's outcome; trading closes at the
  market's `endDate`; it trades while the market is `active`, not `closed`
  and accepting orders. A market Gamma answers with other than two outcomes
  is not taken as binary.
- **The book** is the token's own: its best bid the highest of `bids`, its
  best offer the lowest of `asks`, each with its size in tokens, prices in
  pUSD as text; stated at the book's `timestamp` (milliseconds), its `hash`
  its identity.
- **Its outcome** (contract v23; the lake plan's "vL1c") is read from the
  same Gamma answer, and only once the market is resolved: its
  `umaResolutionStatus` `resolved` and the market `closed`, when its
  `outcomePrices` state what each token settles at -- one pUSD, nothing, or
  half for an "Unknown/50-50" resolution -- each exactly 1, 0 or 0.5 and
  the market's adding up to one. The token's outcome is its own: a NO token
  of a market resolved YES pays nothing. Its stage is final: a UMA
  resolution, once made, is reported on chain and redeemed, and Polymarket
  states none between a proposal and it. A proposal (`proposed`, in its
  2-hour challenge period) and a dispute (`disputed`) state their stage but
  never their answer -- Gamma's `outcomePrices` stay the book's while one
  stands -- so nothing is recorded for either: the plugin records a
  Polymarket outcome at its final stage alone (approved 2026-10-13 as a
  plugin's choice within contract v23). Polymarket's word, kept as
  reported, is the token's own stated price (`polymarket:outcomePrices`),
  with each outcome and its price as text. Polymarket states no time of
  resolution or of payout: the outcome is valid from when the answer first
  stating it arrived, and its payout time is left 0 (holders redeem their
  tokens themselves).
- **The event** (contract v26; W3.29) is Gamma's, by its slug
  (`/events/slug/{slug}`), found from the market of the contract's
  condition (`/markets?condition_ids=`, its `events`): its slug its
  reference, its `title` its words, its series the first of its `series`
  by slug where it states one. Its members are its markets' YES tokens --
  the token of the outcome `Yes`, else a market's first -- each a contract
  of its own. Polymarket states its grouping through negative risk
  (docs.polymarket.com, "Negative risk"): an event with `negRisk` lets a NO
  in one market convert into a YES in each of the others, which holds only
  when exactly one outcome resolves YES, so its markets are mutually
  exclusive and exhaustive. An augmented negative-risk event -- its
  `negRiskAugmented`, or a market of it marked `negRiskOther` -- adds
  placeholder outcomes named later and an "Other" whose meaning changes, so
  its named outcomes are mutually exclusive but their exhaustiveness is not
  stated (never false). An event without negative risk states neither. An
  event unchanged keeps the time its answer first arrived, which is when
  the grouping is reported valid from.
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

from meridian.roles.data import NANOS_PER_SECOND, Endpoint, Limits, Session, Unread, number
from meridian.roles.data.event_contracts import (
    FINAL,
    Cash,
    Contract,
    Event,
    Resolution,
    Tick,
    Top,
)

from .venue import BURST, CLOB, GAMMA, NOT_FOUND, RATE_PER_SECOND, Polymarket, VenueError

VENUE = "polymarket"
NAME = "Polymarket"
#: What the venue entitles this plugin to: its public market data, no key.
ENTITLED = "Public market data: a contract is read only for a subject the lake asked for"
#: What each outcome token is and pays, said on the Datasets page.
VENDOR_NOTE = (
    "Each outcome is its own token and contract, paying one pUSD, Polymarket's collateral "
    "token, if it is the result."
)
#: Polymarket in the venue master: its own code, as a symbol.
VENUE_IDENTIFIERS: tuple[tuple[str, str, str], ...] = (("symbol", "polymarket", "polymarket"),)
#: pUSD on Polygon, by its CAIP-19 (ruling 550): the contract
#: 0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB, "pUSD (CollateralToken Poly v2)"
#: on Polymarket's Contracts page, lower-cased as CAIP-10 addresses are.
PUSD_CAIP19 = "eip155:137/erc20:0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"
CASH = Cash("PUSD", "token", scheme="caip19", value=PUSD_CAIP19,
            name="pUSD, Polymarket's collateral")  # fmt: skip
#: What one outcome token pays if its outcome is the result: one pUSD.
PAYOUT = Decimal("1")
#: What a resolution settles a token at: its payout, half of it, or nothing.
SETTLES = frozenset({Decimal(0), Decimal("0.5"), PAYOUT})
#: Where Polymarket's word for a resolution is, as reported.
OUTCOME_PRICES = "polymarket:outcomePrices"

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


def resolution(token: str, body: Mapping[str, Any]) -> Resolution | None:
    """The token's outcome once its market is resolved, final; None before,
    a proposal and a dispute among them, whose answer Gamma does not state."""
    if str(body.get("umaResolutionStatus") or "").lower() != "resolved" or not body.get("closed"):
        return None
    tokens, outcomes = _listed(body.get("clobTokenIds")), _listed(body.get("outcomes"))
    prices = _listed(body.get("outcomePrices"))
    text = ", ".join(f"{o} {p}" for o, p in zip(outcomes, prices, strict=False))
    read = [number(p) for p in prices]
    if (
        token not in tokens
        or len(read) != len(tokens)
        or any(p not in SETTLES for p in read)
        or sum(p for p in read if p is not None) != PAYOUT
    ):
        unread = (Unread("market.outcomePrices", str(body.get("outcomePrices"))),)
        return Resolution(stage=FINAL, value=None, unread=unread)
    index = tokens.index(token)
    return Resolution(
        stage=FINAL, value=read[index], scheme=OUTCOME_PRICES, word=prices[index], text=text
    )


def contract(
    token: str, body: Mapping[str, Any], raw_key: str, received_ns: int = 0
) -> Contract | None:
    """The outcome token `token` of one Gamma market, with its outcome once the
    market is resolved, or None where the market holds no such token."""
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
        resolution=resolution(token, body),
        read_at_ns=received_ns,
    )


def _yes_token(body: Mapping[str, Any]) -> str:
    """A market's YES token: its outcome `Yes`'s, else its first."""
    tokens, outcomes = _listed(body.get("clobTokenIds")), _listed(body.get("outcomes"))
    if not tokens:
        return ""
    if "Yes" in outcomes and outcomes.index("Yes") < len(tokens):
        return tokens[outcomes.index("Yes")]
    return tokens[0]


def event(body: Mapping[str, Any], raw_key: str, received_ns: int = 0) -> Event | None:
    """One Gamma event, from `/events/slug/{slug}`: its markets' YES tokens,
    the two flags as its negative risk states them. None where it names no
    slug or no market."""
    slug = str(body.get("slug") or "")
    markets = body.get("markets")
    listed = markets if isinstance(markets, Sequence) and not isinstance(markets, str) else []
    held = [m for m in listed if isinstance(m, Mapping)]
    members = tuple(token for token in (_yes_token(m) for m in held) if token)
    if not slug or not members:
        return None
    augmented = body.get("negRiskAugmented") is True or any(
        m.get("negRiskOther") is True for m in held
    )
    exclusive: bool | None = True if body.get("negRisk") is True else None
    exhaustive: bool | None = None if augmented or exclusive is None else True
    series = body.get("series")
    first = (
        series[0] if isinstance(series, Sequence) and series and not isinstance(series, str) else {}
    )
    return Event(
        ref=slug,
        title=str(body.get("title") or ""),
        members=members,
        mutually_exclusive=exclusive,
        exhaustive=exhaustive,
        series=str(first.get("slug") or "") if isinstance(first, Mapping) else "",
        valid_from_ns=received_ns,
        raw_key=raw_key,
    )


def event_slug(markets: object) -> str:
    """The slug of the event a Gamma market answer's market belongs to;
    empty where it names none."""
    for body in markets if isinstance(markets, list) else []:
        events = body.get("events") if isinstance(body, Mapping) else None
        for each in events if isinstance(events, list) else []:
            if isinstance(each, Mapping) and each.get("slug"):
                return str(each["slug"])
    return ""


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
        #: Each condition's event slug, once read: a condition's event does
        #: not change.
        self._slugs: dict[str, str] = {}
        live = mode == "live"
        elsewhere = f"{mode}: no call leaves the deployment"
        self.session = Session(
            mode=mode,
            endpoints=(
                Endpoint(
                    "Gamma",
                    GAMMA if live else elsewhere,
                    "the market a token belongs to, and its outcome",
                ),
                Endpoint("CLOB", CLOB if live else elsewhere, "a token's book and last trade"),
            ),
            limits=LIMITS,
            health=client.health,
        )

    def contract(self, code: str, watching: bool = False) -> Contract | None:
        try:
            fetched = self.client.market(code, live=watching)
        except VenueError as refused:
            if refused.status == NOT_FOUND:
                return None
            raise
        markets = fetched.value if isinstance(fetched.value, list) else []
        for body in markets:
            if isinstance(body, Mapping) and (
                read := contract(code, body, fetched.raw_key, fetched.received_at_ns)
            ):
                return read
        return None

    def event(self, ref: str) -> Event | None:
        """The event a contract belongs to, by its reference (the contract's
        `market`, its condition ID): the condition's market read once for
        its event's slug, then the event; None where Polymarket names
        none."""
        slug = self._slugs.get(ref)
        try:
            if slug is None:
                slug = event_slug(self.client.condition(ref).value)
                if not slug:
                    return None
                self._slugs[ref] = slug
            fetched = self.client.event(slug)
        except VenueError as refused:
            if refused.status == NOT_FOUND:
                return None
            raise
        if not isinstance(fetched.value, Mapping):
            return None
        return event(fetched.value, fetched.raw_key, fetched.received_at_ns)

    def last(self, of: Contract) -> Tick:
        fetched = self.client.last_trade(of.code)
        return tick(of, fetched.value, fetched.raw_key, fetched.received_at_ns)

    def top(self, of: Contract) -> Top:
        fetched = self.client.book(of.code)
        return top(of, fetched.value, fetched.raw_key, fetched.received_at_ns)
