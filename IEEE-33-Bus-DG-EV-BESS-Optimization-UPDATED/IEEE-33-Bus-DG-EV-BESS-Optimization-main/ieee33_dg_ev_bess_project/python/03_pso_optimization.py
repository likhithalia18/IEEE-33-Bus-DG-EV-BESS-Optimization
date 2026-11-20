"""
Particle Swarm Optimization for DG, EVCS and BESS placement on the modified
IEEE 33-bus network.

The PSO optimizes one 120% loading operating point. Its best placement is then
evaluated by 02_resource_scenarios.py across the operating-scenario suite.
"""
import numpy as np
import pandas as pd
import pandapower as pp
from common import (
    make_network, run_loadflow, scale_loads, total_active_loss_mw,
    voltage_deviation, voltage_stability_index, OUT, V_MIN, V_MAX
)

LOAD_FACTOR = 1.20
EVCS_P_MW = 0.30
EVCS_Q_MVAR = 0.05
DG_MIN_MW, DG_MAX_MW = 0.05, 0.80
BESS_MIN_MW, BESS_MAX_MW = 0.05, 0.50
W_LOSS = 1.0
W_VD = 10.0
PENALTY_WEIGHT = 1000.0

# Bus index 0 is the slack bus; candidate indices 1..32 are buses 2..33.
CANDIDATE_BUSES = np.arange(1, 33)
N_PARTICLES = 40
N_ITERATIONS = 80
SEEDS = [7, 17, 27, 37, 47]


def decode_position(x):
    dg_bus = int(np.clip(np.rint(x[0]), CANDIDATE_BUSES.min(), CANDIDATE_BUSES.max()))
    ev_bus = int(np.clip(np.rint(x[2]), CANDIDATE_BUSES.min(), CANDIDATE_BUSES.max()))
    bess_bus = int(np.clip(np.rint(x[3]), CANDIDATE_BUSES.min(), CANDIDATE_BUSES.max()))
    return dg_bus, ev_bus, bess_bus


def evaluate(x):
    dg_bus, ev_bus, bess_bus = decode_position(x)
    dg_mw = float(np.clip(x[1], DG_MIN_MW, DG_MAX_MW))
    bess_mw = float(np.clip(x[4], BESS_MIN_MW, BESS_MAX_MW))

    # Separate placements are required unless a shared hub is explicitly modeled.
    if len({dg_bus, ev_bus, bess_bus}) != 3:
        return 1e9, {"fitness": 1e9, "converged": False,
                     "placement_constraint_violation": True}

    try:
        net = make_network()
        scale_loads(net, LOAD_FACTOR)
        pp.create_sgen(net, bus=dg_bus, p_mw=dg_mw, q_mvar=0.0, name="Optimized PV DG")
        pp.create_load(net, bus=ev_bus, p_mw=EVCS_P_MW, q_mvar=EVCS_Q_MVAR, name="EVCS")
        if bess_mw > 0:
            pp.create_sgen(net, bus=bess_bus, p_mw=bess_mw, q_mvar=0.0, name="BESS discharge")
        run_loadflow(net)

        v = net.res_bus.vm_pu.to_numpy()
        loss = total_active_loss_mw(net)
        vd = voltage_deviation(net)
        violation = np.maximum(0, V_MIN - v).sum() + np.maximum(0, v - V_MAX).sum()

        # Enforce each line's actual thermal loading limit. pandapower writes
        # calculated loading to res_line.loading_percent; max_loading_percent
        # is the allowable limit (100% unless explicitly changed).
        if "loading_percent" not in net.res_line.columns:
            raise RuntimeError("pandapower did not calculate res_line.loading_percent")
        loading = net.res_line["loading_percent"].to_numpy(dtype=float)
        if np.isnan(loading).all():
            raise RuntimeError("All calculated line-loading values are NaN")
        limits = (net.line["max_loading_percent"].to_numpy(dtype=float)
                  if "max_loading_percent" in net.line.columns
                  else np.full(len(net.line), 100.0))
        valid = np.isfinite(loading) & net.line["in_service"].to_numpy(dtype=bool)
        line_violation = np.maximum(0.0, loading[valid] - limits[valid]).sum() / 100.0

        fitness = W_LOSS * loss + W_VD * vd + PENALTY_WEIGHT * (violation + line_violation)
        details = {
            "fitness": float(fitness),
            "dg_bus_zero_based": dg_bus, "dg_bus_number": dg_bus + 1,
            "dg_mw": dg_mw,
            "evcs_bus_zero_based": ev_bus, "evcs_bus_number": ev_bus + 1,
            "evcs_mw": EVCS_P_MW,
            "bess_bus_zero_based": bess_bus, "bess_bus_number": bess_bus + 1,
            "bess_discharge_mw": bess_mw,
            "active_losses_mw": loss,
            "voltage_deviation_pu2": vd,
            "minimum_vsi": voltage_stability_index(net),
            "min_voltage_pu": float(v.min()), "max_voltage_pu": float(v.max()),
            "voltage_violation_sum": float(violation),
            "line_loading_violation_sum": float(line_violation),
            "placement_constraint_violation": False,
            "converged": bool(net.converged)
        }
        return fitness, details
    except Exception as exc:
        return 1e9, {"fitness": 1e9, "converged": False, "error": str(exc)}


def pso(n_particles=N_PARTICLES, iterations=N_ITERATIONS, seed=7):
    rng = np.random.default_rng(seed)
    lower = np.array([1, DG_MIN_MW, 1, 1, BESS_MIN_MW], dtype=float)
    upper = np.array([32, DG_MAX_MW, 32, 32, BESS_MAX_MW], dtype=float)
    dim = len(lower)
    pos = rng.uniform(lower, upper, size=(n_particles, dim))
    vel = np.zeros_like(pos)

    def repair_bus_collisions(position):
        """Keep DG, EVCS and BESS on three distinct non-slack buses."""
        bus_columns = [0, 2, 3]
        used = set()
        for column in bus_columns:
            bus = int(np.clip(np.rint(position[column]), 1, 32))
            if bus in used:
                available = [b for b in CANDIDATE_BUSES if int(b) not in used]
                bus = int(rng.choice(available))
            position[column] = float(bus)
            used.add(bus)
        return position

    for particle in range(n_particles):
        pos[particle] = repair_bus_collisions(pos[particle])
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

        # Keep rounded DG, EVCS and BESS buses distinct after each update.
        for i in range(n_particles):
            pos[i] = repair_bus_collisions(pos[i])

        print(f"Seed {seed} | Iteration {it+1:02d}/{iterations}: best fitness = {gbest_fit:.8f}")

    _, best_details = evaluate(gbest)
    return gbest, best_details, pd.DataFrame(history)


def main():
    seed_rows = []
    all_histories = []
    best_overall = None
    best_fitness = np.inf

    for seed in SEEDS:
        best_x, best, history = pso(seed=seed)
        history.insert(0, "seed", seed)
        all_histories.append(history)
        row = dict(best)
        row["seed"] = seed
        seed_rows.append(row)
        if best.get("fitness", 1e9) < best_fitness:
            best_fitness = best.get("fitness", 1e9)
            best_overall = best

    if best_overall is None or not np.isfinite(best_fitness) or best_fitness >= 1e9:
        raise RuntimeError("PSO did not find a feasible converged solution. Check network assumptions and constraints.")

    seed_results = pd.DataFrame(seed_rows)
    seed_results.to_csv(OUT / "pso_seed_results.csv", index=False)
    pd.concat(all_histories, ignore_index=True).to_csv(OUT / "pso_convergence.csv", index=False)
    pd.DataFrame([best_overall]).to_csv(OUT / "pso_best_solution.csv", index=False)

    numeric = seed_results.select_dtypes(include=[np.number]).drop(columns=["seed"], errors="ignore")
    stats = pd.DataFrame({
        "metric": numeric.columns,
        "mean": [numeric[c].mean() for c in numeric.columns],
        "std": [numeric[c].std(ddof=1) for c in numeric.columns]
    })
    stats.to_csv(OUT / "pso_seed_statistics.csv", index=False)

    import matplotlib.pyplot as plt
    combined_history = pd.concat(all_histories, ignore_index=True)
    plt.figure(figsize=(8, 5))
    for seed in SEEDS:
        h = combined_history[combined_history["seed"] == seed]
        plt.plot(h["iteration"], h["best_fitness"], label=f"Seed {seed}")
    plt.xlabel("Iteration")
    plt.ylabel("Best fitness")
    plt.title("PSO convergence across independent seeds")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "pso_convergence.png", dpi=200)
    plt.close()

    print("\nBest solution across seeds:")
    for key, value in best_overall.items():
        print(f"  {key}: {value}")
    print("\nAcross-seed statistics:")
    print(stats.to_string(index=False))
    print(f"\nResults saved in: {OUT}")


if __name__ == "__main__":
    main()
