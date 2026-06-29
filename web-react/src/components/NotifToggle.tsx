import { useEffect, useState } from 'react'
import { pushSupported, notifPermission, isSubscribed, enablePush, disablePush, sendTestPush } from '../lib/push'
import Card from './ui/Card'

// Activar / desactivar notificaciones push en este dispositivo (hub "Yo").
export default function NotifToggle() {
  const [state, setState] = useState<'loading' | 'on' | 'off' | 'denied' | 'unsupported' | 'working'>('loading')

  useEffect(() => {
    if (!pushSupported()) { setState('unsupported'); return }
    if (notifPermission() === 'denied') { setState('denied'); return }
    isSubscribed().then((s) => setState(s ? 'on' : 'off'))
  }, [])

  const toggle = async () => {
    if (state === 'on') {
      setState('working')
      await disablePush()
      setState('off')
    } else {
      setState('working')
      const r = await enablePush()
      if (r.ok) { setState('on'); sendTestPush() } // aviso de prueba para confirmar que llega
      else setState(r.reason === 'denied' ? 'denied' : 'off')
    }
  }

  if (state === 'unsupported') return null

  const stateLabel = state === 'on' ? 'Activadas' : state === 'denied' ? 'Bloqueadas en el navegador' : 'Desactivadas'

  return (
    <Card style={{ display: 'grid', gap: 8 }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>🔔 Notificaciones</div>
      <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>
        Avisos de vencimientos y recordatorios en este dispositivo. En iPhone necesitás tener la app instalada (desde Safari).
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 2 }}>
        <span style={{ fontSize: 14 }}>{stateLabel}</span>
        <button onClick={toggle} disabled={state === 'working' || state === 'denied' || state === 'loading'} style={state === 'on' ? offBtn : onBtn}>
          {state === 'working' ? '…' : state === 'on' ? 'Desactivar' : state === 'denied' ? 'Bloqueadas' : 'Activar'}
        </button>
      </div>
      {state === 'denied' && (
        <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>
          Activalas desde los permisos del sitio en tu navegador y volvé a entrar.
        </div>
      )}
    </Card>
  )
}

const onBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 9999, padding: '6px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit', flexShrink: 0 }
const offBtn: React.CSSProperties = { ...onBtn, background: 'var(--color-mist)', color: 'var(--color-sage)' }
