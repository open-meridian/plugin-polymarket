"""The plugin's pages, under Manage: its Connection and its Datasets.

The same module in meridian-kalshi and meridian-polymarket, the venue's
names read from convert.py.

A `dgm` shows no market data (ruled 2026-10-03: "The data unit only cares for
connectivity and data subscriptions and entitlement resolution"): no price,
bid, offer or size is on either page; viewing prices is for the reading
roles.

- **Connection** (`/`, `read_connection`): where the plugin answers from
  (the venue, or synthetic mode), how the venue has answered -- its calls,
  rate limits met, failures and the last error -- what the venue allows and
  what the plugin spends of it, and the venue master's ID it resolved.
- **Datasets** (`/datasets`, `read_datasets`): what it serves -- each
  dataset of its catalogue, its data types, modes, cadence, declared day and
  default terms -- the contract map (contracts read, those serving the
  subjects the lake asked for, subjects not served and why, the cash its
  prices and payouts are in and the record it resolved to, what not
  resolved), what the venue entitles it to (public market data, no key: a
  contract read only for a subject asked for), the standing wants it keeps
  current, and the wants it heard, each with what it recorded and declined.
  The wants grow, so the kit's search (`om-pager search`, kit 0.11.0)
  narrows the rows drawn, and `?q=` the rows the page draws without it
  (matching every word); the tool answers them all.

Each page declares the typed record it renders (`answers=`), so each is also
a read tool on the deployment's MCP surface answering the same record
(requirement 23: a page's tool answers what the page shows). Both fit one
screen at 1440x900 and 390x844: one-line rows, and the wants paged by the
kit's `om-pager`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import meridian
from meridian.v1 import sidecar_pb2

from .convert import NAME
from .declaration import CATALOGUE
from .dgm import PAYOUT_DIFFERS, Dgm

TITLE = NAME
ENTITLEMENT = (
    f"Public market data: no key, so nothing to resolve at {NAME}; "
    "a contract is read only for a subject the lake asked for"
)
#: The kit the pages are built against: 0.11.0's search above the pager.
KIT = "0.11.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)
#: The longest search the Datasets page reads.
MOST_QUERY = 100


class _Held:
    dgm: Dgm | None = None


HELD = _Held()


def hold(dgm: Dgm) -> None:
    """The work the pages show."""
    HELD.dgm = dgm


def _when(at_ns: int) -> datetime | None:
    return datetime.fromtimestamp(at_ns / 1e9, tz=UTC).replace(microsecond=0) if at_ns else None


# ── Connection ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EndpointRow:
    name: str
    address: str
    what: str


@dataclass(frozen=True)
class Connection:
    """How the plugin reaches the venue, and how the venue has answered."""

    venue: str
    mode: str
    healthy: bool
    endpoints: list[EndpointRow] = field(default_factory=list)
    allowed: str = ""
    spent: str = ""
    calls: int = 0
    rate_limited: int = 0
    failures: int = 0
    last_answer_at: datetime | None = None
    last_error: str = ""
    venue_id: str = ""
    venue_held: bool = False


def connection_now() -> Connection:
    dgm = HELD.dgm
    if dgm is None:
        return Connection(venue=TITLE, mode="starting", healthy=False)
    session = dgm.market.session
    health = session.health
    healthy = health.last_ok_ns >= health.last_failed_ns and (
        health.last_ok_ns > 0 or health.calls == 0
    )
    return Connection(
        venue=dgm.market.name,
        mode=session.mode,
        healthy=healthy,
        endpoints=[EndpointRow(e.name, e.address, e.what) for e in session.endpoints],
        allowed=session.limits.allowed,
        spent=session.limits.spent,
        calls=health.calls,
        rate_limited=health.rate_limited,
        failures=health.failures,
        last_answer_at=_when(health.last_ok_ns),
        last_error=health.last_error,
        venue_id=dgm.venue.venue_id,
        venue_held=dgm.venue.asked and not dgm.venue.missing,
    )


@pages.page("/", "Connection", levels="admin", answers=Connection, name="read_connection")
def connection(request: meridian.Request) -> meridian.Response:
    """How the plugin reaches the venue: the mode, the endpoint, the venue's
    limits and what the plugin spends of them, its calls, rate limits met and
    failures, the last error, and the venue master's ID it resolved."""
    return pages.answer("connection.html", connection_now())


# ── Datasets ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DatasetRow:
    dataset: str
    data_types: str
    modes: str
    cadence_seconds: int
    day: str
    terms: str


@dataclass(frozen=True)
class WantRow:
    want_id: str
    dataset: str
    asked: str
    subjects: int
    recorded: int
    declined: int
    standing: bool
    kept_current: bool
    heard_at: datetime | None = None
    state: str = ""


@dataclass(frozen=True)
class NotServed:
    why: str
    subjects: int


@dataclass(frozen=True)
class Datasets:
    """What the plugin serves the lake, and what the lake asked of it."""

    datasets: list[DatasetRow] = field(default_factory=list)
    entitled_at_vendor: str = ENTITLEMENT
    contracts_read: int = 0
    contracts_mapped: int = 0
    subjects_named: int = 0
    not_served: list[NotServed] = field(default_factory=list)
    payouts_differ: int = 0
    cash: str = ""
    cash_instrument: str = ""
    payouts: list[str] = field(default_factory=list)
    reads_instruments: bool = True
    assets_not_resolved: list[str] = field(default_factory=list)
    contracts_read_at: datetime | None = None
    standing_wants: int = 0
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0
    declined: int = 0
    not_read: int = 0
    wants: list[WantRow] = field(default_factory=list)


def _terms(licence: meridian.DatasetLicence | None) -> str:
    if licence is None:
        return ""
    said = ["kept" if licence.kept else "served, not kept"]
    if licence.retention_days:
        said.append(f"{licence.retention_days} days")
    said.append("display" if licence.display else "no display")
    if licence.personal_use:
        said.append("one person's")
    return ", ".join(said)


def datasets_now() -> Datasets:
    dgm = HELD.dgm
    instance = dgm.plugin.identity.instance_id if dgm else NAME.lower()
    rows = [
        DatasetRow(
            dataset=f"{instance}:{d.key}",
            data_types=", ".join(t.removeprefix("meridian.v1.") for t in d.data_types),
            modes=", ".join(_mode(m) for m in d.modes),
            cadence_seconds=d.cadence,
            day=f"{d.day_time_zone}, ends {d.day_end_minute // 60:02d}:{d.day_end_minute % 60:02d}",
            terms=_terms(d.licence_default),
        )
        for d in CATALOGUE
    ]
    if dgm is None:
        return Datasets(datasets=rows)
    standing = set(dgm.standing)
    wants = [
        WantRow(w.want_id, w.dataset, w.asked, w.subjects, w.recorded, w.declined, w.standing,
                w.want_id in standing, _when(w.at_ns), _state(w.want_id in standing, w.standing))
        for w in dgm.heard
    ]  # fmt: skip
    wants.sort(key=lambda w: (not w.kept_current,))
    reasons: dict[str, int] = {}
    for why in dgm.unnamed.values():
        reasons[why] = reasons.get(why, 0) + 1
    mapped = dgm.contracts.mapped()
    cash = dgm.market.cash
    payouts = sorted(
        {f"{m.contract.payout} {cash.code}" for m in mapped if m.contract.payout is not None}
    )
    return Datasets(
        datasets=rows,
        contracts_read=len(dgm.contracts.contracts),
        contracts_mapped=len(mapped),
        subjects_named=len(dgm.contracts.subjects),
        not_served=[NotServed(why, n) for why, n in sorted(reasons.items())],
        payouts_differ=reasons.get(PAYOUT_DIFFERS, 0),
        cash=cash.code,
        cash_instrument=dgm.contracts.cash_id,
        payouts=payouts,
        reads_instruments=dgm.reads_instruments,
        assets_not_resolved=sorted(dgm.contracts.missing),
        contracts_read_at=_when(dgm.contracts.read_at_ns),
        standing_wants=len(standing),
        recorded=dgm.counts.recorded,
        restated=dgm.counts.restated,
        unchanged=dgm.counts.unchanged,
        declined=dgm.counts.declined,
        not_read=dgm.counts.unread,
        wants=wants,
    )


def _state(kept_current: bool, standing: bool) -> str:
    return "Kept current" if kept_current else "Withdrawn" if standing else "Answered"


def matching(query: str, *texts: str) -> bool:
    """Whether every word of a search is in one of `texts`, case aside."""
    held = " ".join(texts).lower()
    return all(word in held for word in query.lower().split())


def _mode(mode: object) -> str:
    if isinstance(mode, int):
        named = str(sidecar_pb2.ObservationMode.Name(mode))
        return named.removeprefix("OBSERVATION_MODE_").lower()
    return str(mode)


@pages.page("/datasets", "Datasets", levels="admin", answers=Datasets, name="read_datasets")
def datasets(request: meridian.Request) -> meridian.Response:
    """What the plugin serves the lake: each dataset of its catalogue, the
    contract map and the cash its prices and payouts are in, what the venue
    entitles it to, the standing wants it keeps current, and the wants it
    heard with what each recorded and declined."""
    data = datasets_now()
    # A browser's search narrows the wants drawn; the tool answers them all.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    shown = [w for w in data.wants if matching(query, w.want_id, w.dataset, w.asked, w.state)]
    return pages.answer("datasets.html", data, now=time.time(), query=query, shown=shown)
