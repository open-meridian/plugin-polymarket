"""The plugin's data role class (from 0.12.0, open-meridian 0.35): `Lake`,
the SDK's event-contract feed, its source switched by the settings, and
registered on one connection."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from meridian import Settings
from meridian.edge import RawStore
from meridian.roles import data
from meridian.roles.data.testing import Lake as Recorder

from polymarket.__main__ import Lake, contract_map, market
from polymarket.convert import PolymarketMarket
from polymarket.declared import KIND, POLYGON_RPC_URL, SAMPLE_DATA

import venue_cases as v


class Store(RawStore):
    """A raw store whose days are tended as said, nothing moved."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, KIND)
        self.tended: list[tuple[int, str, date]] = []

    async def tend(
        self,
        plugin: Any,
        window_days: int | None = None,
        past: str | None = None,
        today: date | None = None,
        *,
        settings: Any = None,
    ) -> None:
        assert window_days is not None and past is not None and today is not None
        self.tended.append((window_days, past, today))


def _lake(tmp_path: Path) -> tuple[Lake, Store]:
    store = Store(tmp_path)
    chosen = market(store, synthetic=False)
    lake = Lake(chosen, contract_map(store, chosen.session.mode), store=store)
    Recorder(v.VENUE).bind(lake)
    return lake, store


def test_it_is_the_data_roles_class_hearing_what_the_lake_wants() -> None:
    assert issubclass(Lake, data.Role)
    assert Lake.role == "data"
    assert set(Lake.heard_rows()) == {"ObservationsWanted", "WantWithdrawn"}


async def test_the_settings_switch_it_to_sample_data_and_tend_its_store(tmp_path: Path) -> None:
    lake, store = _lake(tmp_path)
    assert lake.market.session.mode == "live"
    await lake.on_settings(Settings(values={SAMPLE_DATA: True, f"{KIND}_window_days": 3}))
    assert lake.market.session.mode == "synthetic"
    assert [(days, past) for days, past, _ in store.tended] == [(3, "kept")]
    await lake.on_settings(Settings(values={SAMPLE_DATA: False}))
    assert lake.market.session.mode == "live"


async def test_the_rpc_url_set_reads_umas_oracle_and_is_never_logged(
    tmp_path: Path, caplog: Any
) -> None:
    lake, _ = _lake(tmp_path)
    assert isinstance(lake.market, PolymarketMarket)
    assert lake.market.chain is None
    secret = "https://polygon.example/v1/a-key"
    with caplog.at_level("INFO"):
        await lake.on_settings(Settings(values={POLYGON_RPC_URL: secret}))
    assert lake.market.chain is not None
    assert secret not in caplog.text
    await lake.on_settings(Settings(values={POLYGON_RPC_URL: ""}))
    assert lake.market.chain is None


async def test_the_venue_is_resolved_through_the_role_not_the_connection(tmp_path: Path) -> None:
    """Registered by `meridian.run`, the class's connection makes no act:
    the venue is resolved through the role object (ruling 1023)."""
    lake, _ = _lake(tmp_path)
    recorder = Recorder(v.VENUE)
    lake._bind(object())  # a connection that makes no act, as the sidecar's
    lake._operate = recorder._operate  # type: ignore[method-assign]
    lake._operations = recorder._operations  # type: ignore[method-assign]
    assert await lake.venue_id()
    assert recorder.on("ResolveVenue")
