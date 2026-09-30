import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useCallback, useRef, type ReactNode } from "react";
import { useOperation } from "../operation";

export function Drawer({ open, onOpenChange, title, children, className = "" }: { open: boolean; onOpenChange: (value: boolean) => void; title: string; children: ReactNode; className?: string }) {
  const previousFocus = useRef<HTMLElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const { registerDialogHost, unregisterDialogHost } = useOperation();
  const setContentRef = useCallback((node: HTMLDivElement | null) => {
    if (contentRef.current) unregisterDialogHost(contentRef.current);
    contentRef.current = node;
    if (node && open) registerDialogHost(node);
  }, [open, registerDialogHost, unregisterDialogHost]);
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content onOpenAutoFocus={() => { previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; }} onCloseAutoFocus={event => { event.preventDefault(); if (previousFocus.current?.isConnected) previousFocus.current.focus(); }} ref={setContentRef} className={`drawer ${className}`}><div className="drawer-head"><Dialog.Title>{title}</Dialog.Title><Dialog.Description className="sr-only">详情内容；正文可独立滚动，按 Esc 关闭。</Dialog.Description><Dialog.Close className="icon-button" aria-label="关闭"><X size={18} /></Dialog.Close></div><div className="detail-content">{children}</div><div className="detail-footer"><Dialog.Close className="secondary">关闭详情</Dialog.Close></div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
