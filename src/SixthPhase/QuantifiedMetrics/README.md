# SixthPhase Quantified Metrics

This workspace contains behaviour-level metrics built from the Sixth Phase
pressure, ACC, and RSSI analyses.

Current tasks:

1. Stair ascent/descent metrics from pressure-derived floor transitions with ACC
   support.
2. Low-motion regular long-stay / sleep-location candidate analysis.
3. Movement-supported room/beacon transition metrics from pressure-floor-aware
   RSSI.

Room transition metrics currently use:

- location source: `pressure_floor_bruteforce_rssi_beacon`
- awake/motion rule: `acc_magnitude_std_clean > 0.010`
- transition support rule: a beacon transition is ACC-supported when the
  transition window or either adjacent 5-min window is awake/moving.

Room transition outputs:

- `new80h_room_transition_acc_support_5min.csv`
- `new80h_room_transition_events.csv`
- `new80h_room_transition_summary.csv`
- `new80h_room_transition_daily_summary.csv`
- `new80h_room_transition_acc_support_timeline.png`

Outputs are written to:

```text
Results/SixthPhase/QuantifiedMetrics
```
