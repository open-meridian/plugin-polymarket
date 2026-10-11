"""The declaration: the catalogue declared from code, as registration and
`meridian plugin upload` read it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from polymarket.declaration import CATALOGUE, DECLARATION, SAMPLE_DATA


def test_one_live_dataset_of_prices_and_quotes_kept_two_days() -> None:
    [live] = CATALOGUE
    assert (live.key, live.vendor, live.day_time_zone, live.day_end_minute) == (
        "live",
        "Polymarket",
        "Etc/UTC",
        0,
    )
    assert list(live.data_types) == ["meridian.v1.Price", "meridian.v1.Quote"]
    assert live.venue_id == "", "the venue's ID is resolved at run time, never invented"
    licence = live.licence_default
    assert licence is not None and licence.kept and licence.retention_days == 2
    assert not (licence.display or licence.derived_use or licence.personal_use), (
        "a default claiming nothing: the deployment's licence replaces it"
    )


def test_no_key_needed_and_sample_data_a_developers_setting() -> None:
    # The data role's settings (spec/plugin-pages-follow-their-role): one
    # environment and no credential, so sample data alone, labelled as the
    # SDK's helper labels it.
    assert isinstance(DECLARATION.settings, tuple)
    [setting] = DECLARATION.settings
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
    assert [d["key"] for d in datasets] == ["live"]
    assert [d["modes"] for d in datasets] == [["pull", "stream"]]
