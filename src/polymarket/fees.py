"""Polymarket's published taker fee rates by market category, as Polymarket
states them, with where and when they were read (571's category column;
task sdk-contract/event-contract-fees-vary-by-market-category).

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

from dataclasses import dataclass, field


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
        "Gamma states each market's own fee (feeSchedule, feeType), which can differ from "
        "its category's row; a market's own applies to it"
    ),
)
