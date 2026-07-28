#!/usr/bin/env bash
# Runs all 5 week notebooks in order via jupyter nbconvert --execute, in place.
# Each notebook loads CSVs saved by the previous one, so order matters — see README.md.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

NOTEBOOKS=(
  notebook/week1_eda.ipynb
  notebook/week2_features.ipynb
  notebook/week3_regression.ipynb
  notebook/week4_ets_forecasting.ipynb
  notebook/week5_scenarios.ipynb
)

if [[ ! -f data/owid-co2-data.csv ]]; then
  echo "error: data/owid-co2-data.csv not found — download it first (see README.md step 4)." >&2
  exit 1
fi

for nb in "${NOTEBOOKS[@]}"; do
  echo "==> Running $nb"
  jupyter nbconvert --to notebook --execute --inplace "$nb"
done

echo "==> All 5 week notebooks completed successfully."
