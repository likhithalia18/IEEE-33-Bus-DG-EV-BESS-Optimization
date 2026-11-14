"""
Basic Particle Swarm Optimization (PSO) demonstration.

Decision variables:
  x[0] = DG bus index (rounded to an eligible bus)
  x[1] = DG active power (MW)
  x[2] = EVCS bus index (rounded to an eligible bus)
  x[3] = BESS bus index (rounded to an eligible bus)
  x[4] = BESS discharge power (MW)

EVCS charging power is fixed so the optimizer cannot reduce the EV demand to zero.
This starter optimizes a single steady-state operating point. It does not yet
optimize DSTATCOM, V2G, switching configuration, queueing, SOC over time, or VSI.
"""
import numpy as np
import pandas as pd
import pandapower as pp
from common import make_network, run_loadflow, scale_loads, total_active_loss_mw, voltage_deviation, OUT, V_MIN, V_MAX

# Illustrative assumptions; replace with approved limits and scenario settings.
LOAD_FACTOR = 1.20
EVCS_P_MW = 0.30
EVCS_Q_MVAR = 0.05
DG_MIN_MW, DG_MAX_MW = 0.05, 0.80
BESS_MIN_MW, BESS_MAX_MW = 0.00, 0.50
W_LOSS = 1.0
W_VD = 10.0
PENALTY_WEIGHT = 1000.0

# Bus index 0 is the slack bus; use buses 1..32 as candidates.
CANDIDATE_BUSES = np.arange(1, 33)

def evaluate(x):
    dg_bus = int(np.clip(np.rint(x[0]), CANDIDATE_BUSES.min(), CANDIDATE_BUSES.max()))
    dg_mw = float(np.clip(x[1], DG_MIN_MW, DG_MAX_MW))
    ev_bus = int(np.clip(np.rint(x[2]), CANDIDATE_BUSES.min(), CANDIDATE_BUSES.max()))
    bess_bus = int(np.clip(np.rint(x[3]), CANDIDATE_BUSES.min(), CANDIDATE_BUSES.max()))
    bess_mw = float(np.clip(x[4], BESS_MIN_MW, BESS_MAX_MW))

    try:
        net = make_network()
        scale_loads(net, LOAD_FACTOR)
        pp.create_sgen(net, bus=dg_bus, p_mw=dg_mw, q_mvar=0.0, name="Optimized PV DG")
        pp.create_load(net, bus=ev_bus, p_mw=EVCS_P_MW, q_mvar=EVCS_Q_MVAR, name="EVCS")
        if bess_mw > 0:
            # Steady-state approximation: BESS discharge represented as generation.
            pp.create_sgen(net, bus=bess_bus, p_mw=bess_mw, q_mvar=0.0, name="BESS discharge")
        run_loadflow(net)

        v = net.res_bus.vm_pu.to_numpy()
        loss = total_active_loss_mw(net)
        vd = voltage_deviation(net)
        violation = np.maximum(0, V_MIN - v).sum() + np.maximum(0, v - V_MAX).sum()
        # Add a small penalty for line loading > 100% only where max_loading_percent is available.
        if "max_loading_percent" in net.line.columns:
            loading = net.res_line.loading_percent.to_numpy()
            line_violation = np.maximum(0, loading - 100.0).sum() / 100.0
        else:
            line_violation = 0.0
        fitness = W_LOSS * loss + W_VD * vd + PENALTY_WEIGHT * (violation + line_violation)
        details = {
            "fitness": fitness, "dg_bus_zero_based": dg_bus, "dg_bus_number": dg_bus + 1,
            "dg_mw": dg_mw, "evcs_bus_zero_based": ev_bus, "evcs_bus_number": ev_bus + 1,
            "evcs_mw": EVCS_P_MW, "bess_bus_zero_based": bess_bus,
            "bess_bus_number": bess_bus + 1, "bess_discharge_mw": bess_mw,
            "active_losses_mw": loss, "voltage_deviation_pu2": vd,
            "min_voltage_pu": float(v.min()), "max_voltage_pu": float(v.max()),
            "voltage_violation_sum": float(violation),
            "converged": bool(net.converged)
        }
        return fitness, details
    except Exception:
        return 1e9, {"fitness": 1e9, "converged": False}

def pso(n_particles=18, iterations=35, seed=7):
    rng = np.random.default_rng(seed)
    lower = np.array([1, DG_MIN_MW, 1, 1, BESS_MIN_MW], dtype=float)
    upper = np.array([32, DG_MAX_MW, 32, 32, BESS_MAX_MW], dtype=float)
    dim = len(lower)
    pos = rng.uniform(lower, upper, size=(n_particles, dim))
    vel = np.zeros_like(pos)
    pbest = pos.copy()
    pbest_fit = np.full(n_particles, np.inf)
    gbest = None
    gbest_fit = np.inf
    history = []

    inertia, c1, c2 = 0.72, 1.49, 1.49

    for it in range(iterations):
        for i in range(n_particles):
            fit, _ = evaluate(pos[i])
            if fit < pbest_fit[i]:
                pbest_fit[i] = fit
                pbest[i] = pos[i].copy()
            if fit < gbest_fit:
                gbest_fit = fit
                gbest = pos[i].copy()

        history.append({"iteration": it + 1, "best_fitness": gbest_fit})
        r1 = rng.random((n_particles, dim))
        r2 = rng.random((n_particles, dim))
        vel = inertia * vel + c1 * r1 * (pbest - pos) + c2 * r2 * (gbest - pos)
        pos = np.clip(pos + vel, lower, upper)

        print(f"Iteration {it+1:02d}/{iterations}: best fitness = {gbest_fit:.8f}")

    _, best_details = evaluate(gbest)
    return gbest, best_details, pd.DataFrame(history)

def main():
    best_x, best, history = pso()
    history.to_csv(OUT / "pso_convergence.csv", index=False)
    pd.DataFrame([best]).to_csv(OUT / "pso_best_solution.csv", index=False)

    import matplotlib.pyplot as plt
    plt.figure(figsize=(8, 5))
    plt.plot(history["iteration"], history["best_fitness"], marker="o", markersize=3)
    plt.xlabel("Iteration")
    plt.ylabel("Best fitness")
    plt.title("PSO convergence")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT / "pso_convergence.png", dpi=200)
    plt.close()

    print("\nBest decision vector:", best_x)
    print("Best solution:")
    for k, v in best.items():
        print(f"  {k}: {v}")
    print(f"\nResults saved in: {OUT}")

if __name__ == "__main__":
    main()
