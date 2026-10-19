"""Polymarket's public market data as an Open Meridian data plugin.

It connects to the sidecar it is launched beside, declaring its catalogue,
its storage and its settings (declaration.py) and its pages (page.py), and
serves them. Then it hears what the lake wants of it, names each subject as
one of Polymarket's outcome tokens and records it, and keeps each standing
want current -- the SDK's work for an event-contract venue
(`meridian.roles.data.event_contracts.Feed`, over Polymarket's conversion in
convert.py) -- until stopped. Everything goes through the sidecar; nothing
but Polymarket's public reads are called, and with sample data not even that
(synthetic.py). Nothing is asked of Polymarket until the lake wants
something of it, and then only the contracts wanted.

From 0.8.0 (contract v26, W3.29) it reports, for each contract it serves,
the event Polymarket groups it in: its markets' YES tokens, and whether
Polymarket's negative risk states them mutually exclusive and exhaustive,
each event when first read and again whenever Polymarket states it
otherwise, so the platform matches or mints the group and keeps a new
version when its members or flags change.

It holds nothing it cannot lose: Polymarket's raw responses and the contract map
are kept in the storage the deployment grants it (decisions/028), and a
restart reads the map back and hears again what the lake wants.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import meridian
from meridian.edge import RawStore, storage_root
from meridian.roles.data import cancelled
from meridian.roles.data.event_contracts import ContractMap, Event, Feed

from .convert import PolymarketMarket
from .declaration import DECLARATION, PORT
from .declared import KIND, SAMPLE_DATA, WINDOW_DAYS
from .page import figures_now, hold, pages
from .synthetic import Recorded, Synthetic
from .venue import Polymarket

log = logging.getLogger("polymarket")

#: Where a developer's recorded exchanges are replayed from, under the
#: plugin's storage, when `make e2e-recorded` mounts them there.
RECORDED = "recorded"


def market(store: RawStore, synthetic: bool) -> PolymarketMarket:
    """Polymarket itself, or with sample data its answers from files: a
    developer's recorded exchanges where storage holds them, else this
    package's synthetic ones."""
    if not synthetic:
        return PolymarketMarket(Polymarket(store), "live")
    recorded = store.root / RECORDED
    if recorded.is_dir():
        return PolymarketMarket(Polymarket(store, transport=Recorded(recorded)), "recorded")
    return PolymarketMarket(Polymarket(store, transport=Synthetic()), "synthetic")


def contract_map(store: RawStore, mode: str) -> ContractMap:
    held = ContractMap(store.root / f"contracts-{mode}.json")
    held.load()
    return held


async def watch_settings(
    plugin: meridian.Plugin, feed: Feed, store: RawStore, configured: asyncio.Event
) -> None:
    """Each delivery of the settings: the source switched where synthetic
    mode changed, its own contract map read back from storage, and each day's
    raw responses past their window moved. Whatever it answers from, nothing
    is asked of the venue, and nothing resolved, until the lake wants
    something of it."""
    while True:
        try:
            await _apply_settings(plugin, feed, store, configured)
        except Exception as failed:  # noqa: BLE001 - the stream broke: said, and watched again
            log.warning("the settings' stream broke, watching again: %s", failed)
        await asyncio.sleep(2)


async def _apply_settings(
    plugin: meridian.Plugin, feed: Feed, store: RawStore, configured: asyncio.Event
) -> None:
    async for delivered in plugin.settings():
        values = delivered.values
        log.info("settings delivered: sample data %s", values.get(SAMPLE_DATA))
        synthetic = values.get(SAMPLE_DATA) is True
        mode = feed.market.session.mode
        if synthetic != (mode != "live"):
            chosen = market(store, synthetic)
            feed.use(chosen, contract_map(store, chosen.session.mode))
            log.info("answering from %s", chosen.session.mode)
        configured.set()
        await tend_now(plugin, store, values)


async def tend_now(plugin: meridian.Plugin, store: RawStore, values: Mapping[str, object]) -> None:
    window = values.get(f"{KIND}_window_days")
    past = values.get(f"{KIND}_past_window")
    await store.tend(
        plugin,
        window if isinstance(window, int) else WINDOW_DAYS,
        past if isinstance(past, str) else "kept",
        datetime.now(UTC).date(),
    )


async def hear_wants(plugin: meridian.Plugin, feed: Feed, configured: asyncio.Event) -> None:
    """What the lake wants, once the settings have said where to answer from."""
    await configured.wait()
    await plugin.receive(observations_wanted=feed.on_want, want_withdrawn=feed.on_withdrawn)


#: How soon an event first served is read, and how often each is read again,
#: in seconds.
EVENTS_FIRST, EVENTS_EVERY = 15.0, 600.0


def _stated(event: Event) -> tuple[object, ...]:
    """What Polymarket states of an event that a new version would change."""
    return (event.members, event.mutually_exclusive, event.exhaustive, event.series, event.title)


class Events:
    """The events of the contracts served, each read once it is first served
    and again every `EVENTS_EVERY` seconds, and reported where it is new or
    Polymarket states it otherwise than as last reported. An event a member of
    which does not resolve is held back (the SDK's `Feed.report_event`) and
    read again on the next pass."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        #: When each contract's event reference was last read.
        self.read_at: dict[str, float] = {}
        #: What was last reported of each event, by its reference.
        self.reported: dict[str, tuple[object, ...]] = {}

    async def now(self, feed: Feed) -> int:
        """One pass; how many events were reported."""
        sent = 0
        refs = {m.contract.market for m in feed.contracts.mapped() if m.contract.market}
        for ref in sorted(refs):
            at = self.read_at.get(ref)
            if at is not None and self.clock() - at < EVENTS_EVERY:
                continue
            self.read_at[ref] = self.clock()
            event = await asyncio.to_thread(feed.market.event, ref)  # type: ignore[attr-defined]
            if event is None or self.reported.get(event.ref) == _stated(event):
                continue
            if await feed.report_event(event) is None:
                del self.read_at[ref]  # held back: read again on the next pass
                continue
            self.reported[event.ref] = _stated(event)
            sent += 1
        return sent


async def report_events(feed: Feed, configured: asyncio.Event) -> None:
    """Once the settings have said where to answer from: the events of the
    contracts served, reported as Polymarket states them."""
    await configured.wait()
    events = Events()
    while True:
        try:
            await events.now(feed)
        except Exception as failed:  # noqa: BLE001 - said, and read again on the next pass
            log.warning("events not reported: %s", failed)
        await asyncio.sleep(EVENTS_FIRST)


async def report_health(plugin: meridian.Plugin, feed: Feed) -> None:
    """Each minute: its datasets' licences read again (contract v20), and
    on the heartbeat whether Polymarket answers, with the data role's figures."""
    while True:
        try:
            await feed.read_licences()
        except meridian.MeridianError as failed:
            log.warning("licences not read: %s", failed)
        health = feed.market.session.health
        healthy = health.last_ok_ns >= health.last_failed_ns
        detail = f"{feed.market.name} answers" if healthy else health.last_error
        try:
            await plugin.report(healthy=healthy, detail=detail[:200], figures=figures_now())
        except (meridian.MeridianError, ValueError) as failed:
            log.warning("health not reported: %s", failed)
        await asyncio.sleep(60)


def _said(task: asyncio.Task[None]) -> None:
    """A task that stopped, said with why, and the plugin stopped with it: a
    restart starts it again."""
    if not task.cancelled() and task.exception() is not None:
        log.error("stopped: %r", task.exception(), exc_info=task.exception())
        os._exit(1)


async def run() -> None:
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop, stopped.set)

    port = PORT
    # The version's whole declaration (declaration.py): its settings, its
    # pages with the levels each serves and their tools, and its documentation.
    # A version registers exactly what it was uploaded with (contract v25).
    async with await meridian.connect(declaration=DECLARATION) as plugin:
        log.info("registered as %s, roles %s", plugin.identity.instance_id, plugin.identity.roles)
        store = RawStore(storage_root(), KIND)
        chosen = market(store, synthetic=False)
        feed = Feed(plugin, chosen, contract_map(store, chosen.session.mode))
        hold(feed)
        served = pages.serve(plugin, port)
        configured = asyncio.Event()
        tasks = [
            asyncio.create_task(watch_settings(plugin, feed, store, configured)),
            asyncio.create_task(hear_wants(plugin, feed, configured)),
            asyncio.create_task(feed.keep_current()),
            asyncio.create_task(report_health(plugin, feed)),
            asyncio.create_task(report_events(feed, configured)),
        ]
        for task in tasks:
            task.add_done_callback(_said)
        await stopped.wait()
        log.info("stopping")
        for task in tasks:
            await cancelled(task)
        served.shutdown()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
