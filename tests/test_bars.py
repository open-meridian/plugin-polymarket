"""Each outcome token's hourly and daily bars, built from Polymarket's public
trades (from 0.11.0; rulings 624 and 625): each trade's wallet and names
dropped before anything is kept, the market's trades read once for both
intervals, closed intervals only, no volume-weighted price."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from meridian.edge import RawStore
from meridian.operations import as_decimal
from meridian.roles.data.event_contracts import DAY, HOUR, ContractMap, Feed
from meridian.roles.data.testing import Lake

from polymarket.convert import MOST_TRADE_PAGES, PolymarketMarket, candles
from polymarket.synthetic import Synthetic
from polymarket.venue import DATA, Polymarket, RateLimiter, Response, trades_kept

import venue_cases as v

CONDITION = "0x" + "5a" * 32
HOUR_NS = 3_600 * 10**9


def test_a_trade_keeps_its_market_token_side_size_price_and_time_alone() -> None:
    page = json.dumps({
        "data": [{"proxy_wallet": "0xabc", "name": "n", "pseudonym": "p", "bio": "b",
                  "profile_image": "i", "profile_image_optimized": "o",
                  "transaction_hash": "0xdef", "title": "t", "slug": "s", "icon": "c",
                  "event_slug": "e", "side": "BUY", "token_id": "T", "condition_id": "C",
                  "size": 10.5, "price": 0.123456789012345678, "timestamp": 1791633000,
                  "outcome": "Yes", "outcome_index": 0}],
        "pagination": {"limit": 1000, "has_more": False, "next_cursor": None},
    })  # fmt: skip
    page = page.replace("0.12345678901234568", "0.123456789012345678")
    kept = json.loads(trades_kept(page))
    [fill] = kept["data"]
    assert set(fill) == {"condition_id", "token_id", "outcome", "outcome_index", "side", "size",
                         "price", "timestamp"}  # fmt: skip
    assert "0.123456789012345678" in trades_kept(page), "a number kept as it arrived"
    assert kept["pagination"]["next_cursor"] is None
    assert trades_kept('{"error":"x"}') == '{"error":"x"}'


def _market(tmp_path: Path, transport: object | None = None) -> PolymarketMarket:
    client = Polymarket(
        RawStore(tmp_path),
        transport=transport or Synthetic(v.SYNTHETIC),  # type: ignore[arg-type]
        limiter=RateLimiter(1000.0, 1000, sleep=lambda _: None),
        clock_ns=lambda: v.NOW_NS,
        sleep=lambda _: None,
    )
    return PolymarketMarket(client, "synthetic")


async def test_hours_and_days_closed_kept_from_the_synthetic_finals_trades(
    tmp_path: Path,
) -> None:
    lake = Lake(v.VENUE)
    market = _market(tmp_path)
    feed = Feed(lake, market, ContractMap(), clock_ns=lambda: v.NOW_NS)
    await feed.name([await lake.held(feed, v.BASE)])
    assert await feed.keep_bars(v.BARS_DECLARED, once=True) == 5
    bars = lake.rows("RecordBars")
    hours = [b for b in bars if not b.meta.business_date]
    days = [b for b in bars if b.meta.business_date]
    assert len(hours) == 4 and [d.meta.business_date for d in days] == ["2026-10-09"]
    [day] = days
    assert [str(as_decimal(getattr(day, f).amount)) for f in ("open", "high", "low", "close")] == [
        "0.41", "0.43", "0.39", "0.42",
    ]  # fmt: skip
    assert as_decimal(day.volume) == Decimal("195.5") and day.trade_count == 4
    assert not day.HasField("vwap"), "no volume-weighted price"
    nine = next(b for b in hours if b.meta.row_key.endswith(":1h:1791536400"))
    assert (as_decimal(nine.open.amount), as_decimal(nine.close.amount)) == (
        Decimal("0.41"), Decimal("0.39"),
    )  # fmt: skip
    assert as_decimal(nine.volume) == Decimal("125.5"), "the NO token's trade is its own"
    assert all(b.meta.valid_until_ns <= v.NOW_NS - 60 * 10**9 for b in bars), "closed only"
    trades = [r for r in market.client.store.records() if r["call"] == "trades"]
    assert len(trades) == 1, "the market's trades read once for both intervals"
    assert trades[0]["request"]["url"].startswith(f"{DATA}/v2/trades?condition={CONDITION}")
    body = trades[0]["body"]
    assert "proxy_wallet" not in body and "Synthetic-Pseudonym" not in body
    assert "transaction_hash" not in body and "synthetic-trader" not in body
    raw = day.meta.raw.key
    assert raw.startswith("responses/") and "/trades/" in raw


def test_a_walk_cut_short_keeps_only_the_intervals_it_read_whole(tmp_path: Path) -> None:
    # A market trading past MOST_TRADE_PAGES pages in the window: the hours
    # before the oldest second read are left unread, never part-built.
    start = 1_791_504_000  # 2026-10-09 00:00 UTC

    def fill(at: int) -> dict[str, object]:
        return {"token_id": "T", "condition_id": "C", "side": "BUY", "size": 1,
                "price": 0.5, "timestamp": at}  # fmt: skip

    def pages(url: str, headers: object) -> Response:
        cursor = url.split("cursor=")[1] if "cursor=" in url else "0"
        n = int(cursor)
        at = start + 86_400 - 600 * (n + 1)
        body = {"data": [fill(at)], "pagination": {"next_cursor": str(n + 1)}}
        return Response(200, {}, json.dumps(body).encode())

    market = _market(tmp_path, pages)
    contract = type("C", (), {"code": "T", "market": "C"})()
    made = market.bars(contract, HOUR, start * 10**9, (start + 86_400) * 10**9)
    oldest = start + 86_400 - 600 * MOST_TRADE_PAGES
    assert made and all(c.start_ns > oldest * 10**9 for c in made)
    assert market.session.health.calls == MOST_TRADE_PAGES


def test_a_candle_spans_its_interval_and_holds_its_tokens_fills_alone() -> None:
    fills = [
        {"token_id": "T", "price": Decimal("0.2"), "size": Decimal(3), "timestamp": 7_200},
        {"token_id": "U", "price": Decimal("0.9"), "size": Decimal(1), "timestamp": 7_300},
        {"token_id": "T", "price": Decimal("0.4"), "size": Decimal(1), "timestamp": 10_799},
    ]
    [hour] = candles("T", HOUR, fills, ["k1", "k2", "k3"], 0, 4 * HOUR_NS)
    assert (hour.start_ns, hour.end_ns) == (2 * HOUR_NS, 3 * HOUR_NS)
    assert (hour.open, hour.close, hour.volume, hour.trade_count) == (
        Decimal("0.2"), Decimal("0.4"), Decimal(4), 2,
    )  # fmt: skip
    assert hour.vwap is None and hour.raw_key == "k3"
    assert candles("T", DAY, fills, ["k1", "k2", "k3"], 0, 4 * HOUR_NS) == [], "a day to come"
