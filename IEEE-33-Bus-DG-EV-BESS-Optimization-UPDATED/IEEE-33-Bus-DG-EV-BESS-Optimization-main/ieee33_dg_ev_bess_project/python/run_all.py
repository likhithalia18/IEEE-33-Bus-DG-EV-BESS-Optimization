"""Run the complete study in dependency order."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCRIPTS = [
    "03_pso_optimization.py",
    "02_resource_scenarios.py",
    "01_baseline.py",
]

for script in SCRIPTS:
    print(f"\n{'=' * 72}\nRunning {script}\n{'=' * 72}", flush=True)
    subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, check=True)

print("\nAll study scripts completed successfully.")
print(f"Check generated files in: {HERE.parent / 'results'}")
