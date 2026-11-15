import type { ComponentProps, ReactNode } from "react";

/** Saved evidence stays visible; section headings are not disclosure controls. */
export function StoryDisclosure({ label, children, className = "", ...props }: ComponentProps<"section"> & { label: ReactNode; children: ReactNode }) {
  return <section {...props} className={`story-disclosure ${className}`}><h3 className="disclosure-heading">{label}</h3><div className="story-disclosure-content">{children}</div></section>;
}

export function FilterButtons({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: string; count?: number }[]; onChange: (value: string) => void }) {
  return <div className="story-filter" role="group" aria-label={label}><span className="story-filter-label">{label}</span><div className="review-filters">{options.map(option => <button type="button" key={option.value} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}{option.count != null && <span>{option.count}</span>}</button>)}</div></div>;
}

export function StoryEmpty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <section className="story-empty"><h3>{title}</h3><p>{children}</p>{action && <div className="header-actions">{action}</div>}</section>;
}
