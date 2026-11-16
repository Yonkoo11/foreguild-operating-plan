# Foreguild operating plan

Entry for the Seer FAO Operating Plan Contest. Read it at
https://yonkoo11.github.io/foreguild-operating-plan/ or as `foreguild-plan.pdf`.

The version submitted to the contest is commit `76c0420` (7 Nov 2026). The page was updated on
14 Nov 2026; section 13 of the plan lists what changed.

```
.
├── index.html            the plan
├── foreguild-plan.pdf    the same plan as a PDF
├── model.py              unit-economics model behind the plan's tables (no dependencies)
├── model-output.txt      output of model.py
├── measure.py            reads Seer's live pools on Gnosis and prices a push on each one
├── measure-output.txt    its output from the 14 Nov 2026 run
├── census.py             reads every poidh bounty on Base from the two poidh contracts
└── census-output.txt     its output from the 14 Nov 2026 run
```

## Verify it yourself

```
python3 -I model.py | diff - model-output.txt && echo match
```

Expected output (produced by a run made before this README was written):

```
match
```

`measure.py` and `census.py` read live data, so a fresh run will not match the saved files line for
line. Pools change, bounties get posted, and the census values every bounty at the day's ETH price.
The plan quotes the 14 Nov 2026 runs. Both need only Python 3 and a network connection; the census
takes about ten minutes.

```
python3 -I measure.py
python3 -I census.py
```

## What's real, and what we deliberately did not claim

| Capability | Status |
|---|---|
| Break-even task counts in the plan | Reproduced by `model.py`. Inputs ($6,000 monthly fixed cost, $0.60 per task) are assumptions, not measurements. |
| $5 tickets cover costs | No. They never break even in the model. |
| Cost to move the price in Seer's pools | Measured by `measure.py` from Seer's pool index and the chain on 14 Nov 2026. Swap fees are left out, so costs are slightly low. |
| Markets can bind decisions today | No. In the deepest futarchy pool, a 10% push cost about 2,469 sDAI and lost about 115 if the price returned. The first markets advise. |
| Demand for $40+ machine-checkable tasks | Not proven. The census found 9 poidh bounties paid at $40 or more in the 90 days to 14 Nov 2026. |
| Stake-capped futarchy (a market binds a decision only up to what an attacker would lose) | Design proposal. Not run on a live market. |
| A futarchy proposal settled against a revenue number | Not verified. Seer's docs describe multi-scalar markets; I found no page showing a futarchy proposal settled that way. The plan uses the shipped price-based YES/NO design. |
| Fee-to-token link | Design choice of this plan, not a Seer feature. |
| Reality.eth bond ladder figures | Computed from the 2x bond rule. |
| Revenue forecast | None given. The plan states break-even thresholds only. |
