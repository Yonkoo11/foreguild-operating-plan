"""Foreguild plan model. Every input marked A= is an ASSUMPTION; F= a verified fact.
Run: python3 -I model.py"""
import math
# F: poidh page shows 0.5 ETH = $1109.97 -> ETH/USD
ETH=1109.97/0.5
MIN_BOUNTY_USD=0.001*ETH            # F: poidh min bounty 0.001 ETH
print(f"F ETH/USD from poidh page: {ETH:,.0f}; min poidh bounty ${MIN_BOUNTY_USD:.2f}")

# 1. Break-even tasks/month = fixed / (ticket*take - variable cost per task)
def be(F,T,r,c):
    m=T*r-c
    return math.inf if m<=0 else F/m
F_=6000   # A: monthly fixed cost (infra, model credits, 0.5 FTE reviewer)
print("\nBreak-even settled tasks per month (fixed $%d):"%F_)
print("ticket\\take  6%    8%    10%   12%   (A: variable cost/task $0.60 = verify+dispute reserve)")
for T in (5,15,40,100):
    row=[]
    for r in (.06,.08,.10,.12):
        b=be(F_,T,r,0.60); row.append("inf" if b==math.inf else f"{b:,.0f}")
    print(f"${T:<9}", "  ".join(f"{x:>6}" for x in row))

# 2. Reality.eth bond ladder (F: each answer >= 2x previous). Start bond b0.
print("\nOracle: cost to keep a WRONG answer standing, bonds double each round")
b0=100
for k in range(0,9):
    print(f"round {k}: must post ${b0*2**k:,}  cumulative ${b0*(2**(k+1)-1):,}")

# 3. Attack model (A: constant-product pool, depth D per side)
def attack(D,m):
    cap=D*(math.sqrt(1+m)-1); return cap, cap*m   # A: attacker loses about margin x capital pushed (assumption, not derived)
print("\nStake cap: value one market may govern V <= attack_loss / S (A: S=1, attacker gain <= V)")
S=1
print("depth    margin  capital   loss   max_governed_value")
for D in (20_000,100_000,500_000):
    for m in (0.05,0.10):
        c,l=attack(D,m); print(f"${D:>7,}  {m:.0%}   ${c:>7,.0f}  ${l:>6,.0f}  ${l/S:>9,.0f}")

# 4. Self-dealing: metric = fees RETAINED after the 14-day refund window. A wash trader pays the fee for real,
#    so inflating the metric by $X costs >= $X. Defence added: no single funding cluster may supply >10% of the metric.
import random
random.seed(7)
def run(cap=0.10,n_buyers=200,attacker_share=0.30):
    # A: honest fees follow a heavy-tailed split (Pareto); attacker adds attacker_share of total via one cluster
    honest=[random.paretovariate(1.5) for _ in range(n_buyers)]
    H=sum(honest); att=H*attacker_share/(1-attacker_share)
    total=H+att
    def counted(x): return min(x,cap*total)
    c_att=counted(att); c_hon=sum(counted(x) for x in honest)
    lost=H-c_hon
    return att,c_att,lost/H
att,c_att,lost=run()
print(f"\nConcentration cap test (A: synthetic Pareto honest buyers, attacker adds 30% of fees via one cluster):")
print(f"attacker fees paid ${att:,.0f} (real cost), counted ${c_att:,.0f}; honest fees dropped by the cap: {lost:.1%}")

# 5. Cap on a small buyer base (A: synthetic Pareto buyers, NO attacker, mean over 2000 draws)
random.seed(11)
print("\nHonest fees clipped by the 10% cap with no attacker, by number of buyers:")
for n in (3,10,20,50,200):
    m=sum(run(n_buyers=n,attacker_share=0.0)[2] for _ in range(2000))/2000
    print(f"{n:>4} buyers: {m:.1%} of honest fees dropped")
