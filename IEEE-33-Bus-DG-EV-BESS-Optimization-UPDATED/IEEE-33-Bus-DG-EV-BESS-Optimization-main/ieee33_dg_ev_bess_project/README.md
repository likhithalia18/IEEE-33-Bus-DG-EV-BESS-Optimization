# Modified IEEE 33-Bus DG–EVCS–BESS Optimization

This project evaluates distributed PV generation (DG), an electric-vehicle charging station (EVCS), and a battery energy storage system (BESS) on a modified IEEE 33-bus distribution benchmark using pandapower and particle swarm optimization (PSO).

## What is included

- `python/common.py`: common network construction, AC load flow, bus-number reporting, loss calculation, voltage-deviation calculation, VSI calculation, and plotting utilities.
- `python/01_baseline.py`: baseline voltage and loss analysis at 100%, 110%, 120%, and 130% loading.
- `python/03_pso_optimization.py`: PSO placement/sizing at 120% loading, with 40 particles, 80 iterations, five random seeds, distinct DG/EVCS/BESS buses, voltage limits, and line thermal-loading penalties.
- `python/02_resource_scenarios.py`: compares uncompensated EV loading, heuristic placement, and PSO placement at multiple loading levels; also runs the 24-hour QSTS using the PSO-selected buses and sizes.
- `python/run_all.py`: executes the scripts in the required order.

## Network modifications and study assumptions

The standard pandapower `case33bw()` network is modified by adding an aggregate commercial/EV-corridor load of 0.20 MW and 0.08 MVAr at Bus 18, and by applying a 10% planning derating to the existing line current ratings. These are illustrative study assumptions introduced for this project; they are not measured utility data or manufacturer ratings. State and justify them in the final report and confirm them with the project guide.

The PSO operating point is 120% load. DG and EVCS buses are selected from non-slack buses, and DG, EVCS, and BESS must occupy distinct buses. The BESS discharge rating is bounded from 0.05 MW to 0.50 MW so that the QSTS study can demonstrate both charging and discharging.

The QSTS model uses hourly steps, a 1 MWh BESS, 95% charge/discharge efficiency, and 20%–90% SOC limits. For the illustrative schedule, up to 50% of instantaneous PV output is allocated to BESS charging during solar hours, and evening BESS discharge is limited to 50% of EVCS demand. These are simplified scheduling assumptions, not a full AC-coupled/EMS dispatch model or measured PV surplus.

The VSI implemented in `common.py` is a line-based two-bus voltage-stability indicator calculated from branch parameters and load-flow results. Its formula, assumptions, and interpretation should be described in the report; do not present it as a universally standardized index without citing the chosen reference.

## Requirements

- Python 3.10 or newer recommended
- pandapower 2.14 or newer
- NumPy 1.24 or newer
- pandas 2.0 or newer
- Matplotlib 3.7 or newer

Install from the project folder:

```bash
python -m pip install -r python/requirements.txt
```

## Run the complete study

Open a terminal in `ieee33_dg_ev_bess_project` and run:

```bash
python python/run_all.py
```

Or run individually from the `python` directory in this order:

```bash
python 03_pso_optimization.py
python 02_resource_scenarios.py
python 01_baseline.py
```

The PSO run is computationally heavier: 5 seeds × 80 iterations × 40 particles. Do not interrupt it before it finishes.

## Generated outputs

The scripts create CSV and PNG files in `results/`, including:

- `pso_best_solution.csv`, `pso_seed_results.csv`, `pso_seed_statistics.csv`, `pso_convergence.csv`, `pso_convergence.png`
- `multi_scenario_summary.csv`, `multi_scenario_voltage_profiles.png`, `multi_scenario_active_losses.png`
- `qsts_24h_results.csv`, `qsts_24h_power_profile.png`, `qsts_24h_soc.png`
- `baseline_summary.csv`, bus-voltage CSV files, weak-bus CSV, and baseline plots

Generated results are deliberately not bundled as if they had been reproduced here. Run the scripts on your computer to create results from this updated source code.

## Important limitations

1. The PV, EVCS, commercial feeder, line derating, load profiles, BESS rating/capacity, efficiencies, and dispatch fractions are illustrative assumptions. Replace them with guide-approved or sourced values where available.
2. The 24-hour study is a quasi-static hourly sequence, not a dynamic EMT simulation.
3. The BESS schedule is rule-based and simplified; it does not solve an optimal energy-management problem or prove that all charging energy is physically available as PV surplus.
4. MATLAB/Simulink files are not included in this ZIP.
5. Validate the selected VSI equation and all assumptions with the project guide before final defense.
