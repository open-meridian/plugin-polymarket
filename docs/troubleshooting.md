# Troubleshooting

## Polymarket is not answering

The Connection page's status says so, with the last error. The plugin waits
out a rate limit and tries again. Check the deployment can reach
gamma-api.polymarket.com and clob.polymarket.com.

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
- **Its record states another payout**: the record's payout is not one in
  Polymarket's USDC. Correct it on the Instruments page if it is
  Polymarket's token.
- **Its record could not be read**: the deployment does not let the plugin
  read an instrument's record (a runtime before contract v18's ruling of
  2026-10-10).

## Not resolved: USDC

Two of your deployment's records carry Polymarket's USDC code. Merge them on
the Instruments page; nothing is priced until it resolves to one record.
