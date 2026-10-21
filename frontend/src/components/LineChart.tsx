/** A small multi-point line/bar trend chart, used wherever a page needs
 * more than a sparkline (energy CUSUM, production forecast, energy
 * intensity history) but a full charting library would be overkill for a
 * scaffold-stage product. Plain inline SVG — 2px rounded line, a thin-bar
 * mode for signed series (CUSUM can go negative), direct end-label on the
 * line variant, and a per-point <title> tooltip (the lightweight
 * equivalent of a hover layer here). One series only — a single accent
 * colour needs no legend box (see dataviz skill's marks-and-anatomy.md). */
export default function LineChart({
  points,
  mode = "line",
  height = 110,
  color = "#5b8def",
  negativeColor = "#c0392b",
  unit = "",
  formatTitle,
  zeroLine = false,
}: {
  points: { x: string | number; y: number }[];
  mode?: "line" | "bar";
  height?: number;
  color?: string;
  negativeColor?: string;
  unit?: string;
  formatTitle?: (p: { x: string | number; y: number }) => string;
  zeroLine?: boolean;
}) {
  if (points.length === 0) {
    return <p className="note">داده‌ای برای رسم موجود نیست.</p>;
  }
  const width = 560;
  const padL = 36;
  const padR = 12;
  const padT = 14;
  const padB = 20;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const ys = points.map((p) => p.y);
  let lo = Math.min(0, ...ys);
  let hi = Math.max(0, ...ys);
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const span = hi - lo;
  const xFor = (i: number) => padL + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const yFor = (v: number) => padT + (1 - (v - lo) / span) * innerH;
  const zeroY = yFor(0);

  const niceTicks = [hi, lo + span / 2, lo];

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: 640 }} role="img" aria-label="نمودار روند">
      {niceTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={width - padR} y1={yFor(t)} y2={yFor(t)} stroke="#e1e0d9" strokeWidth={1} />
          <text x={padL - 6} y={yFor(t) + 3} textAnchor="end" fontSize={9} fill="#898781">
            {Math.round(t * 100) / 100}
          </text>
        </g>
      ))}
      {zeroLine && lo < 0 && hi > 0 && (
        <line x1={padL} x2={width - padR} y1={zeroY} y2={zeroY} stroke="#c3c2b7" strokeWidth={1} />
      )}

      {mode === "bar" &&
        points.map((p, i) => {
          const barW = Math.min(18, innerW / points.length - 3);
          const x = xFor(i) - barW / 2;
          const y0 = yFor(Math.max(0, p.y));
          const y1 = yFor(Math.min(0, p.y));
          const h = Math.max(1, y1 - y0);
          const title = formatTitle ? formatTitle(p) : `${p.x}: ${p.y}${unit}`;
          return (
            <rect key={i} x={x} y={y0} width={barW} height={h} rx={3} fill={p.y < 0 ? negativeColor : color}>
              <title>{title}</title>
            </rect>
          );
        })}

      {mode === "line" && (
        <>
          <path
            d={points.map((p, i) => `${i === 0 ? "M" : "L"}${xFor(i).toFixed(1)},${yFor(p.y).toFixed(1)}`).join(" ")}
            fill="none"
            stroke={color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          {points.map((p, i) => (
            <circle key={i} cx={xFor(i)} cy={yFor(p.y)} r={3.5} fill={color} stroke="#fff" strokeWidth={1.5}>
              <title>{formatTitle ? formatTitle(p) : `${p.x}: ${p.y}${unit}`}</title>
            </circle>
          ))}
          <text x={xFor(points.length - 1)} y={yFor(points[points.length - 1].y) - 8} textAnchor="end" fontSize={10} fill="#52514e">
            {points[points.length - 1].y}
            {unit}
          </text>
        </>
      )}

      <text x={padL} y={height - 4} fontSize={9} fill="#898781">
        {points[0].x}
      </text>
      <text x={width - padR} y={height - 4} textAnchor="end" fontSize={9} fill="#898781">
        {points[points.length - 1].x}
      </text>
    </svg>
  );
}
