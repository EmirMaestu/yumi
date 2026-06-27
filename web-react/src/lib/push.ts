import { apiGet, apiPost } from './api'

function urlB64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const arr = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i)
  return arr
}

export function pushSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    typeof window !== 'undefined' &&
    'PushManager' in window &&
    'Notification' in window
  )
}

export function notifPermission(): NotificationPermission | 'unsupported' {
  if (!pushSupported()) return 'unsupported'
  return Notification.permission
}

export async function isSubscribed(): Promise<boolean> {
  if (!pushSupported()) return false
  try {
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.getSubscription()
    return !!sub
  } catch {
    return false
  }
}

/** Pide permiso, se suscribe y manda la suscripción al backend. */
export async function enablePush(): Promise<{ ok: boolean; reason?: string }> {
  if (!pushSupported()) return { ok: false, reason: 'unsupported' }
  let perm: NotificationPermission
  try {
    perm = await Notification.requestPermission()
  } catch {
    return { ok: false, reason: 'denied' }
  }
  if (perm !== 'granted') return { ok: false, reason: 'denied' }
  let key = ''
  try {
    key = (await apiGet<{ key: string }>('/api/push/vapid-public-key')).key
  } catch {
    return { ok: false, reason: 'no-key' }
  }
  if (!key) return { ok: false, reason: 'no-key' }
  try {
    const reg = await navigator.serviceWorker.ready
    let sub = await reg.pushManager.getSubscription()
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(key) as unknown as BufferSource,
      })
    }
    await apiPost('/api/push/subscribe', { subscription: sub.toJSON() })
    return { ok: true }
  } catch (e) {
    return { ok: false, reason: 'subscribe-failed' }
  }
}

export async function disablePush(): Promise<void> {
  if (!pushSupported()) return
  try {
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.getSubscription()
    if (sub) {
      await apiPost('/api/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {})
      await sub.unsubscribe().catch(() => {})
    }
  } catch {
    /* noop */
  }
}

export async function sendTestPush(): Promise<number> {
  try {
    const r = await apiPost<{ ok: boolean; sent: number }>('/api/push/test')
    return r.sent ?? 0
  } catch {
    return 0
  }
}
