"""Census of every poidh bounty on Base, read straight from the two poidh contracts.
No keys, standard library only. Run: python3 -I census.py   (numbers move as bounties are posted)

Each bounty record holds issuer, amount (wei), claimer and createdAt. In poidh's contract a bounty is
  open       when claimer is the zero address,
  cancelled  when claimer equals the issuer (the issuer took the money back),
  paid out   when claimer is anyone else.
Dollar values use one ETH price read at run time, so old bounties are valued at today's price.
The current contract sets amount to zero once a bounty is paid or cancelled, so for those the size
is read from the bounty's creation event (size when posted; later top-ups by others are not counted).
"""
import json, statistics, time, urllib.request

RPC = "https://mainnet.base.org"
BOARDS = {"older contract": "0xb502c5856F7244DccDd0264A541Cc25675353D39",
          "current contract": "0x5555Fa783936C260f77385b4E153B9725feF1719"}
PRICE = "https://coins.llama.fi/prices/current/coingecko:ethereum"
LOGS = "https://base.gateway.tenderly.co"          # serves old logs, 1,000 blocks per request
CREATED = "0xd265c5d6a9224c4853317e9e3262b0605b45f0e87c8bfd17d020e54a87c439af"   # creation event, topic 1 = id
GENESIS = 1686789347                               # Base block n has time GENESIS + 2n until the 2026 speed-up
UA = {"content-type": "application/json", "user-agent": "census.py"}


def rpc(calls):
    """Batch of (to, data) eth_calls against Base. Returns hex results in order."""
    out = []
    for i in range(0, len(calls), 20):
        body = [{"jsonrpc": "2.0", "id": k, "method": "eth_call", "params": [{"to": to, "data": d}, "latest"]}
                for k, (to, d) in enumerate(calls[i:i + 20])]
        for attempt in range(5):
            try:
                res = json.load(urllib.request.urlopen(
                    urllib.request.Request(RPC, json.dumps(body).encode(), UA), timeout=60))
                if isinstance(res, list) and all("result" in r for r in res):
                    break
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        else:
            raise SystemExit("Base RPC did not answer")
        out += [r["result"] for r in sorted(res, key=lambda r: r["id"])]
        time.sleep(1)                      # the public Base endpoint allows 25 calls a second
    return out


def bounties(board):
    """Every bounty on one contract as (issuer, eth, claimer, created)."""
    n = int(rpc([(board, "0xa0d59787")])[0], 16)                      # bountyCounter()
    raw = rpc([(board, "0xdc2f8744" + hex(i)[2:].rjust(64, "0")) for i in range(n)])   # bounties(i)
    rows = []
    for r in raw:
        w = [r[2 + 64 * k: 66 + 64 * k] for k in range(8)]
        rows.append((w[1][-40:], int(w[4], 16) / 1e18, w[5][-40:], int(w[6], 16)))
    return rows


def ask(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(5):
        try:
            res = json.load(urllib.request.urlopen(urllib.request.Request(LOGS, body, UA), timeout=40))
            if "result" in res:
                return res["result"]
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    raise SystemExit("log endpoint did not answer")


def clock():
    """Returns a function mapping a timestamp to its approximate Base block number."""
    stamp = lambda n: int(ask("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)
    top = ask("eth_getBlockByNumber", ["latest", False])
    hi, hi_t = int(top["number"], 16), int(top["timestamp"], 16)
    lo, end = 41000000, hi                          # last block still on the 2-second schedule
    while end - lo > 1:
        mid = (lo + end) // 2
        lo, end = (mid, end) if stamp(mid) == GENESIS + 2 * mid else (lo, mid)
    lo_t, rate = GENESIS + 2 * lo, (hi - lo) / max(1, hi_t - (GENESIS + 2 * lo))
    return lambda t: (t - GENESIS) // 2 if t <= lo_t else lo + int((t - lo_t) * rate)


def posted_size(board, i, block):
    """ETH put up when bounty i was created, from its creation event near `block`. None if not found."""
    topic = "0x" + hex(i)[2:].rjust(64, "0")
    for off in (0, -1000, 1000, -2000, 2000):
        logs = ask("eth_getLogs", [{"address": board, "topics": [CREATED, topic],
                                    "fromBlock": hex(block + off - 500), "toBlock": hex(block + off + 499)}])
        time.sleep(0.2)
        if logs:
            return int(logs[0]["data"][2 + 128: 2 + 192], 16) / 1e18
    return None


def fill_sizes(board, rows):
    """Replace zeroed amounts on settled bounties with the size at posting. Returns (rows, not found)."""
    block_of, out, missing = clock(), [], 0
    for i, (issuer, eth, claimer, t) in enumerate(rows):
        if eth == 0 and state(issuer, claimer) != "open":
            found = posted_size(board, i, block_of(t))
            missing += found is None
            eth = found or 0.0
        out.append((issuer, eth, claimer, t))
    return out, missing


def state(issuer, claimer):
    return "open" if int(claimer, 16) == 0 else "cancelled" if claimer == issuer else "paid"


def report(name, rows, usd):
    by = {s: [e for i, e, c, _ in rows if state(i, c) == s] for s in ("paid", "cancelled", "open")}
    sizes = [e * usd for _, e, _, _ in rows]
    print("\n%s: %d bounties; paid out %d (%.0f%%), cancelled %d, open %d"
          % (name, len(rows), len(by["paid"]), 100 * len(by["paid"]) / len(rows),
             len(by["cancelled"]), len(by["open"])))
    print("  size of all bounties: median $%.2f; under $5: %.0f%%; $40 or more: %.0f%%"
          % (statistics.median(sizes), 100 * sum(s < 5 for s in sizes) / len(sizes),
             100 * sum(s >= 40 for s in sizes) / len(sizes)))
    paid = [e * usd for e in by["paid"]]
    print("  paid-out bounties: median $%.2f, total $%s; of $40 or more: %d, worth $%s"
          % (statistics.median(paid), format(round(sum(paid)), ","), sum(p >= 40 for p in paid),
             format(round(sum(p for p in paid if p >= 40)), ",")))


def recent(rows, usd, now, days=90):
    r = [(i, e * usd, c) for i, e, c, t in rows if t > now - days * 86400]
    paid = [u for i, u, c in r if state(i, c) == "paid"]
    big = [u for u in paid if u >= 40]
    issuers = {i for i, u, c in r if state(i, c) == "paid" and u >= 40}
    print("\nLast %d days, both contracts: %d bounties posted, %d paid out worth $%s"
          % (days, len(r), len(paid), format(round(sum(paid)), ",")))
    print("  paid out at $40 or more: %d bounties from %d distinct issuers, worth $%s (about %.0f a month)"
          % (len(big), len(issuers), format(round(sum(big)), ","), len(big) * 30 / days))


def main():
    usd = json.load(urllib.request.urlopen(urllib.request.Request(PRICE, headers=UA), timeout=30)
                    )["coins"]["coingecko:ethereum"]["price"]
    now = time.time()
    print("poidh bounties on Base, read %s UTC. ETH = $%.2f (coins.llama.fi)"
          % (time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)), usd))
    print("0.5 ETH = $%.2f; poidh minimum bounty 0.001 ETH = $%.2f" % (usd / 2, usd / 1000))
    everything = []
    for name, board in BOARDS.items():
        rows = bounties(board)
        if name == "current contract":
            rows, missing = fill_sizes(board, rows)
            print("\n(current contract: %d settled bounties whose creation event was not found, counted as $0)" % missing)
        report(name, rows, usd)
        everything += rows
    report("Both contracts", everything, usd)
    recent(everything, usd, now)


if __name__ == "__main__":
    main()
