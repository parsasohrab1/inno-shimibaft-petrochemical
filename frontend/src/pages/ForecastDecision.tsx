import { FormEvent, useEffect, useState } from "react";
import { AuthError, api } from "../api";
import BarList from "../components/BarList";
import Collapsible from "../components/Collapsible";
import KpiCard from "../components/KpiCard";
import LineChart from "../components/LineChart";
import RecommendationCard from "../components/RecommendationCard";

type Outlook = {
  ready: boolean;
  is_placeholder: boolean;
  data_source?: string;
  method?: string;
  forecast_kg_h_by_horizon_h?: Record<string, number[]>;
  measured_rmse_pct_by_horizon_h?: Record<string, number>;
  overall_rmse_pct?: number;
  target_rmse_pct?: number;
  meets_target?: boolean;
  note?: string;
};

type WhatIfResult = {
  ready: boolean;
  is_placeholder: boolean;
  parameter?: string;
  delta_pct?: number;
  baseline?: { predicted_purity_pct: number; production_rate_kg_h: number; predicted_energy_intensity_gj_per_t: number; oos_margin_pct: number };
  scenario?: { predicted_purity_pct: number; production_rate_kg_h: number; predicted_energy_intensity_gj_per_t: number; oos_margin_pct: number };
  method?: string;
  error?: string;
  valid_parameters?: string[];
};

type RankedScenario = {
  name: string;
  delta: Record<string, number>;
  production_rate_kg_h: number;
  predicted_purity_pct: number;
  predicted_energy_intensity_gj_per_t: number;
  score: number;
};

type ScenariosResult = { ready: boolean; weights_note?: string; scenarios: RankedScenario[]; recommended?: string | null };

type Decision = { decision: string; actor_username: string | null; note: string | null; ts: string };
type Recommendation = {
  id: number;
  module: string;
  title: string;
  detail: string;
  status: string;
  effective_status: string;
  suggested_action: { parameter: string; delta_pct: number } | null;
  expected_effect: Record<string, number> | null;
  decisions: Decision[];
  created_at: string;
};

function Delta({ before, after }: { before: number; after: number }) {
  const diff = after - before;
  if (Math.abs(diff) < 1e-9) return <span className="note">بدون تغییر</span>;
  return (
    <span className="note">
      {diff > 0 ? "▲" : "▼"} {Math.abs(diff).toFixed(2)}
    </span>
  );
}

/** Module 4 — FR-M4-01..03 (docs/SRS.md section 3.1.4).
 * outlook/what-if/scenarios are now real (Holt's forecaster + a genuine
 * cross-module re-simulation through modules 2-3 — see
 * backend/app/ml/module4_forecast.py). Recommendations carry a
 * suggested_action + expected_effect and an append-only accept/reject
 * audit trail (NFR-06) — the original row is never mutated.
 *
 * Presentation rewritten: the forecast becomes a labelled line chart
 * (kept honest — no fabricated confidence band, since the Holt model
 * doesn't return one), scenario ranking becomes ranked bar cards, the
 * what-if table gets a Δ column, and recommendations render as the new
 * RecommendationCard (action/effect chips + accept/reject buttons)
 * instead of plain text. */
export default function ForecastDecision({ onAuthLost }: { onAuthLost: () => void }) {
  const [outlook, setOutlook] = useState<Outlook | null>(null);
  const [param, setParam] = useState("reactor_temp_C");
  const [delta, setDelta] = useState(1);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [scenarios, setScenarios] = useState<ScenariosResult | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);

  const load = async () => {
    try {
      setOutlook(await api<Outlook>("/api/forecast/outlook"));
      setScenarios(await api<ScenariosResult>("/api/forecast/scenarios"));
      setRecs(await api<Recommendation[]>("/api/forecast/recommendations"));
    } catch (e) {
      if (e instanceof AuthError) onAuthLost();
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runWhatIf = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setResult(
        await api<WhatIfResult>("/api/forecast/what-if", {
          method: "POST",
          body: JSON.stringify({ parameter: param, delta_pct: delta }),
        })
      );
    } catch (e) {
      if (e instanceof AuthError) onAuthLost();
    }
  };

  const decide = async (recId: number, status: "accepted" | "rejected") => {
    try {
      await api(`/api/forecast/recommendations/${recId}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (e) {
      if (e instanceof AuthError) onAuthLost();
    }
  };

  const autoGenerate = async () => {
    try {
      await api("/api/forecast/recommendations/auto-generate", { method: "POST" });
      await load();
    } catch (e) {
      if (e instanceof AuthError) onAuthLost();
    }
  };

  const horizonSeries = outlook?.forecast_kg_h_by_horizon_h?.["8"] ?? [];
  const maxScore = Math.max(1e-9, ...(scenarios?.scenarios.map((s) => Math.abs(s.score)) ?? [1]));

  return (
    <div className="card">
      <h2>ماژول ۴ — پیش‌بینی تولید و تصمیم‌یار عملیاتی بلادرنگ</h2>

      <h3>پیش‌بینی نرخ تولید ۱ تا ۸ ساعت آینده (هولت) — FR-M4-01</h3>
      {outlook?.ready ? (
        <>
          <div className="kpi-grid">
            <KpiCard
              label="RMSE% کلی پیش‌بینی"
              value={outlook.overall_rmse_pct}
              unit="٪"
              status={outlook.meets_target ? "good" : "bad"}
              statusText={outlook.meets_target ? "برآورده شد" : "برآورده نشد"}
              target={`هدف ≤ ${outlook.target_rmse_pct}٪`}
            />
          </div>
          <LineChart
            points={horizonSeries.map((v, i) => ({ x: `${i * 15}m`, y: v }))}
            mode="line"
            unit=" kg/h"
            formatTitle={(p) => `+${p.x}: ${p.y} kg/h`}
          />
          <p className="note">نمودار بالا: پیش‌بینی ۸ ساعت آینده (هر نقطه ۱۵ دقیقه)، بر پایه سری مرجع سنتتیک — بدون باند اطمینان ساختگی، چون مدل هولت خروجی عدم‌قطعیت نمی‌دهد.</p>
          <Collapsible>
            <p className="note">{outlook.data_source}</p>
            <p className="note">{outlook.method}</p>
            <p className="note">
              به تفکیک افق:{" "}
              {Object.entries(outlook.measured_rmse_pct_by_horizon_h ?? {})
                .map(([h, v]) => `${h}h: ${v}٪`)
                .join(" | ")}
            </p>
          </Collapsible>
        </>
      ) : (
        <p className="note">{outlook?.note ?? "در حال بارگذاری..."}</p>
      )}

      <h3>شبیه‌ساز «چه‌می‌شود اگر» (بازاجرای واقعی ماژول‌های ۲ و ۳) — FR-M2-04</h3>
      <form onSubmit={runWhatIf}>
        <label>
          پارامتر
          <select value={param} onChange={(e) => setParam(e.target.value)}>
            <option value="reactor_temp_C">دمای راکتور (TI-101)</option>
            <option value="reactor_pressure_MPa">فشار راکتور (PI-102)</option>
            <option value="feed_flow_kg_h">دبی خوراک رافینیت ۱ (FI-103)</option>
            <option value="meoh_isobutene_ratio">نسبت متانول:ایزوبوتیلن</option>
          </select>
        </label>{" "}
        <label>
          تغییر (٪)
          <input type="number" value={delta} onChange={(e) => setDelta(Number(e.target.value))} />
        </label>{" "}
        <button type="submit">اجرا</button>
      </form>
      {result?.error && <p style={{ color: "#c0392b" }}>{result.error}</p>}
      {result?.baseline && result?.scenario && (
        <table>
          <thead>
            <tr>
              <th></th>
              <th>خلوص پیش‌بینی‌شده (٪)</th>
              <th>نرخ تولید (kg/h)</th>
              <th>شدت انرژی (GJ/t)</th>
              <th>حاشیه تا مشخصه (٪)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>پایه</td>
              <td>{result.baseline.predicted_purity_pct}</td>
              <td>{result.baseline.production_rate_kg_h}</td>
              <td>{result.baseline.predicted_energy_intensity_gj_per_t}</td>
              <td>{result.baseline.oos_margin_pct}</td>
            </tr>
            <tr>
              <td>سناریو ({result.delta_pct! > 0 ? "+" : ""}{result.delta_pct}٪)</td>
              <td>{result.scenario.predicted_purity_pct} <Delta before={result.baseline.predicted_purity_pct} after={result.scenario.predicted_purity_pct} /></td>
              <td>{result.scenario.production_rate_kg_h} <Delta before={result.baseline.production_rate_kg_h} after={result.scenario.production_rate_kg_h} /></td>
              <td>{result.scenario.predicted_energy_intensity_gj_per_t} <Delta before={result.baseline.predicted_energy_intensity_gj_per_t} after={result.scenario.predicted_energy_intensity_gj_per_t} /></td>
              <td>{result.scenario.oos_margin_pct} <Delta before={result.baseline.oos_margin_pct} after={result.scenario.oos_margin_pct} /></td>
            </tr>
          </tbody>
        </table>
      )}
      {result?.method && <p className="note">{result.method}</p>}

      <h3>رتبه‌بندی سناریوهای عملیاتی جایگزین — FR-M4-03</h3>
      {scenarios?.ready ? (
        <>
          <p className="note">{scenarios.weights_note}</p>
          <BarList
            items={scenarios.scenarios.map((s) => ({ label: s.name, value: s.score }))}
            color="#5b8def"
            formatValue={(v) => v.toFixed(2)}
          />
          {scenarios.scenarios.map((s) => (
            <div key={s.name} className={`scenario-card ${s.name === scenarios.recommended ? "best" : ""}`}>
              <div className="rec-head">
                <b>{s.name}</b>
                {s.name === scenarios.recommended && <span className="badge badge-ok">بالاترین امتیاز</span>}
              </div>
              <div className="rec-chips">
                <span className="chip">امتیاز {s.score}</span>
                <span className="chip">تولید {s.production_rate_kg_h} kg/h</span>
                <span className="chip">خلوص {s.predicted_purity_pct}٪</span>
                <span className="chip">شدت انرژی {s.predicted_energy_intensity_gj_per_t} GJ/t</span>
              </div>
            </div>
          ))}
        </>
      ) : (
        <p className="note">در حال بارگذاری...</p>
      )}

      <h3>توصیه‌ها (اقدام پیشنهادی + اثر مورد انتظار، ممیزی append-only) — FR-M4-02 / NFR-06</h3>
      <button onClick={autoGenerate}>تولید توصیه از برآورد کیفیت فعلی</button>
      {recs.length === 0 && <p className="note">توصیه‌ای ثبت نشده.</p>}
      {recs.map((r) => (
        <RecommendationCard
          key={r.id}
          title={r.title}
          detail={r.detail}
          status={r.effective_status}
          suggestedAction={r.suggested_action}
          expectedEffect={r.expected_effect}
          decisions={r.decisions}
          onAccept={() => decide(r.id, "accepted")}
          onReject={() => decide(r.id, "rejected")}
        />
      ))}
    </div>
  );
}
