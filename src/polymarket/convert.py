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
  of a market resolved YES pays nothing. That stage is final: a UMA
  resolution, once made, is reported on chain and redeemed. Polymarket's
  word, kept as reported, is the token's own stated price
  (`polymarket:outcomePrices`), with each outcome and its price as text.
  Polymarket states no time of resolution or of payout: the outcome is
  valid from when the answer first stating it arrived, and its payout time
  is left 0 (holders redeem their tokens themselves).
- **A proposal and a dispute** (from 0.11.0; ruling 622). Gamma states
  their stage (`proposed`, in its challenge period; `disputed`) but never
  their answer -- `outcomePrices` stay the book's while one stands. Where
  the deployment admin has entered a Polygon RPC URL, the answer is read
  from UMA's oracle on chain (uma.py): the proposed stage with the price
  proposed as this token's settlement value, valid from the proposal's
  time, its challenge window's end (`challenge_ends_at_ns`) the request's
  expiration; the disputed stage with the price disputed and no window;
  the plugin's word for both the oracle's price as it holds it
  (`uma:proposedPrice`, `1000000000000000000` paying the market's first
  outcome). The oracle's prices pay the market's outcomes in Gamma's order
  of them (`outcomes`, `clobTokenIds`), the adapter's payout slots. Without
  the setting, nothing is recorded for either, as before 0.11.0: a
  Polymarket outcome at its final stage alone.
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
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any

from meridian.roles.data import NANOS_PER_SECOND, Endpoint, Limits, Session, Unread, number
from meridian.roles.data.event_contracts import (
    DAY,
    DISPUTED,
    FINAL,
    HOUR,
    PROPOSED,
    Candle,
    Cash,
    Contract,
    Event,
    Resolution,
    Tick,
    Top,
)

from . import fees, uma
from .venue import (
    BURST,
    CLOB,
    DATA,
    GAMMA,
    NOT_FOUND,
    RATE_PER_SECOND,
    Fetched,
    Polymarket,
    VenueError,
)

log = logging.getLogger("polymarket")

VENUE = "polymarket"
NAME = "Polymarket"
#: What the venue entitles this plugin to: its public market data, no key.
ENTITLED = "Public market data: a contract is read only for a subject the lake asked for"
#: What each outcome token is and pays, said on the Datasets page.
VENDOR_NOTE = "Each outcome is its own token and contract."
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


#: Gamma's word for a market's stage while its resolution stands open.
OPEN_STAGES = {"proposed": PROPOSED, "disputed": DISPUTED}


def staged(token: str, body: Mapping[str, Any], said: uma.Proposal | None) -> Resolution | None:
    """The token's proposed or disputed stage, from what UMA's oracle states
    of its market's request (`said`); None where Gamma states neither stage,
    or the oracle states no proposal and Gamma no dispute. A dispute whose
    request the adapter has sent again, nothing proposed on it yet, states
    the stage and no answer: the answer recorded last stands."""
    stage = OPEN_STAGES.get(str(body.get("umaResolutionStatus") or "").lower())
    tokens, outcomes = _listed(body.get("clobTokenIds")), _listed(body.get("outcomes"))
    if stage is None or said is None or token not in tokens:
        return None
    if not said.proposed:
        return Resolution(stage=DISPUTED, value=None) if stage == DISPUTED else None
    paid = uma.payouts(said.price, len(tokens))
    word = str(said.price)
    if paid is None:
        return Resolution(
            stage=DISPUTED if said.disputed else PROPOSED,
            value=None,
            unread=(Unread("uma.proposedPrice", word),),
        )
    text = ", ".join(f"{o} {p}" for o, p in zip(outcomes, paid, strict=False))
    if said.disputed:
        return Resolution(
            stage=DISPUTED,
            value=paid[tokens.index(token)],
            scheme=uma.PROPOSED_PRICE,
            word=word,
            text=f"disputed: {text}",
        )
    return Resolution(
        stage=PROPOSED,
        value=paid[tokens.index(token)],
        scheme=uma.PROPOSED_PRICE,
        word=word,
        text=f"proposed: {text}",
        determined_at_ns=uma.seconds_ns(said.proposed_at),
        challenge_ends_at_ns=uma.seconds_ns(said.expires_at),
    )


def candles(
    code: str, interval: str, fills: Sequence[Mapping[str, Any]], raw_keys: Sequence[str],
    first_ns: int, until_ns: int,
) -> list[Candle]:  # fmt: skip
    """A token's candles of `interval` -- an hour, or a UTC day, its
    declared day -- built from the market's fills, oldest first, each the
    token's own and within [`first_ns`, `until_ns`): open the first fill's
    price, close the last's, volume the tokens traded, the fills counted.
    No volume-weighted price is stated (the a-daily-bar case leaves it
    unset). `raw_keys[i]` is the record fill i was kept in."""
    width = 3_600 if interval == HOUR else 86_400
    held: dict[int, list[tuple[Decimal, Decimal, str]]] = {}
    for fill, key in zip(fills, raw_keys, strict=True):
        if str(fill.get("token_id")) != code:
            continue
        price, size, at = number(fill.get("price")), number(fill.get("size")), fill.get("timestamp")
        if price is None or size is None or not isinstance(at, int | Decimal):
            continue
        seconds = int(at)
        if not first_ns <= seconds * NANOS_PER_SECOND < until_ns:
            continue
        held.setdefault(seconds - seconds % width, []).append((price, size, key))
    made: list[Candle] = []
    for start, traded in sorted(held.items()):
        end_ns = (start + width) * NANOS_PER_SECOND
        if start * NANOS_PER_SECOND < first_ns or end_ns > until_ns:
            continue
        prices = [p for p, _, _ in traded]
        made.append(Candle(
            code=code, start_ns=start * NANOS_PER_SECOND, end_ns=end_ns,
            open=prices[0], high=max(prices), low=min(prices), close=prices[-1],
            volume=sum((s for _, s, _ in traded), Decimal(0)), trade_count=len(traded),
            raw_key=traded[-1][2],
        ))  # fmt: skip
    return made


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


#: The most pages of a market's fills one read of its bars walks back: a
#: market trading more than this in the window asked is kept from where the
#: read reached, its earlier intervals left unread.
MOST_TRADE_PAGES = 20
#: How long a market's fills read for its bars answer its other token and
#: interval asked in the same pass, in nanoseconds.
_FILLS_HELD_NS = 60 * NANOS_PER_SECOND


class PolymarketMarket:
    """Polymarket's market data, as the shared data plugin's work asks for it."""

    venue = VENUE
    name = NAME
    venue_identifiers = VENUE_IDENTIFIERS
    cash = CASH

    def __init__(
        self, client: Polymarket, mode: str = "live", chain: uma.Uma | None = None
    ) -> None:
        self.client = client
        #: Each condition's event slug, once read: a condition's event does
        #: not change.
        self._slugs: dict[str, str] = {}
        #: Each token's market's own fee as Gamma states it (None: none),
        #: and each condition's event's tag labels, as last read (ruling 630).
        self.fees_said: dict[str, str | None] = {}
        self.tags: dict[str, list[str]] = {}
        #: A market's fills as last read for its bars: when, the time from
        #: which they are whole, until, whether the walk was cut short, and
        #: each fill with its raw record's key.
        self._fills: dict[str, tuple[int, int, int, bool, list[Mapping[str, Any]], list[str]]] = {}
        self.mode = mode
        live = mode == "live"
        elsewhere = f"{mode}: no call leaves the deployment"
        self._elsewhere = elsewhere
        self.session = Session(
            mode=mode,
            endpoints=(),
            limits=LIMITS,
            health=client.health,
        )
        self._gamma = Endpoint(
            "Gamma",
            GAMMA if live else elsewhere,
            "the market a token belongs to, its outcome and its fee",
        )
        self._clob = Endpoint("CLOB", CLOB if live else elsewhere, "a token's book and last trade")
        self._data = Endpoint(
            "Data API",
            DATA if live else elsewhere,
            "a market's trades, for its bars: each trade's wallet and names dropped before kept",
        )
        self.chain: uma.Uma | None = None
        self.read_on_chain(chain)

    def read_on_chain(self, chain: uma.Uma | None) -> None:
        """Read proposals and disputes through `chain`, or none (ruling
        622): the Connection says which, and never the RPC's URL."""
        self.chain = chain
        if chain is None:
            said = "not set: outcomes are recorded final only"
        elif self.mode == "live":
            said = "set by the deployment admin (secret)"
        else:
            said = self._elsewhere
        self.session.endpoints = (
            self._gamma,
            self._clob,
            self._data,
            Endpoint("Polygon RPC", said, "UMA's proposals and disputes, read only"),
        )

    def _staged(self, token: str, body: Mapping[str, Any]) -> Resolution | None:
        """A proposal's or a dispute's stage from UMA's oracle, where Gamma
        states one, the RPC is set and the market names its question."""
        status = str(body.get("umaResolutionStatus") or "").lower()
        if self.chain is None or status not in OPEN_STAGES:
            return None
        asked = uma.question_of(body)
        if asked is None:
            return None
        return staged(token, body, self.chain.proposal(*asked))

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
                self.fees_said[code] = fees.stated(body)
                if read.resolution is None:
                    try:
                        open_stage = self._staged(code, body)
                    except (uma.ChainError, ValueError, IndexError) as failed:
                        # Said, never raised: the contract is read without it,
                        # and its stage asked again on its next read.
                        log.warning("%s's stage not read on chain: %s", code, failed)
                        open_stage = None
                    if open_stage is not None:
                        read = replace(read, resolution=open_stage)
                return read
        return None

    def event(self, ref: str) -> Event | None:
        """The event a contract belongs to, by its reference (the contract's
        `market`, its condition ID): the condition's market read once for
        its event's slug, then the event; None where Polymarket names
        none. Its tags' labels are kept for its markets' fee category."""
        slug = self._slugs.get(ref)
        try:
            if slug is None:
                slug = event_slug(self.client.condition(ref).value)
                if not slug:
                    self.tags[ref] = []  # no event: no tag, no category
                    return None
                self._slugs[ref] = slug
            fetched = self.client.event(slug)
        except VenueError as refused:
            if refused.status == NOT_FOUND:
                return None
            raise
        if not isinstance(fetched.value, Mapping):
            return None
        tags = fetched.value.get("tags")
        listed = tags if isinstance(tags, list) else []
        self.tags[ref] = [str(t.get("label")) for t in listed if isinstance(t, Mapping)]
        return event(fetched.value, fetched.raw_key, fetched.received_at_ns)

    def fee(self, of: Contract) -> fees.MarketFee:
        """The fee applying to a contract (ruling 630): its market's own,
        else its category's row, else none, with why."""
        return fees.market_fee(of.code, self.fees_said.get(of.code), self.tags.get(of.market))

    def last(self, of: Contract) -> Tick:
        fetched = self.client.last_trade(of.code)
        return tick(of, fetched.value, fetched.raw_key, fetched.received_at_ns)

    def top(self, of: Contract) -> Top:
        fetched = self.client.book(of.code)
        return top(of, fetched.value, fetched.raw_key, fetched.received_at_ns)

    def _market_fills(
        self, condition: str, first_ns: int, until_ns: int
    ) -> tuple[int, list[Mapping[str, Any]], list[str]]:
        """A market's fills from its UTC day holding `first_ns`, oldest
        first, each with its raw record's key, and the time from which they
        are whole: `first_ns`'s day, or where the walk stopped. One read
        answers both tokens and both intervals asked within a minute."""
        now = self.client.clock_ns()
        day_ns = 86_400 * NANOS_PER_SECOND
        start = first_ns - first_ns % day_ns
        held = self._fills.get(condition)
        # A read held a minute answers a window it covers, or any, where its
        # walk was cut short: reading again would stop at the same place.
        if held is not None and now - held[0] <= _FILLS_HELD_NS and held[2] >= until_ns \
                and (held[1] <= start or held[3]):  # fmt: skip
            return max(held[1], start), held[4], held[5]
        fills: list[Mapping[str, Any]] = []
        keys: list[str] = []
        cursor, whole_from, pages, cut = "", start, 0, False
        while True:
            fetched: Fetched = self.client.trades(condition, cursor)
            pages += 1
            page = fetched.value if isinstance(fetched.value, Mapping) else {}
            data = page.get("data")
            rows = [f for f in data if isinstance(f, Mapping)] if isinstance(data, list) else []
            fills += rows
            keys += [fetched.raw_key] * len(rows)
            times = [int(f["timestamp"]) for f in rows if isinstance(f.get("timestamp"), int)]
            if times and min(times) * NANOS_PER_SECOND < start:
                break
            said = page.get("pagination")
            cursor = str(said.get("next_cursor") or "") if isinstance(said, Mapping) else ""
            if not cursor:
                break
            if pages >= MOST_TRADE_PAGES:
                # Whole only after the oldest second read, which may go on.
                oldest = min(times) if times else until_ns // NANOS_PER_SECOND
                whole_from, cut = (oldest + 1) * NANOS_PER_SECOND, True
                break
        fills.reverse()
        keys.reverse()
        self._fills[condition] = (now, whole_from, until_ns, cut, fills, keys)
        return whole_from, fills, keys

    def bars(self, of: Contract, interval: str, first_ns: int, until_ns: int) -> list[Candle]:
        """A token's hourly or daily (UTC) candles from `first_ns` to
        `until_ns`, built from its market's public trades (ruling 624):
        each fill's wallet and names dropped before it was kept."""
        if interval not in (HOUR, DAY) or not of.market:
            return []
        whole_from, fills, keys = self._market_fills(of.market, first_ns, until_ns)
        return candles(of.code, interval, fills, keys, max(first_ns, whole_from), until_ns)
