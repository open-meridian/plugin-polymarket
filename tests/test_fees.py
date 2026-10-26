"""Polymarket's published taker fee rate by market category, on Connection
and in `read_connection` (fees.py; from 0.10.0): each category's rate as
Polymarket's page lists it, with its source and the day it was read."""

from __future__ import annotations

from decimal import Decimal

from meridian.testing import PageClient

from polymarket import page
from polymarket.fees import FEES


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
