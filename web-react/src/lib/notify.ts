import { toast } from 'sonner'

export const notifyOk = (msg: string) => toast.success(msg)

// Éxito con acción "Deshacer" durante 10s (borrados recuperables, UX7).
export function notifyUndo(msg: string, onUndo: () => void) {
  toast(msg, { action: { label: 'Deshacer', onClick: onUndo }, duration: 10000 })
}

// Extrae el mensaje del ApiError. El body del server viene en español; FastAPI
// suele mandarlo como {"detail":"..."} → desempaquetamos el detail.
export function notifyErr(e: unknown) {
  toast.error(errMessage(e))
}

export function errMessage(e: unknown): string {
  const raw = (e as { message?: unknown })?.message
  if (typeof raw === 'string' && raw.trim()) {
    const t = raw.trim()
    if (t.startsWith('{')) {
      try {
        const d = (JSON.parse(t) as { detail?: unknown }).detail
        if (typeof d === 'string' && d.trim()) return d
      } catch { /* body no-JSON: usamos el texto tal cual */ }
    }
    return t
  }
  return 'Algo salió mal. Probá de nuevo.'
}
