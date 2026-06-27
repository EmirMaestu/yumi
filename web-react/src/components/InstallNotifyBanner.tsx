import { useEffect, useState } from 'react'
import Card from './ui/Card'
import { pushSupported, isSubscribed, enablePush, notifPermission, sendTestPush } from '../lib/push'

type BIPEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> }

function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const iosStandalone = (window.navigator as any).standalone === true
  return window.matchMedia('(display-mode: standalone)').matches || iosStandalone
}

function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent)
}

export default function InstallNotifyBanner() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem('yumi.banner.dismissed') === '1')
  const [installEvt, setInstallEvt] = useState<BIPEvent | null>(null)
  const [standalone, setStandalone] = useState(isStandalone())
  const [notifState, setNotifState] = useState<'idle' | 'on' | 'denied' | 'working'>('idle')
  const [showIosHint, setShowIosHint] = useState(false)

  useEffect(() => {
    const onBIP = (e: Event) => {
      e.preventDefault()
      setInstallEvt(e as BIPEvent)
    }
    const onInstalled = () => setStandalone(true)
    window.addEventListener('beforeinstallprompt', onBIP)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onBIP)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  useEffect(() => {
    if (pushSupported()) {
      if (notifPermission() === 'granted') {
        isSubscribed().then((s) => setNotifState(s ? 'on' : 'idle'))
      } else if (notifPermission() === 'denied') {
        setNotifState('denied')
      }
    }
  }, [])

  const dismiss = () => {
    localStorage.setItem('yumi.banner.dismissed', '1')
    setDismissed(true)
  }

  const onInstall = async () => {
    if (installEvt) {
      await installEvt.prompt()
      try { await installEvt.userChoice } catch { /* noop */ }
      setInstallEvt(null)
    } else if (isIOS()) {
      setShowIosHint((v) => !v)
    }
  }

  const onEnableNotif = async () => {
    setNotifState('working')
    const r = await enablePush()
    setNotifState(r.ok ? 'on' : r.reason === 'denied' ? 'denied' : 'idle')
    if (r.ok) sendTestPush() // aviso de prueba inmediato para confirmar que llega
  }

  // ¿Hay algo para ofrecer?
  const canInstall = !standalone && (installEvt !== null || isIOS())
  const canNotify = pushSupported() && notifState !== 'on'
  // En iPhone, push solo anda con la app instalada → no ofrecer notif si no está instalada.
  const offerNotify = canNotify && !(isIOS() && !standalone)

  if (dismissed || (!canInstall && !offerNotify)) return null

  return (
    <Card style={{ display: 'grid', gap: 10, background: 'var(--color-mist)', border: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>📲 Aprovechá Yumi al máximo</div>
          <div style={{ fontSize: 12.5, color: 'var(--color-sage)', marginTop: 2 }}>
            {canInstall && offerNotify
              ? 'Instalá la app y activá los avisos de vencimientos.'
              : canInstall
                ? 'Instalá la app en tu pantalla de inicio.'
                : 'Activá los avisos de vencimientos y recordatorios.'}
          </div>
        </div>
        <button onClick={dismiss} aria-label="Cerrar" style={xBtn}>✕</button>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {canInstall && (
          <button onClick={onInstall} style={primaryBtn}>
            {isIOS() && !installEvt ? 'Cómo instalar' : 'Instalar app'}
          </button>
        )}
        {offerNotify && (
          <button onClick={onEnableNotif} disabled={notifState === 'working'} style={ghostBtn}>
            {notifState === 'working' ? 'Activando…' : notifState === 'denied' ? 'Notificaciones bloqueadas' : 'Activar notificaciones'}
          </button>
        )}
      </div>

      {notifState === 'denied' && (
        <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>
          Están bloqueadas en el navegador. Activalas desde los permisos del sitio.
        </div>
      )}

      {showIosHint && (
        <div style={{ fontSize: 12, color: 'var(--color-sage)', lineHeight: 1.5 }}>
          En iPhone <b>solo se puede desde Safari</b> 🧭 (no Brave ni Chrome). En Safari: tocá
          <b> Compartir</b> (⬆️) → <b>Agregar a inicio</b>. Después abrila desde el ícono para
          recibir notificaciones.
        </div>
      )}
    </Card>
  )
}

const xBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  fontSize: 13, color: 'var(--color-sage)', padding: 2, lineHeight: 1,
}
const primaryBtn: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '9px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit',
}
const ghostBtn: React.CSSProperties = {
  background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '9px 14px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
