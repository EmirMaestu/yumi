import { useState } from 'react'
import Card from '../components/ui/Card'
import Select from '../components/ui/Select'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { useMe } from '../hooks/useMe'
import { useAdminOverview, useAdminUsers, useAdminUserMutations, useAdminReferrals, useAdminHouseholds } from '../hooks/useAdmin'
import { type AdminUser } from '../lib/types'

function fmtUsd(n: number): string {
  const v = n || 0
  return 'US$' + (v >= 1 ? v.toFixed(2) : v.toFixed(4))
}
const fmtInt = (n: number) => (n || 0).toLocaleString('es-AR')
const planLabel = (p: string) => p.charAt(0).toUpperCase() + p.slice(1)

export default function Admin() {
  const { data: me } = useMe()
  const ov = useAdminOverview()
  const us = useAdminUsers()
  const { update } = useAdminUserMutations()
  const [deactivate, setDeactivate] = useState<AdminUser | null>(null)

  if (me && me.is_admin === false) {
    return (
      <div style={{ padding: '14px 18px 24px' }}>
        <div className="cap">Admin</div>
        <Card style={{ marginTop: 12 }}>No tenés acceso a esta sección.</Card>
      </div>
    )
  }

  // Solo confiamos en la data si tiene la forma esperada (un mock/respuesta rara no debe romper la UI).
  const o = ov.data && typeof ov.data === 'object' && (ov.data as { caps?: unknown }).caps ? ov.data : undefined
  const capUsed = o && o.caps.daily_global_usd > 0 ? Math.min(1, o.cost_today / o.caps.daily_global_usd) : 0

  return (
    <div style={{ padding: '14px 18px 28px', display: 'grid', gap: 16 }}>
      <div className="cap">Admin · panel</div>

      {ov.isError && <Card style={errCard}>No se pudo cargar el panel (¿sos admin? ¿reiniciaste la web?).</Card>}
      {o && !o.usage_ready && (
        <Card style={warnCard}>
          Todavía no hay datos de uso. Se empiezan a registrar cuando el bot procesa mensajes
          (asegurate de haber reiniciado el bot con los controles de costo).
        </Card>
      )}

      {/* ── KPIs ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
        <Kpi label="Costo hoy" value={o ? fmtUsd(o.cost_today) : '…'} />
        <Kpi label="Costo del mes" value={o ? fmtUsd(o.cost_month) : '…'} />
        <Kpi label="Mensajes hoy" value={o ? fmtInt(o.msgs_today) : '…'} sub={o ? `${fmtInt(o.calls_today)} llamadas` : undefined} />
        <Kpi label="Usuarios" value={o ? `${o.users_active}` : '…'} sub={o ? `${o.users_total} en total` : undefined} />
      </div>

      {/* ── Tope diario global ── */}
      {o && (
        <Card style={{ display: 'grid', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span className="cap" style={{ fontSize: 10.5 }}>Tope diario global</span>
            <span style={{ fontSize: 13, color: 'var(--color-sage)' }}>
              {fmtUsd(o.cost_today)} / {fmtUsd(o.caps.daily_global_usd)}
            </span>
          </div>
          <div style={{ height: 8, borderRadius: 999, background: 'var(--color-mist)', overflow: 'hidden' }}>
            <div style={{ width: `${capUsed * 100}%`, height: '100%', background: capUsed >= 0.85 ? '#d6453a' : 'var(--color-voltage)', transition: 'width .3s' }} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-sage)' }}>
            Plan free: {o.caps.free_daily_msgs} mensajes/día. Al llegar al tope, el bot pausa hasta el día siguiente.
          </div>
        </Card>
      )}

      {/* ── Uso por modelo ── */}
      {o && o.by_model.length > 0 && (
        <div style={{ display: 'grid', gap: 8 }}>
          <div className="cap" style={{ fontSize: 10.5 }}>Uso por modelo · este mes</div>
          <Card style={{ display: 'grid', gap: 10 }}>
            {o.by_model.map((m) => (
              <div key={m.model} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{shortModel(m.model)}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>
                    {fmtInt(m.calls)} llamadas · {fmtInt(m.input_tokens)} in / {fmtInt(m.output_tokens)} out
                  </div>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{fmtUsd(m.cost_usd)}</div>
              </div>
            ))}
          </Card>
        </div>
      )}

      {/* ── Usuarios ── */}
      <div style={{ display: 'grid', gap: 8 }}>
        <div className="cap" style={{ fontSize: 10.5 }}>Usuarios</div>
        {us.isLoading && <Card>Cargando usuarios…</Card>}
        {us.data?.users?.map((u) => (
          <Card key={u.id} style={{ display: 'grid', gap: 10, opacity: u.active ? 1 : 0.55 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 500 }}>
                  {u.name}
                  <button
                    onClick={() => {
                      const nuevo = window.prompt('Nuevo nombre para este usuario:', u.name)
                      if (nuevo && nuevo.trim() && nuevo.trim() !== u.name) update.mutate({ id: u.id, name: nuevo.trim() })
                    }}
                    title="Renombrar"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, marginLeft: 6, opacity: 0.6 }}
                  >✏️</button>
                  {u.is_admin && <span style={badge}>admin</span>}
                  {!u.active && <span style={{ ...badge, background: 'var(--color-mist)', color: 'var(--color-sage)' }}>inactivo</span>}
                </div>
                <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>@{u.username}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{fmtUsd(u.cost_month)}</div>
                <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>{fmtInt(u.msgs_today)} msj hoy</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <Select
                ariaLabel={`Plan de ${u.name}`}
                value={u.plan}
                onValueChange={(plan) => update.mutate({ id: u.id, plan })}
                options={(us.data?.plans ?? ['free', 'pareja', 'pro']).map((p) => ({ value: p, label: planLabel(p) }))}
                style={{ flex: '0 0 auto' }}
              />
              <button
                onClick={() => (u.active ? setDeactivate(u) : update.mutate({ id: u.id, active: true }))}
                style={u.active ? ghostBtn : voltageBtn}
              >
                {u.active ? 'Desactivar' : 'Reactivar'}
              </button>
            </div>
          </Card>
        ))}
        {o && o.cost_month_system > 0 && (
          <Card style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, background: 'var(--color-linen)' }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 500 }}>
                Sistema
                <span style={{ ...badge, background: 'var(--color-mist)', color: 'var(--color-sage)' }}>sin usuario</span>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>búsquedas de precio, resumen diario…</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{fmtUsd(o.cost_month_system)}</div>
              <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>este mes</div>
            </div>
          </Card>
        )}
      </div>

      {/* ── Familias ── */}
      <Familias />

      {/* ── Referidos ── */}
      <Referidos />

      <ConfirmDialog
        open={!!deactivate}
        onOpenChange={(o2) => !o2 && setDeactivate(null)}
        title={`¿Desactivar a ${deactivate?.name}?`}
        description="No va a poder usar el bot ni la app hasta que lo reactives. No se borra nada."
        confirmLabel="Desactivar"
        onConfirm={() => {
          if (deactivate) update.mutate({ id: deactivate.id, active: false })
          setDeactivate(null)
        }}
      />
    </div>
  )
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card style={{ display: 'grid', gap: 3 }}>
      <div className="cap" style={{ fontSize: 10 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em' }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>{sub}</div>}
    </Card>
  )
}

function Familias() {
  const hh = useAdminHouseholds()
  const data = hh.data
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div className="cap" style={{ fontSize: 10.5 }}>Familias (hogares)</div>
      {hh.isLoading && <Card style={{ fontSize: 13, color: 'var(--color-sage)' }}>Cargando…</Card>}
      {data?.households?.map((h) => {
        const full = h.size >= h.cap
        return (
          <Card key={h.household_id} style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>
                {h.members[0]?.name ?? `Hogar ${h.household_id}`}{h.size > 1 ? ` +${h.size - 1}` : ''}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-sage)', whiteSpace: 'nowrap' }}>
                <span style={{ textTransform: 'capitalize', color: 'var(--color-obsidian-ink)', fontWeight: 500 }}>{h.plan}</span>
                {' · '}<span style={{ color: full ? '#d6453a' : 'var(--color-sage)' }}>{h.size}/{h.cap}</span>
                {' · '}{h.daily_msgs >= 100000 ? '∞' : h.daily_msgs} msj/día
              </div>
            </div>
            <div style={{ display: 'grid', gap: 4 }}>
              {h.members.map((m) => (
                <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5 }}>
                  <span style={{ color: m.active ? 'var(--color-obsidian-ink)' : 'var(--color-sage)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {m.name} <span style={{ color: 'var(--color-sage)' }}>@{m.username}</span>{!m.active && ' · inactivo'}
                  </span>
                  <span style={{ color: 'var(--color-sage)', whiteSpace: 'nowrap', textTransform: 'capitalize' }}>{m.plan}</span>
                </div>
              ))}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

function Referidos() {
  const { data: me } = useMe()
  const refs = useAdminReferrals()
  const [copied, setCopied] = useState<string | null>(null)
  const data = refs.data
  const mine = data?.users?.find((u) => u.id === me?.id)

  function copy(kind: string, link: string | null | undefined) {
    if (!link) return
    navigator.clipboard?.writeText(link)
      .then(() => { setCopied(kind); setTimeout(() => setCopied(null), 1500) })
      .catch(() => {})
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div className="cap" style={{ fontSize: 10.5 }}>Referidos</div>

      {data && !data.ready && (
        <Card style={warnCard}>Esperando la migración del bot — reiniciá el bot para generar los códigos.</Card>
      )}

      {mine && (
        <Card style={{ display: 'grid', gap: 12 }}>
          <div className="cap" style={{ fontSize: 10 }}>Tu link de invitación</div>
          {(mine.invite_link_wa || mine.invite_link) ? (
            <>
              {mine.invite_link_wa && (
                <div style={{ display: 'grid', gap: 5 }}>
                  <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}><i className="ti ti-brand-whatsapp" aria-hidden /> WhatsApp</div>
                  <div style={{ fontSize: 12.5, wordBreak: 'break-all' }}>{mine.invite_link_wa}</div>
                  <button onClick={() => copy('wa', mine.invite_link_wa)} style={{ ...voltageBtn, justifySelf: 'start' }}>{copied === 'wa' ? '¡Copiado!' : 'Copiar link WhatsApp'}</button>
                </div>
              )}
              {mine.invite_link && (
                <div style={{ display: 'grid', gap: 5 }}>
                  <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}><i className="ti ti-brand-telegram" aria-hidden /> Telegram</div>
                  <div style={{ fontSize: 12.5, wordBreak: 'break-all' }}>{mine.invite_link}</div>
                  <button onClick={() => copy('tg', mine.invite_link)} style={{ ...ghostBtn, justifySelf: 'start' }}>{copied === 'tg' ? '¡Copiado!' : 'Copiar link Telegram'}</button>
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>
              Tu código: <b>{mine.referral_code ?? '—'}</b>. Configurá <code>BOT_USERNAME</code> / <code>WHATSAPP_NUMBER</code> en el servidor para los links.
            </div>
          )}
        </Card>
      )}

      <Card style={{ display: 'grid', gap: 10 }}>
        <div className="cap" style={{ fontSize: 10 }}>Quién invitó a quién</div>
        {refs.isLoading && <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>Cargando…</div>}
        {data?.users?.map((u) => (
          <div key={u.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500 }}>{u.name}</div>
              {u.referred_by_name && <div style={{ fontSize: 11.5, color: 'var(--color-sage)' }}>lo invitó {u.referred_by_name}</div>}
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--color-sage)', whiteSpace: 'nowrap' }}>
              {u.invited_count > 0 ? `invitó ${u.invited_count}` : '—'}
            </div>
          </div>
        ))}
      </Card>
    </div>
  )
}

function shortModel(m: string): string {
  if (m.includes('haiku')) return 'Haiku 4.5'
  if (m.includes('sonnet')) return 'Sonnet 4.6'
  if (m.includes('opus')) return 'Opus'
  return m
}

const badge: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
  background: 'var(--color-pollen)', color: 'var(--voltage-on-dark)', borderRadius: 6,
  padding: '2px 6px', marginLeft: 8, verticalAlign: 'middle',
}
const ghostBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '9px 14px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
const voltageBtn: React.CSSProperties = {
  ...ghostBtn, border: 'none', background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', fontWeight: 500,
}
const warnCard: React.CSSProperties = { background: '#fff8e6', border: '1px solid #f0d98a', fontSize: 13, color: '#7a5b00' }
const errCard: React.CSSProperties = { background: '#fdecea', border: '1px solid #f0b3ac', fontSize: 13, color: '#8a2a20' }
