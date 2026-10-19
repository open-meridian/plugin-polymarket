"""Polymarket's side of the data role's checks: this plugin's synthetic exchanges,
named for what each of the checks asks a source to present.

tests/test_data_role.py runs the SDK's checks for an event-contract venue
(`meridian.roles.data.testing.EventContractsChecks`) -- the data suite
unchanged, the venue's work past the suite's cases, its outcomes, and the
pages -- against this plugin's own conversion; this module is the one place
they learn which venue they are holding. Each answer comes through the
plugin's real client, raw records and reading (synthetic.py's transport over
the exchanges this package carries, `src/polymarket/synthetic/`), with invented
markets and values; real recordings are never committed (the plan's Q11).
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from meridian.edge import RawStore
from meridian.roles.data.event_contracts import Event, Market

from polymarket import page
from polymarket.convert import PolymarketMarket
from polymarket.synthetic import Synthetic
from polymarket.venue import Polymarket, RateLimiter

__all__ = ["page"]

SYNTHETIC = Path(__file__).parent.parent / "src" / "polymarket" / "synthetic"

#: The venue's name as a symbol's source, and the plugin's.
VENUE = "polymarket"
#: The suite's clock: 2026-10-10 12:00 UTC.
NOW_NS = 1_791_633_600 * 1_000_000_000
TODAY = date(2026, 10, 10)

#: An outcome token -- a final's YES -- with both sides of its book and a last
#: trade.
BASE = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
#: Its last trade's price, its best bid and offer and their sizes, in USDC.
LAST = "0.440"
BID, BID_SIZE = "0.43", "550.5"
ASK, ASK_SIZE = "0.45", "125.25"
#: What one token pays if its outcome is the result, in the venue's cash.
PAYOUT, CASH = "1", "USDC"
#: A token whose prices have more places than a float holds.
EXACT = "10000000000000000000000000000000000000000000000000000000000000000000000000017"
EXACT_LAST = "0.123456789012345678"
#: A token with bids and no offer.
ONE_SIDED = "20000000000000000000000000000000000000000000000000000000000000000000000000029"
#: A token of a market of three outcomes, which is not binary.
NOT_BINARY = "30000000000000000000000000000000000000000000000000000000000000000000000000041"
#: Polymarket prices in USDC, its own token instrument: never a currency code.
STABLE = True

# ── Outcomes (contract v23) ─────────────────────────────────────────────────

#: The YES token of a market Polymarket has resolved YES: its outcome from its
#: own side, final, with Polymarket's word, the token's own stated price.
RESOLVED = "40000000000000000000000000000000000000000000000000000000000000000000000000053"
RESOLVED_STAGE = "OUTCOME_STAGE_FINAL"
WORD = ("polymarket:outcomePrices", "1")
#: The same market's NO token: it pays nothing.
RESOLVED_LOSER = "40000000000000000000000000000000000000000000000000000000000000000000000000054"
#: A token of a market resolved "Unknown/50-50": half its payout.
PARTIAL, PARTIAL_VALUE = (
    "60000000000000000000000000000000000000000000000000000000000000000000000000067",
    "0.5",
)
#: A token past its market's end with a resolution proposed: Gamma states the
#: stage and not the proposal's answer, so nothing is recorded.
PENDING = "80000000000000000000000000000000000000000000000000000000000000000000000000081"
#: No later stage: a Polymarket resolution is final once made.
LATER: tuple[tuple[Path, str, int], ...] = ()
#: The suite's outcome cases as Polymarket presents them: an outcome recorded
#: at the stage it states, final (the case takes determined or final, ruled
#: 2026-10-13), and a partial payout. A dispute it never states: see
#: NOT_PRESENTED.
DETERMINED: str | None = RESOLVED
DISPUTED: tuple[str, tuple[Path, ...]] | None = None

# ── Event groups (contract v26) ─────────────────────────────────────────────

#: A negative-risk event (`negRisk`): the synthetic final, its three markets
#: -- the base contract's among them -- mutually exclusive and exhaustive;
#: and an augmented one (`negRiskAugmented`, an "Other" market marked
#: `negRiskOther`), its named outcomes mutually exclusive, their
#: exhaustiveness not stated. Each by its slug, and the condition of one of
#: its markets, by which a contract served finds it.
FINAL, MAYOR = "synthetic-final-winner", "synthetic-mayor"
FINAL_CONDITION = "0x" + "5a" * 32
MAYOR_CONDITION = "0x" + "6a" * 32
#: The final's other two markets' YES tokens.
RIVAL = "9" + "0" * 73 + "911"
DRAW = "9" + "0" * 73 + "921"

#: The suite's cases Polymarket's one dataset never presents, each with why:
#: the dataset publishes prices and quotes now, per outcome token, in USDC.
NOT_PRESENTED = {
    "a-daily-close": "its one dataset publishes live prices and quotes, and no daily closes",
    "the-forming-day-restated": "its one dataset publishes no daily closes to restate",
    "a-daily-bar": "its one dataset publishes live prices and quotes, and no bars",
    "an-fx-rate": "it prices event contracts, and no currency's rate against another",
    "a-subject-another-source-resolved": "its subjects are event contracts, and no security",
    "a-trade-recorded": "its one dataset publishes prices and quotes, and no trades",
    "the-makers-side-inverted": "its one dataset publishes no trades",
    "a-condition-converted": "its one dataset publishes no trades",
    "a-condition-not-converted": "its one dataset publishes no trades",
    "a-trade-withdrawn": "its one dataset publishes no trades",
    "a-standing-want-streamed": "its one dataset publishes no trades to stream",
    "the-takers-side-stated": "its one dataset publishes no trades",
    "a-restarts-gap-backfilled": "its one dataset publishes no trades, so a restart leaves no gap "
    "of trades to read back",
    "reads-a-calendar": "it records event contracts' prices and quotes as they stream: it reads "
    "no settlement calendar",
    "asks-for-a-settlement-date": "it records prices and quotes as published; an event contract "
    "settles on its outcome, and it never computes a settlement date",
    "restates-a-disputed-outcome": "Polymarket's public reads state a resolution only once it is "
    "final; a proposal's answer and a dispute are not stated",
}


def _instant(_: float) -> None:
    return None


def market(now_ns: int = NOW_NS, directory: Path | None = None) -> Market:
    """Polymarket's synthetic exchange through the plugin's own client, its
    answers kept in a fresh store."""
    store = RawStore(Path(tempfile.mkdtemp(prefix="polymarket-raw-")))
    client = Polymarket(
        store,
        transport=Synthetic(directory or SYNTHETIC),
        limiter=RateLimiter(1000.0, 1000, sleep=_instant),
        clock_ns=lambda: now_ns,
        sleep=_instant,
    )
    return PolymarketMarket(client, "synthetic")


def event(condition: str) -> Event:
    """One of Polymarket's synthetic events, found from one of its markets'
    conditions as the plugin's conversion reads it."""
    read = market().event(condition)  # type: ignore[attr-defined]
    assert isinstance(read, Event), condition
    return read


#: The data suite's event groups (contract v26): `reports-an-event-group` on
#: the negative-risk final, `reports-a-flag-the-venue-does-not-state` on the
#: augmented mayoral race.
EVENT = event(FINAL_CONDITION)
EVENT_PLACEHOLDERS = event(MAYOR_CONDITION)


def calls(market: Any) -> list[str]:
    """The URLs the plugin asked of the venue, in order, from its raw records."""
    return [r["request"]["url"] for r in market.client.store.records()]
