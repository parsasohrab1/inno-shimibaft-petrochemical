import { ReactNode } from "react";

type Decision = { decision: string; actor_username: string | null; note: string | null; ts: string };

const STATUS_LABEL: Record<string, string> = { pending: "در انتظار تأیید", accepted: "پذیرفته‌شده", rejected: "رد‌شده" };
const STATUS_BADGE: Record<string, string> = { pending: "badge-warn", accepted: "badge-ok", rejected: "badge-bad" };

/** An actionable recommendation card: title + prominent status badge,
 * the suggested action and expected-effect numbers as small chips (not
 * buried in a sentence), and accept/reject as real buttons — upgrading
 * the previous plain-text `scenario-card` rendering of
 * suggested_action/expected_effect per this round's request. The
 * append-only decision audit trail (NFR-06) is kept, just folded behind
 * a details toggle so it doesn't compete with the action itself. */
export default function RecommendationCard({
  title,
  detail,
  status,
  suggestedAction,
  expectedEffect,
  decisions,
  onAccept,
  onReject,
  children,
}: {
  title: string;
  detail: string;
  status: string;
  suggestedAction?: { parameter: string; delta_pct: number } | null;
  expectedEffect?: Record<string, number> | null;
  decisions: Decision[];
  onAccept: () => void;
  onReject: () => void;
  children?: ReactNode;
}) {
  return (
    <div className={`rec-card rec-${status}`}>
      <div className="rec-head">
        <b>{title}</b>
        <span className={`badge ${STATUS_BADGE[status] ?? "badge-warn"}`}>{STATUS_LABEL[status] ?? status}</span>
      </div>
      <p className="note">{detail}</p>
      {(suggestedAction || expectedEffect) && (
        <div className="rec-chips">
          {suggestedAction && (
            <span className="chip chip-action">
              اقدام: {suggestedAction.parameter} {suggestedAction.delta_pct > 0 ? "+" : ""}
              {suggestedAction.delta_pct}٪
            </span>
          )}
          {expectedEffect &&
            Object.entries(expectedEffect).map(([k, v]) => (
              <span className="chip" key={k}>
                {k} {v > 0 ? "▲" : v < 0 ? "▼" : "•"} {v}
              </span>
            ))}
        </div>
      )}
      {children}
      {status === "pending" && (
        <div className="rec-actions">
          <button className="btn-accept" onClick={onAccept}>
            ✓ تأیید
          </button>
          <button className="btn-reject" onClick={onReject}>
            ✗ رد
          </button>
        </div>
      )}
      {decisions.length > 0 && (
        <details className="detail-toggle">
          <summary>تاریخچه ممیزی ({decisions.length} رویداد)</summary>
          <div className="detail-body note">{decisions.map((d) => `${STATUS_LABEL[d.decision] ?? d.decision}@${d.ts}`).join(" → ")}</div>
        </details>
      )}
    </div>
  );
}
