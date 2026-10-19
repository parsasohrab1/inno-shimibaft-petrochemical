/** A simple horizontal range bar: shows ``value`` positioned between ``lo``
 * and ``hi``, with an optional ``marker`` (e.g. the mean) drawn on top.
 * No charting library — plain CSS (see styles.css's .rangebar). */
export default function RangeBar({
  value,
  lo,
  hi,
  marker,
}: {
  value: number | null | undefined;
  lo: number;
  hi: number;
  marker?: number | null;
}) {
  const span = hi - lo || 1;
  const pct = (v: number) => Math.max(0, Math.min(100, ((v - lo) / span) * 100));
  return (
    <div className="rangebar" title={`${lo} - ${hi}`}>
      {value != null && <div className="fill" style={{ insetInlineStart: 0, width: `${pct(value)}%` }} />}
      {marker != null && <div className="marker" style={{ insetInlineStart: `${pct(marker)}%` }} />}
    </div>
  );
}
