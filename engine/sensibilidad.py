"""
Análisis de sensibilidad del modelo de Transporte a partir de la base óptima de MODI.

Calcula:
  - Precios sombra de la oferta de cada origen y de la demanda de cada destino,
    expresados sobre el problema original (no balanceado).
  - Rango de validez de cada precio sombra: cuánto puede cambiar la oferta o la
    demanda sin que cambie la base óptima.
  - Costos reducidos de las rutas no utilizadas.
  - Rango de variación de cada costo unitario c_ij dentro del cual el plan óptimo
    no cambia (análisis de optimalidad).
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .transporte import EPS, FICTICIO, IteracionMODI, Problema, multiplicadores


# ----------------------------------------------------------------------------
# Rutas dentro del árbol de la base
# ----------------------------------------------------------------------------
def _ruta_en_arbol(p: Problema, basicas: set[tuple[int, int]], desde: str, hasta: str):
    """Camino entre dos nodos del árbol básico. Los nodos se nombran 'O<i>' o 'D<j>'.
    Devuelve la lista de celdas (i, j) recorridas en orden."""
    vecinos: dict[str, list[tuple[str, tuple[int, int]]]] = {}
    for (i, j) in basicas:
        vecinos.setdefault(f"O{i}", []).append((f"D{j}", (i, j)))
        vecinos.setdefault(f"D{j}", []).append((f"O{i}", (i, j)))
    previo: dict[str, tuple[str, tuple[int, int]] | None] = {desde: None}
    cola = deque([desde])
    while cola:
        nodo = cola.popleft()
        if nodo == hasta:
            break
        for sig, celda in vecinos.get(nodo, []):
            if sig not in previo:
                previo[sig] = (nodo, celda)
                cola.append(sig)
    if hasta not in previo:
        raise RuntimeError("La base no conecta los nodos solicitados.")
    camino, nodo = [], hasta
    while previo[nodo] is not None:
        anterior, celda = previo[nodo]
        camino.append(celda)
        nodo = anterior
    return camino[::-1]


def _rango_cambio(p, x, basicas, desde, hasta):
    """Rango [-a, +b] de δ para el cual la base sigue siendo factible cuando se
    envían δ unidades adicionales del nodo 'desde' al nodo 'hasta' por el árbol."""
    camino = _ruta_en_arbol(p, basicas, desde, hasta)
    bajar, subir = -np.inf, np.inf
    for k, celda in enumerate(camino):
        if k % 2 == 0:          # la celda aumenta en δ
            bajar = max(bajar, -x[celda])
        else:                   # la celda disminuye en δ
            subir = min(subir, x[celda])
    return float(bajar), float(subir)


# ----------------------------------------------------------------------------
# Análisis principal
# ----------------------------------------------------------------------------
def analizar(p: Problema, optimo: IteracionMODI) -> dict:
    x, basicas = optimo.asignacion, optimo.basicas
    u, v = optimo.u, optimo.v
    m_real = p.m - (1 if p.ficticio == "origen" else 0)
    n_real = p.n - (1 if p.ficticio == "destino" else 0)

    oferta, demanda = [], []
    # Cada cambio en el problema original se compensa con el nodo ficticio
    # (o, si está balanceado, se expresa con los multiplicadores directos).
    for i in range(m_real):
        if p.ficticio == "destino":
            precio = u[i] + v[-1]
            rango = _rango_cambio(p, x, basicas, f"O{i}", f"D{p.n - 1}")
        elif p.ficticio == "origen":
            precio = u[i] - u[-1]
            rango = _rango_cambio(p, x, basicas, f"O{i}", f"O{p.m - 1}")
        else:
            precio, rango = u[i], None
        holgura = float(x[i, -1]) if p.ficticio == "destino" else 0.0
        oferta.append({"nombre": p.origenes[i], "valor": float(p.oferta[i]),
                       "usado": float(p.oferta[i] - holgura), "holgura": holgura,
                       "precio_sombra": float(precio),
                       "rango": _rango_absoluto(p.oferta[i], rango)})

    for j in range(n_real):
        if p.ficticio == "destino":
            precio = v[j] - v[-1]
            rango = _invertir_demanda(p, x, basicas, j)
        elif p.ficticio == "origen":
            precio = v[j] + u[-1]
            rango = _rango_cambio(p, x, basicas, f"O{p.m - 1}", f"D{j}")
        else:
            precio, rango = v[j], None
        no_atendida = float(x[-1, j]) if p.ficticio == "origen" else 0.0
        demanda.append({"nombre": p.destinos[j], "valor": float(p.demanda[j]),
                        "atendida": float(p.demanda[j] - no_atendida),
                        "precio_sombra": float(precio),
                        "rango": _rango_absoluto(p.demanda[j], rango)})

    rutas = []
    for i in range(m_real):
        for j in range(n_real):
            c = float(p.costos[i, j])
            if (i, j) in basicas:
                baja, sube = _rango_costo_basico(p, basicas, optimo.costos_reducidos, i, j)
                rutas.append({"origen": p.origenes[i], "destino": p.destinos[j],
                              "cantidad": float(x[i, j]), "costo": c, "basica": True,
                              "costo_reducido": 0.0, "minimo": c - baja, "maximo": c + sube})
            else:
                d = float(optimo.costos_reducidos[i, j])
                rutas.append({"origen": p.origenes[i], "destino": p.destinos[j],
                              "cantidad": 0.0, "costo": c, "basica": False,
                              "costo_reducido": d, "minimo": c - d, "maximo": float("inf")})

    return {"oferta": oferta, "demanda": demanda, "rutas": rutas,
            "interpretacion": interpretar(oferta, demanda, rutas)}


def _invertir_demanda(p, x, basicas, j):
    """Rango de δ al aumentar la demanda del destino j en δ, absorbido por el destino
    ficticio (la oferta total no cambia; el ficticio recibe δ unidades menos)."""
    # Aumentar d_j en δ y disminuir d_F en δ equivale a redirigir δ unidades del nodo
    # D_F hacia D_j por el árbol.
    camino = _ruta_en_arbol(p, basicas, f"D{p.n - 1}", f"D{j}")
    bajar, subir = -np.inf, np.inf
    for k, celda in enumerate(camino):
        if k % 2 == 0:          # sale menos hacia el ficticio
            subir = min(subir, x[celda])
        else:
            bajar = max(bajar, -x[celda])
    return float(bajar), float(subir)


def _rango_absoluto(valor, rango):
    if rango is None:
        return None
    baja, sube = rango
    return [max(0.0, valor + baja), valor + sube]


def _rango_costo_basico(p, basicas, reducidos, i, j):
    """Cuánto puede bajar o subir c_ij (celda básica) sin que algún costo reducido
    se vuelva negativo. Se calcula el efecto de un cambio unitario en u y v."""
    base_u, base_v = multiplicadores(p, basicas)
    costos = p.costos.copy()
    costos[i, j] += 1.0
    q = Problema(p.origenes, p.destinos, p.oferta, p.demanda, costos)
    nu, nv = multiplicadores(q, basicas)
    # Cambio de cada costo reducido por unidad de cambio en c_ij.
    delta = -((nu - base_u)[:, None] + (nv - base_v)[None, :])
    baja, sube = np.inf, np.inf
    for a in range(p.m):
        for b in range(p.n):
            if (a, b) in basicas:
                continue
            r, g = reducidos[a, b], delta[a, b]
            if g < -EPS:      # el costo reducido baja si c_ij sube
                sube = min(sube, r / -g)
            elif g > EPS:     # el costo reducido baja si c_ij baja
                baja = min(baja, r / g)
    return float(baja), float(sube)


# ----------------------------------------------------------------------------
# Interpretación gerencial
# ----------------------------------------------------------------------------
def _pesos(v):
    return f"${abs(v):,.2f}".replace(".00", "")


def _num(v):
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def interpretar(oferta, demanda, rutas) -> list[str]:
    notas = []
    for o in oferta:
        ps = o["precio_sombra"]
        r = o["rango"]
        if o["holgura"] > EPS:
            notas.append(f"{o['nombre']} tiene {_num(o['holgura'])} unidades ociosas: ampliar su "
                         f"capacidad no reduce el costo (precio sombra $0).")
        elif ps < -EPS:
            extra = f" Este valor se mantiene mientras su capacidad esté entre {_num(r[0])} y {_num(r[1])}." if r else ""
            notas.append(f"{o['nombre']} opera a toda su capacidad. Cada unidad adicional ahorraría "
                         f"{_pesos(ps)}; conviene ampliarla solo si cuesta menos que eso.{extra}")
    if demanda:
        cara = max(demanda, key=lambda d: d["precio_sombra"])
        barata = min(demanda, key=lambda d: d["precio_sombra"])
        notas.append(f"Atender una unidad más de demanda cuesta desde {_pesos(barata['precio_sombra'])} "
                     f"({barata['nombre']}) hasta {_pesos(cara['precio_sombra'])} ({cara['nombre']}). "
                     f"Sirve como base para fijar el cargo de envío por sucursal.")
    no_usadas = sorted((r for r in rutas if not r["basica"]), key=lambda r: r["costo_reducido"])
    if no_usadas:
        r = no_usadas[0]
        if r["costo_reducido"] < EPS:
            notas.append(f"La ruta {r['origen']} → {r['destino']} tiene costo reducido 0: hay un plan "
                         f"alterno con el mismo costo total.")
        else:
            notas.append(f"La ruta no utilizada más cercana a convenir es {r['origen']} → {r['destino']}: "
                         f"entraría al plan si su tarifa bajara de {_pesos(r['costo'])} a menos de "
                         f"{_pesos(r['minimo'])}.")
    estrechas = [r for r in rutas if r["basica"] and r["cantidad"] > EPS]
    if estrechas:
        r = min(estrechas, key=lambda r: min(r["costo"] - r["minimo"], r["maximo"] - r["costo"]))
        notas.append(f"La ruta más sensible del plan es {r['origen']} → {r['destino']}: el plan solo se "
                     f"mantiene si su tarifa queda entre {_pesos(r['minimo'])} y "
                     f"{'sin límite' if np.isinf(r['maximo']) else _pesos(r['maximo'])}.")
    return notas
