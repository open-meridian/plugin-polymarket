"""Polymarket's published taker fee rate by market category, on Connection
and in `read_connection` (fees.py; from 0.10.0): each category's rate as
Polymarket's page lists it, with its source and the day it was read."""

from __future__ import annotations

import asyncio
from decimal import Decimal

from meridian.roles.data.event_contracts import ContractMap, Feed
from meridian.roles.data.testing import Lake
from meridian.testing import PageClient

from polymarket import page
from polymarket.fees import FEES, MarketFee, market_fee, stated

import venue_cases as v


def test_each_rate_is_the_venues_text_and_reads_as_a_number() -> None:
    assert FEES.source.startswith("https://docs.polymarket.com/")
    assert FEES.read_on == "2026-10-26"
    categories = [r.category for r in FEES.rates]
    assert len(categories) == len(set(categories)) == 12
    for rate in FEES.rates:
        assert Decimal(rate.taker) >= 0 and Decimal(rate.maker) == 0
    assert {r.category: r.taker for r in FEES.rates}["Geopolitics"] == "0"


def test_connection_answers_and_shows_the_fees() -> None:
    client = PageClient(page.pages)
    fees = client.call_tool("read_connection", level="admin").data["fees"]
    assert fees["source"] == FEES.source and fees["read_on"] == FEES.read_on
    assert [r["category"] for r in fees["rates"]] == [r.category for r in FEES.rates]
    shown = client.get("/", "admin").text
    assert "Taker by category: Crypto 0.07, Sports 0.05" in shown
    assert "read 2026-10-26" in shown


# ── Each market's fee as it applies (from 0.11.0; ruling 630) ───────────────


def test_a_markets_own_fee_applies_before_its_categorys() -> None:
    body = {
        "feeSchedule": {"exponent": 1, "rate": 0, "takerOnly": True, "rebateRate": 0},
        "feeType": "zero_fees",
    }
    said = stated(body)
    assert said == "rate 0, exponent 1, takerOnly true, rebateRate 0, feeType zero_fees"
    applying = market_fee("T", said, ["Weather"])
    assert (applying.taker, applying.source) == ("0", "market"), "Weather's row says 0.05"
    assert stated({"feeSchedule": None}) is None


def test_with_no_fee_of_its_own_its_one_category_applies_else_none() -> None:
    assert market_fee("T", None, ["Weather", "Recurring"]) == MarketFee(
        "T", "0.05", "category", "no feeSchedule; category Weather"
    )
    unread = market_fee("T", None, None)
    assert (unread.taker, unread.source) == ("", "none") and "not read yet" in unread.said
    neither = market_fee("T", None, ["Recurring"])
    assert (neither.taker, neither.source) == (
        "",
        "none",
    ) and "no tag is a category" in neither.said
    both = market_fee("T", None, ["Sports", "Politics"])
    assert both.source == "none" and "Politics, Sports" in both.said, "never another's rate"


def test_connection_says_which_fee_applies_to_each_contract_served() -> None:
    lake = Lake(v.VENUE)
    feed = Feed(lake, v.market(), ContractMap(), clock_ns=lambda: v.NOW_NS)
    mayor = v.event(v.MAYOR_CONDITION).members[0]

    async def served() -> None:
        for code in (v.BASE, mayor):
            await feed.name([await lake.held(feed, code)])
        await feed.keep_events(once=True)

    asyncio.run(served())
    page.hold(feed)
    try:
        client = PageClient(page.pages)
        fees = client.call_tool("read_connection", level="admin").data["fees"]
        applying = {m["code"]: (m["taker"], m["source"]) for m in fees["markets"]}
        assert applying == {v.BASE: ("0.05", "market"), mayor: ("0.04", "category")}
        assert "Per market: 1 own, 1 by category, 0 none" in client.get("/", "admin").text
    finally:
        page.HELD.feed = None
