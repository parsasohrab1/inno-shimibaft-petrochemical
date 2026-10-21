/** A horizontal ranked bar list — real feature-importance / score values,
 * each bar capped (never fills the slot), rounded data-end, with the
 * value labelled at the bar's tip and the category name beside it in
 * text ink (never inside the coloured bar), per the dataviz skill's
 * mark spec. Replaces a plain two-column table for ranked magnitudes. */
export default function BarList({
  items,
  color = "#5b8def",
  formatValue,
}: {
  items: { label: string; value: number }[];
  color?: string;
  formatValue?: (v: number) => string;
}) {
  if (items.length === 0) return <p className="note">داده‌ای موجود نیست.</p>;
  const max = Math.max(1e-9, ...items.map((i) => Math.abs(i.value)));
  const fmt = formatValue ?? ((v: number) => `${(v * 100).toFixed(1)}٪`);
  return (
    <div className="bar-list">
      {items.map((it, i) => (
        <div className="bar-list-row" key={i}>
          <span className="bar-list-label">{it.label}</span>
          <div className="bar-list-track">
            <div
              className="bar-list-fill"
              style={{ width: `${Math.max(2, (Math.abs(it.value) / max) * 100)}%`, background: color }}
            />
          </div>
          <span className="bar-list-value">{fmt(it.value)}</span>
        </div>
      ))}
    </div>
  );
}
