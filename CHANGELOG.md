# Changelog

## 0.10.0

On open-meridian 0.33.0, contract v28 (meridian-design `plans/the-v28-build.md`;
task `sdk-contract/venue-plugins-keep-outcome-stages-and-bars`), on core
v28's harness.

- **Fees by market category** (571; task
  `sdk-contract/event-contract-fees-vary-by-market-category`): Connection's
  "Limits and use" gains a "Fees" row, and `read_connection` a `fees`
  record -- Polymarket's published taker fee rate by market category, maker
  rate and rebate, and formula, read from docs.polymarket.com/trading/fees
  on 2026-10-26, for the options sample's fee schedule to take (`fees.py`).
  Gamma also states each market's own fee (`feeSchedule`, `feeType`), which
  can differ from its category's row (read 2026-10-26: an election market
  `zero_fees` at 0 against Politics' 0.04; a sports market
  `sports_fees_v2` at 0.03 against Sports' 0.05); a market's own applies to
  it.
- **Proposed and disputed stages: still not recorded, checked again.** On
  2026-10-26, of 144 markets Gamma answered as `proposed` or `disputed`,
  none stated the proposed answer (`outcomePrices` stay the book's) or the
  challenge window's end (`umaEndDate` empty on every one), and the
  contract's `Outcome` needs a settlement value at every stage. Both are on
  chain, in UMA's oracle, which this version does not read; an outcome is
  still recorded at its final stage alone, its `challenge_ends_at_ns` 0.
- **The suite's v28 cases**: `reports-its-feed-delay` is presented (518) on a
  standing want of the token's quote, whose book states its time --
  Polymarket's last trade states none, so the SDK's producer, keeping last
  prices alone, would age nothing (`tests/venue_cases.producers`, run by
  `tests/test_data_role.py`); `a-crossed-quote-is-recorded-invalid` on a
  synthetic token whose book is crossed (`CROSSED`); the option-chain,
  filings, duplicate and gap cases not presented, the SDK's list (602).
- **`meridian plugin migrate`** (to_0_33_0): e2e/reader.py's SubjectRefs
  handed to the SDK are `meridian.SubjectRef` (ruling 599).
- **The pins**: open-meridian 0.33.0 and plugin-python:0.33.0 by tag and
  digest (`sha256:c95f1a03...c0fe39c6`); core v28's runtime and harness at
  `8def82a` (chart 0.1.313) by digest; `meridian` stays 0.1.52 in
  check.yaml until 0.1.53 is released.
- The README's "not released" line is gone.

## 0.9.0

On open-meridian 0.32.3, contract v27 (meridian-design `plans/the-v27-build.md`,
§B and §G), on core v27's harness.

- **For users outside the US** (ruling 488): the README, docs/overview.md,
  AGENTS.md and the package's description say it reads the international
  Polymarket, and that US users use plugin-polymarket-us.
- **The events are the SDK's.** `__main__.Events`, the loop reading each
  served token's event once first served and every ten minutes and
  reporting it on a change, is gone: `Feed.keep_events` (open-meridian
  0.32.0) does the same over `PolymarketMarket.event`.
  `tests/test_events.py` holds the SDK's loop to what Polymarket's did, and
  that its reports carry no member's bounds (ruling 464): Gamma states no
  range market's bounds.
- **No challenge deadline.** Contract v27's `Outcome.challenge_ends_at_ns`
  stays 0 ("deadline not reported"): Gamma states a proposal's liveness
  (`customLiveness`) but not when it was proposed (`umaEndDate` is empty
  until resolved), the end is UMA's on chain, and the plugin records the
  final stage alone. Said in the README, AGENTS.md and docs/overview.md.
- **The suite's v27 cases** are named not presented through the SDK's
  `EVENT_CONTRACTS_NOT_PRESENTED`: the seven rates cases;
  `records-a-datasets-liveness` (Polymarket is polled each second, and no
  stream gives a heartbeat); `queries-the-lake-within-bounds`, about trades
  from v27 (it records none); and `reports-its-feed-delay`, about latency,
  with ruling 518's reason (core receives ReportLatency from contract v28,
  ruling 515). The override of `test_a_record_already_complete_is_not_resolved_again`
  is gone: the SDK's own check holds the ticker since 0.31.1.
- **Its cash is pUSD** (ruling 550): `Cash("PUSD", "token", scheme="caip19",
  value="eip155:137/erc20:0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb")`,
  Polymarket's collateral token ("the collateral token used for all
  trading", docs.polymarket.com) by its contract on Polygon, which the
  platform's pUSD record carries. It was `USDC`, known by its code at
  `polymarket` alone, which no master record matched, so a deployment
  minted its own. Prices, quotes and outcomes are in pUSD. A contract map
  kept by 0.8.0 has its cash resolved again on start
  (`__main__.contract_map`, `tests/test_cash.py`): the SDK's map keeps the
  cash's ID and never asks again, so an upgrade would otherwise go on
  pricing in the old record. A token's record a person completed with a
  payout in the old USDC record is declined as another payout until its
  payout is corrected to one pUSD.
- **The e2e in full.** `HARNESS_PAYS_USD` and the harness-limited path are
  gone: core v27's stand-in (4574643) mints a token paying the venue's own
  payout, one pUSD on its CAIP-19 record, where the source offers no
  currency, so the custodian offers none, and every step runs -- prices,
  the quote, the event group, the decline, the outcome, both read tools and
  the lake's record, in pUSD.
- **The pins**: open-meridian 0.32.3 and plugin-python:0.32.3 by tag and
  digest (`sha256:596236b9...661674f3`); core v27's runtime and harness at
  `4574643` (chart 0.1.311) by digest; `meridian` 0.1.52 in check.yaml.
  e2e-latest.yaml keeps the harness's hidden logs (`include-hidden-files`).
- Its `DatasetLicence` sets none of the licence fields 0.32.2 and 0.32.3
  added (the licence hold); they come in a later version. The terms page is
  unchanged.

## 0.8.0

On open-meridian 0.31.0, contract v26: Polymarket's events reported as
groups (meridian-design `spec/the-contract-gaps-v26-and-v27-close.md`, A1
to A9; W3.29), on core v26's harness. One version for v26 (open question
234): it carries 0.6.0 and 0.7.0, which never merged on their own. The
international Polymarket, as before; Polymarket US is plugin-polymarket-us.

- **Event groups.** For each token it serves, the plugin reads the Gamma
  event its market belongs to (`/markets?condition_ids=` for the event's
  slug, read once per condition; `/events/slug/{slug}`) and reports it
  through the SDK's `Feed.report_event`: its markets' YES tokens, and the
  flags as negative risk states them -- `negRisk` mutually exclusive and
  exhaustive; augmented (`negRiskAugmented`, or a market marked
  `negRiskOther`) mutually exclusive, exhaustiveness not stated; neither
  stated without negative risk. Each event is read once its first token is
  served and every ten minutes after, and reported again only where
  Polymarket states it otherwise; an event a member of which does not
  resolve is held back and read again (`__main__.Events`).
- **The data suite's v26 cases mapped**: `reports-an-event-group` on a
  synthetic negative-risk event (the final, the base contract's market
  among its three), `reports-a-flag-the-venue-does-not-state` on an
  augmented one, `queries-the-lake-within-bounds` the SDK's producer
  (`tests/venue_cases.py`'s `EVENT` and `EVENT_PLACEHOLDERS`). Polymarket's
  markets state no range bounds, so none are read.
- **e2e on core v26's harness** (199): the custodian states the token's ID
  under Polymarket's `VEN-` ID beside its own symbol, so the stand-in
  platform mints the platform's record by it. The stand-in mints every
  event contract paying 1 USD (core 17a13a2, `deploy/harness/platform.py`
  `event_contract()`), where a token pays 1 USDC on Polymarket's own
  instrument, so the plugin declines it as another payout, never serving a
  wrong one: the run proves what the harness can (the record minted by the
  token's ID and declined for its payout, the market of three outcomes
  declined, no row, no miss), and its price, quote, event-group (5a) and
  outcome steps wait behind `HARNESS_PAYS_USD` for the harness fix queued
  for v27. On a failure the run logs the instruments, the plugin's
  Datasets record and the lake's record.
- **Tests**: `tests/test_events.py`, the conversion's events; the SDK check
  `test_a_record_already_complete_is_not_resolved_again` held to ruling
  312's ticker until open-meridian 0.31.1 corrects its own. e2e.yaml keeps
  the harness's logs on a failure (`include-hidden-files`).
- **The pins**: open-meridian 0.31.0 and plugin-python:0.31.0 by tag and
  digest (`sha256:e041f83c...24cf5d2`); core v26's runtime and harness
  (17a13a2, merged as 648e25f) by digest; `meridian` 0.1.49, the first CLI
  carrying contract v26's suites.

## 0.7.0 (not released on its own: carried by 0.8.0)

On open-meridian 0.30.0, contract 25 unchanged: the data role's work is
the SDK's (sdk-contract/the-sdk-carries-each-roles-common-logic; ruling
202). It follows 0.6.0 (contract v25: the whole declaration and docs/),
which has not merged to main yet: this branch carries it.

- **The data role from the SDK's helpers.** `market.py`, `dgm.py`,
  `contracts.py` and `raw.py`, kept byte for byte with plugin-kalshi, are
  gone: the work is `meridian.roles.data.event_contracts.Feed` (prices,
  quotes and outcomes) over this venue's values and `ContractMap`, raw
  records `meridian.edge.RawStore`, and the pages the SDK's for an
  event-contract venue (`page.py` builds them; `templates/` gone),
  answering the kind's `ConnectionRead` and `DatasetsRead`.
  `e2e/reader.py` stays as this plugin's own e2e stand-in.
- **suite-same retired.** The copied tests (`test_suite`, `test_dgm`,
  `test_page`, `test_raw`, `conftest`) are one class,
  `tests/test_data_role.py`, running the SDK's `EventContractsChecks`
  against this plugin's conversion and the data suite by name; raw records
  are tested in the SDK. The Makefile's `suite-same`, `PAIR` and `SAME` are
  gone.
- **The pins**: open-meridian 0.30.0, as released on PyPI, and
  plugin-python:0.30.0 by tag and digest
  (`sha256:a238c6d9...3473ed6`) in the Dockerfile, which `make image` now
  builds on as an upload does; core v25's runtime and harness (abf028f) and
  `meridian` 0.1.46 as 0.6.0 set them.

Earlier versions are described in the git history.
