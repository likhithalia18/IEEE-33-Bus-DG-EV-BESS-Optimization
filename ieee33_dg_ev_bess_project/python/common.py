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

def make_network():
    """Load the standard pandapower IEEE 33-bus benchmark."""
    net = pn.case33bw()
    if len(net.bus) != 33:
        raise RuntimeError(f"Expected 33 buses, got {len(net.bus)}")
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

def result_summary(net, case_name):
    v = net.res_bus.vm_pu
    return {
        "case": case_name,
        "min_voltage_pu": float(v.min()),
        "min_voltage_bus": int(v.idxmin()),
        "max_voltage_pu": float(v.max()),
        "max_voltage_bus": int(v.idxmax()),
        "active_losses_mw": total_active_loss_mw(net),
        "voltage_deviation_pu2": voltage_deviation(net),
        "converged": bool(net.converged),
    }

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
