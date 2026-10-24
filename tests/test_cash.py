"""The cash is pUSD from 0.9.0 (ruling 550): a contract map kept by 0.8.0,
its cash resolved for `USDC` by its code alone, has it resolved again, and
one resolved for pUSD keeps it."""

from __future__ import annotations

from pathlib import Path

from meridian.edge import RawStore

from polymarket.__main__ import contract_map


def _store(root: Path) -> RawStore:
    return RawStore(root, "responses")


def test_a_cash_resolved_by_0_8_0_is_resolved_again(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old = contract_map(store, "live")
    (store.root / "cash-live.txt").unlink()  # as 0.8.0 kept it: no marker
    old.cash_id, old.subjects = "LCL-usdc", {"INS-T": "71"}
    old.save()
    held = contract_map(store, "live")
    assert held.cash_id == "" and held.subjects == {"INS-T": "71"}, "only the cash is dropped"
    held.cash_id = "INS-PUSD"
    held.save()
    assert contract_map(store, "live").cash_id == "INS-PUSD", "pUSD's kept once resolved"
