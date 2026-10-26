# Overview

The Polymarket plugin puts Polymarket's public market data for its outcome
tokens into your deployment's lake, where the plugins that watch and value
your book read it. It needs no key: Polymarket's market data is public.

It is for users outside the US: it reads the international Polymarket,
which does not serve US persons. For users in the US, install the Polymarket
US plugin (plugin-polymarket-us) instead.

It is a data plugin: its first-use path, its two pages and its Summary figures are every data plugin's, described once on [Using a data plugin](https://open-meridian.dev/how-to/using-a-data-plugin/). These sections cover what is Polymarket's own.

## Its role

It holds one role, `data`: it records prices and quotes into the lake, with
Polymarket's tokens named as your deployment's instruments, and keeps
Polymarket's answers in its own storage. It shows no prices itself: reading
them is for the reporting, portfolio, signal and other reading plugins.

## What it records

For each outcome token a reader asks about, now: the last trade's price and
the best bid and offer, per token in pUSD, and the best bid and offer with
their sizes as a quote, at most once a second for each token while a reader
keeps asking.

It records what readers ask for, not the whole exchange: when a reader asks
for a price nothing has recorded, the lake asks the plugin, which asks
Polymarket for that one token's market and book and records it, or says why
it cannot.

## Two tokens, two instruments

A Polymarket market ("Will it rain in Paris tomorrow?") has two outcomes,
Yes and No, each traded as its own token. Each token pays one pUSD if its
outcome happens and nothing if not, so each is a binary event contract of
its own, with its own record in your deployment and its own prices.

## How it names what it prices

Each instrument a reader asks about is one of your deployment's records. The
plugin reads it and looks for the token's ID on it (as Polymarket's own
symbol), or another source's symbol that is a Polymarket token ID. It serves
a token only where its market has two outcomes.

Where the record lacks the token's ID, its class or its type, the plugin
offers them, with Polymarket's words for it (the market's question and the
token's outcome), so you can complete the record on the Instruments page. If
the record already states a payout that is not one pUSD, the
plugin does not serve it.

## Prices are money, not probabilities

A price is what one token costs: 0.43 means 0.43 pUSD for a token that pays
one pUSD. The market's implied probability (43%) is that price over the
payout, which a reading plugin may compute; the lake stores only the price.

Prices are in pUSD, the token Polymarket trades and pays out in (its
collateral, backed by USDC), named by its address on Polygon and matched to
the platform's pUSD record; never in dollars: pUSD is a token, valued in
dollars only through a price of it, never by assuming one for one.

## Outcomes

Once Polymarket resolves the market of a token a reader asked about, the
plugin records the token's outcome: whether it pays its one pUSD, pays
nothing, or pays half (an "Unknown/50-50" resolution), from the token's own
side, so the NO token of a market resolved YES pays nothing. It records the
final resolution alone: while a resolution is proposed or disputed,
Polymarket's public data says so but does not say what was proposed.
Outcomes are kept by default. Paying the holders of a position is not the
plugin's: it records what Polymarket resolved.

An outcome carries no challenge deadline: your pages show "deadline not
reported". Polymarket's public data does not say when a proposed resolution
can no longer be challenged, and the plugin never works one out itself.

## Fees

Connection's "Fees" row shows Polymarket's published taker fee rate by
market category, as read from its fees page (docs.polymarket.com/trading/fees)
on 2026-10-26: a taker pays the rate times the shares times p x (1 - p), at
a price p; makers pay none; Geopolitics markets are fee-free, and every
combo pays the Combos rate. Polymarket also states each market's own fee,
which can differ from its category's row and applies to that market. The
options sample's fee schedule takes these rates with this source and date;
a later schedule is read again at the plugin's next version.

## Events

For each outcome token it serves, the plugin also reports the Polymarket
event its market belongs to: the event's markets, by their YES tokens, and
what Polymarket states of them. In a negative-risk event exactly one market
resolves YES, so its markets are reported mutually exclusive and covering
every result. Where Polymarket may name more outcomes later (an "Other"
market), they are reported mutually exclusive, but whether they cover every
result is reported as not stated, never as no; an event without negative
risk states neither. Your deployment keeps the group beside its instrument
records and asks the platform to match it; a change makes a new version.

## What it never makes up

- A figure is recorded exactly as Polymarket stated it, never rounded and
  never through a float.
- A side of the book with no order is left empty, never zero.
- Nothing is recorded for a day already past: Polymarket's public reads
  answer now.

## What it keeps

Polymarket's answers, as received, in the storage your deployment gives the
plugin, for 30 days by default, each price naming the answer it came from.
Past that window, a day's answers are archived, kept or deleted as you set
it. Its live dataset's default licence keeps its rows two days; its outcomes
dataset is kept.
