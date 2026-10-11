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

**Its licence default keeps its rows two days** (the plan's Q21 for a live
dataset). The default claims nothing about Polymarket's terms, which the
deployment admin settles with whoever uses the deployment; the admin states
the deployment's licence on the Data sources page, which replaces this one.

`venue_id` is empty: the venue master's ID for Polymarket is minted by the
platform, not known to the code a catalogue is declared from, so each row
names the venue by the ID it resolves at run time (dgm.py), by Polymarket's
code.

**Its storage**: one kind of raw record, Polymarket's responses as received,
kept a month by default (raw.py); the SDK declares the kind's two window
settings. **Its settings**: sample data, a developer's (synthetic.py). No
secret: Polymarket's public market data needs no key.
"""

import meridian
from meridian import DatasetDeclaration, DatasetLicence, Declaration, RecordKind, Storage

from .raw import KIND, LABEL, WINDOW_DAYS

VENDOR = "Polymarket"
SAMPLE_DATA = "sample_data"

#: Its settings, in the data role's order (spec/plugin-pages-follow-their-role):
#: no environment and no credential -- Polymarket's public market data has one
#: environment and needs no key -- so only sample data, a developer's.
SETTINGS = [
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
]

DECLARATION = Declaration(
    settings=SETTINGS,
    storage=Storage(kinds=[RecordKind(KIND, LABEL, window_days=WINDOW_DAYS)]),
    catalogue=CATALOGUE,
)
