import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useOperation } from "../operation";

export function Drawer({ open, onOpenChange, title, children, className = "", guardEdits = false, editDirty, contentKey }: { open: boolean; onOpenChange: (value: boolean) => void; title: string; children: ReactNode; className?: string; guardEdits?: boolean; editDirty?: boolean; contentKey?: string }) {
  const previousFocus = useRef<HTMLElement | null>(null);
  const [dirty, setDirty] = useState(false), [discard, setDiscard] = useState(false);
  useEffect(() => { setDirty(false); setDiscard(false); }, [open, contentKey]);
  useEffect(() => { if (editDirty === false) setDiscard(false); }, [editDirty]);
  const changeOpen = (value: boolean) => { if (!value && guardEdits && (editDirty ?? dirty)) setDiscard(true); else { setDirty(false); setDiscard(false); onOpenChange(value); } };
  const contentRef = useRef<HTMLDivElement | null>(null);
  const { registerDialogHost, unregisterDialogHost } = useOperation();
  const setContentRef = useCallback((node: HTMLDivElement | null) => {
    if (contentRef.current) unregisterDialogHost(contentRef.current);
    contentRef.current = node;
    if (node && open) registerDialogHost(node);
  }, [open, registerDialogHost, unregisterDialogHost]);
  return <><ConfirmDialog open={discard} onOpenChange={setDiscard} title="放弃未保存修改？" onConfirm={() => { setDirty(false); setDiscard(false); onOpenChange(false); }}><p>当前输入尚未保存。已保存的修订草案和审计记录会保留。</p></ConfirmDialog><Dialog.Root open={open} onOpenChange={changeOpen}><Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content onOpenAutoFocus={() => { previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; }} onCloseAutoFocus={event => { event.preventDefault(); if (previousFocus.current?.isConnected) previousFocus.current.focus(); }} ref={setContentRef} onChangeCapture={() => { if (guardEdits && editDirty === undefined) setDirty(true); }} className={`drawer ${className}`}><div className="drawer-head"><Dialog.Title>{title}</Dialog.Title><Dialog.Description className="sr-only">详情内容；正文可独立滚动，按 Esc 关闭。</Dialog.Description><Dialog.Close className="icon-button" aria-label="关闭"><X size={18} /></Dialog.Close></div><div className="detail-content">{children}</div><div className="detail-footer"><Dialog.Close className="secondary">关闭详情</Dialog.Close></div></Dialog.Content></Dialog.Portal></Dialog.Root></>;
}

export function ConfirmDialog({ open, onOpenChange, title, children, busy, onConfirm }: { open: boolean; onOpenChange: (value: boolean) => void; title: string; children: ReactNode; busy?: boolean; onConfirm: () => void }) {
  const previousFocus = useRef<HTMLElement | null>(null);
  return <Dialog.Root open={open} onOpenChange={value => { if (!busy) onOpenChange(value); }}><Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content className="confirm-dialog" onOpenAutoFocus={() => { previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; }} onCloseAutoFocus={event => { event.preventDefault(); if (previousFocus.current?.isConnected) previousFocus.current.focus(); }}><Dialog.Title>{title}</Dialog.Title><Dialog.Description asChild><div>{children}</div></Dialog.Description><div className="header-actions"><Dialog.Close className="secondary" disabled={busy}>取消</Dialog.Close><button className="primary" disabled={busy} onClick={onConfirm}>{busy ? "处理中…" : "确认"}</button></div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
