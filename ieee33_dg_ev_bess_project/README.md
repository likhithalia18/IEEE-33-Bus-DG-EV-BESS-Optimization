# IEEE 33-bus DG–EVCS–BESS simulation starter project

This is a reproducible **starter implementation** based on the Review 2 presentation.
It separates:
- Python/pandapower: IEEE 33-bus AC load flow, loading cases, resource scenarios,
  result tables/plots, and a basic PSO placement-and-sizing demonstration.
- MATLAB: transparent time-series/averaged component models for PV, EV demand,
  BESS SOC, and a simplified DSTATCOM reactive-power controller.

## Important scope and modelling notes

1. The presentation specifies the `pandapower.networks.case33bw()` IEEE 33-bus
   benchmark and Newton–Raphson AC load flow. The Python scripts follow that.
2. The presentation's core decision variables include DG, EVCS and BESS bus
   locations and sizes. This starter PSO optimizes DG bus/size, EVCS bus and
   BESS bus/discharge size. EV charging power is held fixed during optimization
   so the optimizer cannot "improve" the objective by eliminating EV demand.
3. The starter fitness is `w1 * active_loss_MW + w2 * voltage_deviation + penalties`.
   VSI, DSTATCOM, V2G, queueing, dynamic reconfiguration, detailed economics and
   uncertainty are **not fully implemented** here. Add them only after the
   baseline and core model are validated, and document each added equation.
4. MATLAB files are averaged/steady-state educational models, not switching-level
   converter models or a complete Simulink IEEE 33-bus network. For a detailed
   converter study, build the blocks in Simulink/Simscape Electrical and use
   manufacturer/model parameters.
5. Values for DG, EVCS, BESS and DSTATCOM in the scripts are **illustrative
   starting assumptions**, not values stated in the presentation or measured data.
   Replace them with your supervisor-approved project parameters.
6. `case33bw()` commonly represents a 12.66 kV system and uses its own base
   data. Do not silently change base voltage, line data, or loads. Record any
   modifications to the benchmark.

## Installation

Recommended: Python 3.10 or 3.11 in a fresh virtual environment.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r python/requirements.txt
```

If installation of pandapower fails, use a supported Python version (3.10/3.11)
and install in a clean environment.

## Run order

From the project folder:

```bash
python python/01_baseline.py
python python/02_resource_scenarios.py
python python/03_pso_optimization.py
```

Results are saved in `results/` as CSV tables and PNG plots.

## Python scripts

- `01_baseline.py`: base network, 100/110/120/130% load flow, weak-bus table,
  voltage and loss graphs.
- `02_resource_scenarios.py`: base, high-EV, low-PV and combined resource cases.
- `03_pso_optimization.py`: simple PSO for DG size/location, EVCS location and
  BESS discharge size/location. It is a starting optimizer, not a final
  publication-grade multi-objective implementation.

## MATLAB

Open MATLAB, set the current folder to `matlab/`, then run:

```matlab
component_models_demo
```

It generates illustrative PV, EV load, BESS SOC and DSTATCOM response plots.
Edit the parameter section before using the results in your report.

## Validation checklist

- Confirm the `case33bw()` network has 33 buses and 32 branches.
- Check convergence of every load-flow run.
- Check voltage limits (0.95–1.05 pu) as stated in the presentation.
- Check line/transformer loading only if the network elements have meaningful
  ratings in the model; do not treat missing ratings as zero loading.
- Verify power balance and units (pandapower uses MW/Mvar internally).
- Compare the same bus locations, load assumptions and resource powers in
  Python and MATLAB before claiming validation.
- Keep raw CSV outputs and software/package versions for reproducibility.
