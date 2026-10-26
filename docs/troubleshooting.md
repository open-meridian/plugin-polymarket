# Troubleshooting

## Polymarket is not answering

The Connection page's status says so, with the last error. The plugin waits
out a rate limit and tries again. Check the deployment can reach
gamma-api.polymarket.com, clob.polymarket.com and data-api.polymarket.com.

## Polygon RPC: no answer

With a Polygon RPC URL set, a failed on-chain read shows as the last error
("Polygon RPC: ..."), never with the URL, and the market is read again on
its next pass: the proposal is recorded once the RPC answers. Check the URL
with your provider, and that the deployment can reach it.

## No bars for a contract

Bars are built from the contract's trades: an hour or a day it did not
trade in has no bar, and one still open is kept once it closes (each pass is
five minutes). A market trading very heavily keeps the intervals its first
read reached back to, at most 20 pages of trades.

## Venue master: not held

Your deployment does not hold Polymarket in the platform's venue master by
its code. Each price is recorded with its venue left empty and Polymarket
named as reported, and the plugin asks again the next day.

## A subject not served

The Datasets page says why for each:

- **Its record names none of the venue's binary event contracts**: the
  record carries no Polymarket token ID (nor another source's symbol that is
  one), or the token's market does not have two outcomes. Add the token's
  ID as a `symbol` with source `polymarket` on the Instruments page.
- **Its record states another payout**: the record's payout is not one
  pUSD. Correct it on the Instruments page if it is Polymarket's token.
  A record completed before 0.9.0 may state one in a USDC record of the
  deployment's own: from 0.9.0 the plugin's cash is pUSD.
- **Its record could not be read**: the deployment does not let the plugin
  read an instrument's record (a runtime before contract v18's ruling of
  2026-10-10).

## Not resolved: PUSD

The plugin names pUSD by its address on Polygon (its CAIP-19), which the
platform's record of pUSD carries. If your deployment holds no record with
it, or two, nothing is priced until it resolves to one: ask the platform
for pUSD's record, or merge the two, on the Instruments page.
