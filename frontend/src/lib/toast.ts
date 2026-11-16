// Short messages in the top corner (shown by <Toaster />), callable from anywhere
export type ToastKind = "success" | "error" | "info";

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((listener) => listener());
}

export function toast(message: string, kind: ToastKind = "success", seconds = 4): void {
  const item = { id: nextId++, message, kind };
  toasts = [...toasts, item].slice(-4);
  emit();
  setTimeout(() => dismissToast(item.id), seconds * 1000);
}

export function dismissToast(id: number): void {
  toasts = toasts.filter((item) => item.id !== id);
  emit();
}

export function subscribeToasts(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getToasts(): Toast[] {
  return toasts;
}
