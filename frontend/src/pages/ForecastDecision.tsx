import { FormEvent, useEffect, useState } from "react";
import { AuthError, api } from "../api";

type Outlook = { basis: string; by_product: { product: string; total_t: number }[]; is_placeholder: boolean };
type WhatIfResult = {
  parameter: string;
  delta_pct: number;
  base_total_t: number;
  naive_estimated_total_t: number;
  warning: string;
};

/** Module 4 — FR-M4-01..03 (docs/SRS.md section 3.1.4). All heuristic placeholders. */
export default function ForecastDecision({ onAuthLost }: { onAuthLost: () => void }) {
  const [outlook, setOutlook] = useState<Outlook | null>(null);
  const [param, setParam] = useState("feed_rate");
  const [delta, setDelta] = useState(5);
  const [result, setResult] = useState<WhatIfResult | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setOutlook(await api<Outlook>("/api/forecast/outlook"));
      } catch (e) {
        if (e instanceof AuthError) onAuthLost();
      }
    })();
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

  return (
    <div className="card">
      <h2>ماژول ۴ — پیش‌بینی تولید و تصمیم‌یار عملیاتی بلادرنگ</h2>
      <h3>چشم‌انداز تولید (نمونه)</h3>
      <table>
        <thead>
          <tr>
            <th>محصول</th>
            <th>مجموع (تن)</th>
          </tr>
        </thead>
        <tbody>
          {outlook?.by_product.map((p) => (
            <tr key={p.product}>
              <td>{p.product}</td>
              <td>{p.total_t}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>شبیه‌ساز «چه‌می‌شود اگر» (جای‌نگه‌دار خطی ساده)</h3>
      <form onSubmit={runWhatIf}>
        <label>
          پارامتر
          <input value={param} onChange={(e) => setParam(e.target.value)} />
        </label>{" "}
        <label>
          تغییر (٪)
          <input type="number" value={delta} onChange={(e) => setDelta(Number(e.target.value))} />
        </label>{" "}
        <button type="submit">اجرا</button>
      </form>
      {result && (
        <p>
          برآورد ساده: {result.base_total_t} → {result.naive_estimated_total_t} تن
          <br />
          <small style={{ color: "#b7950b" }}>{result.warning}</small>
        </p>
      )}
    </div>
  );
}
