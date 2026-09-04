import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Drawer({ open, onOpenChange, title, children }: { open: boolean; onOpenChange: (value: boolean) => void; title: string; children: ReactNode }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content className="drawer"><div className="drawer-head"><Dialog.Title>{title}</Dialog.Title><Dialog.Close className="icon-button" aria-label="Close"><X size={18} /></Dialog.Close></div>{children}</Dialog.Content></Dialog.Portal></Dialog.Root>;
}
