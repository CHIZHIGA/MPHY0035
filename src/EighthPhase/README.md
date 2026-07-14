# EighthPhase unified pipeline

Run all eligible collections:

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=src \
  /home/czg/miniforge3/envs/0249_env/bin/python \
  src/EighthPhase/run_pipeline.py --dataset all
```

Run one collection without regenerating plots:

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=src \
  /home/czg/miniforge3/envs/0249_env/bin/python \
  src/EighthPhase/run_pipeline.py --dataset EF-001 --no-plots
```

Dataset paths, adapters, time zones, mappings, sessions, pressure overrides,
reference sources, and co-presence pairs are declared in
`config/datasets.json`. Algorithm defaults are stored in
`PipelineParameters` and written to `Results/EighthPhase/pipeline_parameters.json`
on each run.

Step fallback treats the source as a cumulative counter. Equal counter values
no more than 35 minutes apart reconstruct the intervening five-minute windows
as zero-step plateaus; increasing and longer gaps remain unknown. Because zero
steps do not distinguish sleep from quiet wakefulness, a step-derived sleep
episode can change room output only when its supported dominant room is
Bedroom.

Tests:

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=src \
  /home/czg/miniforge3/envs/0249_env/bin/python \
  -m unittest EighthPhase.test_pipeline -v
```
