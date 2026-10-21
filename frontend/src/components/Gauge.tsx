import TrafficLight from "./TrafficLight";

const ZONE = { red: "#f6d4cf", yellow: "#fbe9b8", green: "#d9f0e1" };
const POINTER = { red: "#c0392b", yellow: "#b7950b", green: "#1e8449", unknown: "#52514e" };

/** A bigger, standalone range gauge: the exact value, a coloured-zone
 * range bar (red/yellow/green matching the same thresholds the backend
 * computed the status from — see services/process_intelligence.py's
 * `_status_from_band`: red beyond a 10%-of-span margin either side of
 * [lo, hi], yellow inside that margin, green inside [lo, hi] itself),
 * and the 3-lamp traffic light + text label (never colour alone — this
 * account's standing indicator rule). This is the "big" visual meant to
 * replace a bare number-next-to-a-text-range cell. */
export default function Gauge({
  value,
  lo,
  hi,
  unit = "",
  status,
  statusLabel,
  marker,
  markerLabel,
  title,
}: {
  value: number | null | undefined;
  lo: number;
  hi: number;
  unit?: string;
  status: "red" | "yellow" | "green" | "unknown" | string;
  statusLabel?: string;
  marker?: number | null;
  markerLabel?: string;
  title?: string;
}) {
  const span = hi - lo || 1;
  const margin = span * 0.1;
  const domainLo = lo - margin;
  const domainHi = hi + margin;
  const domainSpan = domainHi - domainLo || 1;
  const pct = (v: number) => Math.max(0, Math.min(100, ((v - domainLo) / domainSpan) * 100));
  const zoneLoPct = pct(lo);
  const zoneHiPct = pct(hi);
  const valuePct = value != null ? pct(value) : null;
  const pointerColor = POINTER[(status as keyof typeof POINTER) ?? "unknown"] ?? POINTER.unknown;

  return (
    <div className="gauge">
      <div className="gauge-head">
        <span className="gauge-value">
          {value != null ? value : "—"}
          {value != null && <span className="gauge-unit">{unit}</span>}
        </span>
        <TrafficLight status={status} label={statusLabel} size="lg" />
      </div>
      <div className="gauge-track" title={title ?? `${lo}–${hi} ${unit}`}>
        <div className="gauge-zone" style={{ insetInlineStart: 0, width: `${zoneLoPct}%`, background: ZONE.red }} />
        <div
          className="gauge-zone"
          style={{ insetInlineStart: `${zoneLoPct}%`, width: `${zoneHiPct - zoneLoPct}%`, background: ZONE.green }}
        />
        <div
          className="gauge-zone"
          style={{ insetInlineStart: `${zoneHiPct}%`, width: `${100 - zoneHiPct}%`, background: ZONE.red }}
        />
        {marker != null && <div className="gauge-marker" style={{ insetInlineStart: `${pct(marker)}%` }} title={markerLabel} />}
        {valuePct != null && (
          <div className="gauge-pointer" style={{ insetInlineStart: `${valuePct}%`, background: pointerColor }} />
        )}
      </div>
      <div className="gauge-ticks">
        <span>{lo}</span>
        <span className="note">محدوده نرمال</span>
        <span>{hi}</span>
      </div>
    </div>
  );
}
