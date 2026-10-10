# meridian-polymarket

Polymarket's public market data for its outcome tokens in an Open Meridian
deployment's lake: a `dgm` plugin. For each outcome token a deployment's
readers ask about -- each a binary event contract -- it records the last
trade's price and the best bid and offer, per token in USDC, and the best bid
and offer with their sizes as a quote, every figure exactly as Polymarket
stated it. No key: Polymarket's market data is public.

It is the second half of the lake's second batch, with
[meridian-kalshi](https://github.com/open-meridian/meridian-kalshi): the two
pass one `dgm` suite unchanged between them (meridian-design
`plans/the-lake-prices-the-book.md`, row 20).

**Status.** 0.1.0, built on open-meridian 0.23.0 (contract v19), committed in
meridian-python and not yet on PyPI, and proven against core's v19 runtime,
built locally from core c7b3cbd and not yet released. Until both are, CI's
`check`, `ci` and `e2e` jobs fail at installing the SDK or building on its
base image; the same gates pass locally (`make ci-local
SDK_REPO=<meridian-python at 0.23.0>`). Not released, uploaded or launched
anywhere.

## What it does

One dataset, declared from code in its catalogue (`declaration.py`):

| Dataset | Data | Modes | Day | Default licence |
|---|---|---|---|---|
| `<instance>:live` | each token's last trade, best bid and offer as prices; its best bid and offer with sizes as a quote | pull, stream | `Etc/UTC`, ending at 00:00 | kept two days |

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
  traded as its own token on its own book; each token pays one USDC if its
  outcome is the result and nothing if not, so each is a binary event
  contract of its own, with its own record. A market with other than two
  outcomes is not served, nor a token whose record states another payout.
  Where the record lacks the token's ID, or its class or type, the ID is
  reported beside the identifier it matched, with `event_contract`,
  `binary_event_contract` and Polymarket's words (the market's question and
  the token's outcome) offered, so a person completing the record on the
  Instruments page has them.
- **Money per token, in Polymarket's USDC.** A price is what one token costs,
  never a probability: the implied probability is the price over the
  payout, a reader's computation. It is named in Polymarket's own USDC
  instrument -- resolved once by its code at `polymarket`, offered as cash,
  a deployment-side record minted where the deployment holds none (the
  platform's master holds no USDC instrument today), as Coinbase's plugin
  does for a quote currency -- and never in dollars: a stablecoin is a token, never its currency. Each
  token's payout is one USDC, and a price outside nothing to the payout is
  left unrecorded and counted.
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
- **The venue** is named as Coinbase's and Kraken's plugins name theirs, by
  its code (`symbol` `polymarket`, source `polymarket`: ISO 10383 has no MIC
  for it). The platform's venue master holds Polymarket (international)
  with no identifier yet, so the code does not resolve it today (v18's
  known finding for a venue with no MIC): each row has the venue left empty
  and the code beside it as reported, and the miss is reported, asked again
  the next day, until the master carries the code.

### What it does not serve

The SDK's `dgm` suite's cases about a kind of data this plugin never
publishes are marked not presented, with why, as contract v19 allows
(`tests/venue_cases.py`): daily closes and bars, trades, a currency's rate
and a security's price. Every other case passes, a price in a stablecoin on
the token's own instrument among them.

## Settings

| Setting | What it does |
|---|---|
| Synthetic mode (`synthetic`) | A developer's setting, shown only on a development deployment: answer from the synthetic exchanges this plugin carries instead of calling Polymarket, or from a developer's recorded exchanges where its storage holds them (`recorded/`). |
| Raw responses' window (`responses_window_days`, `responses_past_window`) | The SDK's, for the plugin's one kind of raw record: how long Polymarket's answers stay in its storage (30 days by default), and whether a day past it is archived, kept or deleted. |

No secret: Polymarket's public market data needs no key.

## Its pages, under Manage

A `dgm` shows no market data: viewing prices is for the reading roles.

- **Connection**: where it answers from (Polymarket, or synthetic mode), the
  two endpoints (Gamma for a token's market, the CLOB for its book), what
  the plugin spends of Polymarket's limits (at most 5 requests a second, a
  429 waited out), its calls, rate limits met and failures, the last error,
  and the venue master's ID it resolved.
- **Datasets**: its dataset; the contracts mapped for the subjects the lake
  asked for, and those not served with why; the cash its prices and payouts
  are in (Polymarket's USDC, and the deployment's record for it) and what
  each contract pays; what Polymarket entitles it to (public data, no key);
  and the wants it heard, standing ones first, each with what it recorded
  and declined, under the kit's search.

Both fit one screen at 1440x900 and 390x844, rows one line each, the wants
paged by the kit's `om-pager`.

### Offered to agents

Each page is a read tool on the deployment's MCP surface, answering the record
the page shows: `read_connection` and `read_datasets`, at the plugin's admin
level. The plugin has no route that changes anything.

## Raw responses

Every answer Polymarket sends, an error as much as a book, is kept in the
storage the deployment grants the plugin before anything is read from it,
with the request that asked for it, its status and headers, and when it
arrived (`raw.py`); a live answer is a line of its day's file, added only
when it changed, and a row read from an unchanged answer names the line and
time it first arrived. Each row names its raw record (`RawRecordRef`). Kept in
units of a UTC day under `responses/`, moved past the window through the SDK.

## Proven on core's harness

    make e2e

runs the plugin in synthetic mode on core's plugin harness beside the e2e's
reader (`e2e/reader.py`, holding `custody` to name a custodian's records,
`reporting` to read prices and `signal` to read quotes): the catalogue
listed, nothing asked of Polymarket before a want, a custodian's outcome
token read and named, its prices and quote recorded on Polymarket's own USDC
instrument, read and heard, a market of three outcomes declined, both read
tools answering what the pages show, and `store lake` numbering each row
with no holes (`e2e/run.py` says each step).

    docker run --rm --entrypoint python -v "$PWD/e2e":/e2e:ro \
        -v "$PWD/recordings":/recordings polymarket:local /e2e/record.py TOKEN ...
    make e2e-recorded RECORDED=recordings/<directory>

records Polymarket's real answers to its public reads for the tokens named,
with the plugin's own client and no key, into the git-ignored `recordings/`,
then runs the same replaying them, holding each row to its shape rather than
to the synthetic values.

## Working on it

    make ci-local        # every gate: lint, tests, plugin check, the image, e2e, the pair the same
    make test            # the tests, the SDK's dgm suite among them
    make preview         # preview/: each page on synthetic data, linking the kit
    make install-hooks   # git push runs ci-local first

`AGENTS.md` is for any coding agent working on it; `CLAUDE.md` leads Claude
Code there. The documentation for a deployment admin is in `docs/`.

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`. Polymarket is a trademark of its
owner; this project is not affiliated with or endorsed by Polymarket.
