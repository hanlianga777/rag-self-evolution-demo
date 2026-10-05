import { useEffect, useRef, type ReactNode } from "react";

/** Shared viewport shell: headers stay visible; only the content scrolls. */
export function PageShell({ className = "page", header, tabs, resetKey, children }: {
  className?: string; header: ReactNode; tabs?: ReactNode; resetKey?: string; children: ReactNode;
}) {
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => { if (content.current) content.current.scrollTop = 0; }, [resetKey]);
  return <div className={`${className} page-shell`}><header className="page-shell-header">{header}{tabs}</header><div ref={content} className="page-content">{children}</div></div>;
}
