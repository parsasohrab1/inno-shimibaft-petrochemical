/** Three-lamp traffic light (red/yellow/green, only the active lamp lit)
 * plus a text label — never colour alone. Matches the convention used by
 * the Khorasan Petrochemical SEM dashboard on this account (see
 * backend/app/services/process_intelligence.py's status/status_label). */
export default function TrafficLight({
  status,
  label,
}: {
  status: "red" | "yellow" | "green" | "unknown" | string;
  label?: string;
}) {
  const lamp = (color: "red" | "yellow" | "green") => {
    const on = status === color;
    const fill = on ? { red: "#c0392b", yellow: "#e0b000", green: "#1e8449" }[color] : "#dfe3e8";
    return <circle key={color} cx={0} cy={0} r={6} fill={fill} />;
  };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <svg width={48} height={16} viewBox="-8 -8 48 16" aria-hidden="true">
        <g transform="translate(0,0)">{lamp("red")}</g>
        <g transform="translate(16,0)">{lamp("yellow")}</g>
        <g transform="translate(32,0)">{lamp("green")}</g>
      </svg>
      {label && <span className={`status-${status}`}>{label}</span>}
    </span>
  );
}
