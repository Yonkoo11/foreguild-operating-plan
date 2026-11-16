"""Measure what it costs to move the price in Seer's live pools on Gnosis.
Reads Seer's public market index and the Swapr v3 pool index (both served by app.seer.pm),
then walks each pool's liquidity tick by tick. No keys, standard library only.
Run: python3 -I measure.py            (prints a dated report; numbers move as pools change)

Method (Uniswap v3 maths, which Swapr v3 / Algebra pools follow):
  inside one tick range with liquidity L, pushing sqrt-price from a to b costs L*(b-a) of token1
  and takes L*(1/a-1/b) of token0 out. Crossing an initialised tick adds its liquidityNet to L.
  "cost" = collateral paid in to reach the target price. "loss" = cost minus the tokens received
  valued at the starting price, i.e. what the pusher loses if the price fully returns.
  Swap fees are ignored (pool fee is read and printed as a range), so cost is a slight underestimate.
"""
import json, math, statistics, time, urllib.request

URL = "https://app.seer.pm/subgraph?_subgraph=%s&_chainId=100"
SDAI = "0xaf204776c7245bf4147c2612bf6e5972ee483701"
Q96 = 2 ** 96


def gql(sub, query):
    req = urllib.request.Request(URL % sub, json.dumps({"query": query}).encode(),
                                 {"content-type": "application/json", "user-agent": "measure.py"})
    for attempt in range(4):
        try:
            out = json.load(urllib.request.urlopen(req, timeout=60))
            if "data" in out:
                return out["data"]
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    raise SystemExit("subgraph did not answer: " + sub)


def markets():
    """Every Seer market on Gnosis: outcome token -> (market type, resolved?)."""
    token, n, off = {}, 0, 0
    while True:
        rows = gql("seer", "{ Market(limit:1000, offset:%d, order_by:{id:asc}, where:{chainId:{_eq:100}})"
                           "{ marketType wrappedTokens payoutReported } }" % off)["Market"]
        for m in rows:
            for t in m["wrappedTokens"]:
                token[t.lower()] = (m["marketType"], m["payoutReported"])
        n, off = n + len(rows), off + 1000
        if len(rows) < 1000:
            return token, n


def paged(entity, where, fields):
    last, rows = "", []
    while True:
        page = gql("algebra", '{ %s(first:1000, orderBy:id, where:{id_gt:"%s", %s}){ id %s } }'
                   % (entity, last, where, fields))[entity]
        rows += page
        if len(page) < 1000:
            return rows
        last = page[-1]["id"]


def walk(pool, ticks, target_sqrt):
    """Push the pool's sqrt-price to target_sqrt. Returns (token_in, token_out, reached)."""
    s, L = int(pool["sqrtPrice"]) / Q96, int(pool["liquidity"])
    up = target_sqrt > s
    cur = int(pool["tick"])
    todo = sorted((t for t in ticks if (t[0] > cur) == up), reverse=not up)
    paid = got = 0.0
    for idx, net in todo + [(None, 0)]:
        edge = target_sqrt if idx is None else 1.0001 ** (idx / 2)
        nxt = min(edge, target_sqrt) if up else max(edge, target_sqrt)
        if up:
            paid += L * (nxt - s); got += L * (1 / s - 1 / nxt)
        else:
            paid += L * (1 / nxt - 1 / s); got += L * (s - nxt)
        s = nxt
        if s == target_sqrt:
            return paid / 1e18, got / 1e18, True
        L += net if up else -net
    return paid / 1e18, got / 1e18, False


def push_outcome(pool, ticks, cents):
    """sDAI needed to lift an outcome token's price by `cents` in an outcome/sDAI pool."""
    p = (int(pool["sqrtPrice"]) / Q96) ** 2
    sdai_is_1 = pool["token1"]["id"] == SDAI
    price = p if sdai_is_1 else 1 / p
    goal = min(price + cents, 0.999)
    if not 0 < price < goal:
        return None
    target = math.sqrt(goal) if sdai_is_1 else math.sqrt(1 / goal)
    paid, got, _ = walk(pool, ticks, target)
    return paid, paid - got * price


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def report_outcome(pools, ticks):
    print("\nOutcome-token / sDAI pools with live liquidity: %d" % len(pools))
    held = [float(p["totalValueLockedToken1" if p["token1"]["id"] == SDAI else "totalValueLockedToken0"])
            for p in pools]
    print("sDAI sitting in the pool: median %.2f, 90th pct %.0f, largest %.0f; pools holding over 1,000 sDAI: %d"
          % (statistics.median(held), pct(held, .9), max(held), sum(h > 1000 for h in held)))
    print("sDAI to lift the outcome price by N cents (cost) and what is lost if it fully reverts (loss):")
    print("move   pools   median cost   90th pct cost   largest cost   median loss   largest loss")
    for c in (0.02, 0.05, 0.10):
        r = [x for x in (push_outcome(p, ticks.get(p["id"], []), c) for p in pools) if x]
        cost, loss = [a for a, _ in r], [b for _, b in r]
        print("%2dc   %5d   %11.2f   %13.0f   %12.0f   %11.2f   %12.0f"
              % (c * 100, len(r), statistics.median(cost), pct(cost, .9), max(cost),
                 statistics.median(loss), max(loss)))


RPC = "https://rpc.gnosischain.com"
FACTORY = "0xa0864cca6e114013ab0e27cbd5b6f4c8947da766"   # Swapr v3 (Algebra) factory on Gnosis
pad = lambda addr: addr[2:].rjust(64, "0")


def rpc(calls):
    """Batch of (to, data) eth_calls against Gnosis. Returns hex results in order."""
    out = []
    for i in range(0, len(calls), 100):
        body = [{"jsonrpc": "2.0", "id": k, "method": "eth_call", "params": [{"to": to, "data": d}, "latest"]}
                for k, (to, d) in enumerate(calls[i:i + 100])]
        req = urllib.request.Request(RPC, json.dumps(body).encode(),
                                     {"content-type": "application/json", "user-agent": "measure.py"})
        res = sorted(json.load(urllib.request.urlopen(req, timeout=60)), key=lambda r: r["id"])
        out += [r.get("result", "0x") for r in res]
    return out


def futarchy_markets():
    rows = gql("seer", '{ Market(limit:1000, where:{chainId:{_eq:100}, marketType:{_eq:"Futarchy"}})'
                       "{ marketName wrappedTokens outcomes payoutReported } }")["Market"]
    return [m for m in rows if len(m["wrappedTokens"]) == 4]


def futarchy_pools():
    """Seer's pool index does not list futarchy proposal pools, so read them from the chain.
    Tokens are [Yes-token, No-token, Yes-currency, No-currency]; pools are Yes/Yes and No/No.
    Returns (proposals, pools found, live pools as (market, side, pool state, currency is token0))."""
    ms = futarchy_markets()
    pairs = [(m, side, m["wrappedTokens"][i], m["wrappedTokens"][i + 2])
             for m in ms for side, i in (("yes", 0), ("no", 1))]
    addrs = rpc([(FACTORY, "0xd9a641e1" + pad(a) + pad(b)) for _, _, a, b in pairs])
    found = {r[-40:].lower(): p for p, r in zip(pairs, addrs) if int(r, 16)}     # one row per pool address
    state = rpc([c for pool in found for c in (("0x" + pool, "0x1a686502"), ("0x" + pool, "0xe76c01e4"))])
    live = []
    for k, (pool, (m, side, tok, cur)) in enumerate(found.items()):
        L, sq = int(state[2 * k], 16), int(state[2 * k + 1][2:66], 16)
        if L and sq:
            live.append((m, side, {"liquidity": L, "sqrtPrice": sq, "tick": 0}, cur.lower() < tok.lower()))
    return ms, len(found), live


def margin_cost(p, cur_is_0, mg):
    """(cost, loss on full reversion) to move a futarchy pool's price by margin mg."""
    s = p["sqrtPrice"] / Q96
    paid, got, _ = walk(p, [], s / math.sqrt(1 + mg) if cur_is_0 else s * math.sqrt(1 + mg))
    return paid, paid - got * (1 / (s * s) if cur_is_0 else s * s)


def report_futarchy(top=12):
    ms, n_found, live = futarchy_pools()
    print("\nFutarchy proposals on Gnosis: %d (%d unresolved). Yes/no pools that exist on chain: %d; "
          "with liquidity at the current price: %d"
          % (len(ms), sum(not m["payoutReported"] for m in ms), n_found, len(live)))
    rows = sorted(((margin_cost(p, c0, .05) + margin_cost(p, c0, .10), m, side) for m, side, p, c0 in live),
                  key=lambda r: -r[0][2])
    costs = [r[0][2] for r in rows]
    print("Currency-side tokens to move the pool price by the pass margin, liquidity held as deep as it is now.")
    print("The %d deepest pools (the other %d are shallower):" % (min(top, len(rows)), max(0, len(rows) - top)))
    print("side  state     paid in  cost +5%    loss   cost +10%    loss   proposal")
    for row, m, side in rows[:top]:
        print("%-4s  %-8s  %-6s %9.2f %7.2f %10.2f %7.2f   %s" % (
            side, "resolved" if m["payoutReported"] else "open",
            m["outcomes"][2].split("-")[-1][:6], *row, m["marketName"][:60]))
    print("All %d pools, cost to move the price 10%%: median %.2f, 90th pct %.2f, largest %.2f; "
          "pools needing over 100: %d (each pool's own currency token)"
          % (len(costs), statistics.median(costs), pct(costs, .9), max(costs), sum(c > 100 for c in costs)))
    print("Loss on full reversion is cost x (1 - 1/sqrt(1+margin)): 2.41% of cost at +5%, 4.65% at +10%.")


def main():
    token, n_markets = markets()
    kinds = {}
    for kind, _ in token.values():
        kinds[kind] = kinds.get(kind, 0) + 1
    pools = paged("pools", "liquidity_gt:0",
                  "liquidity sqrtPrice tick fee totalValueLockedToken0 totalValueLockedToken1 "
                  "token0{id symbol} token1{id symbol}")
    ticks = {}
    for t in paged("ticks", "liquidityGross_gt:0", "poolAddress tickIdx liquidityNet"):
        ticks.setdefault(t["poolAddress"], []).append((int(t["tickIdx"]), int(t["liquidityNet"])))
    is_out = lambda p: SDAI in (p["token0"]["id"], p["token1"]["id"]) and \
        any(p[k]["id"] in token for k in ("token0", "token1"))
    out = [p for p in pools if is_out(p)]
    print("Seer pools on Gnosis, read %s UTC" % time.strftime("%Y-%m-%d %H:%M", time.gmtime()))
    print("Seer markets on Gnosis: %d (outcome tokens by market type: %s)" % (n_markets, kinds))
    print("Swapr v3 pools in Seer's index with live liquidity: %d; outcome/sDAI: %d; other pairs: %d"
          % (len(pools), len(out), len(pools) - len(out)))
    fees = sorted({int(p["fee"]) / 1e4 for p in out})
    print("Pool swap fee across these pools: %.2f%% to %.2f%% (not included in costs)" % (fees[0], fees[-1]))
    report_outcome(out, ticks)
    report_futarchy()


if __name__ == "__main__":
    main()
