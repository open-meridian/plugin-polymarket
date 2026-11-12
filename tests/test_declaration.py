"""The declaration: the catalogue declared from code, as registration and
`meridian plugin upload` read it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from meridian.v1 import sidecar_pb2

from polymarket.declaration import DECLARATION
from polymarket.declared import (
    BARS,
    CATALOGUE,
    OUTCOME_TERMS,
    POLYGON_RPC_URL,
    SAMPLE_DATA,
    TERMS,
)


def test_one_live_dataset_of_prices_and_quotes() -> None:
    [live, _, _] = CATALOGUE
    assert (live.key, live.vendor, live.day_time_zone, live.day_end_minute) == (
        "live",
        "Polymarket",
        "Etc/UTC",
        0,
    )
    assert list(live.data_types) == ["meridian.v1.Price", "meridian.v1.Quote"]
    assert live.venue_id == "", "the venue's ID is resolved at run time, never invented"
    # Contract 30 (ruling 1032): Polymarket's terms in words, no licence; a
    # gap is not fetched again, Polymarket serving no history of its book.
    assert (live.terms_and_pricing, live.gap_recovery) == (TERMS, "stream_only")
    assert live.sessions_calendar_id == "", "Polymarket trades around the clock"


def test_its_outcomes_pushed() -> None:
    # Contract v23: each token's outcome, recorded unasked, kept so that it
    # is read back.
    [_, outcomes, _] = CATALOGUE
    assert (outcomes.key, outcomes.vendor, outcomes.venue_id) == ("outcomes", "Polymarket", "")
    assert list(outcomes.data_types) == ["meridian.v1.Outcome"]
    assert list(outcomes.modes) == [sidecar_pb2.OBSERVATION_MODE_PUSH]
    # Polymarket and UMA state the current stage only; the RPC's terms beside.
    assert (outcomes.terms_and_pricing, outcomes.gap_recovery) == (OUTCOME_TERMS, "stream_only")
    assert "Polygon" in OUTCOME_TERMS and OUTCOME_TERMS.startswith(TERMS)


def test_polymarkets_terms_in_words() -> None:
    # Ruling 1032: what Polymarket's Terms of Use say, within the bound.
    assert 0 < len(OUTCOME_TERMS) <= 2000
    for said in ("no key", "written agreement", "restricted jurisdictions"):
        assert said in TERMS


def test_its_bars_pushed_and_pulled_on_the_utc_day() -> None:
    # 0.11.0 (rulings 624, 625 and 629): the bars dataset, of the lake's bar
    # kind with its trades counted, on the UTC day as the live dataset's.
    [_, _, bars] = CATALOGUE
    assert bars is BARS
    assert (bars.key, bars.vendor, bars.venue_id) == ("bars", "Polymarket", "")
    assert list(bars.data_types) == ["meridian.v1.Bar", "meridian.v1.Bar.trade_count"]
    assert list(bars.modes) == [
        sidecar_pb2.OBSERVATION_MODE_PULL,
        sidecar_pb2.OBSERVATION_MODE_PUSH,
    ]
    assert (bars.day_time_zone, bars.day_end_minute, bars.history) == ("Etc/UTC", 0, 30)
    # The public trades go back in time: a gap is asked again.
    assert (bars.terms_and_pricing, bars.gap_recovery) == (TERMS, "backfill")


def test_no_key_needed_the_rpc_a_secret_and_sample_data_a_developers_setting() -> None:
    # The data role's settings (spec/plugin-pages-follow-their-role): one
    # environment and no credential; from 0.11.0 the Polygon RPC URL, a
    # secret (ruling 629); last sample data, labelled as the SDK's helper
    # labels it.
    assert isinstance(DECLARATION.settings, tuple)
    [rpc, setting] = DECLARATION.settings
    assert (rpc.name, rpc.label, rpc.secret, rpc.required, rpc.developer) == (
        POLYGON_RPC_URL, "Polygon RPC URL", True, False, False,
    )  # fmt: skip
    assert (setting.name, setting.developer, setting.secret) == (SAMPLE_DATA, True, False)
    assert (setting.label, setting.default) == ("Sample data", False)
    assert DECLARATION.storage is not None


def test_upload_reads_the_same_declaration() -> None:
    printed = subprocess.run(
        [str(Path(sys.executable).parent / "meridian-declaration"),
         "polymarket.declaration:DECLARATION"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    datasets = json.loads(printed.stdout)["catalogue"]["datasets"]
    assert [d["key"] for d in datasets] == ["live", "outcomes", "bars"]
    assert [d["modes"] for d in datasets] == [["pull", "stream"], ["push"], ["pull", "push"]]
