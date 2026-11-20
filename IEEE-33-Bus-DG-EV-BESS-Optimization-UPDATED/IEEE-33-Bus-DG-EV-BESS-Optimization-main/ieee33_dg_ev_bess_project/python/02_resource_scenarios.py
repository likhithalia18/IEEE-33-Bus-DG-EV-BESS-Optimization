import json
import numpy as np
import pandas as pd
import pandapower as pp
from common import (
    make_network, run_loadflow, scale_loads, result_summary,
    save_voltage_plot, save_bar_plot, OUT, loss_reduction_percent
)

# Illustrative study assumptions retained from the original project.
EVCS_P_MW = 0.30
EVCS_Q_MVAR = 0.05
PV_P_MW = 0.50
BESS_DISCHARGE_MW = 0.20
BESS_Q_MVAR = 0.00

# Original heuristic/trial placement (zero-based pandapower indices).
PV_BUS = 17
EV_BUS = 24
BESS_BUS = 29


def add_pv(net, bus, p_mw):
    return pp.create_sgen(net, bus=bus, p_mw=p_mw, q_mvar=0.0, name="PV DG")


def add_evcs(net, bus, p_mw, q_mvar):
    return pp.create_load(net, bus=bus, p_mw=p_mw, q_mvar=q_mvar, name="EV fast charging station")


def add_bess_as_dispatchable_injection(net, bus, p_discharge_mw):
    """Steady-state BESS discharge approximation as a generation injection."""
    return pp.create_sgen(net, bus=bus, p_mw=p_discharge_mw, q_mvar=BESS_Q_MVAR,
                          name="BESS discharge")


def load_pso_solution():
    path = OUT / "pso_best_solution.csv"
    if not path.exists():
        raise FileNotFoundError(
            "pso_best_solution.csv not found. Run 03_pso_optimization.py before "
            "02_resource_scenarios.py so the optimized placement is evaluated."
        )
    row = pd.read_csv(path).iloc[0]
    required = ["dg_bus_zero_based", "dg_mw", "evcs_bus_zero_based",
                "bess_bus_zero_based", "bess_discharge_mw"]
    missing = [c for c in required if c not in row.index or pd.isna(row[c])]
    if missing:
        raise ValueError(f"PSO solution is missing required columns: {missing}")
    return {
        "dg_bus": int(row["dg_bus_zero_based"]),
        "dg_mw": float(row["dg_mw"]),
        "ev_bus": int(row["evcs_bus_zero_based"]),
        "bess_bus": int(row["bess_bus_zero_based"]),
        "bess_mw": float(row["bess_discharge_mw"]),
    }


def run_placement_case(name, load_factor, placement=None, include_ev=True, pv_scale=1.0):
    net = make_network()
    scale_loads(net, load_factor)
    if include_ev:
        ev_bus = placement["ev_bus"] if placement else EV_BUS
        add_evcs(net, ev_bus, EVCS_P_MW, EVCS_Q_MVAR)

    if placement is None:
        # Heuristic/trial case uses the original fixed DG and BESS locations.
        add_pv(net, PV_BUS, PV_P_MW * pv_scale)
        add_bess_as_dispatchable_injection(net, BESS_BUS, BESS_DISCHARGE_MW)
    else:
        add_pv(net, placement["dg_bus"], placement["dg_mw"] * pv_scale)
        add_bess_as_dispatchable_injection(net, placement["bess_bus"], placement["bess_mw"])

    run_loadflow(net)
    summary = result_summary(net, name)
    return net, summary


def run_qsts_24h(placement):
    """Run a 24-hour quasi-static time-series using the PSO placement.

    Assumptions: 1-hour time step, 1 MWh BESS, 95% charge/discharge
    efficiencies, 20%-90% SOC limits. To represent PV-supported charging,
    at most 50% of instantaneous PV output is allocated to BESS charging;
    the remainder is reserved for other feeder demand. During the evening
    peak, BESS discharge is limited to 50% of EVCS demand and the BESS rating.
    These are study assumptions, not measured operating data.
    """
    pv_profile = np.array([
        0, 0, 0, 0, 0, 0.05, 0.15, 0.35, 0.60, 0.80, 0.95, 1.00,
        0.95, 0.85, 0.65, 0.40, 0.15, 0.02, 0, 0, 0, 0, 0, 0
    ], dtype=float)
    ev_profile = np.array([
        0.10, 0.08, 0.07, 0.06, 0.06, 0.08, 0.12, 0.20, 0.25, 0.20, 0.15, 0.12,
        0.12, 0.12, 0.15, 0.20, 0.35, 0.55, 0.75, 0.90, 1.00, 0.80, 0.45, 0.20
    ], dtype=float)

    pv_bus = int(placement["dg_bus"])
    ev_bus = int(placement["ev_bus"])
    bess_bus = int(placement["bess_bus"])
    pv_rated_mw = float(placement["dg_mw"])
    bess_rated_mw = float(placement["bess_mw"])
    dt_hours = 1.0
    soc = 0.50
    soc_min, soc_max = 0.20, 0.90
    capacity_mwh = 1.00
    eta_charge, eta_discharge = 0.95, 0.95
    rows = []

    for hour in range(24):
        net = make_network()
        scale_loads(net, 1.0)
        pv_output = pv_rated_mw * pv_profile[hour]
        ev_demand = EVCS_P_MW * ev_profile[hour]
        add_evcs(net, ev_bus, ev_demand, EVCS_Q_MVAR * ev_profile[hour])
        add_pv(net, pv_bus, pv_output)

        soc_start = soc
        p_charge = 0.0
        p_discharge = 0.0
        if 9 <= hour <= 15 and bess_rated_mw > 0:
            pv_surplus_allocated = 0.50 * pv_output
            soc_headroom_power = ((soc_max - soc) * capacity_mwh /
                                  (eta_charge * dt_hours))
            p_charge = min(bess_rated_mw, pv_surplus_allocated,
                           max(0.0, soc_headroom_power))
            if p_charge > 0:
                pp.create_load(net, bus=bess_bus, p_mw=p_charge, q_mvar=0.0,
                               name="BESS charging")
                soc += p_charge * eta_charge * dt_hours / capacity_mwh
        elif 17 <= hour <= 22 and bess_rated_mw > 0:
            ev_support_limit = 0.50 * ev_demand
            available_energy_power = ((soc - soc_min) * capacity_mwh *
                                      eta_discharge / dt_hours)
            p_discharge = min(bess_rated_mw, ev_support_limit,
                              max(0.0, available_energy_power))
            if p_discharge > 0:
                pp.create_sgen(net, bus=bess_bus, p_mw=p_discharge, q_mvar=0.0,
                               name="BESS discharging")
                soc -= p_discharge * dt_hours / (eta_discharge * capacity_mwh)

        soc = float(np.clip(soc, soc_min, soc_max))
        run_loadflow(net)
        summary = result_summary(net, f"Hour {hour:02d}")
        rows.append({
            "hour": hour, "pv_bus_number": pv_bus + 1,
            "evcs_bus_number": ev_bus + 1, "bess_bus_number": bess_bus + 1,
            "pv_output_mw": pv_output, "evcs_demand_mw": ev_demand,
            "bess_charge_mw": p_charge, "bess_discharge_mw": p_discharge,
            "bess_soc_start_pu": soc_start, "bess_soc_end_pu": soc,
            "bess_soc_pu": soc, "min_voltage_pu": summary["min_voltage_pu"],
            "min_voltage_bus": summary["min_voltage_bus"],
            "active_losses_mw": summary["active_losses_mw"],
            "minimum_vsi": summary["minimum_vsi"],
            "line_max_loading_percent": float(net.res_line.loading_percent.max())
        })

    qsts = pd.DataFrame(rows)
    qsts.to_csv(OUT / "qsts_24h_results.csv", index=False)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(qsts["hour"], qsts["pv_output_mw"], marker="o", label="PV output (MW)")
    ax.plot(qsts["hour"], qsts["evcs_demand_mw"], marker="o", label="EVCS demand (MW)")
    ax.plot(qsts["hour"], qsts["bess_charge_mw"], marker="o", label="BESS charging (MW)")
    ax.plot(qsts["hour"], qsts["bess_discharge_mw"], marker="o", label="BESS discharging (MW)")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Power (MW)")
    ax.set_title("24-hour PV, EVCS and BESS operating profile (PSO placement)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "qsts_24h_power_profile.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(qsts["hour"], qsts["bess_soc_pu"] * 100, marker="o")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("BESS state of charge (%)")
    ax.set_title("24-hour BESS state-of-charge profile (PSO placement)")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "qsts_24h_soc.png", dpi=200)
    plt.close(fig)
    return qsts


def main():
    pso = load_pso_solution()
    trial = {"dg_bus": PV_BUS, "dg_mw": PV_P_MW, "ev_bus": EV_BUS,
             "bess_bus": BESS_BUS, "bess_mw": BESS_DISCHARGE_MW}

    # Reference cases and comparison of fixed trial vs. PSO placement at
    # multiple operating load levels. This directly connects the PSO output
    # to the multi-scenario evaluation rather than leaving it unused.
    cases = []
    curves = {}
    for factor in [1.00, 1.20, 1.30]:
        label = f"{int(factor * 100)}% load"
        # Uncompensated means no DG/BESS; use EV demand only.
        uncomp = make_network()
        scale_loads(uncomp, factor)
        add_evcs(uncomp, EV_BUS, EVCS_P_MW, EVCS_Q_MVAR)
        run_loadflow(uncomp)
        high_summary = result_summary(uncomp, f"Uncompensated high EV - {label}")
        cases.append(high_summary)
        curves[high_summary["case"]] = (np.arange(1, 34), uncomp.res_bus.vm_pu.to_numpy())

        trial_net, trial_summary = run_placement_case(
            f"Heuristic trial - {label}", factor, placement=trial
        )
        cases.append(trial_summary)
        curves[trial_summary["case"]] = (np.arange(1, 34), trial_net.res_bus.vm_pu.to_numpy())

        pso_net, pso_summary = run_placement_case(
            f"PSO optimized - {label}", factor, placement=pso
        )
        cases.append(pso_summary)
        curves[pso_summary["case"]] = (np.arange(1, 34), pso_net.res_bus.vm_pu.to_numpy())

    # Preserve baseline and low-renewable reference cases from the original study.
    base = make_network()
    run_loadflow(base)
    base_summary = result_summary(base, "Modified-network base load")
    cases.append(base_summary)

    low_pv, low_pv_summary = run_placement_case(
        "Low renewable generation", 1.0, placement=trial, include_ev=False, pv_scale=0.20
    )
    cases.append(low_pv_summary)

    summary = pd.DataFrame(cases)
    reference_loss = summary.loc[summary["case"] == "Uncompensated high EV - 120% load",
                                 "active_losses_mw"].iloc[0]
    summary["loss_reduction_vs_uncompensated_percent"] = summary["active_losses_mw"].apply(
        lambda loss: loss_reduction_percent(reference_loss, loss)
    )
    summary.to_csv(OUT / "multi_scenario_summary.csv", index=False)

    save_voltage_plot(curves, "multi_scenario_voltage_profiles.png",
                      "Uncompensated, heuristic and PSO voltage profiles")
    save_bar_plot(summary["case"], summary["active_losses_mw"],
                  "multi_scenario_active_losses.png",
                  "Active power losses across operating scenarios",
                  "Active power loss (MW)")

    qsts = run_qsts_24h(pso)
    print(summary.to_string(index=False))
    print("\n24-hour QSTS results (first rows):")
    print(qsts.head().to_string(index=False))
    print(f"\nPSO placement used: {json.dumps(pso)}")
    print(f"Results saved in: {OUT}")


if __name__ == "__main__":
    main()
