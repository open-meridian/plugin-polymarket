"""The events of the contracts served, reported (contract v26, W3.29): each
read once first served, reported as Polymarket's negative risk states it,
reported again only where Polymarket states it otherwise, and held back
while a member does not resolve -- through the SDK's `Feed.report_event`,
on Polymarket's synthetic exchange."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data import event_contracts
from meridian.roles.data.testing import Lake, held

from polymarket.__main__ import EVENTS_EVERY, Events

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


async def test_the_event_of_a_contract_served_is_reported_as_polymarket_states_it() -> None:
    lake = Lake(venue.VENUE)
    feed = await _serving(lake)
    assert await Events().now(feed) == 1
    [report] = _reports(lake)
    assert report.venue_event_ref == venue.FINAL and len(report.member_instrument_ids) == 3
    assert report.mutually_exclusive == ops.EVENT_GROUP_FLAG_TRUE
    assert report.exhaustive == ops.EVENT_GROUP_FLAG_TRUE
    assert report.raw_record.key


async def test_an_event_unchanged_is_not_reported_again_and_one_changed_is() -> None:
    lake, clock = Lake(venue.VENUE), Clock()
    feed = await _serving(lake)
    events = Events(clock)
    assert await events.now(feed) == 1
    assert await events.now(feed) == 0, "read again only after EVENTS_EVERY"
    clock.now += EVENTS_EVERY
    assert await events.now(feed) == 0, "read again, unchanged: nothing sent"
    market: Any = feed.market
    stated = market.event(venue.FINAL_CONDITION)
    market.event = lambda ref: replace(stated, exhaustive=None)
    clock.now += EVENTS_EVERY
    assert await events.now(feed) == 1 and len(_reports(lake)) == 2


async def test_an_event_a_member_of_which_does_not_resolve_is_held_back() -> None:
    lake = Lake(venue.VENUE)
    feed = _feed(lake)
    subject = await held(lake.instruments, feed, venue.BASE)
    await feed.name([subject])
    lake.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND),
    )
    events = Events()
    assert await events.now(feed) == 0 and not _reports(lake)
    assert venue.FINAL_CONDITION not in events.read_at, "read again on the next pass"
