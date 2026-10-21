/** Three-lamp traffic light (red/yellow/green, only the active lamp lit)
 * plus a text label — never colour alone. Matches the convention used by
 * the Khorasan Petrochemical SEM dashboard on this account (see
 * backend/app/services/process_intelligence.py's status/status_label). */
export default function TrafficLight({
  status,
  label,
  size = "md",
}: {
  status: "red" | "yellow" | "green" | "unknown" | string;
  label?: string;
  /** "md" (default, inline use) or "lg" (prominent, card-level use). */
  size?: "md" | "lg";
}) {
  const r = size === "lg" ? 9 : 6;
  const step = r * 2 + 4;
  const svgH = r * 2 + 4;
  const svgW = step * 3 - 4;
  const lamp = (color: "red" | "yellow" | "green") => {
    const on = status === color;
    const fill = on ? { red: "#c0392b", yellow: "#e0b000", green: "#1e8449" }[color] : "#dfe3e8";
    return <circle key={color} cx={0} cy={0} r={r} fill={fill} />;
  };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <svg width={svgW} height={svgH} viewBox={`${-r - 2} ${-r - 2} ${svgW} ${svgH}`} aria-hidden="true">
        <g transform="translate(0,0)">{lamp("red")}</g>
        <g transform={`translate(${step},0)`}>{lamp("yellow")}</g>
        <g transform={`translate(${step * 2},0)`}>{lamp("green")}</g>
      </svg>
      {label && <span className={`status-${status}${size === "lg" ? " status-label-lg" : ""}`}>{label}</span>}
    </span>
  );
}
