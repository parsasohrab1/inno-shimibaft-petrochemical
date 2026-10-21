/** A tiny inline-SVG trend line for a KPI card (the "figure" contract's
 * optional `trend`: de-emphasis-hue line, current point picked out in the
 * accent colour). No charting library — plain SVG, consistent with
 * RangeBar/TrafficLight elsewhere in this codebase. Renders nothing
 * (rather than a broken/empty chart) when there are fewer than 2 points. */
export default function Sparkline({
  values,
  width = 96,
  height = 28,
  color = "#5b8def",
}: {
  values: (number | null | undefined)[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const pts = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (pts.length < 2) return null;
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const span = hi - lo || 1;
  const pad = 2;
  const stepX = (width - pad * 2) / (pts.length - 1);
  const coords = pts.map((v, i) => {
    const x = pad + i * stepX;
    const y = pad + (1 - (v - lo) / span) * (height - pad * 2);
    return [x, y] as const;
  });
  const path = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = coords[coords.length - 1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="روند اخیر">
      <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" opacity={0.55} />
      <circle cx={last[0]} cy={last[1]} r={3} fill={color} stroke="#fff" strokeWidth={1.5} />
    </svg>
  );
}
