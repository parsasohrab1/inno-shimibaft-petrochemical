import TrafficLight from "./TrafficLight";

type OverviewNode = {
  id: string;
  label: string;
  status: string;
  status_label: string;
  tag_ids: string[];
  derived_from?: string;
};

type Overview = {
  nodes: OverviewNode[];
  flow: string[];
  note: string;
};

const FILL: Record<string, string> = {
  red: "#fdecea",
  yellow: "#fff3cd",
  green: "#e7f6ec",
  unknown: "#f1f3f5",
};
const STROKE: Record<string, string> = {
  red: "#c0392b",
  yellow: "#b7950b",
  green: "#1e8449",
  unknown: "#999",
};

const NODE_ACRONYM: Record<string, string> = {
  MTBE: "MTBE",
  RAFFINATE2: "Raffinate-2",
  MEK: "MEK",
};

/** GET /api/process-intelligence/process-overview — a simple MTBE ->
 * Raffinate-2 -> MEK flow diagram with a worst-of-tags traffic light per
 * node. Plain inline SVG (no charting library), acronyms and Persian
 * status labels kept as SEPARATE <text> elements (not concatenated in one
 * string) to avoid RTL/LTR bidi scrambling inside SVG text, per this
 * account's lessons learned. */
export default function ProcessOverview({ overview }: { overview: Overview | null }) {
  if (!overview) return null;
  const order = overview.flow;
  const nodeById: Record<string, OverviewNode> = {};
  overview.nodes.forEach((n) => (nodeById[n.id] = n));

  const boxW = 150;
  const boxH = 70;
  const gap = 70;
  const startX = 20;
  const y = 20;

  return (
    <div className="card">
      <h3>نمای کلی فرآیند (MTBE ← رافینیت ۲ ← MEK)</h3>
      <svg
        viewBox={`0 0 ${startX * 2 + order.length * boxW + (order.length - 1) * gap} ${boxH + 40}`}
        width="100%"
        style={{ maxWidth: 640, height: "auto" }}
        role="img"
        aria-label="نمای کلی فرآیند"
      >
        {order.map((id, i) => {
          const node = nodeById[id];
          if (!node) return null;
          const x = startX + i * (boxW + gap);
          return (
            <g key={id}>
              <rect
                x={x}
                y={y}
                width={boxW}
                height={boxH}
                rx={10}
                fill={FILL[node.status] ?? FILL.unknown}
                stroke={STROKE[node.status] ?? STROKE.unknown}
                strokeWidth={2}
              />
              <text x={x + boxW / 2} y={y + 26} textAnchor="middle" fontSize={14} fontWeight="bold">
                {NODE_ACRONYM[id] ?? id}
              </text>
              <text x={x + boxW / 2} y={y + 46} textAnchor="middle" fontSize={11} fill="#333">
                {node.label}
              </text>
              {i < order.length - 1 && (
                <polygon
                  points={`${x + boxW},${y + boxH / 2 - 6} ${x + boxW + gap},${y + boxH / 2} ${x + boxW},${y + boxH / 2 + 6}`}
                  fill="#666"
                />
              )}
            </g>
          );
        })}
      </svg>
      <table>
        <thead>
          <tr>
            <th>گره</th>
            <th>وضعیت</th>
            <th>تگ‌های مرتبط</th>
          </tr>
        </thead>
        <tbody>
          {order.map((id) => {
            const node = nodeById[id];
            if (!node) return null;
            return (
              <tr key={id}>
                <td>{node.label}</td>
                <td>
                  <TrafficLight status={node.status} label={node.status_label} />
                </td>
                <td>{node.tag_ids.length ? node.tag_ids.join("، ") : node.derived_from ? `وضعیت از ${node.derived_from} گرفته شده` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="note">{overview.note}</p>
    </div>
  );
}
