import { useEffect, useState, type CSSProperties } from 'react'
import Sheet from './Sheet'
import { useHouseholdMembers, useShareState, useShareMutation } from '../../hooks/useShare'
import type { ShareEntity } from '../../lib/types'

type Mode = 'private' | 'all' | 'people'

const ENTITY_NOUN: Record<ShareEntity, string> = { tareas: 'tarea', notas: 'nota', lists: 'lista', eventos: 'evento', recordatorios: 'recordatorio' }

export default function ShareSheet({
  open,
  onClose,
  entity,
  id,
}: {
  open: boolean
  onClose: () => void
  entity: ShareEntity
  id: number | null
}) {
  const { data: members } = useHouseholdMembers()
  const { data: state, isLoading } = useShareState(entity, id, open)
  const save = useShareMutation(entity)
  const others = (members ?? []).filter((m) => !m.is_me)

  const [mode, setMode] = useState<Mode>('private')
  const [selected, setSelected] = useState<number[]>([])

  // Prefilar con el estado actual cuando abre o llega el fetch.
  useEffect(() => {
    if (!open || !state) return
    if (state.shared) { setMode('all'); setSelected([]) }
    else if (state.members.length) { setMode('people'); setSelected(state.members) }
    else { setMode('private'); setSelected([]) }
  }, [open, state])

  const toggle = (uid: number) =>
    setSelected((s) => (s.includes(uid) ? s.filter((x) => x !== uid) : [...s, uid]))

  const onSave = () => {
    if (id == null) return
    const body =
      mode === 'all' ? { id, shared: 1 as const, members: [] }
      : mode === 'people' ? { id, shared: 0 as const, members: selected }
      : { id, shared: 0 as const, members: [] }
    save.mutate(body, { onSuccess: onClose })
  }

  const noun = ENTITY_NOUN[entity]
  const canSave = mode !== 'people' || selected.length > 0

  return (
    <Sheet open={open} onClose={onClose} title="Compartir">
      <div style={{ display: 'grid', gap: 10 }}>
        <p style={{ fontSize: 13, color: 'var(--color-sage)', margin: '0 0 4px' }}>
          Elegí quién puede ver y colaborar en esta {noun}. Solo vos podés borrarla o renombrarla.
        </p>

        <OptionRow
          icon="ti-lock"
          label="Privada"
          desc={`Solo vos ves esta ${noun}.`}
          active={mode === 'private'}
          onClick={() => setMode('private')}
        />
        <OptionRow
          icon="ti-users"
          label="Todo el plan"
          desc="Cualquier integrante puede verla y colaborar."
          active={mode === 'all'}
          onClick={() => setMode('all')}
          disabled={others.length === 0}
        />
        <OptionRow
          icon="ti-user-check"
          label="Personas puntuales"
          desc="Elegí con quién compartirla."
          active={mode === 'people'}
          onClick={() => setMode('people')}
          disabled={others.length === 0}
        />

        {mode === 'people' && (
          <div style={{ display: 'grid', gap: 6, marginTop: 2 }}>
            {others.map((m) => {
              const on = selected.includes(m.id)
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => toggle(m.id)}
                  style={{ ...personRow, borderColor: on ? 'var(--color-voltage)' : 'var(--color-mist)' }}
                >
                  <span style={{ ...avatar, background: m.color || 'var(--color-pollen)' }}>
                    {m.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span style={{ flex: 1, textAlign: 'left', fontSize: 14 }}>{m.name}</span>
                  <i
                    className={`ti ${on ? 'ti-circle-check' : 'ti-circle'}`}
                    style={{ fontSize: 20, color: on ? 'var(--color-voltage)' : 'var(--color-mist)' }}
                    aria-hidden
                  />
                </button>
              )
            })}
          </div>
        )}

        {others.length === 0 && (
          <p style={{ fontSize: 13, color: 'var(--color-sage)', margin: 0 }}>
            Todavía no hay otros integrantes en tu plan para compartir.
          </p>
        )}

        <button
          type="button"
          onClick={onSave}
          disabled={!canSave || save.isPending || isLoading}
          style={{ ...ctaBtn, opacity: !canSave || save.isPending ? 0.55 : 1 }}
        >
          {save.isPending ? 'Guardando…' : 'Guardar'}
        </button>
      </div>
    </Sheet>
  )
}

function OptionRow({
  icon, label, desc, active, onClick, disabled,
}: {
  icon: string; label: string; desc: string; active: boolean; onClick: () => void; disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        ...optRow,
        borderColor: active ? 'var(--color-voltage)' : 'var(--color-mist)',
        background: active ? 'var(--color-mist)' : 'var(--color-linen)',
        opacity: disabled ? 0.45 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      <i className={`ti ${icon}`} style={{ fontSize: 20, color: 'var(--color-sage)' }} aria-hidden />
      <span style={{ flex: 1, textAlign: 'left' }}>
        <span style={{ display: 'block', fontSize: 14, fontWeight: 500 }}>{label}</span>
        <span style={{ display: 'block', fontSize: 12, color: 'var(--color-sage)' }}>{desc}</span>
      </span>
      <i
        className={`ti ${active ? 'ti-circle-check' : 'ti-circle'}`}
        style={{ fontSize: 20, color: active ? 'var(--color-voltage)' : 'var(--color-mist)' }}
        aria-hidden
      />
    </button>
  )
}

const optRow: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, width: '100%',
  border: '1px solid var(--color-mist)', borderRadius: 12, padding: '12px 14px', boxSizing: 'border-box',
}
const personRow: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, width: '100%',
  border: '1px solid var(--color-mist)', borderRadius: 12, padding: '10px 12px',
  background: 'var(--color-linen)', cursor: 'pointer', boxSizing: 'border-box',
}
const avatar: CSSProperties = {
  width: 28, height: 28, borderRadius: 9999, display: 'inline-flex', alignItems: 'center',
  justifyContent: 'center', fontSize: 13, fontWeight: 600, color: 'var(--voltage-on-dark, #1a1a1a)', flexShrink: 0,
}
const ctaBtn: CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10,
  padding: 14, fontWeight: 500, cursor: 'pointer', marginTop: 6,
}
