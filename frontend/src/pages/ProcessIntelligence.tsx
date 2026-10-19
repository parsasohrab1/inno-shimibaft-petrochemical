import { useEffect, useState } from "react";
import { AuthError, api } from "../api";

type Tag = {
  tag_id: string;
  unit: string;
  description: string;
  measurement_unit: string;
  normal_min: number;
  normal_max: number;
};

type Envelope = Tag & { value: number | null; status: string; status_label: string };

/** Module 1 — FR-M1-01..03 (docs/SRS.md section 3.1.1). All heuristic placeholders. */
export default function ProcessIntelligence({ onAuthLost }: { onAuthLost: () => void }) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [envelopes, setEnvelopes] = useState<Record<string, Envelope>>({});
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
            <th>محدوده نرمال</th>
            <th>وضعیت</th>
          </tr>
        </thead>
        <tbody>
          {tags.map((t) => {
            const e = envelopes[t.tag_id];
            return (
              <tr key={t.tag_id}>
                <td>{t.tag_id}</td>
                <td>{t.unit}</td>
                <td>{t.description}</td>
                <td>
                  {e?.value ?? "—"} {t.measurement_unit}
                </td>
                <td>
                  {t.normal_min}–{t.normal_max} {t.measurement_unit}
                </td>
                <td className={e ? `status-${e.status}` : ""}>{e?.status_label ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
