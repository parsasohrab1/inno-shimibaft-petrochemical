import { useEffect, useState } from "react";
import { AuthError, api } from "../api";
import BarList from "../components/BarList";
import Collapsible from "../components/Collapsible";
import Gauge from "../components/Gauge";
import KpiCard from "../components/KpiCard";
import TrafficLight from "../components/TrafficLight";

type Risk = {
  sample_id: string;
  product: string;
  parameter: string;
  value: number;
  spec_min: number;
  spec_max: number;
  offspec_risk_0_1: number;
};

type Factor = { feature: string | null; tag_label: string; importance: number | null };

type ModelPredictions = {
  ready: boolean;
  data_source?: string;
  input_features?: Record<string, number>;
  predicted_purity_pct?: number;
  purity_model?: { mae_test_pct: number; target_mae_pct: number; meets_target: boolean };
  oos_30min_probability?: number;
  oos_30min_flag?: boolean;
  oos_model?: {
    decision_threshold: number;
    tpr_test: number;
    precision_test: number;
    auc_test: number;
    target_tpr: number;
    meets_target: boolean;
    caveat: string;
  };
  contributing_factors?: Factor[];
  note?: string;
};

const SPEC_MIN = 97.0;
const SPEC_MAX = 100.0;

function riskStatus(risk: number): "red" | "yellow" | "green" {
  return risk > 0.5 ? "red" : risk > 0.2 ? "yellow" : "green";
}
const RISK_LABEL = { red: "ریسک بالا", yellow: "ریسک متوسط", green: "ریسک پایین" } as const;

/** Module 3 — FR-M3-01..03 (docs/SRS.md section 3.1.3).
 * model-predictions is the real GradientBoosting purity regressor + the
 * 30-min-ahead OOS classifier + real feature-importance ranking — see
 * backend/app/ml/module3_quality.py. The offspec-risk table below is the
 * older, separate "latest sample lab result vs spec" view.
 *
 * Presentation rewritten: purity/MAE/OOS/TPR become KPI tiles with a
 * gauge for purity-vs-spec, the feature-importance table becomes a
 * ranked horizontal bar list, and every lab-sample row now carries the
 * same exact-value + range + 3-lamp traffic-light treatment as the rest
 * of the dashboard instead of a bare risk number. */
export default function QualityPrediction({ onAuthLost }: { onAuthLost: () => void }) {
  const [rows, setRows] = useState<Risk[]>([]);
  const [pred, setPred] = useState<ModelPredictions | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setRows(await api<Risk[]>("/api/quality/offspec-risk"));
        setPred(await api<ModelPredictions>("/api/quality/model-predictions"));
      } catch (e) {
        if (e instanceof AuthError) onAuthLost();
      }
    })();
  }, []);

  return (
    <div className="card">
      <h2>ماژول ۳ — پیش‌بینی هوشمند کیفیت و شناسایی OOS</h2>

      {pred?.ready ? (
        <>
          <p className="note">{pred.data_source}</p>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">خلوص پیش‌بینی‌شده MTBE (مدل واقعی) — FR-M3-01</div>
              <Gauge
                value={pred.predicted_purity_pct}
                lo={SPEC_MIN}
                hi={SPEC_MAX}
                unit="٪"
                status={pred.predicted_purity_pct != null && pred.predicted_purity_pct >= SPEC_MIN ? "green" : "red"}
                statusLabel={pred.predicted_purity_pct != null && pred.predicted_purity_pct >= SPEC_MIN ? "درون مشخصه" : "خارج از مشخصه"}
              />
              <Collapsible>
                <p className="note">
                  MAE روی مجموعه آزمون:{" "}
                  <b className={pred.purity_model?.meets_target ? "status-green" : "status-red"}>
                    {pred.purity_model?.mae_test_pct}٪
                  </b>{" "}
                  (هدف ≤ {pred.purity_model?.target_mae_pct}٪)
                  <span className={`badge ${pred.purity_model?.meets_target ? "badge-ok" : "badge-bad"}`}>
                    {pred.purity_model?.meets_target ? "برآورده شد" : "برآورده نشد"}
                  </span>
                </p>
              </Collapsible>
            </div>

            <KpiCard
              label="احتمال خارج از مشخصه ۳۰ دقیقه آینده — FR-M3-02"
              value={((pred.oos_30min_probability ?? 0) * 100).toFixed(1)}
              unit="٪"
              status={pred.oos_30min_flag ? "bad" : "good"}
              statusText={pred.oos_30min_flag ? "هشدار" : "عادی"}
              target={`آستانه تصمیم ${pred.oos_model?.decision_threshold}`}
            >
              <Collapsible>
                <p className="note">
                  روی مجموعه آزمون: TPR=
                  <b className={pred.oos_model?.meets_target ? "status-green" : "status-red"}>
                    {((pred.oos_model?.tpr_test ?? 0) * 100).toFixed(1)}
                  </b>
                  ٪ (هدف ≥ {(pred.oos_model?.target_tpr ?? 0) * 100}٪), دقت={((pred.oos_model?.precision_test ?? 0) * 100).toFixed(1)}٪،
                  AUC={pred.oos_model?.auc_test}
                </p>
                <p className="warning-text">{pred.oos_model?.caveat}</p>
              </Collapsible>
            </KpiCard>
          </div>

          <h4>عوامل مؤثر رتبه‌بندی‌شده (واقعی) — FR-M3-03</h4>
          <BarList
            items={(pred.contributing_factors ?? []).map((f) => ({ label: f.tag_label, value: f.importance ?? 0 }))}
          />
        </>
      ) : (
        <p className="note">{pred?.note ?? "در حال بارگذاری..."}</p>
      )}

      <h3>آخرین نمونه‌های آزمایشگاه نسبت به مشخصه (داده نمونه)</h3>
      <div className="tag-grid">
        {rows.map((r) => {
          const st = riskStatus(r.offspec_risk_0_1);
          return (
            <div className="tag-card" key={r.sample_id}>
              <div className="tag-card-head">
                <span className="tag-card-id">{r.sample_id}</span>
                <span className="note">{r.product} — {r.parameter}</span>
              </div>
              <Gauge
                value={r.value}
                lo={r.spec_min}
                hi={r.spec_max}
                status={st}
                statusLabel={RISK_LABEL[st]}
              />
              <div className="note" style={{ display: "flex", justifyContent: "space-between" }}>
                <span>ریسک OOS: {r.offspec_risk_0_1}</span>
                <TrafficLight status={st} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
