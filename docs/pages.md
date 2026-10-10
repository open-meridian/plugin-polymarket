# Pages

Both pages are under **Manage**, for the plugin's admin. Neither shows a
price, a side of the book or a size.

## Connection

How the plugin reaches Polymarket: whether it answers from Polymarket or from
synthetic responses, its two endpoints (Gamma, for a token's market, and the
CLOB, for its book), what the plugin spends of Polymarket's limits (at most
5 requests a second), how many calls it made, how many met a rate limit or
failed, the last error, and the venue's ID in the platform's venue master,
or that your deployment does not hold it.

## Datasets

What the plugin serves: its dataset, with its data, modes, day and default
licence; how many tokens are mapped for the instruments the lake asked
about, and how many it did not serve and why; the asset its prices and
payouts are in (Polymarket's USDC), your deployment's record for it, and
what each token pays; what Polymarket entitles it to (public data, no key);
and the wants the lake sent it, those it keeps current first, each with how
many rows it recorded and subjects it declined. The search above the wants
narrows them.

## Tools for agents

Each page is a read tool answering what the page shows: `read_connection` and
`read_datasets`, for a person holding admin on the plugin.
