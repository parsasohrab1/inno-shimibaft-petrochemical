"""Real (not placeholder) ML/analytics layer for SPRO modules 1-4.

Trained on synthetic data only (scripts/generate_synthetic_data.py's
physics-informed MTBE generator, extended here for size/variety — see
synthetic.py). There is still no real Shimi Baft plant data; every
metric this package produces is explicitly a *synthetic-validation-set*
measurement, not a measurement against real plant history. See
docs/SRS.md section 2.3 / 3.2.3-3.2.4 for why that is the deliberate,
anticipated situation for this phase, and the per-requirement status
table in docs/SRS.md section 3.1 for what is and is not measured.

Layout:
  synthetic.py   training-data generation (wraps/extends the official
                 generator; also builds the engineered feature columns
                 shared by modules 1 and 3).
  module1_process.py   FR-M1 operating envelope + 95% CI, multivariate
                        correlation/R^2 against a productivity proxy.
  module2_energy.py    FR-M2 ISO-50001-style EnB regression baseline,
                        EnPI, CUSUM, deviation-detection measurement,
                        and the LP production-mix optimizer.
  module3_quality.py   FR-M3 purity regression model, 30-min-ahead OOS
                        classifier, feature-importance ranking.
  module4_forecast.py  FR-M4 Holt's-smoothing production forecaster,
                        what-if re-simulation through modules 1-3,
                        multi-criteria scenario ranking.
  train.py             orchestrates training of everything above and
                        writes joblib artifacts + a metrics.json summary
                        to the models directory (see registry.py).
  registry.py          lazy-loads the trained artifacts/metrics for the
                        FastAPI services at request time (no retraining
                        per request).
"""
