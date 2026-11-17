from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pandapower as pp
import pandapower.networks as pn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

V_MIN = 0.95
V_MAX = 1.05

# Explicit planning assumptions used to create a modified IEEE 33-bus case.
# pandapower bus indices are zero-based: index 17 is Bus 18 (1-based).
COMMERCIAL_FEEDER_BUS = 17
COMMERCIAL_FEEDER_P_MW = 0.20
COMMERCIAL_FEEDER_Q_MVAR = 0.08
THERMAL_RATING_FACTOR = 0.90


def make_network():
    """Create the modified IEEE 33-bus benchmark used by every study case.

    Modifications are intentionally limited to:
      1) adding an aggregate commercial/EV-corridor feeder at Bus 18; and
      2) applying a 10% planning derating to existing line current ratings.
    These are explicit study assumptions, not manufacturer ratings.
    """
    net = pn.case33bw()
    if len(net.bus) != 33:
        raise RuntimeError(f"Expected 33 buses, got {len(net.bus)}")

    pp.create_load(
        net, bus=COMMERCIAL_FEEDER_BUS,
        p_mw=COMMERCIAL_FEEDER_P_MW,
        q_mvar=COMMERCIAL_FEEDER_Q_MVAR,
        name="Added commercial EV-corridor feeder"
    )

    if "max_i_ka" in net.line.columns:
        rated = net.line["max_i_ka"].notna() & (net.line["max_i_ka"] > 0)
        net.line.loc[rated, "max_i_ka"] *= THERMAL_RATING_FACTOR

    return net


def run_loadflow(net):
    """Run AC Newton-Raphson power flow and fail loudly if it does not converge."""
    pp.runpp(net, algorithm="nr", init="auto", calculate_voltage_angles=True,
             enforce_q_lims=True, max_iteration=30, tolerance_mva=1e-8)
    if not net.converged:
        raise RuntimeError("AC load flow did not converge.")
    return net


def scale_loads(net, factor):
    """Scale all existing constant-power loads by factor."""
    net.load.loc[:, "p_mw"] *= factor
    net.load.loc[:, "q_mvar"] *= factor


def total_active_loss_mw(net):
    line_loss = float(net.res_line.pl_mw.sum()) if len(net.res_line) else 0.0
    trafo_loss = float(net.res_trafo.pl_mw.sum()) if len(net.trafo) else 0.0
    return line_loss + trafo_loss


def voltage_deviation(net):
    v = net.res_bus.vm_pu.to_numpy()
    return float(np.sum((v - 1.0) ** 2))


def voltage_stability_index(net):
    """Return minimum line-based VSI using the receiving-end branch quantities.

    Uses the common two-bus VSI expression in per-unit quantities. Values closer
    to 1 indicate a larger margin; values approaching 0 indicate a weaker line.
    """
    if len(net.line) == 0 or len(net.res_line) == 0:
        return float("nan")
    base_mva = float(net.sn_mva)
    values = []
    for idx, line in net.line.iterrows():
        if not bool(line.in_service):
            continue
        fb = int(line.from_bus)
        v_send = float(net.res_bus.at[fb, "vm_pu"])
        r_ohm = float(line.r_ohm_per_km) * float(line.length_km)
        x_ohm = float(line.x_ohm_per_km) * float(line.length_km)
        vn_kv = float(net.bus.at[fb, "vn_kv"])
        z_base = (vn_kv ** 2) / base_mva
        r_pu, x_pu = r_ohm / z_base, x_ohm / z_base
        p_pu = float(net.res_line.at[idx, "p_to_mw"]) / base_mva
        q_pu = float(net.res_line.at[idx, "q_to_mvar"]) / base_mva
        vsi = (v_send ** 4
               - 4.0 * (p_pu * x_pu - q_pu * r_pu) ** 2
               - 4.0 * (p_pu * r_pu + q_pu * x_pu) * (v_send ** 2))
        values.append(vsi)
    return float(min(values)) if values else float("nan")


def result_summary(net, case_name):
    v = net.res_bus.vm_pu
    min_idx = int(v.idxmin())
    max_idx = int(v.idxmax())
    return {
        "case": case_name,
        "min_voltage_pu": float(v.min()),
        "min_voltage_bus": min_idx + 1,
        "max_voltage_pu": float(v.max()),
        "max_voltage_bus": max_idx + 1,
        "active_losses_mw": total_active_loss_mw(net),
        "voltage_deviation_pu2": voltage_deviation(net),
        "minimum_vsi": voltage_stability_index(net),
        "converged": bool(net.converged),
    }


def loss_reduction_percent(reference_loss, case_loss):
    if reference_loss is None or abs(float(reference_loss)) < 1e-12:
        return 0.0
    return 100.0 * (float(reference_loss) - float(case_loss)) / float(reference_loss)


def save_voltage_plot(curves, filename, title):
    """curves is a dict: label -> (bus-number array, voltage array)."""
    plt.figure(figsize=(10, 5.5))
    for label, (buses, volts) in curves.items():
        plt.plot(buses, volts, marker="o", markersize=3, label=label)
    plt.axhline(V_MIN, linestyle="--", linewidth=1, label="Lower limit 0.95 pu")
    plt.axhline(V_MAX, linestyle="--", linewidth=1, label="Upper limit 1.05 pu")
    plt.xlabel("Bus number")
    plt.ylabel("Voltage magnitude (p.u.)")
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / filename, dpi=200)
    plt.close()


def save_bar_plot(labels, values, filename, title, ylabel):
    plt.figure(figsize=(8, 5))
    plt.bar(labels, values)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT / filename, dpi=200)
    plt.close()
