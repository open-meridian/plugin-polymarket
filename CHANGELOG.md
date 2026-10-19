# Changelog

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
