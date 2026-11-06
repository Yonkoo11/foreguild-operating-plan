# Foreguild operating plan

Entry for the Seer FAO Operating Plan Contest (6 November 2026).

- `index.html`: the plan.
- `model.py`: the unit-economics model behind the plan's numbers. No dependencies.
- `model-output.txt`: its output.

To check the numbers:

```
python3 -I model.py | diff - model-output.txt && echo match
```

Expected output: `match`.
