import { useState, type CSSProperties } from 'react'
import { useHousehold } from '../hooks/useHousehold'
import Card from './ui/Card'
import SettingHeader from './ui/SettingHeader'

// Tarjeta "Tu pareja / familia": integrantes del hogar + invitar (Telegram/WhatsApp),
// respetando el plan. Reemplaza el "solo por /invitar en Telegram".
export default function HouseholdCard() {
  const { data: h, isLoading } = useHousehold()
  const [copied, setCopied] = useState(false)
  const [shared, setShared] = useState(false)

  if (isLoading || !h) return null

  // Link que la PAREJA tiene que abrir: al tocarlo, SE LE abre el chat con Yumi
  // y el mensaje `...(fam_<code>)`; al enviarlo, se suma al hogar. El que invita
  // NO debe abrirlo (se lo mandaría a Yumi él mismo) — tiene que COMPARTIRLO.
  const inviteLink = h.whatsapp || h.telegram || ''
  const shareTitle = 'Sumate a mi familia en Yumi'
  const shareMsg = 'Te invito a compartir todo en Yumi 🌱 (listas, gastos y agenda). Tocá este link y mandá el mensaje que aparece:'
  const shareText = `${shareMsg} ${inviteLink}`

  // Botón principal: elegir a la pareja en WhatsApp y mandarle el link.
  // wa.me SIN número → abre WhatsApp para elegir un contacto y enviarle ese texto.
  const waPickHref = inviteLink
    ? `https://wa.me/?text=${encodeURIComponent(shareText)}`
    : ''
  // Telegram: abre el selector de contactos de Telegram para reenviar el link.
  const tgShareHref = h.telegram
    ? `https://t.me/share/url?url=${encodeURIComponent(h.telegram)}&text=${encodeURIComponent(shareMsg)}`
    : ''

  const copy = async () => {
    if (!inviteLink) return
    try {
      await navigator.clipboard.writeText(inviteLink)
      setCopied(true); setTimeout(() => setCopied(false), 1600)
    } catch { /* ignore */ }
  }

  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function'
  const share = async () => {
    if (!inviteLink) return
    try {
      await navigator.share({ title: shareTitle, text: shareMsg, url: inviteLink })
      setShared(true); setTimeout(() => setShared(false), 1600)
    } catch { /* usuario canceló o no soportado → fallback: copiar */ await copy() }
  }

  return (
    <Card style={{ display: 'grid', gap: 12 }}>
      <SettingHeader icon="ti-users" title="Tu pareja / familia" />

      {/* Integrantes */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {h.members.map((m) => (
          <span key={m.id} style={chip}>
            <span style={{ ...dot, background: m.color || 'var(--color-pollen)' }}>{m.name.slice(0, 1).toUpperCase()}</span>
            {m.name}{m.is_me ? ' (vos)' : ''}
          </span>
        ))}
      </div>

      {h.cap <= 1 ? (
        <p style={hint}>
          Tu plan es <b>individual</b>. Para compartir con tu pareja o familia (listas, gastos, agenda),
          actualizá a un plan <b>Pareja</b> o superior.
        </p>
      ) : h.slots <= 0 ? (
        <p style={hint}>
          Tu hogar está completo: <b>{h.current}/{h.cap}</b> integrantes para tu plan ({h.plan}).
          Actualizá el plan para sumar a más.
        </p>
      ) : (
        <>
          <p style={hint}>
            Te queda{h.slots !== 1 ? 'n' : ''} <b>{h.slots}</b> lugar{h.slots !== 1 ? 'es' : ''} (plan {h.plan}).
            <b> Compartí este link con tu pareja</b>: cuando ELLA lo abra y mande el mensaje, se suma a tu hogar y comparten todo.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {waPickHref && (
              <a href={waPickHref} target="_blank" rel="noreferrer" style={waBtn}>
                <i className="ti ti-brand-whatsapp" aria-hidden /> Enviar a mi pareja por WhatsApp
              </a>
            )}
            {canShare && inviteLink && (
              <button onClick={share} style={shareBtn}>
                <i className={`ti ${shared ? 'ti-check' : 'ti-share'}`} aria-hidden /> {shared ? 'Compartido' : 'Compartir link'}
              </button>
            )}
            {tgShareHref && (
              <a href={tgShareHref} target="_blank" rel="noreferrer" style={tgBtn}>
                <i className="ti ti-brand-telegram" aria-hidden /> Compartir por Telegram
              </a>
            )}
            <button onClick={copy} style={copyBtn}>
              <i className={`ti ${copied ? 'ti-check' : 'ti-copy'}`} aria-hidden /> {copied ? 'Copiado' : 'Copiar link'}
            </button>
          </div>
        </>
      )}
    </Card>
  )
}

const hint: CSSProperties = { margin: 0, fontSize: 12.5, color: 'var(--color-sage)', lineHeight: 1.5 }
const chip: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13,
  background: 'var(--color-mist)', borderRadius: 9999, padding: '4px 10px 4px 4px',
}
const dot: CSSProperties = {
  width: 22, height: 22, borderRadius: '50%', display: 'inline-flex', alignItems: 'center',
  justifyContent: 'center', fontSize: 11, fontWeight: 600, color: 'var(--voltage-on-dark, #1a1a1a)',
}
const baseBtn: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 10, padding: '9px 14px',
  fontSize: 13, fontWeight: 500, cursor: 'pointer', textDecoration: 'none', border: 'none', font: 'inherit',
}
const waBtn: CSSProperties = { ...baseBtn, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)' }
const shareBtn: CSSProperties = { ...baseBtn, background: 'var(--color-mist)', color: 'var(--color-obsidian-ink)' }
const tgBtn: CSSProperties = { ...baseBtn, background: 'var(--color-mist)', color: 'var(--color-obsidian-ink)' }
const copyBtn: CSSProperties = { ...baseBtn, background: 'transparent', border: '1px solid var(--color-mist)', color: 'var(--color-sage)' }
