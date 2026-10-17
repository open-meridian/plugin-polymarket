"""Polymarket's answers read into the venue's values: two tokens, two
contracts, each paying one USDC; a token's own book; its last trade."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from meridian.roles.data.event_contracts import Contract

from polymarket import convert

import venue_cases as venue

CONTRACT = Contract(code="111", title="Will it? (Yes)", binary=True, payout=Decimal("1"))
GAMMA = {
    "question": "Will it?",
    "conditionId": "0xabc",
    "outcomes": '["Yes", "No"]',
    "clobTokenIds": '["111", "222"]',
    "endDate": "2026-12-31T23:59:00Z",
    "active": True,
    "closed": False,
    "acceptingOrders": True,
}


def _top(book: dict[str, Any]) -> Any:
    return convert.top(CONTRACT, book, "responses/2026-10-10/book/111.jsonl#0", 7)


def test_each_token_of_a_market_is_its_own_binary_contract_paying_one_usdc() -> None:
    yes, no = convert.contract("111", GAMMA, "raw"), convert.contract("222", GAMMA, "raw")
    assert yes is not None and no is not None
    assert (yes.title, no.title) == ("Will it? (Yes)", "Will it? (No)")
    assert yes.binary and no.binary and yes.payout == no.payout == Decimal("1")
    assert yes.market == "0xabc" and yes.tradable
    assert yes.closes_at_ns == 1_798_761_540 * 1_000_000_000
    assert convert.contract("333", GAMMA, "raw") is None


def test_a_market_of_three_outcomes_is_not_binary_and_a_closed_one_not_traded() -> None:
    three = GAMMA | {"outcomes": '["A", "B", "C"]', "clobTokenIds": '["111", "222", "333"]'}
    read = convert.contract("111", three, "raw")
    assert read is not None and not read.binary
    closed = convert.contract("111", GAMMA | {"closed": True, "active": False}, "raw")
    assert closed is not None and not closed.tradable and closed.status == "closed"


def test_the_best_bid_is_the_highest_and_the_best_offer_the_lowest() -> None:
    book = {
        "bids": [{"price": "0.41", "size": "1200"}, {"price": "0.43", "size": "550.5"}],
        "asks": [{"price": "0.47", "size": "300"}, {"price": "0.45", "size": "125.25"}],
        "timestamp": "1791633590000",
        "hash": "h",
    }
    top = _top(book)
    assert (str(top.bid), str(top.bid_size), str(top.ask), str(top.ask_size)) == (
        "0.43",
        "550.5",
        "0.45",
        "125.25",
    )
    assert top.stated and top.at_ns == 1_791_633_590_000_000_000 and top.ident == "h"


def test_an_empty_side_is_unset_and_a_level_that_does_not_read_kept_as_sent() -> None:
    top = _top({"bids": [{"price": "x", "size": "1"}, {"price": "0.2", "size": "?"}], "asks": []})
    assert str(top.bid) == "0.2" and top.bid_size is None and top.ask is None
    assert {u.field for u in top.unread} == {"book.bids.price", "book.bids.size"}
    assert top.stated is False and top.at_ns == 7


def test_the_last_trade_is_the_tokens_own_with_no_time() -> None:
    tick = convert.tick(CONTRACT, {"price": "0.440", "side": "BUY"}, "k", 9)
    assert str(tick.price) == "0.440" and not tick.stated and tick.at_ns == 9
    unread = convert.tick(CONTRACT, {"price": "n/a", "side": "SELL"}, "k", 9)
    assert unread.price is None and unread.unread


def test_an_answer_naming_no_side_is_no_trade() -> None:
    never = convert.tick(CONTRACT, {"price": "0.5", "side": ""}, "k", 9)
    assert never.price is None and not never.unread


def test_the_synthetic_exchange_reads_as_the_cases_say() -> None:
    market = venue.market()
    base = market.contract(venue.BASE)
    assert base is not None and str(base.payout) == venue.PAYOUT
    assert str(market.last(base).price) == venue.LAST, "its own, never the book's"
    top = market.top(base)
    assert (str(top.bid), str(top.ask)) == (venue.BID, venue.ASK)
    one = market.contract(venue.ONE_SIDED)
    assert one is not None and market.last(one).price is None, "never traded"
    assert market.contract("123") is None
    assert market.cash.code == "USDC" and not market.cash.currency_code
    assert market.venue_identifiers == (("symbol", "polymarket", "polymarket"),)


# ── Its outcome (contract v23) ──────────────────────────────────────────────


def _resolved(status: str = "resolved", closed: bool = True, prices: str = '["1", "0"]') -> Any:
    return {**GAMMA, "umaResolutionStatus": status, "closed": closed, "outcomePrices": prices}


def test_a_resolved_market_settles_each_token_from_its_own_side() -> None:
    yes, no = (convert.resolution(t, _resolved()) for t in ("111", "222"))
    assert yes is not None and no is not None
    assert (yes.stage, yes.value, yes.scheme, yes.word, yes.text) == (
        "final",
        Decimal("1"),
        "polymarket:outcomePrices",
        "1",
        "Yes 1, No 0",
    )
    assert (no.stage, no.value, no.word) == ("final", Decimal("0"), "0")
    assert yes.determined_at_ns == 0 and yes.settled_at_ns == 0, "Polymarket states neither"


def test_an_unknown_50_50_resolution_settles_each_token_at_half() -> None:
    half = convert.resolution("222", _resolved(prices='["0.5", "0.5"]'))
    assert half is not None and half.value == Decimal("0.5")


def test_a_proposal_or_a_dispute_states_no_answer_so_none() -> None:
    # Gamma's outcomePrices stay the book's while a proposal stands: 0.5 and
    # 0.5 there is no resolution at half.
    for status in ("proposed", "disputed"):
        assert convert.resolution("111", _resolved(status, False, '["0.5", "0.5"]')) is None
    assert convert.resolution("111", _resolved("resolved", False)) is None, "not closed yet"
    assert convert.resolution("111", GAMMA) is None


def test_prices_that_state_no_settlement_are_kept_as_sent() -> None:
    said = convert.resolution("111", _resolved(prices='["0.9995", "0.0005"]'))
    assert said is not None and said.value is None
    assert said.unread[0].field == "market.outcomePrices"


def test_a_token_is_read_with_its_outcome_and_when_its_answer_arrived() -> None:
    market = venue.market()
    resolved = market.contract(venue.RESOLVED)
    assert resolved is not None and resolved.resolution is not None
    assert resolved.read_at_ns == venue.NOW_NS and not resolved.tradable
    active = market.contract(venue.BASE)
    assert active is not None and active.resolution is None
