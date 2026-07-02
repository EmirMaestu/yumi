import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVencimientos } from '../hooks/useVencimientos'
import { useAccountsWithBalances, useAccountMutations } from '../hooks/useAccounts'
import { useRecurring } from '../hooks/useRecurring'
import { Money } from '../lib/privacy'
import { type Account } from '../lib/types'
import { cicloEnCurso, aPagarCard } from '../lib/cards'
import Card from '../components/ui/Card'
import BackButton from '../components/ui/BackButton'
import AlertPill from '../components/ui/AlertPill'
import { TarjetasSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import AccountForm from '../components/AccountForm'

function fmtDay(d?: string): string { return d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : '—' }

export default function Tarjetas() {
  const navigate = useNavigate()
  const venc = useVencimientos()
  const accounts = useAccountsWithBalances()
  const recurring = useRecurring()
  const { remove } = useAccountMutations()

  const [editCard, setEditCard] = useState<Account | null>(null)
  const [deleteCard, setDeleteCard] = useState<Account | null>(null)

  const cards = accounts.data?.filter((a) => a.type === 'credito') ?? []

  if (accounts.isLoading) return <TarjetasSkeleton />
  if (cards.length === 0) return <EmptyState>No tenés tarjetas de crédito cargadas.</EmptyState>

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><BackButton /><div className="cap">Tarjetas y cuotas</div></div>
      {cards.map((card) => {
        const v = venc.data?.find((x) => x.account_id === card.id)
        const aPagar = aPagarCard(v)                                // resumen a pagar (lo que vence)
        const enCurso = cicloEnCurso(card.id, v, recurring.data)    // próximo resumen (proyección)
        const dias = v?.next_closing ? Math.ceil((new Date(v.next_closing).getTime() - Date.now()) / 86_400_000) : null
        const hasVenc = !!v
        return (
          <Card
            key={card.id}
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/tarjetas/${card.id}`)}
          >
            {/* Header: name left, actions right */}
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 500, flex: 1 }}>{card.name}</span>
              <CardActions
                onEdit={() => setEditCard(card)}
                onDelete={() => setDeleteCard(card)}
              />
            </div>
            {/* Resumen a pagar (lo exigible) primero; próximo resumen como proyección */}
            <div style={{ marginTop: 10 }}>
              <div className="cap">Resumen a pagar</div>
              {aPagar > 0
                ? <div className="num-serif" style={{ fontSize: 30, marginTop: 4 }}><Money value={aPagar} /></div>
                : <div style={{ fontSize: 15, marginTop: 4 }}>Sin resumen pendiente 🎉</div>}
              <div style={{ marginTop: 4, fontSize: 11, color: 'var(--color-sage)' }}>
                Próximo resumen{hasVenc && v!.next_closing ? ` (cierra ${fmtDay(v!.next_closing)})` : ''}: <Money value={enCurso} />
                {!hasVenc && ' · cargá cierre y vencimiento'}
              </div>
              {dias !== null && dias >= 0 && dias <= 5 && (
                <div style={{ marginTop: 6 }}><AlertPill>cierra en {dias} día{dias === 1 ? '' : 's'}</AlertPill></div>
              )}
            </div>
          </Card>
        )
      })}

      {/* Edit modal — uses AccountForm with credit type defaults */}
      <AccountForm
        key={editCard ? `card-${editCard.id}` : 'card-edit'}
        account={editCard}
        open={editCard !== null}
        onClose={() => setEditCard(null)}
        defaultType="credito"
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteCard !== null}
        onOpenChange={(o) => { if (!o) setDeleteCard(null) }}
        title="¿Borrar esta tarjeta?"
        description={deleteCard ? `Se eliminará "${deleteCard.name}".` : ''}
        onConfirm={() => {
          if (deleteCard) remove.mutate(deleteCard.id)
          setDeleteCard(null)
        }}
      />
    </div>
  )
}
