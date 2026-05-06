# Stakeholder integration suite — summary

Run at: 2026-05-06 02:45:29
Suite size: 20 queries
Outcomes: 20 ok / 0 errored / 0 timed-out

Framing score: 0–5 (5 = opening directly answers the question shape; 3 = generic Status with place named; 1 = no engagement).

| # | Persona | Intent | Wall (s) | Stones | Mellea | Citations | Frame | Status |
|---|---------|--------|---------:|--------|--------|----------:|------:|--------|
| 01 | Resident / homebuyer (Pioneer) | single_address | 140.96 | 5(19 steps) | 3/4 (rr=1) | 5 | 5 | mellea 3/4 |
| 02 | Real-estate attorney (Gold) | single_address | 133.53 | 5(19 steps) | 4/4 (rr=1) | 5 | 5 | ok |
| 03 | NYC OEM/DEP planner (Hollis) | neighborhood | 68.33 | 3(10 steps) | 4/4 (rr=0) | 6 | 2 | ok |
| 04 | Insurance underwriter (Houston) | single_address | 90.66 | 5(19 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 05 | Climate journalist (Coney Island) | neighborhood | 74.81 | 3(10 steps) | 4/4 (rr=0) | 6 | 2 | ok |
| 06 | Architect / developer (Gowanus) | development_check | 114.8 | 0(3 steps) | 2/4 (rr=1) | 1 | 4 | mellea 2/4 |
| 07 | Resident, disclosure-suspicion (Grand) | single_address | 7.85 | 5(19 steps) | 0/4 (rr=0) | 0 | 3 | mellea 0/4 |
| 08 | NYCHA-in-flood-zone planner (Hammels) | neighborhood | 59.99 | 3(10 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 09 | MTA capital planner | neighborhood | 67.15 | 3(9 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 10 | Planner — NYCHA + Sandy memory (Red Hook) | neighborhood | 63.87 | 3(10 steps) | 4/4 (rr=0) | 4 | 2 | ok |
| 11 | DOE school siting (PS 188) | single_address | 111.4 | 5(19 steps) | 3/4 (rr=1) | 0 | 2 | mellea 3/4 |
| 12 | Planner — protected neighborhood (BPC) | neighborhood | 70.57 | 3(10 steps) | 4/4 (rr=0) | 5 | 2 | ok |
| 13 | Climate-grant evidence (Two Bridges) | neighborhood | 68.0 | 3(10 steps) | 4/4 (rr=0) | 5 | 5 | ok |
| 14 | Time-machine retrospective (Hollis pre-Ida) | single_address | 4.59 | 5(19 steps) | 0/4 (rr=0) | 0 | 3 | mellea 0/4 |
| 15 | EJNYC × Riprap pairing | development_check | 5.65 | 0(0 steps) | 0/4 (rr=0) | 0 | 2 | mellea 0/4 |
| 16 | FloodNet alert federation (BK-018) | live_now | 17.16 | 3(4 steps) | 0/4 (rr=0) | 2 | 2 | mellea 0/4 |
| 17 | Compare intent (Pioneer vs Grand) | single_address | 102.08 | 5(19 steps) | 4/4 (rr=0) | 4 | 2 | ok |
| 18 | Court testimony (Houston × Ida) | single_address | 11.85 | 5(19 steps) | 0/4 (rr=0) | 0 | 3 | mellea 0/4 |
| 19 | Capital planning, protection-shadow (BBMCR) | neighborhood | 10.69 | 0(0 steps) | 0/4 (rr=0) | 0 | 4 | mellea 0/4 |
| 20 | Neighborhood control case (Astoria) | neighborhood | 112.64 | 3(10 steps) | 4/4 (rr=1) | 5 | 2 | ok |

## Framing-score distribution

- score 0: 0 queries
- score 1: 0 queries
- score 2: 12 queries
- score 3: 3 queries
- score 4: 2 queries
- score 5: 3 queries

## Framing rationale per query

- **q01 (resident-pioneer)** [5/5] — verdict marker matched: /\b(yes|no)\b[,.]/
- **q02 (attorney-gold)** [5/5] — verdict marker matched: /\b(disclosure|disclose) (is )?(required|not required|triggered|warranted)/
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
- **q13 (grant-twobridges-cdbg)** [5/5] — verdict marker matched: /vulnerabilit(y|ies) (assessment|profile|evidence)/
- **q14 (retrospective-hollis-ida)** [3/5] — place reference only: /this address|this neighborhood/
- **q15 (ejnyc-nycha-ranking)** [2/5] — on-topic exposure language but no question-aware framing
- **q16 (floodnet-bk018-livenow)** [2/5] — on-topic exposure language but no question-aware framing
- **q17 (compare-pioneer-grand)** [2/5] — on-topic exposure language but no question-aware framing
- **q18 (court-houston-ida)** [3/5] — place reference only: /this address|this neighborhood/
- **q19 (bbmcr-protection-envelope)** [4/5] — topic marker matched: /planning|investment|infrastructure|hardening|resilien(ce|cy)/ (no verdict)
- **q20 (control-astoria)** [2/5] — on-topic exposure language but no question-aware framing
