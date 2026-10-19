import { useEffect, useState } from "react";
import { AuthError, api } from "../api";
import RangeBar from "../components/RangeBar";

type Tag = {
  tag_id: string;
  unit: string;
  description: string;
  measurement_unit: string;
  normal_min: number;
  normal_max: number;
};

type Envelope = Tag & {
  value: number | null;
  status: string;
  status_label: string;
  basis: "model" | "not_modeled";
  operating_band_p2_5_97_5?: [number, number];
  ci95_of_mean?: [number, number];
  model_mean?: number;
  note?: string;
};

type Correlation = {
  ready: boolean;
  target?: string;
  target_note?: string;
  features?: string[];
  r2_test?: number;
  r2_train?: number;
  target_r2?: number;
  meets_target?: boolean;
  n_train?: number;
  n_test?: number;
};

/** Module 1 — FR-M1-01..03 (docs/SRS.md section 3.1.1).
 * FR-M1-02/03 now show real trained-model output (operating envelope +
 * 95% CI, multivariate R^2) for the tags backend/app/ml/synthetic.py
 * models; everything else is still the old fixed-band heuristic,
 * labelled "basis: not_modeled". Measured on synthetic data only. */
export default function ProcessIntelligence({ onAuthLost }: { onAuthLost: () => void }) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [envelopes, setEnvelopes] = useState<Record<string, Envelope>>({});
  const [correlation, setCorrelation] = useState<Correlation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await api<Tag[]>("/api/process-intelligence/tags");
        setTags(list);
        const results = await Promise.all(
          list.map((t) => api<Envelope>(`/api/process-intelligence/tags/${t.tag_id}/envelope`))
        );
        const byId: Record<string, Envelope> = {};
        results.forEach((r) => (byId[r.tag_id] = r));
        setEnvelopes(byId);
        setCorrelation(await api<Correlation>("/api/process-intelligence/productivity-correlation"));
      } catch (e) {
        if (e instanceof AuthError) onAuthLost();
        else setError(String(e));
      }
    })();
  }, []);

  return (
    <div className="card">
      <h2>ماژول ۱ — هوش فرآیند و بهینه‌سازی شرایط عملیاتی</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}

      <table>
        <thead>
          <tr>
            <th>تگ</th>
            <th>واحد فرآیندی</th>
            <th>شرح</th>
            <th>مقدار</th>
            <th>محدوده</th>
            <th>نمودار محدوده</th>
            <th>CI ۹۵٪ میانگین</th>
            <th>وضعیت</th>
          </tr>
        </thead>
        <tbody>
          {tags.map((t) => {
            const e = envelopes[t.tag_id];
            const band = e?.operating_band_p2_5_97_5 ?? [t.normal_min, t.normal_max];
            return (
              <tr key={t.tag_id}>
                <td>{t.tag_id}</td>
                <td>{t.unit}</td>
                <td>{t.description}</td>
                <td>
                  {e?.value ?? "—"} {t.measurement_unit}
                </td>
                <td>
                  {band[0]}–{band[1]} {t.measurement_unit}
                  {e?.basis === "model" ? (
                    <span className="badge badge-model">مدل</span>
                  ) : (
                    <span className="badge badge-warn">مدل‌سازی‌نشده</span>
                  )}
                </td>
                <td>
                  <RangeBar value={e?.value} lo={band[0]} hi={band[1]} marker={e?.model_mean ?? null} />
                </td>
                <td>{e?.ci95_of_mean ? `${e.ci95_of_mean[0]} – ${e.ci95_of_mean[1]}` : "—"}</td>
                <td className={e ? `status-${e.status}` : ""}>{e?.status_label ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="note">
        «مدل»: محدوده و CI ۹۵٪ از مدل آموزش‌دیده روی داده سنتتیک. «مدل‌سازی‌نشده»: مقایسه با محدوده ثابت seed‌شده (جای‌نگه‌دار).
      </p>

      <h3>همبستگی چندمتغیره با شاخص بهره‌وری (FR-M1-03)</h3>
      {correlation?.ready ? (
        <>
          <p>
            هدف: <code>{correlation.target}</code> — R²<sub>test</sub> ={" "}
            <b className={correlation.meets_target ? "status-green" : "status-red"}>{correlation.r2_test}</b>
            {" "}(هدف ≥ {correlation.target_r2}, آموزش n={correlation.n_train}, آزمون n={correlation.n_test})
          </p>
          <p className="note">{correlation.target_note}</p>
          <p className="note">متغیرها ({correlation.features?.length}): {correlation.features?.join("، ")}</p>
        </>
      ) : (
        <p className="note">مدل‌ها هنوز آموزش ندیده‌اند.</p>
      )}
    </div>
  );
}
