import copy
import numpy as np
import pandas as pd 
from common import make_network, run_loadflow, scale_loads, result_summary, save_voltage_plot, save_bar_plot, OUT

# ILLUSTRATIVE starting assumptions only. Confirm with your supervisor.
EVCS_P_MW = 0.30       # e.g. aggregate 300 kW charging demand
EVCS_Q_MVAR = 0.05     # illustrative reactive demand
PV_P_MW = 0.50         # illustrative PV active power
BESS_DISCHARGE_MW = 0.20
BESS_Q_MVAR = 0.00

# pandapower bus indices are zero-based. Avoid bus 0 (external-grid/slack bus).
PV_BUS = 17
EV_BUS = 24
BESS_BUS = 29

def add_pv(net, bus, p_mw):
    pp_sgen = __import__("pandapower").create_sgen(
        net, bus=bus, p_mw=p_mw, q_mvar=0.0, name="PV DG"
    )
    return pp_sgen

def add_evcs(net, bus, p_mw, q_mvar):
    return __import__("pandapower").create_load(
        net, bus=bus, p_mw=p_mw, q_mvar=q_mvar, name="EV fast charging station"
    )

def add_bess_as_dispatchable_injection(net, bus, p_discharge_mw):
    """
    Simplified steady-state BESS representation as a negative load (injection).
    Positive p_discharge_mw means discharging into the grid.
    This is NOT an SOC/time-coupled battery model; use MATLAB/time-series
    implementation for SOC and charging/discharging energy constraints.
    """
    return __import__("pandapower").create_sgen(
        net, bus=bus, p_mw=p_discharge_mw, q_mvar=0.0, name="BESS discharge"
    )

def run_case(name, ev=False, pv_mw=0.0, bess_mw=0.0, load_factor=1.0):
    net = make_network()
    scale_loads(net, load_factor)
    if ev:
        add_evcs(net, EV_BUS, EVCS_P_MW, EVCS_Q_MVAR)
    if pv_mw > 0:
        add_pv(net, PV_BUS, pv_mw)
    if bess_mw > 0:
        add_bess_as_dispatchable_injection(net, BESS_BUS, bess_mw)
    run_loadflow(net)
    return net, result_summary(net, name)

def main():
    # Scenario 1: base case
    base, s_base = run_case("Base load", load_factor=1.0)

    # Scenario 2: high EV demand; use 120% base load plus EV charging station
    high_ev, s_ev = run_case("High EV demand", ev=True, load_factor=1.20)

    # Scenario 3: low renewable output; small PV output with base load
    low_pv, s_lowpv = run_case("Low renewable generation", pv_mw=0.10, load_factor=1.0)

    # Scenario 4: co-optimized-style illustrative combination.
    # This is a fixed trial allocation, NOT the PSO result. Replace with PSO output.
    combined, s_combined = run_case(
        "Combined PV + EVCS + BESS",
        ev=True, pv_mw=PV_P_MW, bess_mw=BESS_DISCHARGE_MW,
        load_factor=1.0
    )

    summary = pd.DataFrame([s_base, s_ev, s_lowpv, s_combined])
    summary.to_csv(OUT / "multi_scenario_summary.csv", index=False)

    curves = {
        "Base load": (np.arange(1, 34), base.res_bus.vm_pu.to_numpy()),
        "High EV demand": (np.arange(1, 34), high_ev.res_bus.vm_pu.to_numpy()),
        "Low renewable generation": (np.arange(1, 34), low_pv.res_bus.vm_pu.to_numpy()),
        "PV + EVCS + BESS": (np.arange(1, 34), combined.res_bus.vm_pu.to_numpy()),
    }
    save_voltage_plot(curves, "multi_scenario_voltage_profiles.png",
                      "Voltage profile comparison across operating scenarios")
    save_bar_plot(summary["case"], summary["active_losses_mw"],
                  "multi_scenario_active_losses.png",
                  "Active power losses across operating scenarios",
                  "Active power loss (MW)")

    print(summary.to_string(index=False))
    print(f"\nResults saved in: {OUT}")

if __name__ == "__main__":
    main()
