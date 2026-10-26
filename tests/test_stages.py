"""A proposal's and a dispute's stage, read from UMA's oracle on Polygon
through the deployment's RPC (uma.py; from 0.11.0, ruling 622): the answer
proposed, its time and the challenge window's end; nothing read on chain
without the setting, or for a market Gamma states neither stage of; the
RPC's URL never kept."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from meridian.edge import RawStore
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data import Health
from meridian.roles.data.event_contracts import DISPUTED, PROPOSED, ContractMap, Feed
from meridian.roles.data.testing import Lake
from meridian.testing import PageClient

from polymarket import page
from polymarket.convert import PolymarketMarket, staged
from polymarket.synthetic import Synthetic, SyntheticChain
from polymarket.uma import ONE, ChainError, Proposal, Uma, payouts, question_of
from polymarket.venue import Polymarket, RateLimiter, Response

import venue_cases as v

ADAPTER = "0x" + "ad" * 20
QUESTION = "0x" + "71" * 32


def _at(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp()) * 10**9


def _body(status: str) -> dict[str, object]:
    return {
        "clobTokenIds": json.dumps(["T-YES", "T-NO"]),
        "outcomes": json.dumps(["Yes", "No"]),
        "umaResolutionStatus": status,
    }


def _proposal(price: int, disputer: str = "0x" + "00" * 20) -> Proposal:
    return Proposal("0x" + "5e" * 20, disputer, price, 1_791_637_200, 7_200, "rpc/key")


def test_a_proposal_states_each_tokens_answer_its_time_and_window() -> None:
    yes = staged("T-YES", _body("proposed"), _proposal(ONE))
    no = staged("T-NO", _body("proposed"), _proposal(ONE))
    assert yes is not None and no is not None
    assert (yes.stage, yes.value, no.value) == (PROPOSED, Decimal(1), Decimal(0))
    assert (yes.scheme, yes.word) == ("uma:proposedPrice", "1000000000000000000")
    assert yes.text == "proposed: Yes 1, No 0"
    assert yes.determined_at_ns == _at("2026-10-10T11:00:00")
    assert yes.challenge_ends_at_ns == _at("2026-10-10T13:00:00")
    half = staged("T-NO", _body("proposed"), _proposal(ONE // 2))
    assert half is not None and half.value == Decimal("0.5")


def test_a_dispute_states_the_price_disputed_and_no_window() -> None:
    said = staged("T-YES", _body("disputed"), _proposal(0, disputer="0x" + "d1" * 20))
    assert said is not None
    assert (said.stage, said.value, said.challenge_ends_at_ns) == (DISPUTED, Decimal(0), 0)


def test_a_dispute_sent_again_with_nothing_proposed_states_no_answer() -> None:
    # The adapter's reset: a new request, no proposal on it yet. The stage
    # stands with the answer recorded last; a proposal Gamma states with none
    # on chain records nothing.
    empty = Proposal("0x" + "00" * 20, "0x" + "00" * 20, 0, 0, 7_200, "rpc/key")
    said = staged("T-YES", _body("disputed"), empty)
    assert said is not None and (said.stage, said.value) == (DISPUTED, None)
    assert staged("T-YES", _body("proposed"), empty) is None


def test_the_too_early_price_is_no_answer() -> None:
    said = staged("T-YES", _body("proposed"), _proposal(-(2**255)))
    assert said is not None and said.value is None
    assert [u.field for u in said.unread] == ["uma.proposedPrice"]
    assert payouts(ONE, 3) is None, "a market of three outcomes is not the adapter's"


def test_a_stage_gamma_does_not_state_reads_nothing_on_chain() -> None:
    assert staged("T-YES", _body(""), _proposal(ONE)) is None
    assert staged("T-YES", _body("resolved"), _proposal(ONE)) is None


def test_the_question_is_a_negative_risk_markets_request() -> None:
    body = {"resolvedBy": ADAPTER, "questionID": QUESTION, "negRisk": False}
    assert question_of(body) == (ADAPTER, QUESTION)
    other = "0x" + "88" * 32
    assert question_of({**body, "negRisk": True, "negRiskRequestID": other}) == (ADAPTER, other)
    assert question_of({**body, "resolvedBy": "not an address"}) is None


class _Posted:
    """The chain's synthetic answers, each request kept."""

    def __init__(self) -> None:
        self.chain = SyntheticChain(v.SYNTHETIC)
        self.sent: list[tuple[str, Mapping[str, str], bytes]] = []

    def __call__(self, url: str, headers: Mapping[str, str], body: bytes) -> Response:
        self.sent.append((url, headers, body))
        return self.chain(url, headers, body)


def _uma(tmp_path: Path, post: object) -> Uma:
    return Uma(
        "https://rpc.example.invalid/v1/SECRET-KEY",
        RawStore(tmp_path),
        Health(),
        post=post,  # type: ignore[arg-type]
        limiter=RateLimiter(1000.0, 1000, sleep=lambda _: None),
        clock_ns=lambda: v.NOW_NS,
    )


def test_read_only_calls_and_the_urls_secret_never_kept(tmp_path: Path) -> None:
    posted = _Posted()
    chain = _uma(tmp_path, posted)
    said = chain.proposal(ADAPTER, QUESTION)
    assert said is not None and said.proposed and not said.disputed
    assert (said.price, said.expires_at, said.liveness) == (ONE, 1_791_637_200, 7_200)
    methods = [json.loads(body)["method"] for _, _, body in posted.sent]
    assert methods == ["eth_call"] * 4, "getQuestion, optimisticOracle, getRequest, liveness"
    assert all("Authorization" not in headers for _, headers, _ in posted.sent)
    assert chain.proposal(ADAPTER, QUESTION) is not None
    assert len(posted.sent) == 6, "the oracle and its default liveness read once"
    kept = [p.read_text() for p in tmp_path.rglob("*.json")]
    assert kept and not any("SECRET-KEY" in text or "example.invalid" in text for text in kept)


def test_an_rpc_error_is_said_without_its_url(tmp_path: Path) -> None:
    def refused(url: str, headers: Mapping[str, str], body: bytes) -> Response:
        raise OSError(f"cannot reach {url}")

    chain = _uma(tmp_path, refused)
    with pytest.raises(ChainError) as failed:
        chain.proposal(ADAPTER, QUESTION)
    assert "SECRET" not in str(failed.value) and "SECRET" not in chain.health.last_error
    assert chain.health.failures == 1

    def errs(url: str, headers: Mapping[str, str], body: bytes) -> Response:
        return Response(200, {}, b'{"jsonrpc":"2.0","id":1,"error":{"code":-32000}}')

    with pytest.raises(ChainError):
        _uma(tmp_path, errs).proposal(ADAPTER, QUESTION)


def _market(tmp_path: Path, chain: bool, directory: Path = v.SYNTHETIC) -> PolymarketMarket:
    client = Polymarket(
        RawStore(tmp_path),
        transport=Synthetic(directory),
        limiter=RateLimiter(1000.0, 1000, sleep=lambda _: None),
        clock_ns=lambda: v.NOW_NS,
        sleep=lambda _: None,
    )
    uma = Uma("synthetic", client.store, client.health, post=SyntheticChain(directory),
              clock_ns=lambda: v.NOW_NS) if chain else None  # fmt: skip
    return PolymarketMarket(client, "synthetic", uma)


def test_without_the_setting_a_proposal_records_nothing_as_before(tmp_path: Path) -> None:
    market = _market(tmp_path, chain=False)
    read = market.contract(v.PROPOSED)
    assert read is not None and read.resolution is None
    assert market.session.health.calls == 1, "Gamma alone: nothing read on chain"
    [*_, rpc] = market.session.endpoints
    assert rpc.name == "Polygon RPC" and rpc.address.startswith("not set")


async def test_proposed_then_disputed_each_a_version_of_one_outcome(tmp_path: Path) -> None:
    lake = Lake(v.VENUE)
    feed = Feed(lake, _market(tmp_path, chain=True), ContractMap(), clock_ns=lambda: v.NOW_NS)
    subject = await lake.held(feed, v.PROPOSED)
    await feed.name([subject])
    assert await feed.record_outcomes([feed.contracts.serving(subject)]) == 1
    [proposed] = lake.rows("RecordOutcomes")
    assert ops.OutcomeStage.Name(proposed.stage) == "OUTCOME_STAGE_PROPOSED"
    assert ops.OutcomeDetermination.Name(proposed.determination) == "OUTCOME_DETERMINATION_PAYS"
    assert proposed.meta.valid_from_ns == _at("2026-10-10T11:00:00"), "the proposal's time"
    assert proposed.challenge_ends_at_ns == _at("2026-10-10T13:00:00")
    assert proposed.determination_as_reported.scheme == "uma:proposedPrice"
    feed.market = _market(tmp_path / "later", chain=True, directory=v.EXCHANGES / "disputed")
    assert await feed.watch_outcomes() == 1
    disputed = lake.rows("RecordOutcomes")[-1]
    assert ops.OutcomeStage.Name(disputed.stage) == "OUTCOME_STAGE_DISPUTED"
    assert disputed.meta.row_key == proposed.meta.row_key
    assert disputed.meta.valid_from_ns == proposed.meta.valid_from_ns
    assert disputed.challenge_ends_at_ns == 0, "a second dispute goes to UMA's vote"
    assert await feed.watch_outcomes() == 0, "stated again unchanged: nothing sent"


def test_connection_says_whether_the_rpc_is_set_and_never_its_url(tmp_path: Path) -> None:
    market = _market(tmp_path, chain=False)
    page.hold(Feed(Lake(v.VENUE), market, ContractMap(), clock_ns=lambda: v.NOW_NS))
    try:
        client = PageClient(page.pages)
        assert "Polygon RPC URL" not in client.get("/", "admin").text, "sample data calls nothing"
        live = PolymarketMarket(market.client, "live")
        page.hold(Feed(Lake(v.VENUE), live, ContractMap(), clock_ns=lambda: v.NOW_NS))
        assert "Not set: outcomes are recorded final only" in client.get("/", "admin").text
        live.read_on_chain(_uma(tmp_path, _Posted()))
        page.hold(Feed(Lake(v.VENUE), live, ContractMap(), clock_ns=lambda: v.NOW_NS))
        shown = client.get("/", "admin").text
        said = client.call_tool("read_connection", level="admin").data
        assert "Set by the deployment admin (secret)" in shown
        assert "SECRET-KEY" not in shown and "SECRET-KEY" not in json.dumps(said)
    finally:
        page.HELD.feed = None
