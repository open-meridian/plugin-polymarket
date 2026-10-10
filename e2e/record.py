"""Record Polymarket's real answers for `make e2e-recorded`: the plugin's own client
asks Polymarket's public reads -- no key -- for each outcome token named, and keeps every
answer as the plugin keeps its raw records, under a directory of its own.

Run in the plugin's image, which carries the package and the SDK, writing
into recordings/ (git-ignored: a recording is the developer's who made it,
never committed; the plan's Q11):

    make image
    docker run --rm --entrypoint python -v "$PWD/e2e":/e2e:ro \\
        -v "$PWD/recordings":/recordings polymarket:local /e2e/record.py TOKEN [TOKEN ...]
    make e2e-recorded RECORDED=recordings/<the directory it printed>

Each token's market, its book twice a second apart and its last trade are
asked; a token Polymarket knows nothing by is kept as its answer. Standard library
and the plugin only.
"""

import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from polymarket.raw import RawStore
from polymarket.venue import Polymarket, VenueError


def main(tokens):
    if not tokens:
        print("name at least one Polymarket outcome token's ID", file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path("/recordings") / stamp
    client = Polymarket(RawStore(root))
    for token in tokens:
        for ask in (client.market, client.book, client.last_trade):
            try:
                ask(token)
            except VenueError as refused:
                print(f"{token}: {refused}", file=sys.stderr)
        time.sleep(1)
        try:
            client.book(token)
        except VenueError as refused:
            print(f"{token}: {refused}", file=sys.stderr)
    print(f"recordings/{stamp}: {client.health.calls} answers kept")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
