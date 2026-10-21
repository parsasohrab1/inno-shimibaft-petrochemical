import { useEffect, useState } from "react";
import { AuthError, api } from "../api";
import Collapsible from "../components/Collapsible";
import Gauge from "../components/Gauge";
import KpiCard from "../components/KpiCard";
import ProcessOverview from "../components/ProcessOverview";
import Sparkline from "../components/Sparkline";

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

type History = { tag_id: string; points: { ts: string; value: number }[] };

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
 * FR-M1-02/03 show real trained-model output (operating envelope + 95%
 * CI, multivariate R^2). As of the shared digital-twin work
 * (backend/app/ml/digital_twin.py), ALL 10 tags — MTBE unit and MEK unit
 * — are covered ("basis: model"); the "not_modeled" fallback below is
 * only a defensive default for any future tag added without a twin
 * column. Measured on synthetic data only.
 *
 * Presentation rewritten to a glanceable card grid (big gauge + trend +
 * traffic light per tag) instead of a dense text/table wall — the full
 * numeric table (CI95, basis) stays available as a collapsible detail so
 * nothing is lost, only de-emphasised. */
export default function ProcessIntelligence({ onAuthLost }: { onAuthLost: () => void }) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [envelopes, setEnvelopes] = useState<Record<string, Envelope>>({});
  const [histories, setHistories] = useState<Record<string, History>>({});
  const [correlation, setCorrelation] = useState<Correlation | null>(null);
  const [mekCorrelation, setMekCorrelation] = useState<Correlation | null>(null);
  const [overview, setOverview] = useState<any>(null);
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
        // History backs an optional trend sparkline only — fetched with
        // allSettled so one tag's history failing (e.g. a brand-new tag
        // with no historian rows yet) never blocks the rest of the page.
        const histSettled = await Promise.allSettled(
          list.map((t) => api<History>(`/api/process-intelligence/tags/${t.tag_id}/history?limit=40`))
        );
        const histById: Record<string, History> = {};
        histSettled.forEach((r) => {
          if (r.status === "fulfilled") histById[r.value.tag_id] = r.value;
          else if (r.reason instanceof AuthError) onAuthLost();
        });
        setHistories(histById);
        setCorrelation(await api<Correlation>("/api/process-intelligence/productivity-correlation"));
        setMekCorrelation(await api<Correlation>("/api/process-intelligence/mek-productivity-correlation"));
        setOverview(await api<any>("/api/process-intelligence/process-overview"));
      } catch (e) {
        if (e instanceof AuthError) onAuthLost();
        else setError(String(e));
      }
    })();
  }, []);

  const renderCorrelation = (title: string, c: Correlation | null) =>
    c?.ready ? (
      <KpiCard
        label={title}
        value={c.r2_test}
        status={c.meets_target ? "good" : "bad"}
        statusText={c.meets_target ? "برآورده شد" : "برآورده نشد"}
        target={`R²test (هدف ≥ ${c.target_r2}، آموزش n=${c.n_train}، آزمون n=${c.n_test})`}
      >
        <Collapsible>
          <p className="note">هدف: {c.target}</p>
          <p className="note">{c.target_note}</p>
          <p className="note">متغیرها ({c.features?.length}): {c.features?.join("، ")}</p>
        </Collapsible>
      </KpiCard>
    ) : (
      <div className="kpi-card">
        <div className="kpi-label">{title}</div>
        <p className="note">مدل‌ها هنوز آموزش ندیده‌اند.</p>
      </div>
    );

  return (
    <>
      <ProcessOverview overview={overview} />
      <div className="card">
        <h2>ماژول ۱ — هوش فرآیند و بهینه‌سازی شرایط عملیاتی</h2>
        {error && <p style={{ color: "#c0392b" }}>{error}</p>}

        <div className="tag-grid">
          {tags.map((t) => {
            const e = envelopes[t.tag_id];
            const band = e?.operating_band_p2_5_97_5 ?? [t.normal_min, t.normal_max];
            const h = histories[t.tag_id];
            return (
              <div className="tag-card" key={t.tag_id}>
                <div className="tag-card-head">
                  <span className="tag-card-id">{t.tag_id}</span>
                  <span className="note">{t.unit}</span>
                </div>
                <div className="tag-card-desc">{t.description}</div>
                <Gauge
                  value={e?.value}
                  lo={band[0]}
                  hi={band[1]}
                  unit={t.measurement_unit}
                  status={e?.status ?? "unknown"}
                  statusLabel={e?.status_label}
                  marker={e?.model_mean ?? null}
                  markerLabel="میانگین مدل"
                />
                {h && h.points.length >= 2 && (
                  <div className="kpi-trend" style={{ marginTop: 4 }}>
                    <Sparkline values={h.points.map((p) => p.value)} width={180} />
                  </div>
                )}
                <div className="note" style={{ marginTop: 4 }}>
                  {e?.basis === "model" ? (
                    <span className="badge badge-model">مدل</span>
                  ) : (
                    <span className="badge badge-warn">مدل‌سازی‌نشده</span>
                  )}
                  {e?.ci95_of_mean && (
                    <span style={{ marginInlineStart: 6 }}>
                      CI ۹۵٪ میانگین: {e.ci95_of_mean[0]} – {e.ci95_of_mean[1]}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <Collapsible title="جزئیات فنی (محدوده دقیق، مبنای هر تگ)">
          <table>
            <thead>
              <tr>
                <th>تگ</th>
                <th>واحد فرآیندی</th>
                <th>مقدار</th>
                <th>محدوده</th>
                <th>CI ۹۵٪ میانگین</th>
                <th>مبنا</th>
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
                    <td>{e?.value ?? "—"} {t.measurement_unit}</td>
                    <td>{band[0]}–{band[1]} {t.measurement_unit}</td>
                    <td>{e?.ci95_of_mean ? `${e.ci95_of_mean[0]} – ${e.ci95_of_mean[1]}` : "—"}</td>
                    <td>{e?.basis === "model" ? "مدل" : "مدل‌سازی‌نشده"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="note">
            «مدل»: محدوده و CI ۹۵٪ از مدل آموزش‌دیده روی دوقلوی دیجیتال سنتتیک مشترک (برای همه ۱۰ تگ). «مدل‌سازی‌نشده»: حالت پیش‌فرض محافظه‌کارانه برای تگ‌های آینده‌ای که هنوز ستونی در دوقلوی دیجیتال ندارند.
          </p>
        </Collapsible>

        <h3>همبستگی چندمتغیره با شاخص‌های بهره‌وری (FR-M1-03)</h3>
        <div className="kpi-grid">
          {renderCorrelation("همبستگی واحد MTBE", correlation)}
          {renderCorrelation("همبستگی واحد MEK (دوقلوی دیجیتال)", mekCorrelation)}
        </div>
      </div>
    </>
  );
}
