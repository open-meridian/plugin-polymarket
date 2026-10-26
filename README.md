# plugin-polymarket

Polymarket's public market data for its outcome tokens in an Open Meridian
deployment's lake: a data plugin. For each outcome token a deployment's
readers ask about -- each a binary event contract -- it records the last
trade's price and the best bid and offer, per token in pUSD, and the best bid
and offer with their sizes as a quote, every figure exactly as Polymarket
stated it; from contract v23, each such token's outcome once Polymarket
resolves its market -- and, from 0.11.0, its proposed and disputed stages,
read from UMA's oracle on chain where the deployment admin entered a Polygon
RPC URL; and from 0.11.0 each token's hourly and daily bars, built from
Polymarket's public trades. No key: Polymarket's market data is public.

**For users outside the US.** This plugin reads the international
Polymarket, which does not serve US persons. A deployment for users in the
US uses [plugin-polymarket-us](https://github.com/open-meridian/plugin-polymarket-us),
which reads Polymarket US, the CFTC-designated exchange (QCEX), instead.

It is one of the lake's second batch, with
[plugin-kalshi](https://github.com/open-meridian/plugin-kalshi): each runs the SDK's
data suite and its checks for an event-contract venue unchanged against its own conversion
(meridian-design `plans/the-lake-prices-the-book.md`, row 20); what the two do alike is
the SDK's (`meridian.roles.data.event_contracts`, open-meridian 0.33.1), never copied
between them.

**Status.** 0.11.0, built on open-meridian 0.33.1 (contract v28: a proposal's and a dispute's stage read from UMA's oracle on chain, each token's hourly and daily bars from its public trades, the fee applying to each market on Connection, its feed delay reported on its quotes, a crossed quote recorded invalid at the edge, its published fee rate by market category on Connection; contract v27: the events kept by the SDK's `Feed.keep_events`; contract v26: each contract's event reported as a group; contract v25's whole declaration and docs/, which a deployment shows on its Documentation tab; its work the SDK's role helpers), holding the
role `data`, and proven against the core it pins, by digest.

## What it does

Three datasets, declared from code in its catalogue (`declaration.py`):

| Dataset | Data | Modes | Day | Default licence |
|---|---|---|---|---|
| `<instance>:live` | each token's last trade, best bid and offer as prices; its best bid and offer with sizes as a quote | pull, stream | `Etc/UTC`, ending at 00:00 | kept two days |
| `<instance>:outcomes` | each token's outcome once its market is resolved, final (contract v23); from 0.11.0 proposed and disputed first, where a Polygon RPC URL is set | push | `Etc/UTC`, ending at 00:00 (an outcome names no business date) | kept |
| `<instance>:bars` | from 0.11.0, each token's hourly and daily bars, built from its public trades, trades counted, no volume-weighted price | pull, push | `Etc/UTC`, ending at 00:00 | kept |

- **Per subject wanted, never the whole venue.** A reader reads a price or
  quote nothing has recorded; the lake asks this plugin (a want). The plugin
  reads the subject's record (W3.6) and names the Polymarket outcome token it
  is by its identifiers: the token's ID (`symbol` at `polymarket`), else
  another source's symbol that Polymarket answers as one of its tokens
  (never for a record that is a security, or a type other than a binary
  event contract). It asks Polymarket for that token's market and book
  alone; Polymarket's market list is never read, and no record is minted for
  a token no reader asked about.
- **Two tokens, two contracts.** A Polymarket market has two outcomes, each
  traded as its own token on its own book; each token pays one pUSD if its
  outcome is the result and nothing if not, so each is a binary event
  contract of its own, with its own record. A market with other than two
  outcomes is not served, nor a token whose record states another payout.
  Where the record lacks the token's ID, or its class or type, the ID is
  reported beside the identifier it matched, with `event_contract`,
  `binary_event_contract` and Polymarket's words (the market's question and
  the token's outcome) offered, so a person completing the record on the
  Instruments page has them.
- **Money per token, in pUSD** (ruling 550). A price is what one token
  costs, never a probability: the implied probability is the price over the
  payout, a reader's computation. It is named in pUSD, the token Polymarket
  documents as "the collateral token used for all trading" (an ERC-20 on
  Polygon backed by USDC) -- resolved once by its CAIP-19,
  `eip155:137/erc20:0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb` (its
  contract on Polymarket's Contracts page), to the platform's pUSD record,
  code `PUSD` -- and never in dollars: a stablecoin is a token, never its
  currency. Each token's payout is one pUSD, and a price outside nothing to
  the payout is left unrecorded and counted. Before 0.9.0 it was `USDC`,
  known by its code at `polymarket` alone, which no master record matched;
  a contract map kept by 0.8.0 has its cash resolved again on start.
- **Wants**, each recorded against or declined per subject with why:
  `not_covered` (not one of Polymarket's binary tokens), `beyond_history` (a
  day or range already past: Polymarket's public reads answer now),
  `source_silent` (Polymarket states nothing for it). A standing want keeps
  its subjects current, at most once a second, until the lake withdraws it.
- **Kept two days**, by default, as a live dataset (the plan's Q21). The
  deployment admin states the deployment's own licence on the Data sources
  page, which replaces the default; the default claims nothing about
  Polymarket's terms, which are for the deployment admin and whoever uses
  the deployment to settle.
- **Outcomes** (contract v23; meridian-design `plans/the-lake-prices-the-book.md`,
  "vL1c"). For each token a reader asked about, the plugin records its
  outcome, unasked, once Polymarket resolves its market (Gamma's
  `umaResolutionStatus` `resolved`, the market closed): from the token's own
  side -- one pUSD, nothing, or half for an "Unknown/50-50" resolution, as
  the market's `outcomePrices` state it -- so a NO token of a market
  resolved YES pays nothing. Polymarket's word, the token's own stated
  price, is kept as reported. That stage is final: a UMA resolution, once
  made, is reported on chain. Polymarket states no time of resolution or
  payout: a final outcome is valid from when the answer first stating it
  arrived, its payout time left 0 (holders redeem their tokens
  themselves). One row key per token (`<token>:outcome`), each stage a new
  version of it; a token past its market's end is read again each minute
  until its final outcome is recorded. Kept by default; paying holders is
  servicing's, not the lake's.
- **A proposal and a dispute** (from 0.11.0; ruling 622). Gamma states
  their stage (`proposed`, `disputed`) but never their answer -- its
  `outcomePrices` stay the book's while one stands, and `umaEndDate` is
  empty until it resolves. Both are on chain, in UMA's optimistic oracle on
  Polygon. Where the deployment admin has entered a **Polygon RPC URL**
  (the secret setting below), the plugin reads them there with read-only
  `eth_call`s (`uma.py`): no wallet, no key, no signing, no transaction.
  For a market Gamma states proposed or disputed it asks the UMA adapter
  the market names (`resolvedBy`) for its question (`questionID`, or a
  negative-risk market's `negRiskRequestID`: `getQuestion`), then the
  adapter's oracle for the request outstanding (`getRequest`): two calls
  each time the market is read (each minute past its close), plus the
  adapter's oracle and the oracle's default liveness once each. A request
  proposed and not disputed is the **proposed** stage: the price proposed
  as this token's settlement value (10^18 pays the market's first outcome,
  0 its second, half each half; any other, "too early" among them, is no
  answer), valid from the proposal's time -- the request's expiration less
  the liveness it ran under -- and its challenge window's end
  (`Outcome.challenge_ends_at_ns`) the expiration. A request disputed is the
  **disputed** stage, the price disputed, no window (a second dispute goes
  to UMA's vote). A dispute the adapter has asked again, nothing proposed
  on it yet, stands with the answer recorded last. The plugin's word for
  both is the oracle's price as it holds it (`uma:proposedPrice`). Without
  the setting nothing is read on chain and an outcome is recorded at its
  final stage alone, as before 0.11.0; Connection's "Polygon RPC" endpoint
  says which, never the URL.
- **Bars** (from 0.11.0; rulings 624 and 625). For each token it serves,
  the plugin keeps hourly and daily (UTC day) bars, built from its market's
  public trades on Polymarket's data API (`/v2/trades?condition=`, each
  fill once on its taker side): open the first trade's price, high, low,
  close the last's, volume the tokens traded, the trades counted
  (`trade_count`), and no volume-weighted price. **A trade's wallet and
  names are dropped before anything is kept**: of each fill only its
  market, token, outcome, side, size, price and time are read and kept as
  the raw record -- never its proxy wallet, display name, pseudonym, bio,
  profile images or transaction hash. The SDK's `Feed.keep_bars` (open-
  meridian 0.33.1) runs it: every five minutes each closed hour and day
  since the last kept, first 30 days back, recorded unasked; a want of
  `bars` is answered from the same trades. A market's trades are read once
  per pass for both its tokens and both intervals, walking back at most 20
  pages of 1,000; a market trading more than that in the window asked keeps
  the intervals the walk read whole, never one part-built.
- **Events** (contract v26; meridian-design
  `spec/the-contract-gaps-v26-and-v27-close.md`, A1 to A9; W3.29). For each
  outcome token it serves, the plugin reads the Gamma event its market
  belongs to (the condition's market, `/markets?condition_ids=`, for its
  event's slug; then `/events/slug/{slug}`) and reports it
  (`ReportEventGroup`, the SDK's `Feed.report_event`): its markets' YES
  tokens, each named as the deployment's record, and the two flags as
  Polymarket's negative risk states them. A negative-risk event (`negRisk`)
  holds only when exactly one outcome resolves YES, so its markets are
  mutually exclusive and exhaustive; an augmented one (`negRiskAugmented`,
  or a market marked `negRiskOther`) adds outcomes named later and an
  "Other", so its named outcomes are mutually exclusive and their
  exhaustiveness not stated; an event without negative risk states
  neither. Not stated is never false. The platform matches or mints the
  group (`EVG-`), the deployment keeping its own `LCL-` group meanwhile.
  Each event is read once its first token is served and again every ten
  minutes, and reported again only where Polymarket states it otherwise,
  which makes a new version; an event a member of which does not resolve is
  held back and read again. From 0.9.0 that loop is the SDK's
  (`Feed.keep_events`, open-meridian 0.32.0), over the plugin's
  `event(ref)`. Gamma states no range market's bounds as such, so its
  reports carry no member's bounds (contract v27, ruling 464).
- **The venue** is named as Coinbase's and Kraken's plugins name theirs, by
  its code (`symbol` `polymarket`, source `polymarket`: ISO 10383 has no MIC
  for it). The platform's venue master holds Polymarket (international)
  with no identifier yet, so the code does not resolve it today (v18's
  known finding for a venue with no MIC): each row has the venue left empty
  and the code beside it as reported, and the miss is reported, asked again
  the next day, until the master carries the code.

### What it does not serve

The SDK's data suite's cases about a kind of data this plugin never
publishes are marked not presented, with why, as contracts v19 and v20
allow (`tests/venue_cases.py`): daily closes, trades, a currency's rate
and a security's price. From 0.11.0 `a-daily-bar` passes on the synthetic
final's trades the day before. It records no trades (its bars are built
from them, never kept as trades), so a
restart leaves no gap of trades to read back (`a-restarts-gap-backfilled`,
contract v20, not presented): its live dataset is read again when it is
next wanted. Contract v22's two calendar cases are not presented either: it
reads no settlement calendar, and an event contract settles on its outcome,
so it never computes a settlement date. Of contract v23's three outcome
cases, `records-an-outcome` is mapped to a resolution recorded final (the
case takes determined or final, ruled 2026-10-13),
`records-a-partial-payout` to a 50-50 resolution, and from 0.11.0
`restates-a-disputed-outcome` to a synthetic proposal read on the
synthetic chain, then disputed (`tests/exchanges/disputed`). Contract v26's are mapped:
`reports-an-event-group` on a negative-risk event,
`reports-a-flag-the-venue-does-not-state` on an augmented one;
`hears-and-reads-an-event-group` is answered by the SDK. Contract v27's
cases an event-contract venue never presents are the SDK's list
(`EVENT_CONTRACTS_NOT_PRESENTED`): the seven rates cases (it publishes no
rates); `records-a-datasets-liveness` (Polymarket is polled over REST each
second, and no stream gives a heartbeat to record); and
`queries-the-lake-within-bounds`, about trades from v27 (it records none).
Contract v28's are the SDK's list too: the option-chain and filings cases
(it lists no chain and publishes no filing), and
`a-duplicate-is-recorded-suspicious` and `rows-after-a-gap-are-suspicious`
(its quotes are polled; no message is numbered).
`a-crossed-quote-is-recorded-invalid` passes on a synthetic token whose
book is crossed. `reports-its-feed-delay` (required from contract v28,
ruling 518) passes on the SDK's own producer: from open-meridian 0.33.1
(ruling 626) it stands its want on the quote where the venue's last trade
states no time, as Polymarket's does, so 0.10.0's own producer is gone. Every other case passes, a price in a stablecoin on the token's
own instrument and `reads-its-datasets-licences` among them: it reads which
of its datasets a deployment admin has licensed, on start and each minute.

## Settings

| Setting | What it does |
|---|---|
| Polygon RPC URL (`polygon_rpc_url`) | From 0.11.0; a **secret** the deployment admin enters, never logged, kept or shown: a Polygon JSON-RPC endpoint through which UMA's oracle is read, read only, for a market's proposed and disputed stages and its challenge window's end. Empty: outcomes are recorded once final, as before 0.11.0. |
| Sample data (`sample_data`) | A developer's setting, shown only on a development deployment: answer from the synthetic exchanges this plugin carries instead of calling Polymarket, or from a developer's recorded exchanges where its storage holds them (`recorded/`). |
| Raw responses' window (`responses_window_days`, `responses_past_window`) | The SDK's, for the plugin's one kind of raw record: how long Polymarket's answers stay in its storage (30 days by default), and whether a day past it is archived, kept or deleted. |

Polymarket's public market data needs no key; the RPC URL is the one secret, as an RPC provider's URL often carries its own key.

## Its pages, under Manage

The data role's two pages (meridian-design
`spec/plugin-pages-follow-their-role.md`), the same sections, rows, labels
and "not set up yet" states as every data plugin's, drawn from the SDK's
role templates (`meridian.roles.data`); Polymarket's nuance only at their
extension points. A data plugin shows no market data: viewing prices is for
the reading roles.

- **Connection**: "Key" -- the mode (Live, or Sample data), "No key needed",
  what Polymarket entitles it to (public data: a contract read only for a
  subject the lake asked for) and, the role's row for a source of one venue,
  the venue master's ID it resolved, and its endpoints -- Gamma, the CLOB,
  from 0.11.0 the data API (trades, for bars) and the Polygon RPC ("set by
  the deployment admin (secret)" or "not set: outcomes are recorded final
  only", never its URL); "Limits and use" -- what Polymarket allows
  and what the plugin spends of it, its calls and the rate-limited ones
  waited out, the last call and the last error, and, from 0.10.0, "Fees":
  Polymarket's published taker fee rate by market category (Crypto 0.07,
  Sports 0.05, Politics 0.04, Geopolitics 0, Combos 0.05 and the rest),
  makers never charged, read from docs.polymarket.com/trading/fees on
  2026-10-26, for the options sample's fee schedule to take; from 0.11.0
  (ruling 630) it says which applies to each contract served -- "Per
  market: n own, n by category, n none" -- each contract's a tap away and
  in `read_connection`'s `fees.markets`: its market's own fee as Gamma
  states it (`feeSchedule`, `feeType`; source `market`), else, where Gamma
  states none, the row of the one category its event's tags name
  (`category`), else no rate and why (`none`), never another category's
  (`fees.py`); "Stream" -- "Does not
  stream": it reads a contract when it is wanted, at most once a second.
- **Datasets**: "Served" -- each dataset (`live`, `outcomes`, from 0.11.0 `bars`), its data, how
  its rows arrive, its day, its default terms and whether a deployment admin
  has licensed it ("Licensed" or "Not licensed yet", read from the
  deployment from contract v20), what it recorded and declined and when it
  last recorded, each dataset's own; "Wants" --
  the wants it heard and the standing wants it keeps current, searched and
  paged by the kit's `om-pager`; "Subjects" -- whether the deployment lets
  it read an instrument's record; then a section under Polymarket's name: the
  contracts mapped for the subjects the lake asked for and those not served
  with why, the cash its prices and payouts are in (pUSD, Polymarket's collateral token, never the dollar) and what each
  contract pays (one pUSD), and that each outcome is its own token and
  contract. Before the lake has asked anything it says the
  next step: "No wants yet", a deployment admin licensing its dataset on
  Data sources.

Its Summary carries the data role's figures, in the role's order:
Connection, Entitled at the vendor, Stream ("Does not stream") and Last
recorded. Both pages fit one screen at 1440x900 and 390x844, rows one line
each.

### Offered to agents

Each page is a read tool on the deployment's MCP surface, answering the record
the page shows: `read_connection` and `read_datasets`, at the plugin's admin
level. The plugin has no route that changes anything.

## Raw responses

Every answer Polymarket sends, an error as much as a book, is kept in the
storage the deployment grants the plugin before anything is read from it,
with the request that asked for it, its status and headers, and when it
arrived (`meridian.edge.RawStore`); a live answer is a line of its day's file, added only
when it changed, and a row read from an unchanged answer names the line and
time it first arrived. Each row names its raw record (`RawRecordRef`). Kept in
units of a UTC day under `responses/`, moved past the window through the SDK.
Two exceptions, from 0.11.0: a page of the data API's trades is kept with
each fill's wallet, profile and transaction already dropped (the record is
what was read, not the bytes as they arrived); and an RPC answer is kept
with its request but never the URL it went to, the deployment's secret.

## Proven on core's harness

    make e2e

runs the plugin with sample data on core's plugin harness beside the e2e's
reader (`e2e/reader.py`, holding `custody` to name a custodian's records,
`reporting` to read prices and `signal` to read quotes): the catalogue
listed, nothing asked of Polymarket before a want, a custodian's outcome
token read and named, its prices and quote recorded on the platform's pUSD
instrument, read and heard, its event reported and read back as a group, a
market of three outcomes declined, a resolved
token's outcome recorded, kept, heard and read back, both read tools
answering what the pages show, and `store lake` numbering each row with no
holes and keeping the outcome's one (`e2e/run.py` says each step).
The custodian offers no currency, so core v27's stand-in platform
(4574643) mints each token paying the venue's own payout, one pUSD on its
CAIP-19 record (ruling 550), which the plugin's cash resolves to.

    docker run --rm --entrypoint python -v "$PWD/e2e":/e2e:ro \
        -v "$PWD/recordings":/recordings polymarket:local /e2e/record.py TOKEN ...
    make e2e-recorded RECORDED=recordings/<directory>

records Polymarket's real answers to its public reads for the tokens named,
with the plugin's own client and no key, into the git-ignored `recordings/`,
then runs the same replaying them, holding each row to its shape rather than
to the synthetic values.

## Working on it

    make ci-local        # every gate: lint, tests, plugin check, the image, e2e, the pair the same
    make test            # the tests, the SDK's data suite among them
    make preview         # preview/: each page on synthetic data, linking the kit
    make install-hooks   # git push runs ci-local first

`AGENTS.md` is for any coding agent working on it; `CLAUDE.md` leads Claude
Code there. The documentation for a deployment admin is in `docs/`.

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`. Polymarket is a trademark of its
owner; this project is not affiliated with or endorsed by Polymarket.
