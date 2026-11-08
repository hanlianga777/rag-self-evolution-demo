import { Children, cloneElement, isValidElement, useLayoutEffect, useRef, type ReactElement, type ReactNode, type TableHTMLAttributes } from "react";
import { ClampText } from "../ui/ClampText";
import { TruncatedText } from "./Primitives";

// Keep form controls and multi-action cells usable; prose shares one hover surface.
function controls(node: ReactNode): number {
  return Children.toArray(node).reduce<number>((count, child) => {
    if (!isValidElement<{ children?: ReactNode }>(child)) return count;
    return count + (["button", "input", "select", "textarea", "a"].includes(String(child.type)) ? 1 : controls(child.props.children));
  }, 0);
}
function hasClamp(node: ReactNode): boolean {
  return Children.toArray(node).some(child => isValidElement<{ children?: ReactNode }>(child) && (child.type === TruncatedText || child.type === ClampText || hasClamp(child.props.children)));
}
function cells(node: ReactNode, clickable = false): ReactNode {
  return Children.map(node, child => {
    if (!isValidElement<{ children?: ReactNode; colSpan?: number; onClick?: unknown; hoverOnly?: boolean }>(child)) return child;
    const rowAction = clickable || child.type === "tr" && typeof child.props.onClick === "function";
    if (child.type === TruncatedText && rowAction) return cloneElement(child, { hoverOnly: true });
    if (child.type === "td" && !child.props.colSpan && controls(child.props.children) < 2 && !hasClamp(child.props.children)) {
      return cloneElement(child, {}, <TruncatedText lines={1} hoverOnly={rowAction}>{child.props.children}</TruncatedText>);
    }
    return child.props.children ? cloneElement(child as ReactElement, {}, cells(child.props.children, rowAction)) : child;
  });
}

export function DataTable({ children, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  const table = useRef<HTMLTableElement>(null);
  useLayoutEffect(() => {
    const node = table.current, box = node?.closest<HTMLElement>(".table-scroll");
    if (!node || !box) return;
    const fit = () => {
      if (!box.getClientRects().length) return;
      // Scroll position must not change the region's fixed height.
      const content = box.closest<HTMLElement>(".page-content,.detail-content");
      box.style.setProperty("--table-available-height", `${Math.max(180, innerHeight - box.getBoundingClientRect().top - (content?.scrollTop || 0) - 28)}px`);
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [children]);
  return <table ref={table} {...props}>{cells(children)}</table>;
}
