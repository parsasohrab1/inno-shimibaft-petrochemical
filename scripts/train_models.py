"""CLI to (re)train SPRO's real module 1-4 models from synthetic data.

The backend also does this automatically in a background thread on first
boot if no trained models are cached yet (see backend/app/main.py's
``_ensure_models``, mirroring ``seed.py``'s auto-seed pattern) — run this
script directly when you want a bigger/different training run, or to
force a retrain after changing backend/app/ml/*.py.

Usage:
    python scripts/train_models.py
    python scripts/train_models.py --n-points 50000 --seed 7
    python scripts/train_models.py --out data/models

Trains ONLY on synthetic data (scripts/generate_synthetic_data.py,
extended in backend/app/ml/synthetic.py) — there is still no real Shimi
Baft plant data. See docs/SRS.md and backend/app/ml/__init__.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import config  # noqa: E402
from app.ml.train import train_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-points", type=int, default=config.TRAIN_N_POINTS)
    parser.add_argument("--seed", type=int, default=config.TRAIN_SEED)
    parser.add_argument("--out", type=str, default=str(config.MODELS_DIR))
    parser.add_argument("--upset-rate", type=float, default=0.015)
    parser.add_argument("--upset-scale", type=float, default=3.0)
    args = parser.parse_args()

    print(f"Training on {args.n_points} synthetic points (seed={args.seed}) -> {args.out} ...")
    metrics = train_all(
        out_dir=Path(args.out),
        n_points=args.n_points,
        seed=args.seed,
        upset_rate=args.upset_rate,
        upset_scale=args.upset_scale,
    )
    print(f"Done in {metrics['training_seconds']}s. Summary:")
    summary = {
        "module1.productivity_correlation.r2_test": metrics["module1"]["productivity_correlation"]["r2_test"],
        "module2.deviation_detection.measured_recall": metrics["module2"]["deviation_detection"]["measured_recall"],
        "module3.purity_regression.mae_test_pct": metrics["module3"]["purity_regression"]["mae_test_pct"],
        "module3.oos_classifier.tpr_test": metrics["module3"]["oos_classifier"]["tpr_test"],
        "module4.forecast.overall_rmse_pct": metrics["module4"]["forecast"]["overall_rmse_pct"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
