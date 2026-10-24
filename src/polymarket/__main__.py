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
version when its members or flags change. From 0.9.0 (contract v27) that is
the SDK's `Feed.keep_events`.

It holds nothing it cannot lose: Polymarket's raw responses and the contract map
are kept in the storage the deployment grants it (decisions/028), and a
restart reads the map back and hears again what the lake wants.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import Mapping
from datetime import UTC, datetime

import meridian
from meridian.edge import RawStore, storage_root
from meridian.roles.data import cancelled
from meridian.roles.data.event_contracts import ContractMap, Feed

from .convert import CASH, PolymarketMarket
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
    """The contract map kept in storage for `mode`, its cash resolved again
    where it was resolved for another cash than this version's: 0.8.0's
    `USDC`, known by its code alone, before pUSD by its CAIP-19 (0.9.0,
    ruling 550). The SDK's map keeps the cash's ID and never asks again, so
    an upgraded plugin would otherwise go on pricing in the old record."""
    held = ContractMap(store.root / f"contracts-{mode}.json")
    held.load()
    resolved_for = store.root / f"cash-{mode}.txt"
    cash = f"{CASH.scheme}:{CASH.value}"
    said = resolved_for.read_text(encoding="utf-8") if resolved_for.is_file() else ""
    if held.cash_id and said != cash:
        log.info("the cash was resolved for %s: resolved again as %s", said or "USDC", cash)
        held.cash_id = ""
        held.save()
    resolved_for.parent.mkdir(parents=True, exist_ok=True)
    resolved_for.write_text(cash, encoding="utf-8")
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


async def report_events(feed: Feed, configured: asyncio.Event) -> None:
    """Once the settings have said where to answer from: the events of the
    contracts served, reported as Polymarket states them -- the SDK's
    `Feed.keep_events` (open-meridian 0.32.0), each event read once its
    first contract is served and every ten minutes after, reported where it
    is new or Polymarket states it otherwise, and one held back while a member
    does not resolve read again on the next pass."""
    await configured.wait()
    await feed.keep_events()


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
