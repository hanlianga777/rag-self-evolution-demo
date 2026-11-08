/** 浮层定位：放在目标元素下方，空间不够时翻到上方，并始终限制在视口内。 */
export type FloatPosition = { top: number; left: number; placement: "below" | "above" };

export function computeFloatPosition(anchor: DOMRect, size: { width: number; height: number }, viewport = { width: window.innerWidth, height: window.innerHeight }, gap = 8): FloatPosition {
  const margin = 12;
  const below = anchor.bottom + gap;
  const fitsBelow = below + size.height <= viewport.height - margin;
  const above = anchor.top - gap - size.height;
  const placement = fitsBelow || above < margin ? "below" : "above";
  const top = placement === "below" ? Math.min(below, Math.max(margin, viewport.height - margin - size.height)) : above;
  const left = Math.min(Math.max(margin, anchor.left), Math.max(margin, viewport.width - margin - size.width));
  return { top: Math.round(top), left: Math.round(left), placement };
}
