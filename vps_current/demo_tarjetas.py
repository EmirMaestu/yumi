#!/usr/bin/env python3
"""Demo del comportamiento real de tarjetas usando vencimientos.py del server."""
import datetime as dt
import vencimientos as v
from datetime import timedelta

def _shift_month(d, n):
    return v._shift_month(d, n)

def ciclos(cd, dd, today):
    lc, nc, nd = v.proximo_cierre_y_vencimiento(cd, dd, today)
    prev_prev = _shift_month(lc, -1)
    cerr_ini = prev_prev + timedelta(days=1)
    ab_ini = lc + timedelta(days=1)
    return lc, nc, nd, cerr_ini, ab_ini

def donde_cae(cd, dd, gasto, today):
    lc, nc, nd, cerr_ini, ab_ini = ciclos(cd, dd, today)
    if cerr_ini <= gasto <= lc:
        return f"CICLO CERRADO ({cerr_ini}..{lc}) -> a pagar ya, vence {nd}"
    if ab_ini <= gasto <= nc:
        return f"CICLO ABIERTO ({ab_ini}..{nc}) -> se paga despues (cierra {nc})"
    if gasto < cerr_ini:
        return f"ciclo viejo (anterior a {cerr_ini}) -> ya vencido/pagado"
    return f"futuro (despues de {nc})"

def card(cd, dd, label):
    print(f"\n{'='*70}\nTARJETA {label}: cierre dia {cd}, vencimiento dia {dd}\n{'='*70}")
    print("-- Cómo se ven los ciclos según el día que mirás --")
    for t in [dt.date(2026,3,10), dt.date(2026,3,28), dt.date(2026,3,29),
              dt.date(2026,4,2), dt.date(2026,4,6)]:
        lc, nc, nd, cerr_ini, ab_ini = ciclos(cd, dd, t)
        print(f"  miro el {t}:  cerrado(a pagar)={cerr_ini}..{lc} vence {nd}  |  abierto(en curso)={ab_ini}..{nc}")
    print("-- Un GASTO de contado: dónde aparece según cuándo lo cargás (mirando el 2026-03-29) --")
    for g in [dt.date(2026,3,15), dt.date(2026,3,27), dt.date(2026,3,28), dt.date(2026,3,29)]:
        print(f"  gasto {g}: {donde_cae(cd, dd, g, dt.date(2026,3,29))}")
    print("-- Una CUOTA comprada hoy (2026-03-20): en qué fecha 'se cobra' (vencimiento) --")
    venc = v.venc_de_cuota(cd, dd, dt.date(2026,3,20))
    print(f"  compra 2026-03-20 -> primera cuota vence {venc}")

card(28, 5, "A (cierre 28 / venc 5)")
card(2, 2, "B (cierre 2 / venc 2)")
card(2, 13, "C (cierre 2 / venc 13)")
