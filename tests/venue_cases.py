"""Polymarket's side of the shared tests: this plugin's synthetic exchanges,
named for what each of the data suite's cases asks a source to present.

tests/test_suite.py, the same file in plugin-kalshi, runs the SDK's data
suite unchanged against each plugin's own conversion; this module is the one
place it learns which venue it is holding. Each answer comes through the
plugin's real client, raw records and reading (synthetic.py's transport over
the exchanges this package carries, `src/polymarket/synthetic/`), with
invented markets, token IDs and values; real recordings are never committed
(the plan's Q11).
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from polymarket import page, raw, synthetic
from polymarket.contracts import ContractMap
from polymarket.convert import PolymarketMarket
from polymarket.dgm import Dgm, Standing
from polymarket.market import Market
from polymarket.raw import RawStore
from polymarket.synthetic import Synthetic
from polymarket.venue import Polymarket, RateLimiter

__all__ = ["ContractMap", "Dgm", "Standing", "market", "page", "raw", "synthetic"]

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


def calls(market: Any) -> list[str]:
    """The URLs the plugin asked of the venue, in order, from its raw records."""
    return [r["request"]["url"] for r in market.client.store.records()]
