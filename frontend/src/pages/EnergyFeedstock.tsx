import { useEffect, useState } from "react";
import { AuthError, api } from "../api";

type Intensity = {
  items: { product: string; ts: string; gj_per_t: number }[];
  average_gj_per_t: number | null;
  flagged: { product: string; gj_per_t: number }[];
  note?: string;
  energy_baseline?: {
    ready: boolean;
    intercept_gj?: number;
    slope_gj_per_t?: number;
    interval_min?: number;
    deviation_threshold_rel_pct?: number;
    deviation_detection?: {
      target_recall_pct: number;
      measured_recall_pct: number;
      measured_precision_pct: number;
      meets_target: boolean;
      method: string;
    };
    note?: string;
  };
  energy_timeseries_preview?: { ts: string; enpi: number; cusum_gj: number }[];
};

type FeedBatch = { batch_id: string; feed_type: string; quantity_t: number; quality_assay: string; received_at: string };

type Scenario = {
  name: string;
  description: string;
  assumptions_note: string;
  production_t: Record<string, number>;
  revenue_usd: number;
  feed_cost_usd: number;
  energy_cost_usd: number;
  profit_usd: number;
  binding_constraints: string[];
  feasible: boolean;
};

type MixResult = {
  feed_availability_t: Record<string, number>;
  energy_budget_gj: number;
  scenarios: Scenario[];
  recommended_scenario: string | null;
  is_placeholder: boolean;
};

/** Module 2 — FR-M2-01..04 (docs/SRS.md section 3.1.2).
 * Energy baseline (EnB/EnPI/CUSUM) and the LP production-mix optimizer
 * are now real, trained/solved on synthetic data — see
 * backend/app/ml/module2_energy.py. */
export default function EnergyFeedstock({ onAuthLost }: { onAuthLost: () => void }) {
  const [intensity, setIntensity] = useState<Intensity | null>(null);
  const [batches, setBatches] = useState<FeedBatch[]>([]);
  const [mix, setMix] = useState<MixResult | null>(null);
  const [loadingMix, setLoadingMix] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setIntensity(await api<Intensity>("/api/energy-feedstock/intensity"));
        setBatches(await api<FeedBatch[]>("/api/energy-feedstock/feed-batches"));
      } catch (e) {
        if (e instanceof AuthError) onAuthLost();
      }
    })();
  }, []);

  const runOptimizer = async () => {
    setLoadingMix(true);
    try {
      setMix(await api<MixResult>("/api/energy-feedstock/optimize-mix", { method: "POST" }));
    } catch (e) {
      if (e instanceof AuthError) onAuthLost();
    } finally {
      setLoadingMix(false);
    }
  };

  const dd = intensity?.energy_baseline?.deviation_detection;
  const preview = intensity?.energy_timeseries_preview ?? [];
  const maxAbsCusum = Math.max(1, ...preview.map((p) => Math.abs(p.cusum_gj)));

  return (
    <div className="card">
      <h2>ماژول ۲ — بهینه‌سازی هوشمند مصرف انرژی و خوراک</h2>
      <p>
        میانگین Energy Intensity (نمونه نمایشی): <b>{intensity?.average_gj_per_t ?? "—"} GJ/t</b>
      </p>
      {intensity?.note && <p className="note">{intensity.note}</p>}

      <h3>خط پایه انرژی ISO 50001 (EnB) — FR-M2-01/02</h3>
      {intensity?.energy_baseline?.ready ? (
        <div className="grid-2">
          <div>
            <p className="note">
              energy_gj = {intensity.energy_baseline.intercept_gj} + {intensity.energy_baseline.slope_gj_per_t} ×
              production_t (بازه مرجع {intensity.energy_baseline.interval_min} دقیقه)
            </p>
            {dd && (
              <p>
                نرخ تشخیص انحراف &gt;۵٪:{" "}
                <b className={dd.meets_target ? "status-green" : "status-red"}>{dd.measured_recall_pct}٪</b>
                {" "}(هدف ≥ {dd.target_recall_pct}٪، دقت {dd.measured_precision_pct}٪)
                <span className={`badge ${dd.meets_target ? "badge-ok" : "badge-bad"}`}>
                  {dd.meets_target ? "برآورده شد" : "برآورده نشد"}
                </span>
                <br />
                <small className="note">{dd.method}</small>
              </p>
            )}
          </div>
          <div>
            <p className="note">CUSUM انرژی (پیش‌نمایش سری سنتتیک مرجع):</p>
            <div className="bars">
              {preview.map((p, i) => (
                <div
                  key={i}
                  className={`bar ${p.cusum_gj < 0 ? "negative" : ""}`}
                  style={{ height: `${Math.max(2, (Math.abs(p.cusum_gj) / maxAbsCusum) * 76)}px` }}
                  title={`${p.ts}: CUSUM=${p.cusum_gj} GJ, EnPI=${p.enpi}`}
                />
              ))}
            </div>
          </div>
        </div>
      ) : (
        <p className="note">{intensity?.energy_baseline?.note ?? "در حال بارگذاری..."}</p>
      )}

      <h3>دسته‌های خوراک اخیر</h3>
      <table>
        <thead>
          <tr>
            <th>شناسه بچ</th>
            <th>نوع خوراک</th>
            <th>مقدار (تن)</th>
            <th>کیفیت</th>
          </tr>
        </thead>
        <tbody>
          {batches.map((b) => (
            <tr key={b.batch_id}>
              <td>{b.batch_id}</td>
              <td>{b.feed_type}</td>
              <td>{b.quantity_t}</td>
              <td>{b.quality_assay}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>بهینه‌ساز ترکیب تولید (LP) — FR-M2-03</h3>
      <button onClick={runOptimizer} disabled={loadingMix}>
        {loadingMix ? "در حال محاسبه..." : "اجرای بهینه‌سازی"}
      </button>
      {mix && (
        <>
          <p className="note">
            موجودی خوراک: {Object.entries(mix.feed_availability_t).map(([k, v]) => `${k}: ${v.toFixed(0)}t`).join(" | ")}
            {" — "}بودجه انرژی: {mix.energy_budget_gj} GJ
          </p>
          {mix.scenarios.map((s) => (
            <div key={s.name} className={`scenario-card ${s.name === mix.recommended_scenario ? "best" : ""}`}>
              <b>{s.description}</b>
              {s.name === mix.recommended_scenario && <span className="badge badge-ok">پیشنهادی (بیشترین سود)</span>}
              {!s.feasible && <span className="badge badge-bad">غیرممکن</span>}
              <div className="note">
                تولید:{" "}
                {Object.entries(s.production_t).map(([p, v]) => `${p}: ${v.toFixed(1)}t`).join(" | ")}
              </div>
              <div className="note">
                درآمد {s.revenue_usd.toLocaleString()}$ − هزینه خوراک {s.feed_cost_usd.toLocaleString()}$ − هزینه انرژی{" "}
                {s.energy_cost_usd.toLocaleString()}$ = سود <b>{s.profit_usd.toLocaleString()}$</b>
              </div>
              {s.binding_constraints.length > 0 && (
                <div className="note">محدودیت فعال: {s.binding_constraints.join("، ")}</div>
              )}
              <div className="note">{s.assumptions_note}</div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
