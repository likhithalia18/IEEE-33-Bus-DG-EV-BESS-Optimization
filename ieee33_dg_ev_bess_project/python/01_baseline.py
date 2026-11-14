import numpy as np
import pandas as pd
from common import make_network, run_loadflow, scale_loads, result_summary, save_voltage_plot, save_bar_plot, OUT

def main():
    loading_levels = [1.00, 1.10, 1.20, 1.30]
    summaries = []
    curves = {}

    for factor in loading_levels:
        net = make_network()
        scale_loads(net, factor)
        run_loadflow(net)

        label = f"{int(factor * 100)}% load"
        summaries.append(result_summary(net, label))
        buses = np.arange(1, len(net.res_bus) + 1)
        curves[label] = (buses, net.res_bus.vm_pu.to_numpy())

        # Save all bus voltages for reproducibility
        pd.DataFrame({
            "bus_index_zero_based": net.res_bus.index,
            "bus_number_one_based": buses,
            "voltage_pu": net.res_bus.vm_pu.to_numpy()
        }).to_csv(OUT / f"baseline_bus_voltages_{int(factor*100)}pct.csv", index=False)

    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "baseline_summary.csv", index=False)

    # Weak buses at base loading, sorted by lowest voltage
    base = make_network()
    run_loadflow(base)
    weak = pd.DataFrame({
        "bus_index_zero_based": base.res_bus.index,
        "bus_number_one_based": np.arange(1, len(base.res_bus) + 1),
        "voltage_pu": base.res_bus.vm_pu.to_numpy()
    }).sort_values("voltage_pu")
    weak.head(10).to_csv(OUT / "weakest_10_buses_base_case.csv", index=False)

    save_voltage_plot(curves, "baseline_voltage_profiles.png",
                      "IEEE 33-bus voltage profiles under loading variations")
    save_bar_plot(summary["case"], summary["active_losses_mw"],
                  "baseline_active_losses.png",
                  "Active power losses under loading variations",
                  "Active power loss (MW)")
    print(summary.to_string(index=False))
    print("\nLowest-voltage buses in base case:")
    print(weak.head(10).to_string(index=False))
    print(f"\nResults saved in: {OUT}")

if __name__ == "__main__":
    main()
