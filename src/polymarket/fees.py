"""Polymarket's fees: each market's own, as Gamma states it, falling back to
its category's published rate (ruling 630, from 0.11.0), and the category
table itself, as Polymarket states it, with where and when it was read
(571's category column; task
sdk-contract/event-contract-fees-vary-by-market-category).

**Per market** (`market_fee`). Gamma states each market's own fee
(`feeSchedule`: its `rate`, `exponent`, `takerOnly` and `rebateRate`, and
`feeType`, its name) in the same answer the plugin reads the contract from,
so it costs no call: that rate applies to the market, and the Fees row says
so (`source` `market`). Where Gamma states none, the market's category's
row applies (`category`): the category is the one tag of the market's event
(`/events/slug/{slug}`, its `tags`, read with the event the plugin already
reports) whose label is a category of the table -- where none is, or more
than one, the market has no rate, and says why (`none`), never another
category's.

Read from docs.polymarket.com, "Fees" (`/trading/fees`), on 2026-10-26:
"fee = C x feeRate x p x (1 - p)", C the shares traded and p their price;
"Makers are never charged fees"; each category's taker fee rate, maker fee
rate and maker rebate as its table lists them. Geopolitics is fee-free, and
every combo is charged the Combos rate whatever its legs' categories.

The rates are Polymarket's words, kept as text and never computed with
here: the options sample's fee schedule (its settings) takes them, each
with this source and date. Polymarket also states each market's own fee in
Gamma's answer (`feeSchedule`: its `rate`, `exponent`, `takerOnly` and
`rebateRate`, and `feeType`), which can differ from its category's row --
read on 2026-10-26, an election market `zero_fees` at rate 0 and a sports
market `sports_fees_v2` at 0.03 -- so a market's own statement is the one
that applies to it. Polymarket's schedule changes without notice to this
plugin: a newer page is read and dated again at the plugin's next version.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rate:
    """One category's row, in the venue's words: its taker and maker fee
    rates as text, and its maker rebate, the share of taker fees returned
    to makers ("" where the venue lists none)."""

    category: str
    taker: str
    maker: str
    maker_rebate: str = ""


@dataclass(frozen=True)
class MarketFee:
    """One market's fee as it applies: the contract (the outcome token) it
    is for, its taker rate as text ("" where none applies), where that rate
    comes from -- `market` (Gamma's `feeSchedule`), `category` (the
    category table's row) or `none` -- and what the venue said, in its
    words."""

    code: str
    taker: str
    source: str
    said: str


@dataclass(frozen=True)
class Fees:
    """A venue's published fee schedule: where and when it was read, its
    formula, its rows, and where it states a market's own rate."""

    source: str = ""
    read_on: str = ""
    formula: str = ""
    rates: list[Rate] = field(default_factory=list)
    #: What makers pay, in the venue's words.
    makers: str = ""
    per_market: str = ""
    #: Why a rate is left out, where the schedule could not be read.
    not_read: str = ""
    #: Each contract served's fee as it applies (from 0.11.0, ruling 630).
    markets: list[MarketFee] = field(default_factory=list)


SOURCE = "https://docs.polymarket.com/trading/fees"
READ_ON = "2026-10-26"

FEES = Fees(
    source=SOURCE,
    read_on=READ_ON,
    formula="fee = C x feeRate x p x (1 - p), C shares at price p; takers only",
    rates=[
        Rate("Crypto", "0.07", "0", "20%"),
        Rate("Sports", "0.05", "0", "15%"),
        Rate("Finance", "0.04", "0", "25%"),
        Rate("Politics", "0.04", "0", "25%"),
        Rate("Economics", "0.05", "0", "25%"),
        Rate("Culture", "0.05", "0", "25%"),
        Rate("Weather", "0.05", "0", "25%"),
        Rate("Other / General", "0.05", "0", "25%"),
        Rate("Mentions", "0.04", "0", "25%"),
        Rate("Tech", "0.04", "0", "25%"),
        Rate("Geopolitics", "0", "0", ""),
        Rate("Combos", "0.05", "0", "0%"),
    ],
    makers="never charged",
    per_market=(
        "each market's own fee as Gamma states it (feeSchedule, feeType) applies to it; "
        "where it states none, its event's category's row; where no tag is one category, "
        "no rate"
    ),
)

#: Each category's row by its name.
BY_CATEGORY = {r.category: r for r in FEES.rates}


def stated(body: Mapping[str, Any]) -> str | None:
    """A Gamma market's own fee in its words -- its taker rate and how Gamma
    states the rest -- or None where it states no `feeSchedule`."""
    schedule = body.get("feeSchedule")
    if not isinstance(schedule, Mapping) or schedule.get("rate") is None:
        return None
    parts = [f"rate {schedule.get('rate')}"]
    for key in ("exponent", "takerOnly", "rebateRate"):
        if key in schedule:
            parts.append(f"{key} {str(schedule[key]).lower()}")
    if body.get("feeType"):
        parts.append(f"feeType {body['feeType']}")
    return ", ".join(parts)


def market_fee(code: str, said: str | None, tags: Sequence[str] | None) -> MarketFee:
    """The fee applying to one contract: its market's own (`said`, as
    `stated` read it), else its event's category's row by the event's tag
    labels (`tags`; None where the event is not read yet)."""
    if said is not None:
        return MarketFee(code, said.split(",")[0].removeprefix("rate ").strip(), "market", said)
    if tags is None:
        return MarketFee(code, "", "none", "no feeSchedule; its event's category not read yet")
    found = sorted({t for t in tags if t in BY_CATEGORY})
    if len(found) != 1:
        why = (
            "no tag is a category"
            if not found
            else "tags of several categories: " + ", ".join(found)
        )
        return MarketFee(code, "", "none", f"no feeSchedule; {why}")
    row = BY_CATEGORY[found[0]]
    return MarketFee(code, row.taker, "category", f"no feeSchedule; category {row.category}")
