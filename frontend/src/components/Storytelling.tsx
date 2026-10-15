import { useId, useState, type ComponentProps, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

/** Scoped to the evaluation / release / verification workspaces. */
export function StoryDisclosure({ label, children, className = "", ...props }: Omit<ComponentProps<"details">, "children"> & { label: ReactNode; children: ReactNode }) {
  const [expanded, setExpanded] = useState(!!props.open);
  const id = useId();
  return <details {...props} className={`story-disclosure ${className}`} onToggle={event => { setExpanded(event.currentTarget.open); props.onToggle?.(event); }}><summary aria-expanded={expanded} aria-controls={id}><span>{label}</span><ChevronDown size={14} aria-hidden="true" /></summary><div id={id} className="story-disclosure-content">{children}</div></details>;
}

export function FilterButtons({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: string; count?: number }[]; onChange: (value: string) => void }) {
  return <div className="story-filter" role="group" aria-label={label}><span className="story-filter-label">{label}</span><div className="review-filters">{options.map(option => <button type="button" key={option.value} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}{option.count != null && <span>{option.count}</span>}</button>)}</div></div>;
}

export function StoryEmpty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <section className="story-empty"><h3>{title}</h3><p>{children}</p>{action && <div className="header-actions">{action}</div>}</section>;
}
