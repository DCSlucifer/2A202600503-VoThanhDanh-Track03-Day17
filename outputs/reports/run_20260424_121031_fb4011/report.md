# Benchmark report — run `run_20260424_121031_fb4011`

## Aggregate (averages per scenario)

| # | Scenario | Memory | Relevance | Context util | Tok. eff. | Hit rate | Satisfaction |
|---|---|---|---|---|---|---|---|
| 1 | s01_pref_same_session | with |  1.00 | 0.12 | 12.037 | 0.50 | 1.00 |
| 1 | s01_pref_same_session | no  |  0.75 | 0.00 | 11.111 | 0.00 | 0.85 |
| 2 | s02_pref_cross_session | with |  0.67 | 0.14 | 7.398 | 0.33 | 0.80 |
| 2 | s02_pref_cross_session | no  |  0.50 | 0.00 | 7.739 | 0.00 | 0.70 |
| 3 | s03_pref_contradiction | with |  1.00 | 0.10 | 13.650 | 0.33 | 1.00 |
| 3 | s03_pref_contradiction | no  |  0.67 | 0.00 | 11.303 | 0.00 | 0.80 |
| 4 | s04_fact_profile | with |  1.00 | 0.08 | 11.530 | 0.33 | 1.00 |
| 4 | s04_fact_profile | no  |  0.67 | 0.00 | 9.166 | 0.00 | 0.80 |
| 5 | s05_fact_technical | with |  1.00 | 0.18 | 13.039 | 0.50 | 1.00 |
| 5 | s05_fact_technical | no  |  0.50 | 0.00 | 7.936 | 0.00 | 0.70 |
| 6 | s06_episodic_adaptation | with |  0.50 | 0.29 | 3.472 | 0.50 | 0.70 |
| 6 | s06_episodic_adaptation | no  |  0.00 | 0.00 | 0.000 | 0.00 | 0.40 |
| 7 | s07_ambiguous_multi | with |  0.67 | 0.00 | 9.431 | 0.00 | 0.80 |
| 7 | s07_ambiguous_multi | no  |  0.67 | 0.00 | 9.431 | 0.00 | 0.80 |
| 8 | s08_precision | with |  1.00 | 0.00 | 16.667 | 0.00 | 1.00 |
| 8 | s08_precision | no  |  1.00 | 0.00 | 16.667 | 0.00 | 1.00 |
| 9 | s09_long_trim | with |  1.00 | 0.01 | 7.437 | 0.10 | 1.00 |
| 9 | s09_long_trim | no  |  0.90 | 0.00 | 7.040 | 0.00 | 0.94 |
| 10 | s10_cold_start | with |  1.00 | 0.00 | 13.460 | 0.00 | 1.00 |
| 10 | s10_cold_start | no  |  1.00 | 0.00 | 13.460 | 0.00 | 1.00 |

## Deltas (with-mem − no-mem, averaged over turns)

| Scenario | Δ relevance | Δ context util | Δ tok. eff. | Δ hit rate | Δ satisfaction |
|---|---|---|---|---|---|
| s01_pref_same_session | +0.250 | +0.116 | +0.9259 | +0.500 | +0.150 |
| s02_pref_cross_session | +0.167 | +0.140 | -0.3408 | +0.333 | +0.100 |
| s03_pref_contradiction | +0.333 | +0.101 | +2.3474 | +0.333 | +0.200 |
| s04_fact_profile | +0.333 | +0.077 | +2.3641 | +0.333 | +0.200 |
| s05_fact_technical | +0.500 | +0.180 | +5.1021 | +0.500 | +0.300 |
| s06_episodic_adaptation | +0.500 | +0.291 | +3.4722 | +0.500 | +0.300 |
| s07_ambiguous_multi | +0.000 | +0.000 | +0.0000 | +0.000 | +0.000 |
| s08_precision | +0.000 | +0.000 | +0.0000 | +0.000 | +0.000 |
| s09_long_trim | +0.100 | +0.012 | +0.3968 | +0.100 | +0.060 |
| s10_cold_start | +0.000 | +0.000 | +0.0000 | +0.000 | +0.000 |

**With-mem wins ≥ 3/5 metrics on 7/10 scenarios.**

## Per-scenario turn counts

| Scenario | Turns | Sessions | With-mem prompt tokens | No-mem prompt tokens |
|---|---|---|---|---|
| s01_pref_same_session | 2 | 1 | 195.0 | 150.0 |
| s02_pref_cross_session | 3 | 2 | 339.0 | 229.0 |
| s03_pref_contradiction | 3 | 2 | 260.0 | 203.0 |
| s04_fact_profile | 3 | 2 | 288.0 | 256.0 |
| s05_fact_technical | 2 | 2 | 161.0 | 125.0 |
| s06_episodic_adaptation | 2 | 2 | 213.0 | 129.0 |
| s07_ambiguous_multi | 3 | 2 | 212.0 | 212.0 |
| s08_precision | 2 | 2 | 120.0 | 120.0 |
| s09_long_trim | 10 | 1 | 1617.0 | 1571.0 |
| s10_cold_start | 2 | 1 | 156.0 | 156.0 |
