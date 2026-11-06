# Foreguild operating plan

Entry for the Seer FAO Operating Plan Contest (6 November 2026).

```
.
├── index.html         the plan
├── model.py           unit-economics model behind the plan's numbers (no dependencies)
└── model-output.txt   output of model.py
```

## Verify it yourself

```
python3 -I model.py | diff - model-output.txt && echo match
```

Expected output (produced by a run made before this README was written):

```
match
```

## What's real, and what we deliberately did not claim

| Capability | Status |
|---|---|
| Break-even task counts in the plan | Reproduced by `model.py`. Inputs ($6,000 monthly fixed cost, $0.60 per task) are assumptions, not measurements. |
| $5 tickets cover costs | No. They never break even in the model. |
| Stake-capped futarchy (a market binds a decision only up to what an attacker would lose) | Design proposal. Not run on a live market. |
| Seer supports a revenue-valued (scalar) market | Not verified. Shipped Seer markets are price-based YES/NO. |
| Fee-to-token buyback link | Design choice of this plan, not a Seer feature. |
| Reality.eth bond ladder figures | Computed from the 2x bond rule. Kleros appeal cost is an upper bound. |
| Revenue forecast | None given. The plan states break-even thresholds only. |
