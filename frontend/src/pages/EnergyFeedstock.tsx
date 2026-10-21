import { useEffect, useState } from "react";
import { AuthError, api } from "../api";
import Collapsible from "../components/Collapsible";
import KpiCard from "../components/KpiCard";
import LineChart from "../components/LineChart";

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
 * backend/app/ml/module2_energy.py.
 *
 * Presentation rewritten: headline numbers are KPI tiles (with a real
 * trend sparkline built from the already-fetched intensity.items
 * series), the EnB regression formula and deviation-detection method
 * move into a collapsible detail, and the LP scenarios render as
 * proper cards with revenue/cost/profit chips instead of a wall of
 * inline text. */
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
  const intensityTrend = (intensity?.items ?? []).map((i) => i.gj_per_t);

  return (
    <div className="card">
      <h2>ماژول ۲ — بهینه‌سازی هوشمند مصرف انرژی و خوراک</h2>

      <div className="kpi-grid">
        <KpiCard
          label="میانگین شدت انرژی (نمونه نمایشی)"
          value={intensity?.average_gj_per_t ?? "—"}
          unit="GJ/t"
          trend={intensityTrend}
          status="neutral"
        >
          {intensity?.note && <p className="note">{intensity.note}</p>}
        </KpiCard>

        {intensity?.energy_baseline?.ready && dd && (
          <KpiCard
            label="نرخ تشخیص انحراف انرژی (EnB، آستانه ۵٪>)"
            value={dd.measured_recall_pct}
            unit="٪"
            status={dd.meets_target ? "good" : "bad"}
            statusText={dd.meets_target ? "برآورده شد" : "برآورده نشد"}
            target={`هدف ≥ ${dd.target_recall_pct}٪، دقت ${dd.measured_precision_pct}٪`}
          >
            <Collapsible>
              <p className="note">
                خط پایه ISO 50001 (EnB): energy_gj = {intensity.energy_baseline.intercept_gj} +{" "}
                {intensity.energy_baseline.slope_gj_per_t} × production_t (بازه مرجع {intensity.energy_baseline.interval_min} دقیقه)
              </p>
              <p className="note">{dd.method}</p>
            </Collapsible>
          </KpiCard>
        )}
      </div>

      {intensity?.energy_baseline?.ready ? (
        <>
          <h3>CUSUM انرژی — ISO 50001 (پیش‌نمایش سری سنتتیک مرجع)</h3>
          <LineChart
            points={preview.map((p) => ({ x: p.ts.slice(11, 16), y: p.cusum_gj }))}
            mode="bar"
            zeroLine
            unit=" GJ"
            formatTitle={(p) => `${p.x}: CUSUM=${p.y} GJ`}
          />
          <p className="note">
            CUSUM = مجموع تجمعی (مصرف واقعی − مصرف پیش‌بینی‌شده از خط پایه EnB). میله آبی: مصرف واقعی بیشتر از خط پایه؛ میله قرمز: کمتر از خط پایه (صرفه‌جویی تجمعی).
          </p>
        </>
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
              <div className="rec-head">
                <b>{s.description}</b>
                <span>
                  {s.name === mix.recommended_scenario && <span className="badge badge-ok">پیشنهادی (بیشترین سود)</span>}
                  {!s.feasible && <span className="badge badge-bad">غیرممکن</span>}
                </span>
              </div>
              <div className="rec-chips">
                <span className="chip">درآمد {s.revenue_usd.toLocaleString()}$</span>
                <span className="chip">هزینه خوراک {s.feed_cost_usd.toLocaleString()}$</span>
                <span className="chip">هزینه انرژی {s.energy_cost_usd.toLocaleString()}$</span>
                <span className="chip chip-action">سود {s.profit_usd.toLocaleString()}$</span>
              </div>
              <div className="note">
                تولید: {Object.entries(s.production_t).map(([p, v]) => `${p}: ${v.toFixed(1)}t`).join(" | ")}
              </div>
              {s.binding_constraints.length > 0 && (
                <div className="note">محدودیت فعال: {s.binding_constraints.join("، ")}</div>
              )}
              <Collapsible title="جزئیات فرض‌ها">
                <p className="note">{s.assumptions_note}</p>
              </Collapsible>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
