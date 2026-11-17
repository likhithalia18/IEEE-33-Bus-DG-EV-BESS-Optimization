


## Requested code updates (final project)

The Python workflow has been updated only for the items listed in the supplied
modification checklist:

- `common.py`: all reported bus numbers are 1-based; the study network now
  includes a stated 0.20 MW / 0.08 MVAr commercial EV-corridor load at Bus 18
  and a 10% planning derating of existing line current ratings.
- `03_pso_optimization.py`: the thermal penalty uses calculated
  `net.res_line.loading_percent`; PSO uses 40 particles, 80 iterations and
  five independent seeds, reports mean and standard deviation, and prevents
  DG/EVCS/BESS bus co-location.
- `02_resource_scenarios.py`: reads `pso_best_solution.csv` and compares
  uncompensated high-EV, original heuristic placement and PSO placement at
  100%, 120% and 130% loading. It also runs a 24-hour hourly QSTS with PV,
  EVCS, BESS charging/discharging and SOC tracking, and reports VSI and loss
  reduction.

### Run order

From the `python` directory, install `requirements.txt`, then run:

```bash
python 03_pso_optimization.py
python 02_resource_scenarios.py
python 01_baseline.py
```

The 24-hour profiles and scenario outputs are written to the existing `results`
folder. The commercial feeder size, line-rating derating, PV/EV/BESS powers,
and QSTS profiles are explicit illustrative study assumptions and should be
identified as such in the project report and confirmed with the project guide.
