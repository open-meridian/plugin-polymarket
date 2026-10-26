"""What this version declares beside its role (W8.1, W4.1; contract v19).

**Its catalogue** (spec/the-lake, "The catalogue"; the plan's Q21), declared
from code and read the same way at registration and by `meridian plugin
upload`:

- `live`: each outcome token's last trade price and best bid and offer as
  prices, and its best bid and offer with their sizes as a quote, at most
  once a second per subject, pulled for the latest or kept current for a
  standing want. Its day is the UTC day (`day_time_zone` `Etc/UTC`,
  `day_end_minute` 0): Polymarket trades around the clock and states no
  close.
- `outcomes` (contract v23): each outcome token's outcome once Polymarket
  has resolved its market, final, recorded unasked (`push`) for each token a
  subject the lake asked for is, a token past its market's end read again
  each minute until its outcome is recorded -- from 0.11.0 its proposed and
  disputed stages too, where the deployment admin entered a Polygon RPC URL
  (ruling 622). It names no business date; its day is declared as the live
  dataset's.
- `bars` (from 0.11.0; rulings 624, 625 and 629): each outcome token's
  hourly and daily bars, built from Polymarket's public trades (its data
  API), each trade's wallet and names dropped before anything is kept, its
  trades counted (`meridian.v1.Bar.trade_count`) and no volume-weighted
  price. Kept by the SDK's `Feed.keep_bars` for each contract served --
  every closed hour and UTC day, first read 30 days back -- recorded
  unasked (`push`), and a want of `bars` answered from the trades
  (`pull`). Its day is the UTC day, as the live dataset's.

**Its licence defaults**: `live` keeps its rows two days (the plan's Q21 for
a live dataset). `bars` is kept: a closed interval's bar does not change.
`outcomes` is kept: an outcome is read back by the version
in force or as of a time, which a dataset not kept cannot answer (a plugin's
choice within contract v23, approved 2026-10-13). Neither default claims
anything about Polymarket's terms, which the deployment admin settles with
whoever uses the deployment; the admin states the deployment's licence on
the Data sources page, which replaces it.

`venue_id` is empty: the venue master's ID for Polymarket is minted by the
platform, not known to the code a catalogue is declared from, so each row
names the venue by the ID it resolves at run time (the SDK's
`meridian.roles.data.event_contracts.Feed`), by Polymarket's
code.

**Its storage**: one kind of raw record, Polymarket's responses as received,
kept a month by default (`KIND`, kept by the SDK's
`meridian.edge.RawStore`); the SDK declares the kind's two window settings.
**Its settings**: from 0.11.0 the Polygon RPC URL (`polygon_rpc_url`,
ruling 629), a secret the deployment admin enters, through which UMA's
oracle is read for a proposal's and a dispute's answer (uma.py) -- an RPC's
URL often carries its provider's key, so it is never logged, kept or shown;
then sample data, a developer's (synthetic.py). Polymarket's public market
data needs no key.
"""

import meridian
from meridian import DatasetDeclaration, DatasetLicence

VENDOR = "Polymarket"
SAMPLE_DATA = "sample_data"
POLYGON_RPC_URL = "polygon_rpc_url"

#: Its one kind of raw record, Polymarket's responses as received: a month of
#: them by default, enough to re-convert a row a person questions. An admin
#: sets the window in Settings.
KIND = "responses"
LABEL = "Raw responses"
WINDOW_DAYS = 30

#: Its settings, in the data role's order (spec/plugin-pages-follow-their-role):
#: no environment and no credential -- Polymarket's public market data has one
#: environment and needs no key -- then the Polygon RPC URL, a secret, and
#: last sample data, a developer's.
SETTINGS = [
    meridian.Setting(
        POLYGON_RPC_URL,
        str,
        secret=True,
        label="Polygon RPC URL",
        description=(
            "A Polygon JSON-RPC endpoint the plugin reads UMA's oracle through, read only, for "
            "a market's proposed and disputed stages and its challenge window's end. Without "
            "it, outcomes are recorded once final."
        ),
    ),
    meridian.sample_data(
        description=(
            "Answer from built-in made-up Polymarket responses, or a developer's recorded ones, "
            "instead of calling Polymarket. Development deployments only."
        )
    ),
]

CATALOGUE = [
    DatasetDeclaration(
        key="live",
        vendor=VENDOR,
        data_types=["meridian.v1.Price", "meridian.v1.Quote"],
        modes=["pull", "stream"],
        cadence=1,
        history=0,
        licence_default=DatasetLicence(kept=True, retention_days=2),
        day_time_zone="Etc/UTC",
        day_end_minute=0,
    ),
    DatasetDeclaration(
        key="outcomes",
        vendor=VENDOR,
        data_types=["meridian.v1.Outcome"],
        modes=["push"],
        cadence=60,
        history=0,
        licence_default=DatasetLicence(kept=True),
        day_time_zone="Etc/UTC",
        day_end_minute=0,
    ),
    DatasetDeclaration(
        key="bars",
        vendor=VENDOR,
        data_types=["meridian.v1.Bar", "meridian.v1.Bar.trade_count"],
        modes=["pull", "push"],
        cadence=300,
        history=30,
        licence_default=DatasetLicence(kept=True),
        day_time_zone="Etc/UTC",
        day_end_minute=0,
    ),
]
#: The `bars` dataset's declaration, which says the day a daily bar is in.
BARS = CATALOGUE[2]
