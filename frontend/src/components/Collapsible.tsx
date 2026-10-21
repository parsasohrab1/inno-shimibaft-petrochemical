import { ReactNode } from "react";

/** De-emphasises methodology/honesty detail (formulas, caveats, targets,
 * "measured on synthetic data" notes) behind a native <details> toggle,
 * instead of deleting it — this product's credibility rests on that
 * disclosure (see docs/SRS.md section 9), it just should not be the
 * first thing the eye lands on. Defaults to closed so the glanceable KPI
 * is what's visible; opening it is one click away. */
export default function Collapsible({
  title = "جزئیات روش‌شناسی",
  defaultOpen = false,
  children,
}: {
  title?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="detail-toggle" open={defaultOpen}>
      <summary>{title}</summary>
      <div className="detail-body">{children}</div>
    </details>
  );
}
