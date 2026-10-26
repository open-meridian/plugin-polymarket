"""UMA's optimistic oracle on Polygon, read for a Polymarket market's
proposed and disputed stages (from 0.11.0; ruling 622).

Gamma states a market's resolution stage (`umaResolutionStatus`:
`proposed`, `disputed`, `resolved`) but, until it is resolved, never the
answer proposed or when the window to challenge it ends: both are on chain.
Where the deployment admin has entered a Polygon RPC URL (the secret setting
`polygon_rpc_url`), the plugin reads them there, with read-only calls
(`eth_call`) and nothing else: no wallet, no key, no signing, no
transaction.

**Which contracts.** A Polymarket market names the UMA adapter that
resolves it (Gamma's `resolvedBy`), and the question it asked there: its
`questionID`, or for a negative-risk market its `negRiskRequestID`, which
the negative-risk operator asked under. The adapter is Polymarket's UMA CTF
adapter (github.com/Polymarket/uma-ctf-adapter; its versions and addresses
on docs.polymarket.com, "Contracts"), and the oracle it asks is UMA's
OptimisticOracleV2 (github.com/UMAprotocol/protocol,
`OptimisticOracleV2Interface`). Read on 2026-10-26: markets name the
adapters 0x65070BE9..., 0x69c47De9... and 0x2F5e3684..., each asking an
OptimisticOracleV2 (0x2c0367a9... or 0xeE3Afe34...), each answering the
calls below alike. The addresses are read from Gamma and the adapter, never
written here, so a new adapter is read the same way.

**The calls**, each one `eth_call` at the latest block:
- the adapter's `getQuestion(bytes32)`: the question's request time, its
  liveness (0: the oracle's default) and its ancillary data -- the request
  the adapter has outstanding at the oracle, a new one after a reset;
- the adapter's `optimisticOracle()`, once per adapter;
- the oracle's `getRequest(address,bytes32,uint256,bytes)`, asked as the
  adapter for `YES_OR_NO_QUERY` at that time and data: the proposer, the
  disputer, the proposed price and the expiration time;
- the oracle's `defaultLiveness()`, once per oracle, where the request
  sets no liveness of its own.

So a market in its proposed or disputed stage costs two calls each time it
is read (the SDK reads a contract past its close each minute), and nothing
is read on chain for any other market.

**What is read from them.** A request with a proposer and no disputer is
the proposed stage: its answer the proposed price, the challenge window's
end its expiration time, and the proposal's time that expiration less the
liveness it ran under (the oracle sets the expiration to the proposal's
time plus the liveness). One with a disputer is the disputed stage, its
answer the price disputed, no window: a second dispute goes to UMA's vote.
A request with no proposal, where Gamma states the market disputed, is the
new request the adapter sent after the first dispute: the dispute stands
with the answer last proposed, which the plugin recorded when it read it,
and states no answer of its own. The adapter's prices (`YES_OR_NO_QUERY`):
one (10^18) pays the market's first outcome, zero its second, a half (5 x
10^17) each half; any other, the "too early" price among them, is no
answer.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from meridian.edge import RawStore
from meridian.roles.data import Health

from .venue import RateLimiter, Response

#: Each call's selector: the first four bytes of the Keccak-256 of its
#: signature, as Solidity's ABI states.
GET_QUESTION = "58c039cd"  # getQuestion(bytes32)
OPTIMISTIC_ORACLE = "22302922"  # optimisticOracle()
GET_REQUEST = "a9904f9b"  # getRequest(address,bytes32,uint256,bytes)
DEFAULT_LIVENESS = "fe4e1983"  # defaultLiveness()
#: The adapter's identifier at the oracle: "YES_OR_NO_QUERY", right-padded.
YES_OR_NO_QUERY = b"YES_OR_NO_QUERY".ljust(32, b"\0").hex()

#: The adapter's prices (UmaCtfAdapter `_constructPayouts`): one pays the
#: first outcome, zero the second, a half each.
ONE = 10**18
HALF = 5 * 10**17

#: Where the plugin's word for a stage read on chain is, as reported.
PROPOSED_PRICE = "uma:proposedPrice"

#: What the plugin spends of the RPC: at most five calls a second.
RATE_PER_SECOND = 5.0
BURST = 5

_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
_BYTES32 = re.compile(r"0x[0-9a-fA-F]{64}")
_NANOS = 1_000_000_000


Poster = Callable[[str, Mapping[str, str], bytes], Response]


def urllib_poster(url: str, headers: Mapping[str, str], body: bytes) -> Response:
    """One POST over HTTPS, with the standard library."""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as answer:
            return Response(
                answer.status, {k.lower(): v for k, v in answer.headers.items()}, answer.read()
            )
    except urllib.error.HTTPError as answer:
        return Response(
            answer.code, {k.lower(): v for k, v in answer.headers.items()}, answer.read()
        )


class ChainError(Exception):
    """The RPC did not answer a call, or answered it with an error. Its words
    never hold the RPC's URL, which the deployment keeps secret."""


@dataclass(frozen=True)
class Proposal:
    """What the oracle states of a question's outstanding request."""

    proposer: str
    disputer: str
    #: The price proposed, as the oracle holds it (an int256).
    price: int
    #: When the request auto-settles unless disputed, in UTC seconds; 0
    #: where nothing is proposed.
    expires_at: int
    #: The liveness the proposal ran under, in seconds.
    liveness: int
    raw_key: str

    @property
    def proposed(self) -> bool:
        return int(self.proposer, 16) != 0

    @property
    def disputed(self) -> bool:
        return int(self.disputer, 16) != 0

    @property
    def proposed_at(self) -> int:
        """When it was proposed, in UTC seconds: its expiration less its
        liveness, as the oracle set it."""
        return self.expires_at - self.liveness if self.expires_at else 0


def _word(value: int) -> str:
    return format(value % (1 << 256), "064x")


def _words(hex_text: str) -> list[str]:
    body = hex_text[2:] if hex_text.startswith("0x") else hex_text
    return [body[i : i + 64] for i in range(0, len(body), 64)]


def _int256(word: str) -> int:
    value = int(word, 16)
    return value - (1 << 256) if value >> 255 else value


def _address(word: str) -> str:
    return "0x" + word[24:]


def payouts(price: int, slots: int = 2) -> tuple[Decimal, ...] | None:
    """What each outcome pays per token at a proposed price, in the
    market's order; None for no answer (the "too early" price among
    them)."""
    if slots != 2:
        return None
    if price == ONE:
        return (Decimal(1), Decimal(0))
    if price == 0:
        return (Decimal(0), Decimal(1))
    if price == HALF:
        return (Decimal("0.5"), Decimal("0.5"))
    return None


class Uma:
    """Read-only calls to Polygon through the deployment's RPC, each answer
    kept as a raw record; the RPC's URL is never kept, logged or shown."""

    def __init__(
        self,
        url: str,
        store: RawStore,
        health: Health,
        post: Poster = urllib_poster,
        limiter: RateLimiter | None = None,
        clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self._url, self.store, self.health, self.post = url, store, health, post
        self.limiter = limiter or RateLimiter(RATE_PER_SECOND, BURST)
        self.clock_ns = clock_ns
        self._oracles: dict[str, str] = {}
        self._liveness: dict[str, int] = {}
        self._id = 0

    def call(self, to: str, data: str, name: str) -> tuple[str, str]:
        """One `eth_call` at the latest block: its result's hex and the key
        of the raw record it was kept as."""
        self._id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": "eth_call",
            "params": [{"to": to, "data": "0x" + data}, "latest"],
        }
        body = json.dumps(payload).encode("utf-8")
        self.limiter.acquire()
        self.health.calls += 1
        try:
            answer = self.post(
                self._url,
                {"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "plugin-polymarket (+https://open-meridian.dev)"},
                body,
            )  # fmt: skip
        except OSError as failed:
            # The error's words can name the host: only its kind is said.
            self._failed(f"Polygon RPC: no answer ({type(failed).__name__})")
            raise ChainError(f"no answer ({type(failed).__name__})") from None
        received = self.clock_ns()
        text = answer.body.decode("utf-8", errors="replace")
        record = {
            "venue": "polymarket",
            "call": "rpc",
            # The URL is the deployment's secret: the request is kept, never where it went.
            "request": {"method": "POST", "url": "polygon_rpc_url", "body": payload},
            "received_at_ns": received,
            "status": answer.status,
            "body": text,
        }
        raw_key = self.store.keep("rpc", name, record)
        if answer.status != 200:
            self._failed(f"Polygon RPC: {answer.status}")
            raise ChainError(f"{answer.status} (raw record {raw_key})")
        try:
            said = json.loads(text)
        except json.JSONDecodeError:
            self._failed("Polygon RPC: not JSON")
            raise ChainError(f"not JSON (raw record {raw_key})") from None
        result = said.get("result") if isinstance(said, dict) else None
        if not isinstance(result, str) or not result.startswith("0x"):
            error = said.get("error") if isinstance(said, dict) else None
            code = error.get("code") if isinstance(error, dict) else ""
            self._failed(f"Polygon RPC: error {code}")
            raise ChainError(f"error {code} (raw record {raw_key})")
        self.health.last_ok_ns = received
        return result, raw_key

    def _failed(self, why: str) -> None:
        self.health.failures += 1
        self.health.last_failed_ns = self.clock_ns()
        self.health.last_error = why

    def oracle(self, adapter: str) -> str:
        """The oracle an adapter asks, read once."""
        if adapter not in self._oracles:
            result, _ = self.call(adapter, OPTIMISTIC_ORACLE, adapter)
            words = _words(result)
            if not words:
                raise ChainError(f"{adapter} names no oracle")
            self._oracles[adapter] = _address(words[0])
        return self._oracles[adapter]

    def default_liveness(self, oracle: str) -> int:
        """An oracle's default liveness, in seconds, read once."""
        if oracle not in self._liveness:
            result, _ = self.call(oracle, DEFAULT_LIVENESS, oracle)
            words = _words(result)
            if not words:
                raise ChainError(f"{oracle} states no default liveness")
            self._liveness[oracle] = int(words[0], 16)
        return self._liveness[oracle]

    def proposal(self, adapter: str, question: str) -> Proposal | None:
        """The oracle's statement of the request a question has outstanding;
        None where the adapter holds no such question."""
        if not _ADDRESS.fullmatch(adapter) or not _BYTES32.fullmatch(question):
            return None
        result, _ = self.call(adapter, GET_QUESTION + question[2:], question)
        words = _words(result)
        # QuestionData: requestTimestamp, reward, proposalBond, liveness,
        # manualResolutionTimestamp, resolved, paused, reset, refund,
        # rewardToken, creator, then the offset of ancillaryData.
        if len(words) < 14 or int(words[1], 16) == 0:
            return None
        requested, liveness = int(words[1], 16), int(words[4], 16)
        start = 1 + int(words[12], 16) // 32
        size = int(words[start], 16)
        ancillary = "".join(words[start + 1 :])[: size * 2]
        oracle = self.oracle(adapter)
        padded = ancillary + "0" * ((64 - len(ancillary) % 64) % 64)
        data = (
            GET_REQUEST
            + adapter[2:].lower().rjust(64, "0")
            + YES_OR_NO_QUERY
            + _word(requested)
            + _word(4 * 32)
            + _word(size)
            + padded
        )
        result, raw_key = self.call(oracle, data, question)
        request = _words(result)
        # Request: proposer, disputer, currency, settled, then its settings
        # (eventBased, refundOnDispute, three callbacks, bond,
        # customLiveness), proposedPrice, resolvedPrice, expirationTime ...
        if len(request) < 14:
            raise ChainError(f"{oracle}'s request for {question} did not read")
        custom = int(request[10], 16) or liveness
        ran = custom or self.default_liveness(oracle)
        return Proposal(
            proposer=_address(request[0]),
            disputer=_address(request[1]),
            price=_int256(request[11]),
            expires_at=int(request[13], 16),
            liveness=ran,
            raw_key=raw_key,
        )


def question_of(body: Mapping[str, Any]) -> tuple[str, str] | None:
    """The adapter resolving a Gamma market and the question it asked there:
    a negative-risk market's request ID, else its question ID."""
    adapter = str(body.get("resolvedBy") or "")
    asked = body.get("negRiskRequestID") if body.get("negRisk") else None
    question = str(asked or body.get("questionID") or "")
    if not _ADDRESS.fullmatch(adapter) or not _BYTES32.fullmatch(question):
        return None
    return adapter, question


def seconds_ns(seconds: int) -> int:
    return seconds * _NANOS
