import { HoverCard } from '../ui/HoverCard';

// CSS limits visible lines; the complete literal text stays available on hover/focus.
export function AgentExcerpt({text, lines = 1, className = ''}: {text: string; lines?: number; className?: string}) {
  return <HoverCard className="agent-excerpt" content={text}><div className={`ui-clamp ${className}`.trim()} tabIndex={0} style={{WebkitLineClamp: lines}}>{text}</div></HoverCard>;
}
