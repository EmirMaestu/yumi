"""
Hechos del resumen semanal + fallback determinista. Modulo PURO: recibe filas
ya agregadas (por categoria y moneda) y un value_in_ars(amount,currency)->float
inyectado. Convierte a ARS explicitamente para poder rankear; nunca suma ARS+USD
sin pasar por la conversion.
"""


def digest_facts(agg_rows, prev_week_rows, value_in_ars, anomaly_pct=50.0):
    """agg_rows/prev_week_rows = [{'category','currency','total','n'}].
    Devuelve dict de hechos: total_ars, prev_total_ars, top (cat->ars), anomalies."""
    def by_cat_ars(rows):
        out = {}
        for r in rows:
            out[r["category"]] = out.get(r["category"], 0.0) + value_in_ars(
                float(r["total"] or 0), r["currency"])
        return out

    cur = by_cat_ars(agg_rows)
    prev = by_cat_ars(prev_week_rows)
    total = round(sum(cur.values()), 2)
    prev_total = round(sum(prev.values()), 2)
    top = [{"category": k, "total_ars": round(v, 2)}
           for k, v in sorted(cur.items(), key=lambda kv: kv[1], reverse=True)][:3]
    anomalies = []
    for cat, v in cur.items():
        pv = prev.get(cat, 0.0)
        if pv > 0:
            pct = ((v - pv) / pv) * 100
            if pct >= anomaly_pct:
                anomalies.append({"category": cat, "pct": round(pct, 1),
                                  "from_ars": round(pv, 2), "to_ars": round(v, 2)})
    anomalies.sort(key=lambda a: a["pct"], reverse=True)
    return {"total_ars": total, "prev_total_ars": prev_total,
            "top": top, "anomalies": anomalies}


def digest_fallback(facts):
    if not facts["top"]:
        return "Esta semana no registraste gastos. 🎉"
    parts = [f"Esta semana gastaste {facts['total_ars']:,.0f} ARS."]
    top = facts["top"][0]
    parts.append(f"Lo que más pesó: {top['category']} ({top['total_ars']:,.0f} ARS).")
    if facts["anomalies"]:
        a = facts["anomalies"][0]
        parts.append(f"Ojo: {a['category']} subió {a['pct']:.0f}% respecto a la semana anterior.")
    return " ".join(parts)
