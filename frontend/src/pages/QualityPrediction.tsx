import { useEffect, useState } from "react";
import { AuthError, api } from "../api";
import RangeBar from "../components/RangeBar";

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

/** Module 3 — FR-M3-01..03 (docs/SRS.md section 3.1.3).
 * model-predictions is the real GradientBoosting purity regressor + the
 * 30-min-ahead OOS classifier + real feature-importance ranking — see
 * backend/app/ml/module3_quality.py. The offspec-risk table below is the
 * older, separate "latest sample lab result vs spec" view. */
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

      <h3>پیش‌بینی خلوص MTBE (مدل واقعی) — FR-M3-01</h3>
      {pred?.ready ? (
        <>
          <p className="note">{pred.data_source}</p>
          <p>
            خلوص پیش‌بینی‌شده: <b>{pred.predicted_purity_pct}٪</b>
          </p>
          <RangeBar value={pred.predicted_purity_pct} lo={SPEC_MIN} hi={SPEC_MAX} marker={SPEC_MIN} />
          <p className="note">
            MAE روی مجموعه آزمون: <b className={pred.purity_model?.meets_target ? "status-green" : "status-red"}>
              {pred.purity_model?.mae_test_pct}٪
            </b>{" "}
            (هدف ≤ {pred.purity_model?.target_mae_pct}٪)
            <span className={`badge ${pred.purity_model?.meets_target ? "badge-ok" : "badge-bad"}`}>
              {pred.purity_model?.meets_target ? "برآورده شد" : "برآورده نشد"}
            </span>
          </p>

          <h4>احتمال خارج از مشخصه ۳۰ دقیقه آینده — FR-M3-02</h4>
          <p>
            احتمال OOS: <b className={pred.oos_30min_flag ? "status-red" : "status-green"}>
              {((pred.oos_30min_probability ?? 0) * 100).toFixed(1)}٪
            </b>{" "}
            {pred.oos_30min_flag ? "— هشدار" : "— عادی"} (آستانه تصمیم {pred.oos_model?.decision_threshold})
          </p>
          <p className="note">
            روی مجموعه آزمون: TPR=
            <b className={pred.oos_model?.meets_target ? "status-green" : "status-red"}>{(
              (pred.oos_model?.tpr_test ?? 0) * 100
            ).toFixed(1)}</b>
            ٪ (هدف ≥ {(pred.oos_model?.target_tpr ?? 0) * 100}٪), دقت={((pred.oos_model?.precision_test ?? 0) * 100).toFixed(1)}
            ٪، AUC={pred.oos_model?.auc_test}
          </p>
          <p className="warning-text">{pred.oos_model?.caveat}</p>

          <h4>عوامل مؤثر رتبه‌بندی‌شده (واقعی) — FR-M3-03</h4>
          <table>
            <thead>
              <tr>
                <th>عامل</th>
                <th>سهم اهمیت</th>
              </tr>
            </thead>
            <tbody>
              {(pred.contributing_factors ?? []).map((f, i) => (
                <tr key={i}>
                  <td>{f.tag_label}</td>
                  <td>{f.importance != null ? `${(f.importance * 100).toFixed(1)}٪` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="note">{pred?.note ?? "در حال بارگذاری..."}</p>
      )}

      <h3>آخرین نمونه‌های آزمایشگاه نسبت به مشخصه (داده نمونه)</h3>
      <table>
        <thead>
          <tr>
            <th>نمونه</th>
            <th>محصول</th>
            <th>پارامتر</th>
            <th>مقدار</th>
            <th>مشخصه (min–max)</th>
            <th>ریسک OOS (۰–۱)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.sample_id}>
              <td>{r.sample_id}</td>
              <td>{r.product}</td>
              <td>{r.parameter}</td>
              <td>{r.value}</td>
              <td>
                {r.spec_min}–{r.spec_max}
              </td>
              <td className={r.offspec_risk_0_1 > 0.5 ? "status-red" : r.offspec_risk_0_1 > 0.2 ? "status-yellow" : "status-green"}>
                {r.offspec_risk_0_1}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
