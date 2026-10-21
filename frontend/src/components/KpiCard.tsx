import { ReactNode } from "react";
import Sparkline from "./Sparkline";

type Status = "good" | "warn" | "bad" | "neutral";

/** A headline KPI tile: a large value + unit, an optional target line, an
 * optional trend sparkline, and a status pill (reusing this codebase's
 * existing badge-ok/badge-warn/badge-bad colours — never colour alone,
 * the pill always carries a text word). Secondary/methodology detail is
 * passed as `children` and rendered small, so the eye lands on the number
 * first (see dataviz skill's figure/stat-tile contract). */
export default function KpiCard({
  label,
  value,
  unit,
  status = "neutral",
  statusText,
  target,
  trend,
  children,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  status?: Status;
  statusText?: string;
  target?: string;
  trend?: (number | null | undefined)[];
  children?: ReactNode;
}) {
  const badgeClass = { good: "badge-ok", warn: "badge-warn", bad: "badge-bad", neutral: "" }[status];
  return (
    <div className="kpi-card">
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        {statusText && <span className={`badge ${badgeClass}`}>{statusText}</span>}
      </div>
      <div className="kpi-body">
        <div className="kpi-value">
          {value}
          {unit && <span className="kpi-unit">{unit}</span>}
        </div>
        {trend && trend.filter((v) => v != null).length >= 2 && (
          <div className="kpi-trend">
            <Sparkline values={trend} />
          </div>
        )}
      </div>
      {target && <div className="note kpi-target">{target}</div>}
      {children}
    </div>
  );
}
