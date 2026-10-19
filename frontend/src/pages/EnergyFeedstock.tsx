import { useEffect, useState } from "react";
import { AuthError, api } from "../api";

type Intensity = {
  items: { product: string; ts: string; gj_per_t: number }[];
  average_gj_per_t: number | null;
  flagged: { product: string; gj_per_t: number }[];
  note?: string;
};

type FeedBatch = { batch_id: string; feed_type: string; quantity_t: number; quality_assay: string; received_at: string };

/** Module 2 — FR-M2-01..04 (docs/SRS.md section 3.1.2). All heuristic placeholders. */
export default function EnergyFeedstock({ onAuthLost }: { onAuthLost: () => void }) {
  const [intensity, setIntensity] = useState<Intensity | null>(null);
  const [batches, setBatches] = useState<FeedBatch[]>([]);

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

  return (
    <div className="card">
      <h2>ماژول ۲ — بهینه‌سازی هوشمند مصرف انرژی و خوراک</h2>
      <p>
        میانگین Energy Intensity (نمونه): <b>{intensity?.average_gj_per_t ?? "—"} GJ/t</b>
      </p>
      {intensity?.note && <p style={{ fontSize: "0.85rem", color: "#666" }}>{intensity.note}</p>}
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
    </div>
  );
}
