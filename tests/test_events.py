"""The events of the contracts served, reported (contract v26, W3.29): each
read once first served, reported as Polymarket's negative risk states it,
reported again only where Polymarket states it otherwise, and held back
while a member does not resolve -- the SDK's `Feed.keep_events` (0.32.0)
over Polymarket's conversion, on Polymarket's synthetic exchange. Gamma
states no range market's bounds, so its reports carry none (contract v27,
ruling 464)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data import event_contracts
from meridian.roles.data.event_contracts import EVENTS_EVERY_SECONDS
from meridian.roles.data.testing import Lake, held

import venue_cases as venue


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _feed(lake: Lake) -> event_contracts.Feed:
    return event_contracts.Feed(
        lake, venue.market(), event_contracts.ContractMap(), clock_ns=lambda: venue.NOW_NS
    )


async def _serving(lake: Lake) -> event_contracts.Feed:
    feed = _feed(lake)
    subject = await held(lake.instruments, feed, venue.BASE)
    await feed.name([subject])
    for member in venue.EVENT.members:
        await held(lake.instruments, feed, member)
    return feed


def _reports(lake: Lake) -> list[Any]:
    return list(lake.on("ReportEventGroup"))


async def _pass(feed: event_contracts.Feed, clock: Clock | None = None) -> int:
    return await feed.keep_events(once=True, clock=clock or Clock())


async def test_the_event_of_a_contract_served_is_reported_as_polymarket_states_it() -> None:
    lake = Lake(venue.VENUE)
    feed = await _serving(lake)
    assert await _pass(feed) == 1
    [report] = _reports(lake)
    assert report.venue_event_ref == venue.FINAL and len(report.member_instrument_ids) == 3
    assert report.mutually_exclusive == ops.EVENT_GROUP_FLAG_TRUE
    assert report.exhaustive == ops.EVENT_GROUP_FLAG_TRUE
    assert report.raw_record.key
    assert not report.member_bounds, "Gamma states no range market's bounds"


async def test_an_event_unchanged_is_not_reported_again_and_one_changed_is() -> None:
    lake, clock = Lake(venue.VENUE), Clock()
    feed = await _serving(lake)
    assert await _pass(feed, clock) == 1
    assert await _pass(feed, clock) == 0, "read again only after EVENTS_EVERY_SECONDS"
    clock.now += EVENTS_EVERY_SECONDS
    assert await _pass(feed, clock) == 0, "read again, unchanged: nothing sent"
    market: Any = feed.market
    stated = market.event(venue.FINAL_CONDITION)
    market.event = lambda ref: replace(stated, exhaustive=None)
    clock.now += EVENTS_EVERY_SECONDS
    assert await _pass(feed, clock) == 1 and len(_reports(lake)) == 2


async def test_an_event_a_member_of_which_does_not_resolve_is_held_back() -> None:
    lake, clock = Lake(venue.VENUE), Clock()
    feed = _feed(lake)
    subject = await held(lake.instruments, feed, venue.BASE)
    await feed.name([subject])
    lake.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND),
    )
    assert await _pass(feed, clock) == 0 and not _reports(lake)
    lake.instruments.answering(lake)
    for member in venue.EVENT.members:
        await held(lake.instruments, feed, member)
    assert await _pass(feed, clock) == 1, "read again on the next pass, not ten minutes on"
