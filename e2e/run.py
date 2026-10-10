"""`make e2e` and `make e2e-recorded`: the plugin end to end on core's plugin
harness (contract v19), in synthetic mode, beside a reader (e2e/reader.py).

1. Launched: the plugin registers its catalogue; the deployment admin's tool
   lists its one dataset, `live`, of prices and quotes, on the UTC day ending
   at 00:00, pulled or streamed, its default licence kept two days.
2. Synthetic mode on: nothing is asked of the venue and no record minted
   until the lake wants something -- never the venue's list. The reader then
   names an outcome token as a custodian's book holds it, by the custodian's
   own symbol, and a token of a market of three outcomes the same way.
3. Licensed and entitled: the admin sets the dataset's licence -- kept two
   days, as the default says -- and entitles the reader to it.
4. Prices wanted and recorded: the reader follows the token and reads its
   latest; the lake asks the plugin, which reads the record (W3.6), names it
   Polymarket's token by the custodian's symbol, joins the token's ID to it
   with the class, type and Polymarket's words offered, resolves Polymarket's
   own USDC instrument -- the one record it mints -- and records the token's
   last trade, best bid and offer in USDC on that instrument, never the
   dollar, exactly as stated; the reader reads and hears them, each naming
   its raw record and the venue as reported.
5. Quotes wanted and recorded: the reader reads its latest quote; the
   plugin records its best bid and offer with their sizes, read and heard.
6. Declined: the token of a market of three outcomes is declined as not
   covered.
7. Parity: the plugin's two read tools answer through the deployment's MCP
   what its two pages show: one contract mapped, its payout of one USDC on
   Polymarket's USDC record.
8. Its raw responses are in its granted storage, and `store lake` prints
   each row kept, numbered with no holes, the wants asked, answered, declined
   and withdrawn, and the venue's miss.

`make e2e-recorded` (`--recorded=DIR`) runs the same on a developer's
recording of Polymarket's real answers (e2e/record.py), naming the first
token of a binary market it holds, and holds each row to its shape rather
than to the synthetic exchange's values.

Run from the repository's root by the Makefile, which builds the image,
copies the harness out and writes the plugins' compose file first, and
exports what the compose files read. Standard library only.
"""

import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
from decimal import Decimal

VENUE = "polymarket"
NAME = "Polymarket"
DATASET = f"{VENUE}:live"
LOG = ".e2e/runner.log"
RECORDED = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--recorded=")]
EXACT = not RECORDED
COMPOSE = ["docker", "compose", "-p", f"{VENUE}-e2e", "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml",
           *[a for a in sys.argv[1:] if not a.startswith("--recorded=")]]
#: The synthetic exchange's outcome token (a final's YES), what its book
#: states, and a token of a market of three outcomes, which is not binary.
CONTRACT = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
NOT_BINARY = "30000000000000000000000000000000000000000000000000000000000000000000000000041"
STATED = {"PRICE_KIND_LAST": "0.440", "PRICE_KIND_BID": "0.43", "PRICE_KIND_ASK": "0.45"}
QUOTE = {"bid_amount": "0.43", "bid_quantity": "550.5", "ask_amount": "0.45",
         "ask_quantity": "125.25"}


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True, timeout=600)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def read(path):
    return json.loads(page("reader", "read", path))


def call(tool, arguments, *outcomes):
    done = runner("mcp", "call", tool, json.dumps(arguments), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}") from None
    must(answer.get("outcome") in outcomes,
         f"{tool} answered {answer.get('outcome')}, not {outcomes}: {done.stdout[-700:]}")
    return answer


def recorded_contract(directory):
    """The first token of a binary market a recording holds, by its ID."""
    for path in sorted(pathlib.Path(directory).rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("call") == "market" and record.get("status") == 200:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(record["request"]["url"]).query)
            token = query.get("clob_token_ids", [""])[0]
            for market in json.loads(record["body"]):
                if token in market.get("clobTokenIds", "") and len(
                        json.loads(market.get("outcomes", "[]"))) == 2:
                    return token
    raise Failed(f"no binary market's token is recorded under {directory}")


def run():
    started = time.time()
    contract = recorded_contract(RECORDED[0]) if RECORDED else CONTRACT
    compose("down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    for instance in (VENUE, "reader"):
        runner("ready", "--instance", instance)
    runner("grant", "--instance", "reader", "--level", "read", "--role", "reporting")
    runner("grant", "--instance", VENUE, "--level", "admin")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", f"{VENUE}:admin")
    tools = runner("mcp", "list").split()
    named = {t.rsplit("__", 1)[-1]: t for t in tools}
    for name in ("dashboard__list_datasets", "read_connection", "read_datasets"):
        must(name.rsplit("__", 1)[-1] in named, f"step 1, {name} is listed: {tools}")

    # 1. The catalogue, as the deployment admin's tool lists it.
    def datasets():
        held = {d["dataset"]: d for d in
                call("dashboard__list_datasets", {}, "read")["data"]["datasets"]}
        return held if DATASET in held else None
    held = until(90, datasets, "step 1, the dataset was not listed")
    entry, licence = held[DATASET]["catalogue_entry"], held[DATASET]["licence"]
    must(entry["modes"] == ["pull", "stream"] and entry["day_time_zone"] == "Etc/UTC"
         and entry.get("day_end_minute", 0) == 0, f"step 1, its entry: {entry}")
    must(licence["kept"] is True and licence["retention_days"] == 2
         and licence["set_by_the_deployment"] is False,
         f"step 1, its default licence kept two days: {licence}")

    # 2. Synthetic mode: nothing asked, nothing minted; then the reader's
    # records, as a custodian's book holds them.
    runner("settings", "--instance", VENUE, "synthetic=true")
    served = until(90, lambda: call(named["read_datasets"], {}, "read", "unchanged")["data"],
                   "step 2, read_datasets did not answer")
    connection = call(named["read_connection"], {}, "read", "unchanged")["data"]
    must(served["contracts_read"] == 0 and connection["calls"] == 0,
         f"step 2, nothing read of the venue before a want: {served}, {connection}")
    listed = runner("instruments")
    log("instruments, before any want:\n" + listed)
    must(f"({VENUE})" not in listed and contract not in listed,
         f"step 2, no record minted before a want: {listed}")
    for name, scheme, value, source in (("contract", "symbol", contract, "e2e-custodian"),
                                        ("range", "symbol", NOT_BINARY, "e2e-custodian")):
        query = urllib.parse.urlencode({"name": name, "scheme": scheme, "value": value,
                                        "source": source})
        ids = read(f"/resolve?{query}")
    subject, ranged = ids["contract"], ids["range"]

    # 3. Licensed as the default says, and entitled.
    runner("licence", DATASET, "kept=true", "retention_days=2", "display=true",
           "personal_use=false", "note=Kept two days, for the e2e's reader.")
    runner("entitle", "--instance", "reader", DATASET, "note=The e2e's reader.")

    # 4. Prices wanted, recorded, read and heard.
    read(f"/follow?subject={subject}")
    first = read(f"/prices?subject={subject}&dataset={DATASET}")
    # The lake asks the plugin at once: unanswered as asked or, where the
    # plugin's answer is already in, the rows it recorded.
    must(first["unanswered"] or first["prices"],
         f"step 4, a price not recorded is asked of the plugin: {first}")

    def heard(row, kinds):
        rows = [h for h in read("/heard")["heard"]
                if h["row"] == row and h["dataset"] == DATASET and h["subject"] == subject]
        return rows if {h.get("kind", "") for h in rows} >= kinds else None
    prices = until(90, lambda: heard("price", set(STATED) if EXACT else set()),
                   "step 4, the prices were not heard")
    served = call(named["read_datasets"], {}, "read", "unchanged")["data"]
    usdc = served["cash_instrument"]
    must(usdc and served["cash"] == "USDC", f"step 4, Polymarket's USDC resolved: {served}")
    kept = until(60, lambda: read(f"/prices?subject={subject}&dataset={DATASET}")["prices"],
                 "step 4, the prices kept were not read")
    must({r["kind"] for r in kept} <= set(STATED), f"step 4, the latest read: {kept}")
    for row in prices + kept:
        amount = Decimal(row["amount"])
        must((row["amount"] == STATED[row["kind"]] or not EXACT) and 0 <= amount <= 1,
             f"step 4, {row['kind']} per token as Polymarket stated it: {row}")
        must(row["instrument_id"] == usdc and row["currency_code"] == "",
             f"step 4, in Polymarket's USDC, never a currency: {row}")
        must(row["venue_id"] == "" and row["unconverted"] == [f"{VENUE}:venue"]
             and row["raw"].startswith("responses/") and not row["business_date"],
             f"step 4, the venue not held named as reported, its raw record: {row}")
    listed = runner("instruments")
    log("instruments, after the want:\n" + listed)
    joined = [line for line in listed.splitlines() if line.startswith(subject)]
    must(joined and f"symbol ({VENUE}): {contract}" in joined[0],
         f"step 4, the token joined to the custodian's record: {listed}")
    must(sum(1 for line in listed.splitlines() if "USDC" in line) <= 1,
         f"step 4, one record minted, Polymarket's USDC: {listed}")

    # 5. Quotes wanted, recorded, heard.
    read(f"/quotes?subject={subject}&dataset={DATASET}")
    quotes = until(90, lambda: heard("quote", {""}), "step 5, the quote was not heard")
    quote = quotes[-1]
    must("bid_amount" in quote or "ask_amount" in quote, f"step 5, a side quoted: {quote}")
    for field, stated in QUOTE.items():
        must(not EXACT or quote.get(field) == stated,
             f"step 5, the quote's {field} as stated: {quote}")
    must(quote.get("bid_instrument_id", usdc) == quote.get("ask_instrument_id", usdc) == usdc
         and not quote.get("bid_currency_code") and not quote.get("ask_currency_code"),
         f"step 5, the quote in Polymarket's USDC: {quote}")

    # 6. Declined: a market of three outcomes is not binary.
    read(f"/prices?subject={ranged}&dataset={DATASET}")

    # 7. Parity: each read tool answers what its page shows.
    connection = call(named["read_connection"], {}, "read", "unchanged")["data"]
    mode = "synthetic" if EXACT else "recorded"
    must(connection["mode"] == mode and connection["venue"] == NAME
         and connection["venue_held"] is False and connection["calls"] > 0,
         f"step 7, read_connection: {connection}")
    shown = page(VENUE, "admin", "/")
    must(f"{mode.capitalize()}: answers from files" in shown and NAME in shown,
         "step 7, the Connection page shows the same")
    served = call(named["read_datasets"], {}, "read", "unchanged")["data"]
    must([d["dataset"] for d in served["datasets"]] == [DATASET]
         and served["contracts_mapped"] == 1 and served["subjects_named"] == 1
         and served["cash"] == "USDC" and served["cash_instrument"] == usdc
         and served["payouts"] == ["1 USDC"] and served["recorded"] >= 3,
         f"step 7, read_datasets: {served}")
    shown = page(VENUE, "admin", "/datasets")
    must("1 contract mapped for 1 subject" in shown and "each contract pays 1 USDC" in shown,
         "step 7, the Datasets page shows the same")

    # 8. Raw responses kept, and the lake's record.
    kept = compose("exec", "-T", VENUE, "python", "-c",
                   "from meridian import edge; "
                   "print(sum(1 for p in (edge.storage_dir() / 'responses').rglob('*') if p.is_file()))")
    must(int(kept.stdout.strip() or 0) >= 3, f"step 8, raw responses in storage: {kept.stdout}")
    names = {subject: "CONTRACT", ranged: "RANGE", usdc: "USDC"}

    def lake():
        lines = compose("run", "--rm", "-T", "store", "lake").stdout.split("\n")
        for instrument_id, name in names.items():
            lines = [line.replace(instrument_id, name) for line in lines]
        withdrawn = any(line.startswith(f"want|{DATASET}|withdrawn|") for line in lines)
        declined = any(line.startswith(f"want|{DATASET}|declined|RANGE|") for line in lines)
        return lines if withdrawn and declined else None
    lines = until(240, lake, "step 8, the standing want was not withdrawn, or the range not "
                             "declined")
    log("store lake:\n" + "\n".join(lines))
    rows = [line.split("|") for line in lines if line.startswith(f"row|{DATASET}|")]
    sequences = sorted(int(row[3]) for row in rows)
    must(sequences == list(range(1, len(sequences) + 1)) and len(sequences) >= (4 if EXACT else 2),
         f"step 8, the rows kept numbered from 1 with no holes: {sequences}")
    must({row[6] for row in rows} == {"CONTRACT"} and all(row[9] == "" for row in rows),
         f"step 8, each row the token's, with no business date: {rows}")
    must(any(line.startswith(f"want|{DATASET}|asked|CONTRACT|") for line in lines),
         f"step 8, the want asked: {lines}")
    must(any(line.startswith(f"miss|{VENUE}|") for line in lines),
         f"step 8, the venue's miss counted: {lines}")

    print(f"e2e OK in {int(time.time() - started)}s: on core's plugin harness, the live "
          "dataset of prices and quotes listed by the deployment admin's tool, kept two days "
          "by default; nothing asked of Polymarket and no record minted before a want; a "
          "custodian's outcome token, known by its own symbol, read and named, the token's ID "
          "joined to it, and its last trade, bid and offer recorded per token on Polymarket's "
          "own USDC instrument, never the dollar, read and heard; its quote with sizes; the "
          "token of a market of three outcomes declined as not covered; read_connection and "
          "read_datasets answering what the pages show, the payout one USDC; raw responses "
          "in storage; and `store lake` numbering each row with no holes, the wants and the "
          "miss")


def main():
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError) as failed:
        print(f"e2e FAILED: {failed}; the run is in {LOG}, the components' logs in "
              ".e2e/components.log", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
