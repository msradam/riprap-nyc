# Stakeholder integration suite — summary

Run at: 2026-05-06 02:21:31
Suite size: 20 queries
Outcomes: 20 ok / 0 errored / 0 timed-out

Framing score: 0–5 (5 = opening directly answers the question shape; 3 = generic Status with place named; 1 = no engagement).

| # | Persona | Intent | Wall (s) | Stones | Mellea | Citations | Frame | Status |
|---|---------|--------|---------:|--------|--------|----------:|------:|--------|
| 01 | Resident / homebuyer (Pioneer) | single_address | 50.88 | 5(19 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 02 | Real-estate attorney (Gold) | single_address | 96.5 | 5(19 steps) | 3/4 (rr=1) | 6 | 2 | mellea 3/4 |
| 03 | NYC OEM/DEP planner (Hollis) | neighborhood | 134.45 | 3(10 steps) | 4/4 (rr=1) | 4 | 2 | ok |
| 04 | Insurance underwriter (Houston) | single_address | 123.79 | 5(19 steps) | 3/4 (rr=1) | 6 | 2 | mellea 3/4 |
| 05 | Climate journalist (Coney Island) | neighborhood | 65.31 | 3(10 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 06 | Architect / developer (Gowanus) | development_check | 107.74 | 0(3 steps) | 3/4 (rr=1) | 1 | 4 | mellea 3/4 |
| 07 | Resident, disclosure-suspicion (Grand) | single_address | 10.18 | 5(19 steps) | 0/4 (rr=0) | 0 | 3 | mellea 0/4 |
| 08 | NYCHA-in-flood-zone planner (Hammels) | neighborhood | 63.41 | 3(10 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 09 | MTA capital planner | neighborhood | 105.98 | 3(9 steps) | 3/4 (rr=1) | 4 | 2 | mellea 3/4 |
| 10 | Planner — NYCHA + Sandy memory (Red Hook) | neighborhood | 58.68 | 3(10 steps) | 4/4 (rr=0) | 6 | 2 | ok |
| 11 | DOE school siting (PS 188) | single_address | 117.77 | 5(19 steps) | 3/4 (rr=1) | 0 | 2 | mellea 3/4 |
| 12 | Planner — protected neighborhood (BPC) | neighborhood | 57.66 | 3(10 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 13 | Climate-grant evidence (Two Bridges) | neighborhood | 60.68 | 3(10 steps) | 4/4 (rr=0) | 6 | 2 | ok |
| 14 | Time-machine retrospective (Hollis pre-Ida) | single_address | 5.6 | 5(19 steps) | 0/4 (rr=0) | 0 | 3 | mellea 0/4 |
| 15 | EJNYC × Riprap pairing | development_check | 6.26 | 0(0 steps) | 0/4 (rr=0) | 0 | 2 | mellea 0/4 |
| 16 | FloodNet alert federation (BK-018) | live_now | 14.35 | 3(4 steps) | 0/4 (rr=0) | 2 | 0 | mellea 0/4 |
| 17 | Compare intent (Pioneer vs Grand) | single_address | 137.23 | 5(19 steps) | 3/4 (rr=1) | 6 | 2 | mellea 3/4 |
| 18 | Court testimony (Houston × Ida) | single_address | 9.43 | 5(19 steps) | 0/4 (rr=0) | 0 | 3 | mellea 0/4 |
| 19 | Capital planning, protection-shadow (BBMCR) | neighborhood | 8.78 | 0(0 steps) | 0/4 (rr=0) | 0 | 4 | mellea 0/4 |
| 20 | Neighborhood control case (Astoria) | neighborhood | 103.98 | 3(10 steps) | 4/4 (rr=1) | 6 | 2 | ok |

## Framing-score distribution

- score 0: 1 queries
- score 1: 0 queries
- score 2: 14 queries
- score 3: 3 queries
- score 4: 2 queries
- score 5: 0 queries

## Framing rationale per query

- **q01 (resident-pioneer)** [2/5] — on-topic exposure language but no question-aware framing
- **q02 (attorney-gold)** [2/5] — on-topic exposure language but no question-aware framing
- **q03 (planner-hollis)** [2/5] — on-topic exposure language but no question-aware framing
- **q04 (underwriter-houston)** [2/5] — on-topic exposure language but no question-aware framing
- **q05 (journalist-coney)** [2/5] — on-topic exposure language but no question-aware framing
- **q06 (developer-gowanus)** [4/5] — topic marker matched: /construction|development|filing|permit|DOB/ (no verdict)
- **q07 (resident-grand-disclosure)** [3/5] — place reference only: /this address|this location|this property/
- **q08 (planner-hammels)** [2/5] — on-topic exposure language but no question-aware framing
- **q09 (mta-coney-vs-brighton)** [2/5] — on-topic exposure language but no question-aware framing
- **q10 (planner-redhook)** [2/5] — on-topic exposure language but no question-aware framing
- **q11 (doe-ps188)** [2/5] — on-topic exposure language but no question-aware framing
- **q12 (planner-bpc-protected)** [2/5] — on-topic exposure language but no question-aware framing
- **q13 (grant-twobridges-cdbg)** [2/5] — on-topic exposure language but no question-aware framing
- **q14 (retrospective-hollis-ida)** [3/5] — place reference only: /this address|this neighborhood/
- **q15 (ejnyc-nycha-ranking)** [2/5] — on-topic exposure language but no question-aware framing
- **q16 (floodnet-bk018-livenow)** [0/5] — no opening prose to score
- **q17 (compare-pioneer-grand)** [2/5] — on-topic exposure language but no question-aware framing
- **q18 (court-houston-ida)** [3/5] — place reference only: /this address|this neighborhood/
- **q19 (bbmcr-protection-envelope)** [4/5] — topic marker matched: /planning|investment|infrastructure|hardening|resilien(ce|cy)/ (no verdict)
- **q20 (control-astoria)** [2/5] — on-topic exposure language but no question-aware framing
