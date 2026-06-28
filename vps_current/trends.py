"""trends.py — series mensuales para los graficos de tendencia. Puro/testeable.
Recibe filas ya agregadas (ym, ...) y devuelve {labels, series} listo para Chart.js.
NUNCA mezcla monedas: las separa por currency.
"""
import datetime as _dt


def _month_labels(months, today=None):
    """Lista de los ultimos `months` meses 'YYYY-MM' terminando en el mes de today."""
    if today is None:
        today = _dt.date.today().isoformat()
    y, m = int(today[:4]), int(today[5:7])
    labels = []
    for k in range(months - 1, -1, -1):
        yy = y + (m - 1 - k) // 12
        mm = (m - 1 - k) % 12 + 1
        labels.append(f"{yy:04d}-{mm:02d}")
    return labels


def monthly_trend(rows, months=6, today=None):
    """rows: [{ym:'YYYY-MM', type:'gasto'|'ingreso', currency, total}].
    -> {labels:[YYYY-MM...], series:{gasto:{cur:[vals]}, ingreso:{cur:[vals]}}}."""
    labels = _month_labels(months, today)
    idx = {lab: i for i, lab in enumerate(labels)}
    series = {"gasto": {}, "ingreso": {}}
    for r in rows:
        ym = r.get("ym"); typ = r.get("type"); cur = r.get("currency")
        if ym not in idx or typ not in series:
            continue
        series[typ].setdefault(cur, [0.0] * months)[idx[ym]] = float(r.get("total") or 0)
    return {"labels": labels, "series": series}


def bucket_by_category(rows, months=6, today=None, currency="ARS"):
    """rows: [{ym, cat, currency, total}] (gastos). Filtra a `currency`.
    -> {labels:[...], series:{cat:[vals]}}."""
    labels = _month_labels(months, today)
    idx = {lab: i for i, lab in enumerate(labels)}
    series = {}
    for r in rows:
        if r.get("currency") != currency:
            continue
        ym = r.get("ym"); cat = r.get("cat") or "(sin categoría)"
        if ym not in idx:
            continue
        series.setdefault(cat, [0.0] * months)[idx[ym]] = float(r.get("total") or 0)
    return {"labels": labels, "series": series}
