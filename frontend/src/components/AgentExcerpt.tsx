import { HoverCard } from '../ui/HoverCard';

// A literal excerpt, never an inferred summary. The complete saved text stays on hover/focus.
export function AgentExcerpt({text, lines = 2, limit = 36, className = ''}: {text: string; lines?: number; limit?: number; className?: string}) {
  return <HoverCard className="agent-excerpt" content={text}><div className={`ui-clamp ${className}`.trim()} tabIndex={0} style={{WebkitLineClamp: lines}}>{text.length > limit ? `${text.slice(0, limit)}…` : text}</div></HoverCard>;
}
