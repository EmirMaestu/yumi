import { useState, useEffect, useDeferredValue } from 'react'
import { Link } from 'react-router-dom'
import { useTareas } from '../hooks/useTareas'
import { useNotas } from '../hooks/useNotas'
import { useEventos } from '../hooks/useEventos'
import { useRecordatorios } from '../hooks/useRecordatorios'
import { apiGet } from '../lib/api'
import { useQuery } from '@tanstack/react-query'
import { type Transaction } from '../lib/types'
import EmptyState from '../components/ui/EmptyState'
import Card from '../components/ui/Card'
import BackButton from '../components/ui/BackButton'

// ── helpers ──────────────────────────────────────────────────────────────────

function normalize(s: string) {
  return s.toLowerCase()
}

function matches(q: string, ...fields: (string | null | undefined)[]): boolean {
  const nq = normalize(q)
  return fields.some((f) => f && normalize(f).includes(nq))
}

// ── type chip ─────────────────────────────────────────────────────────────────

const CHIP_STYLES: Record<string, { bg: string; color: string }> = {
  Tarea: { bg: '#fff3cd', color: '#7a5c00' },
  Nota: { bg: '#dbeafe', color: '#1e40af' },
  Evento: { bg: '#d1fae5', color: '#065f46' },
  Recordatorio: { bg: 'var(--color-mist)', color: 'var(--color-sage)' },
  Movimiento: { bg: '#ede9fe', color: '#5b21b6' },
}

function TypeChip({ label }: { label: string }) {
  const s = CHIP_STYLES[label] ?? { bg: 'var(--color-mist)', color: 'var(--color-sage)' }
  return (
    <span style={{
      fontSize: 10,
      fontWeight: 600,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.06em',
      padding: '2px 7px',
      borderRadius: 9999,
      background: s.bg,
      color: s.color,
    }}>
      {label}
    </span>
  )
}

// ── result row ────────────────────────────────────────────────────────────────

function ResultRow({ label, text, sub, to }: { label: string; text: string; sub?: string; to: string }) {
  return (
    <Link to={to} style={{ textDecoration: 'none', display: 'block' }}>
      <Card style={{ cursor: 'pointer' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <TypeChip label={label} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-obsidian-ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {text}
            </div>
            {sub && (
              <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>{sub}</div>
            )}
          </div>
        </div>
      </Card>
    </Link>
  )
}

// ── section heading ───────────────────────────────────────────────────────────

function SectionHead({ label, count }: { label: string; count: number }) {
  return (
    <div style={{
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.08em',
      color: 'var(--color-sage)',
      textTransform: 'uppercase' as const,
      marginTop: 8,
      marginBottom: 6,
      display: 'flex',
      alignItems: 'center',
      gap: 6,
    }}>
      {label}
      <span style={{ fontWeight: 400, fontSize: 11, opacity: 0.7 }}>({count})</span>
    </div>
  )
}

// ── main ──────────────────────────────────────────────────────────────────────

export default function Buscar() {
  const [rawQ, setRawQ] = useState('')
  const q = useDeferredValue(rawQ.trim())

  // fetch all data sources
  const { data: tareas } = useTareas('all')
  const { data: notas } = useNotas()
  const { data: eventos } = useEventos(false)
  const { data: eventosPast } = useEventos(true)
  const { data: recordatorios } = useRecordatorios(true)

  // Movimientos: búsqueda server-side sobre TODO el historial (BF11, D12).
  // Debounce 300ms → GET /api/transactions?q=…&limit=50 (sin year/month).
  const [debouncedQ, setDebouncedQ] = useState('')
  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(rawQ.trim()), 300)
    return () => clearTimeout(id)
  }, [rawQ])
  const { data: txResults } = useQuery({
    queryKey: ['transactions', 'buscar', debouncedQ],
    enabled: debouncedQ.length > 0,
    queryFn: async () => {
      const res = await apiGet<{ items: Transaction[] }>(`/api/transactions?q=${encodeURIComponent(debouncedQ)}&limit=50`)
      return res.items ?? []
    },
  })

  // filter
  const filteredTareas = q
    ? (tareas ?? []).filter((t) => matches(q, t.text))
    : []
  const filteredNotas = q
    ? (notas ?? []).filter((n) => matches(q, n.text, ...n.tags))
    : []
  const allEventos = [...(eventos ?? []), ...(eventosPast ?? [])]
  const filteredEventos = q
    ? allEventos.filter((e) => matches(q, e.title, e.location, e.notes))
    : []
  const filteredRecs = q
    ? (recordatorios ?? []).filter((r) => matches(q, r.text))
    : []
  // Ya viene filtrado del server (busca en toda la historia, no solo 500 tx).
  const filteredTx = debouncedQ ? (txResults ?? []) : []

  const total = filteredTareas.length + filteredNotas.length + filteredEventos.length + filteredRecs.length + filteredTx.length

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><BackButton /><div className="cap">Buscar</div></div>

      {/* Search box */}
      <input
        type="search"
        placeholder="Buscar en tareas, notas, eventos, movimientos…"
        value={rawQ}
        onChange={(e) => setRawQ(e.target.value)}
        autoFocus
        style={inputStyle}
      />

      {/* Empty query hint */}
      {!q && (
        <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--color-sage)', fontSize: 14 }}>
          <i className="ti ti-search" style={{ fontSize: 28, display: 'block', marginBottom: 8, opacity: 0.5 }} aria-hidden />
          Escribí para buscar en toda tu información
        </div>
      )}

      {/* No results */}
      {q && total === 0 && (
        <EmptyState>Sin resultados para "{q}"</EmptyState>
      )}

      {/* Results grouped by type */}
      {filteredTareas.length > 0 && (
        <div>
          <SectionHead label="Tareas" count={filteredTareas.length} />
          <div style={{ display: 'grid', gap: 8 }}>
            {filteredTareas.map((t) => (
              <ResultRow
                key={`t-${t.id}`}
                label="Tarea"
                text={t.text}
                sub={`${t.priority} · ${t.status}`}
                to="/tareas"
              />
            ))}
          </div>
        </div>
      )}

      {filteredNotas.length > 0 && (
        <div>
          <SectionHead label="Notas" count={filteredNotas.length} />
          <div style={{ display: 'grid', gap: 8 }}>
            {filteredNotas.map((n) => (
              <ResultRow
                key={`n-${n.id}`}
                label="Nota"
                text={n.text.slice(0, 80) + (n.text.length > 80 ? '…' : '')}
                sub={n.tags.length > 0 ? n.tags.join(', ') : undefined}
                to="/notas"
              />
            ))}
          </div>
        </div>
      )}

      {filteredEventos.length > 0 && (
        <div>
          <SectionHead label="Eventos" count={filteredEventos.length} />
          <div style={{ display: 'grid', gap: 8 }}>
            {filteredEventos.map((e) => (
              <ResultRow
                key={`e-${e.id}`}
                label="Evento"
                text={e.title}
                sub={e.starts_at.slice(0, 16).replace('T', ' ') + (e.location ? ` · ${e.location}` : '')}
                to="/agenda"
              />
            ))}
          </div>
        </div>
      )}

      {filteredRecs.length > 0 && (
        <div>
          <SectionHead label="Recordatorios" count={filteredRecs.length} />
          <div style={{ display: 'grid', gap: 8 }}>
            {filteredRecs.map((r) => (
              <ResultRow
                key={`r-${r.id}`}
                label="Recordatorio"
                text={r.text}
                sub={r.remind_at.slice(0, 16).replace('T', ' ')}
                to="/agenda"
              />
            ))}
          </div>
        </div>
      )}

      {filteredTx.length > 0 && (
        <div>
          <SectionHead label="Movimientos" count={filteredTx.length} />
          <div style={{ display: 'grid', gap: 8 }}>
            {filteredTx.map((t) => (
              <ResultRow
                key={`tx-${t.id}`}
                label="Movimiento"
                text={t.description}
                sub={`${t.type} · ${t.currency} ${Math.abs(t.amount).toLocaleString('es-AR')}${t.cat_name ? ` · ${t.cat_name}` : ''}`}
                to="/movimientos"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '12px 14px',
  fontSize: 15,
  background: 'var(--color-linen)',
  width: '100%',
  boxSizing: 'border-box',
}
