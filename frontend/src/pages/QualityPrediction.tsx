import { useEffect, useState } from "react";
import { AuthError, api } from "../api";

type Risk = {
  sample_id: string;
  product: string;
  parameter: string;
  value: number;
  spec_min: number;
  spec_max: number;
  offspec_risk_0_1: number;
};

/** Module 3 — FR-M3-01..03 (docs/SRS.md section 3.1.3). All heuristic placeholders. */
export default function QualityPrediction({ onAuthLost }: { onAuthLost: () => void }) {
  const [rows, setRows] = useState<Risk[]>([]);

  useEffect(() => {
    (async () => {
      try {
        setRows(await api<Risk[]>("/api/quality/offspec-risk"));
      } catch (e) {
        if (e instanceof AuthError) onAuthLost();
      }
    })();
  }, []);

  return (
    <div className="card">
      <h2>ماژول ۳ — پیش‌بینی هوشمند کیفیت و شناسایی OOS</h2>
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
