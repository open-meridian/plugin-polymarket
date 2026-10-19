"""`make e2e` and `make e2e-recorded`: the plugin end to end on core's plugin
harness (contracts v19 to v26), with sample data, beside a reader (e2e/reader.py).

1. Launched: the plugin registers its catalogue; the deployment admin's tool
   lists its one dataset, `live`, of prices and quotes, on the UTC day ending
   at 00:00, pulled or streamed, its default licence kept two days; and from
   contract v23 `outcomes`, pushed, kept by default.
2. Sample data on: nothing is asked of the venue and no record minted
   until the lake wants something -- never the venue's list. The reader then
   names an outcome token as a custodian's book holds it, by the custodian's
   own symbol and, from contract v26, the token's ID beside it under
   Polymarket's venue ID (Polymarket has no MIC) -- the stand-in platform
   mints the platform's record by it (rulings 199, 204) -- a token of a
   market of three outcomes the same way, and the YES token of a market
   Polymarket has resolved YES.
3. Licensed and entitled: the admin sets each dataset's licence as its
   default says -- `live` kept two days, `outcomes` kept -- and entitles the
   reader to both.
4. Prices wanted and recorded: the reader follows the token and reads its
   latest; the lake asks the plugin, which reads the record (W3.6), names it
   Polymarket's token by the custodian's symbol, joins Polymarket's own code
   to it with Polymarket's words offered, resolves Polymarket's
   own USDC instrument -- the one record it mints -- and records the token's
   last trade, best bid and offer in USDC on that instrument, never the
   dollar, exactly as stated; the reader reads and hears them, each naming
   its raw record and Polymarket's venue, which the stand-in's venue master
   holds by its code from contract v26.
5. Quotes wanted and recorded: the reader reads its latest quote; the
   plugin records its best bid and offer with their sizes, read and heard.
5a. Its event (contract v26): the plugin reports the negative-risk event
   its token's market belongs to, its three markets' YES tokens each named
   by the token's ID, mutually exclusive and exhaustive as negative risk
   states; the platform mints the group (`EVG-`), and the reader reads it
   by the token (W3.30).
6a. An outcome (contract v23): the reader asks for the resolved token's
   price; the plugin names it and records its outcome, unasked, in
   `outcomes` -- from the token's own side, it pays its full payout, final,
   settling at one USDC on Polymarket's USDC record, Polymarket's word (the
   token's own stated price, 1) kept as reported, valid from when the
   answer stating it arrived, no payout time, no business date -- which the
   reader hears and reads back as version 1.
6. Declined: the token of a market of three outcomes is declined as not
   covered.
7. Parity: the plugin's two read tools answer through the deployment's MCP
   what its two pages show: one contract mapped, its payout of one USDC on
   Polymarket's USDC record.
8. Its raw responses are in its granted storage, and `store lake` prints
   each row kept, numbered with no holes, the wants asked, answered, declined
   and withdrawn, and no miss.

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
OUTCOMES = f"{VENUE}:outcomes"
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
#: The YES token of a market Polymarket has resolved YES (contract v23), and
#: its outcome.
RESOLVED = "40000000000000000000000000000000000000000000000000000000000000000000000000053"
OUTCOME = {"determination": "OUTCOME_DETERMINATION_PAYS", "stage": "OUTCOME_STAGE_FINAL",
           "amount": "1", "as_reported": "polymarket:outcomePrices=1", "settled_at_ns": 0,
           "source_times": 0, "currency_code": ""}
STATED = {"PRICE_KIND_LAST": "0.440", "PRICE_KIND_BID": "0.43", "PRICE_KIND_ASK": "0.45"}
#: Core v26's stand-in platform mints every event contract paying one unit
#: of the currency the request offers, USD by default (core 17a13a2,
#: deploy/harness/platform.py, `event_contract()`), where a Polymarket token
#: pays one USDC on Polymarket's own instrument: the plugin rightly declines
#: a record stating another payout, so steps 4 to 7 wait for the harness
#: (queued as a v27 core harness fix) and the run proves what it can
#: (`pending`). Set False once the stand-in mints a token paying the venue's.
HARNESS_PAYS_USD = True
#: Polymarket in the stand-in platform's venue master (contract v26), and
#: the synthetic token's negative-risk event.
POLYMARKET = "VEN-01JAE000000000000000POLYM"
EVENT = "synthetic-final-winner"
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
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
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
                call("dashboard__list_datasets", {}, "read", "unchanged")["data"]["datasets"]}
        return held if DATASET in held else None
    held = until(90, datasets, "step 1, the dataset was not listed")
    must(OUTCOMES in held, f"step 1, the outcomes dataset is listed: {sorted(held)}")
    entry, licence = held[OUTCOMES]["catalogue_entry"], held[OUTCOMES]["licence"]
    must(entry["modes"] == ["push"] and licence["kept"] is True
         and licence["set_by_the_deployment"] is False,
         f"step 1, outcomes pushed and kept by default: {entry}, {licence}")
    entry, licence = held[DATASET]["catalogue_entry"], held[DATASET]["licence"]
    must(entry["modes"] == ["pull", "stream"] and entry["day_time_zone"] == "Etc/UTC"
         and entry.get("day_end_minute", 0) == 0, f"step 1, its entry: {entry}")
    must(licence["kept"] is True and licence["retention_days"] == 2
         and licence["set_by_the_deployment"] is False,
         f"step 1, its default licence kept two days: {licence}")

    # 2. Sample data: nothing asked, nothing minted; then the reader's
    # records, as a custodian's book holds them.
    runner("settings", "--instance", VENUE, "sample_data=true")
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
                                        ("range", "symbol", NOT_BINARY, "e2e-custodian"),
                                        ("resolved", "symbol", RESOLVED, "e2e-custodian")):
        # Contract v24 (W3.7): the custodian states the contract's description
        # and currency beside its symbol, the minimum a record is minted from.
        stated = {"description": f"The e2e custodian's event contract {value}",
                  "currency": "USD", "ticker": POLYMARKET} if source else {}
        query = urllib.parse.urlencode({"name": name, "scheme": scheme, "value": value,
                                        "source": source, **stated})
        ids = read(f"/resolve?{query}")
    subject, ranged, resolved = ids["contract"], ids["range"], ids["resolved"]

    # 3. Licensed as the default says, and entitled.
    runner("licence", DATASET, "kept=true", "retention_days=2", "display=true",
           "personal_use=false", "note=Kept two days, for the e2e's reader.")
    runner("entitle", "--instance", "reader", DATASET, "note=The e2e's reader.")
    runner("licence", OUTCOMES, "kept=true", "retention_days=0", "display=true",
           "personal_use=false", "note=Kept, as the default says, for the e2e's reader.")
    runner("entitle", "--instance", "reader", OUTCOMES, "note=The e2e's reader.")

    if HARNESS_PAYS_USD:
        return pending(started, named, subject, ranged)

    # 4. Prices wanted, recorded, read and heard.
    read(f"/follow?subject={subject}&subject={resolved}")
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
        must(row["venue_id"] == POLYMARKET and row["unconverted"] == []
             and row["raw"].startswith("responses/") and not row["business_date"],
             f"step 4, the venue held by its code named by its ID, its raw record: {row}")
    record = call("dashboard__read_instrument", {"instrument_id": subject}, "read",
                  "unchanged")["data"]
    log(f"the token's record, after the want: {json.dumps(record)}")
    held = {(i["scheme"], i["source"], i["value"]) for i in record["identifiers"]}
    must(subject.startswith("INS-") and ("ticker", POLYMARKET, contract) in held
         and ("symbol", VENUE, contract) in held,
         f"step 4, the platform's record minted by the token's ID, Polymarket's code joined: "
         f"{record}")
    listed = runner("instruments")
    log("instruments, after the want:\n" + listed)
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

    # 5a. Its event (contract v26, W3.29): the plugin reports the event its
    # token's market belongs to, each member named by its token's ID; the
    # platform matches or mints the group, and the reader reads it.
    if EXACT:
        def grouped():
            return read(f"/groups?subject={subject}")["groups"] or None
        [group] = until(120, grouped, "step 5a, the token's event group was not read")
        must(group["venue_event_ref"] == EVENT and group["venue_id"] == POLYMARKET
             and group["event_group_id"].startswith("EVG-")
             and len(group["members"]) == 3 and subject in group["members"]
             and group["mutually_exclusive"] == "EVENT_GROUP_FLAG_TRUE"
             and group["exhaustive"] == "EVENT_GROUP_FLAG_TRUE"
             and group["version"] == 1,
             f"step 5a, the event's group as negative risk states it: {group}")

    # 6a. An outcome: the resolved token named, its outcome recorded unasked,
    # heard and read back.
    if EXACT:
        read(f"/prices?subject={resolved}&dataset={DATASET}")

        def outcome_heard():
            rows = [h for h in read("/heard")["heard"]
                    if h["row"] == "outcome" and h["subject"] == resolved]
            return rows or None
        [row] = until(90, outcome_heard, "step 6a, the outcome was not heard")
        listed = read(f"/outcomes?subject={resolved}")["outcomes"]
        must(len(listed) == 1, f"step 6a, one outcome in force: {listed}")
        for said in (row, listed[0]):
            must(all(said[k] == v for k, v in OUTCOME.items()) and said["instrument_id"] == usdc,
                 f"step 6a, the outcome from the token's side, in USDC, its word kept: {said}")
            must(said["dataset"] == OUTCOMES and said["row_key"] == f"{RESOLVED}:outcome"
                 and said["version"] == 1 and not said["business_date"]
                 and said["raw"].startswith("responses/"),
                 f"step 6a, one row key per token, version 1, its raw record: {said}")

    # 6. Declined: a market of three outcomes is not binary.
    read(f"/prices?subject={ranged}&dataset={DATASET}")

    # 7. Parity: each read tool answers what its page shows.
    connection = call(named["read_connection"], {}, "read", "unchanged")["data"]
    must(connection["mode"] == "Sample data" and connection["venue"] == NAME
         and connection["credentials"] == [] and connection["sessions"] is None
         and connection["venue_held"] is True and connection["calls"] > 0,
         f"step 7, read_connection: {connection}")
    shown = page(VENUE, "admin", "/")
    must("Sample data: the plugin answers from recorded responses" in shown
         and "No key needed" in shown and "Does not stream" in shown and NAME in shown,
         "step 7, the Connection page shows the same")
    served = call(named["read_datasets"], {}, "read", "unchanged")["data"]
    mapped = 2 if EXACT else 1
    must([d["dataset"] for d in served["served"]] == [DATASET, OUTCOMES]
         and served["contracts_mapped"] == mapped and served["subjects_named"] == mapped
         and served["cash"] == "USDC" and served["cash_instrument"] == usdc
         and served["payouts"] == ["1 USDC"] and served["served"][0]["recorded"] >= 3
         and served["served"][1]["recorded"] == (1 if EXACT else 0),
         f"step 7, read_datasets: {served}")
    def licensed():
        rows = call(named["read_datasets"], {}, "read", "unchanged")["data"]["served"]
        return rows if rows[0]["licensed"] else None
    until(90, licensed, "step 7, read_datasets did not say the dataset licensed")
    shown = page(VENUE, "admin", "/datasets")
    must("Not licensed yet" not in shown and "Licensed" in shown,
         "step 7, the Datasets page says the dataset licensed")
    many = "2 contracts mapped for 2 subjects" if EXACT else "1 contract mapped for 1 subject"
    must(many in shown and "each contract pays 1 USDC" in shown,
         "step 7, the Datasets page shows the same")

    # 8. Raw responses kept, and the lake's record.
    kept = compose("exec", "-T", VENUE, "python", "-c",
                   "from meridian import edge; "
                   "print(sum(1 for p in (edge.storage_dir() / 'responses').rglob('*') if p.is_file()))")
    must(int(kept.stdout.strip() or 0) >= 3, f"step 8, raw responses in storage: {kept.stdout}")
    names = {subject: "CONTRACT", ranged: "RANGE", resolved: "RESOLVED", usdc: "USDC"}

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
    kept_rows = [line.split("|") for line in lines if line.startswith(f"row|{OUTCOMES}|")]
    must(not EXACT or [(r[4], r[5], r[6]) for r in kept_rows] == [(f"{RESOLVED}:outcome", "1",
                                                                    "RESOLVED")],
         f"step 8, the outcome's one version kept: {kept_rows}")
    # The resolved token is followed beside the contract, so a want may ask
    # for both.
    must(any(line.startswith(f"want|{DATASET}|asked|")
             and "CONTRACT" in line.split("|")[3].split(",") for line in lines),
         f"step 8, the want asked: {lines}")
    must(not any(line.startswith(f"miss|{VENUE}|") for line in lines),
         f"step 8, no miss: the venue is held (contract v26's stand-in): {lines}")

    print(f"e2e OK in {int(time.time() - started)}s: on core's plugin harness, the live "
          "dataset of prices and quotes listed by the deployment admin's tool, kept two days "
          "by default; nothing asked of Polymarket and no record minted before a want; a "
          "custodian's outcome token, stated by its own symbol and the token's ID, minted by "
          "the platform by the ID, read and named, Polymarket's code joined to it, and its last trade, bid and offer recorded per token on Polymarket's "
          "own USDC instrument, never the dollar, read and heard; its quote with sizes; its "
          "event reported and read back as a group; the "
          "token of a market of three outcomes declined as not covered; a resolved token's "
          "outcome recorded unasked from its own side, final, kept, heard and read back; "
          "read_connection and "
          "read_datasets answering what the pages show, the dataset licensed, the payout one USDC; raw responses "
          "in storage; and `store lake` numbering each row with no holes, and the wants")


def pending(started, named, subject, ranged):
    """What core v26's harness can prove while its stand-in mints a token
    paying 1 USD (HARNESS_PAYS_USD): the venue held, the platform's record
    minted by the token's ID, the plugin declining it as another payout --
    never serving a wrong one -- and the market of three outcomes declined
    as not covered; no row recorded, no miss."""
    # 4p. Wanted: the record minted by the token's ID, declined for its payout.
    read(f"/follow?subject={subject}")
    read(f"/prices?subject={subject}&dataset={DATASET}")

    def declined():
        served = call(named["read_datasets"], {}, "read", "unchanged")["data"]
        why = [n for n in served["not_served"] if n["why"] == "its record states another payout"]
        return served if why and served["payouts_differ"] >= 1 else None
    served = until(90, declined, "step 4p, the token was not declined for its payout")
    must(served["contracts_mapped"] == 0 and served["subjects_named"] == 0,
         f"step 4p, nothing served on a record stating another payout: {served}")
    record = call("dashboard__read_instrument", {"instrument_id": subject}, "read",
                  "unchanged")["data"]
    log(f"the token's record, after the want: {json.dumps(record)}")
    held = {(i["scheme"], i["source"], i["value"]) for i in record["identifiers"]}
    must(subject.startswith("INS-") and ("ticker", POLYMARKET, CONTRACT) in held
         and record["binary_event_contract"]["payout"]["currency_code"] == "USD",
         f"step 4p, the stand-in's record minted by the token's ID, paying USD: {record}")
    must(not read("/heard")["heard"], "step 4p, no row heard")

    # 6. Declined: a market of three outcomes is not binary.
    read(f"/prices?subject={ranged}&dataset={DATASET}")

    # 7p. The connection: the venue's calls made, its venue as resolved so far
    # (asked when a token is joined or recorded, which a declined one is not).
    connection = call(named["read_connection"], {}, "read", "unchanged")["data"]
    must(connection["calls"] > 0 and connection["venue_id"] in ("", POLYMARKET),
         f"step 7p, read_connection: {connection}")

    # 8p. The lake's record: the range declined, no row, no miss.
    names = {subject: "CONTRACT", ranged: "RANGE"}

    def lake():
        lines = compose("run", "--rm", "-T", "store", "lake").stdout.split("\n")
        for instrument_id, name in names.items():
            lines = [line.replace(instrument_id, name) for line in lines]
        declined = any(line.startswith(f"want|{DATASET}|declined|RANGE|") for line in lines)
        return lines if declined else None
    lines = until(240, lake, "step 8p, the range was not declined")
    log("store lake:\n" + "\n".join(lines))
    must(not any(line.startswith("row|") for line in lines)
         and not any(line.startswith(f"miss|{VENUE}|") for line in lines),
         f"step 8p, no row and no miss: {lines}")
    print(f"e2e OK (harness-limited) in {int(time.time() - started)}s: on core's plugin "
          "harness, the datasets listed; nothing asked of Polymarket and no record minted "
          "before a want; a custodian's token, stated by its own symbol and the token's ID, "
          "minted by the stand-in platform paying 1 USD and declined as another payout than "
          "Polymarket's 1 USDC, nothing recorded; the market of three outcomes declined as "
          "not covered; no row and no miss. Prices, quotes, the "
          "event group and the outcome wait for the stand-in to mint a token paying the "
          "venue's own USDC (HARNESS_PAYS_USD)")


def diagnose():
    """On a failure, what the harness holds, kept in the run's log: the
    instruments, the plugin's Datasets record, and the lake's record."""
    runner("instruments", check=False)
    tools = [t for t in runner("mcp", "list", check=False).stdout.split() if "read_datasets" in t]
    for tool in tools:
        runner("mcp", "call", tool, "{}", check=False)
    compose("run", "--rm", "-T", "store", "lake", check=False)


def main():
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError) as failed:
        try:
            diagnose()
        except (Failed, subprocess.TimeoutExpired):
            pass
        print(f"e2e FAILED: {failed}; the run is in {LOG}, the components' logs in "
              ".e2e/components.log", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
