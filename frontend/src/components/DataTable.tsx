import { Children, cloneElement, isValidElement, useLayoutEffect, useRef, type ReactElement, type ReactNode, type TableHTMLAttributes } from "react";
import { TruncatedText } from "./Primitives";

// Keep form controls and multi-action cells usable; prose shares one hover surface.
function controls(node: ReactNode): number {
  return Children.toArray(node).reduce<number>((count, child) => {
    if (!isValidElement<{ children?: ReactNode }>(child)) return count;
    return count + (["button", "input", "select", "textarea", "a"].includes(String(child.type)) ? 1 : controls(child.props.children));
  }, 0);
}
function prose(node: ReactNode): ReactNode {
  return Children.map(node, child => {
    if (!isValidElement<{ children?: ReactNode }>(child)) return child;
    if (child.type === TruncatedText) return prose(child.props.children);
    return child.props.children ? cloneElement(child, {}, prose(child.props.children)) : child;
  });
}
function cells(node: ReactNode): ReactNode {
  return Children.map(node, child => {
    if (!isValidElement<{ children?: ReactNode; colSpan?: number }>(child)) return child;
    if (child.type === "td" && !child.props.colSpan && controls(child.props.children) < 2) {
      return cloneElement(child, {}, <TruncatedText lines={2}>{prose(child.props.children)}</TruncatedText>);
    }
    return child.props.children ? cloneElement(child as ReactElement, {}, cells(child.props.children)) : child;
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
