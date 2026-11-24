"""
Motor del modelo de Transporte de OptiRoute.

Incluye:
  - Balanceo automático con origen o destino ficticio.
  - Soluciones iniciales: esquina noroeste, costo mínimo y aproximación de Vogel.
  - Optimización con el método MODI (u-v), registrando cada iteración.
  - Validación con un solver de Programación Lineal (PuLP/CBC o, si no está
    instalado, SciPy/HiGHS).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

EPS = 1e-9
FICTICIO = "Ficticio"


# ----------------------------------------------------------------------------
# Estructuras de datos
# ----------------------------------------------------------------------------
@dataclass
class Problema:
    origenes: list[str]
    destinos: list[str]
    oferta: list[float]
    demanda: list[float]
    costos: list[list[float]]
    ficticio: str | None = None  # "origen", "destino" o None

    def __post_init__(self):
        self.costos = np.asarray(self.costos, dtype=float)
        m, n = self.costos.shape
        if m != len(self.origenes) or m != len(self.oferta):
            raise ValueError("El número de orígenes no coincide con la matriz de costos.")
        if n != len(self.destinos) or n != len(self.demanda):
            raise ValueError("El número de destinos no coincide con la matriz de costos.")
        if any(v < 0 for v in [*self.oferta, *self.demanda]):
            raise ValueError("La oferta y la demanda no pueden ser negativas.")

    @property
    def m(self) -> int:
        return len(self.origenes)

    @property
    def n(self) -> int:
        return len(self.destinos)

    @property
    def balanceado(self) -> bool:
        return abs(sum(self.oferta) - sum(self.demanda)) < EPS


@dataclass
class Solucion:
    metodo: str
    asignacion: np.ndarray          # matriz m x n de cantidades
    basicas: set[tuple[int, int]]   # celdas básicas (incluye ceros por degeneración)
    costo: float
    pasos: list[str] = field(default_factory=list)


@dataclass
class IteracionMODI:
    numero: int
    asignacion: np.ndarray
    basicas: set[tuple[int, int]]
    costo: float
    u: np.ndarray
    v: np.ndarray
    costos_reducidos: np.ndarray    # c_ij - u_i - v_j (NaN en celdas básicas)
    entra: tuple[int, int] | None
    ciclo: list[tuple[int, int]] | None
    theta: float | None
    sale: tuple[int, int] | None


# ----------------------------------------------------------------------------
# Balanceo
# ----------------------------------------------------------------------------
def balancear(p: Problema, costo_penalizacion: float = 0.0) -> Problema:
    """Agrega un destino ficticio (si sobra oferta) o un origen ficticio (si falta)."""
    total_oferta, total_demanda = sum(p.oferta), sum(p.demanda)
    if abs(total_oferta - total_demanda) < EPS:
        return Problema(p.origenes[:], p.destinos[:], p.oferta[:], p.demanda[:], p.costos.copy())

    if total_oferta > total_demanda:
        costos = np.hstack([p.costos, np.zeros((p.m, 1))])
        return Problema(p.origenes[:], p.destinos + [FICTICIO], p.oferta[:],
                        p.demanda + [total_oferta - total_demanda], costos, ficticio="destino")

    costos = np.vstack([p.costos, np.full((1, p.n), costo_penalizacion)])
    return Problema(p.origenes + [FICTICIO], p.destinos[:], p.oferta + [total_demanda - total_oferta],
                    p.demanda[:], costos, ficticio="origen")


# ----------------------------------------------------------------------------
# Utilidades de la base (árbol de m + n - 1 celdas)
# ----------------------------------------------------------------------------
class _UnionFind:
    def __init__(self, k: int):
        self.padre = list(range(k))

    def buscar(self, a: int) -> int:
        while self.padre[a] != a:
            self.padre[a] = self.padre[self.padre[a]]
            a = self.padre[a]
        return a

    def unir(self, a: int, b: int) -> bool:
        ra, rb = self.buscar(a), self.buscar(b)
        if ra == rb:
            return False
        self.padre[ra] = rb
        return True


def _completar_base(p: Problema, basicas: set[tuple[int, int]], pasos: list[str]) -> set[tuple[int, int]]:
    """Si la solución es degenerada, agrega celdas con asignación 0 (las de menor costo
    que no formen ciclo) hasta tener m + n - 1 celdas básicas."""
    m, n = p.m, p.n
    uf = _UnionFind(m + n)
    base: set[tuple[int, int]] = set()
    for (i, j) in sorted(basicas):
        if uf.unir(i, m + j):
            base.add((i, j))
    if len(base) < m + n - 1:
        candidatas = sorted(((p.costos[i, j], i, j) for i in range(m) for j in range(n)
                             if (i, j) not in base))
        for _, i, j in candidatas:
            if len(base) == m + n - 1:
                break
            if uf.unir(i, m + j):
                base.add((i, j))
                pasos.append(f"Degeneración: se agrega la celda ({p.origenes[i]}, {p.destinos[j]}) "
                             f"como básica con asignación 0.")
    return base


def _costo(p: Problema, x: np.ndarray) -> float:
    return float((p.costos * x).sum())


# ----------------------------------------------------------------------------
# Soluciones iniciales
# ----------------------------------------------------------------------------
def esquina_noroeste(p: Problema) -> Solucion:
    oferta, demanda = list(p.oferta), list(p.demanda)
    x = np.zeros((p.m, p.n))
    basicas, pasos = set(), []
    i = j = 0
    while i < p.m and j < p.n:
        q = min(oferta[i], demanda[j])
        x[i, j] = q
        basicas.add((i, j))
        oferta[i] -= q
        demanda[j] -= q
        pasos.append(f"Asignar {q:g} a ({p.origenes[i]}, {p.destinos[j]}).")
        if oferta[i] < EPS and i < p.m - 1:
            i += 1
        else:
            j += 1
    basicas = _completar_base(p, basicas, pasos)
    return Solucion("Esquina noroeste", x, basicas, _costo(p, x), pasos)


def costo_minimo(p: Problema) -> Solucion:
    oferta, demanda = list(p.oferta), list(p.demanda)
    x = np.zeros((p.m, p.n))
    basicas, pasos = set(), []
    filas_activas, cols_activas = set(range(p.m)), set(range(p.n))
    orden = sorted((p.costos[i, j], i, j) for i in range(p.m) for j in range(p.n))
    for c, i, j in orden:
        if i not in filas_activas or j not in cols_activas:
            continue
        q = min(oferta[i], demanda[j])
        x[i, j] = q
        basicas.add((i, j))
        oferta[i] -= q
        demanda[j] -= q
        pasos.append(f"Costo {c:g}: asignar {q:g} a ({p.origenes[i]}, {p.destinos[j]}).")
        if oferta[i] < EPS and (len(filas_activas) > 1 or demanda[j] > EPS):
            filas_activas.discard(i)
        elif demanda[j] < EPS:
            cols_activas.discard(j)
        if not filas_activas or not cols_activas:
            break
    basicas = _completar_base(p, basicas, pasos)
    return Solucion("Costo mínimo", x, basicas, _costo(p, x), pasos)


def vogel(p: Problema) -> Solucion:
    oferta, demanda = list(p.oferta), list(p.demanda)
    x = np.zeros((p.m, p.n))
    basicas, pasos = set(), []
    filas, cols = set(range(p.m)), set(range(p.n))

    def penalizacion(valores: list[float]) -> float:
        v = sorted(valores)
        return v[1] - v[0] if len(v) > 1 else v[0]

    while filas and cols:
        mejor = None  # (penalización, -costo mínimo, tipo, índice)
        for i in filas:
            pen = penalizacion([p.costos[i, j] for j in cols])
            cmin = min(p.costos[i, j] for j in cols)
            cand = (pen, -cmin, "fila", i)
            if mejor is None or cand[:2] > mejor[:2]:
                mejor = cand
        for j in cols:
            pen = penalizacion([p.costos[i, j] for i in filas])
            cmin = min(p.costos[i, j] for i in filas)
            cand = (pen, -cmin, "columna", j)
            if cand[:2] > mejor[:2]:
                mejor = cand
        pen, _, tipo, k = mejor
        if tipo == "fila":
            i = k
            j = min(cols, key=lambda c: p.costos[i, c])
        else:
            j = k
            i = min(filas, key=lambda r: p.costos[r, j])
        q = min(oferta[i], demanda[j])
        x[i, j] = q
        basicas.add((i, j))
        oferta[i] -= q
        demanda[j] -= q
        nombre = p.origenes[k] if tipo == "fila" else p.destinos[k]
        pasos.append(f"Mayor penalización {pen:g} ({tipo} {nombre}): asignar {q:g} a "
                     f"({p.origenes[i]}, {p.destinos[j]}).")
        # Se elimina solo una línea por paso para conservar la estructura de la base.
        if oferta[i] < EPS and (len(filas) > 1 or demanda[j] > EPS):
            filas.discard(i)
        elif demanda[j] < EPS:
            cols.discard(j)
        else:
            filas.discard(i)
    basicas = _completar_base(p, basicas, pasos)
    return Solucion("Aproximación de Vogel", x, basicas, _costo(p, x), pasos)


METODOS_INICIALES = {
    "noroeste": esquina_noroeste,
    "costo_minimo": costo_minimo,
    "vogel": vogel,
}


# ----------------------------------------------------------------------------
# Método MODI
# ----------------------------------------------------------------------------
def multiplicadores(p: Problema, basicas: set[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray]:
    """Resuelve u_i + v_j = c_ij en las celdas básicas, con u_1 = 0."""
    u = np.full(p.m, np.nan)
    v = np.full(p.n, np.nan)
    u[0] = 0.0
    pendientes = set(basicas)
    while pendientes:
        avance = False
        for (i, j) in list(pendientes):
            if not np.isnan(u[i]) and np.isnan(v[j]):
                v[j] = p.costos[i, j] - u[i]
            elif np.isnan(u[i]) and not np.isnan(v[j]):
                u[i] = p.costos[i, j] - v[j]
            elif np.isnan(u[i]) and np.isnan(v[j]):
                continue
            pendientes.discard((i, j))
            avance = True
        if not avance:
            raise RuntimeError("La base no es conexa; no se pueden calcular u y v.")
    return u, v


def _ciclo(basicas: set[tuple[int, int]], entra: tuple[int, int]) -> list[tuple[int, int]]:
    """Encuentra el ciclo cerrado (stepping stone) que forma la celda que entra."""
    celdas = set(basicas) | {entra}
    # Se eliminan repetidamente las celdas que quedan solas en su fila o columna.
    cambio = True
    while cambio:
        cambio = False
        for (i, j) in list(celdas):
            en_fila = sum(1 for (a, _) in celdas if a == i)
            en_col = sum(1 for (_, b) in celdas if b == j)
            if en_fila < 2 or en_col < 2:
                celdas.discard((i, j))
                cambio = True
    # Se ordena el ciclo alternando movimientos por fila y por columna.
    ciclo = [entra]
    por_fila = True
    while True:
        i, j = ciclo[-1]
        if por_fila:
            sig = next(c for c in celdas if c[0] == i and c != (i, j))
        else:
            sig = next(c for c in celdas if c[1] == j and c != (i, j))
        if sig == entra:
            break
        ciclo.append(sig)
        por_fila = not por_fila
    return ciclo


def modi(p: Problema, inicial: Solucion, max_iter: int = 100) -> list[IteracionMODI]:
    """Mejora la solución inicial hasta que todos los costos reducidos sean >= 0."""
    x = inicial.asignacion.copy()
    basicas = set(inicial.basicas)
    iteraciones: list[IteracionMODI] = []

    for k in range(1, max_iter + 1):
        u, v = multiplicadores(p, basicas)
        reducidos = p.costos - u[:, None] - v[None, :]
        for (i, j) in basicas:
            reducidos[i, j] = np.nan
        minimo = np.nanmin(reducidos) if np.any(~np.isnan(reducidos)) else 0.0

        if minimo >= -EPS:
            iteraciones.append(IteracionMODI(k, x.copy(), set(basicas), _costo(p, x),
                                             u, v, reducidos, None, None, None, None))
            return iteraciones

        entra = tuple(int(a) for a in np.unravel_index(np.nanargmin(reducidos), reducidos.shape))
        ciclo = _ciclo(basicas, entra)
        negativas = ciclo[1::2]
        theta = min(x[c] for c in negativas)
        sale = min((c for c in negativas if abs(x[c] - theta) < EPS),
                   key=lambda c: p.costos[c])

        iteraciones.append(IteracionMODI(k, x.copy(), set(basicas), _costo(p, x),
                                         u, v, reducidos, entra, ciclo, float(theta), sale))
        for idx, c in enumerate(ciclo):
            x[c] += theta if idx % 2 == 0 else -theta
        x[np.abs(x) < EPS] = 0.0
        basicas.discard(sale)
        basicas.add(entra)

    raise RuntimeError("MODI no convergió en el número máximo de iteraciones.")


# ----------------------------------------------------------------------------
# Validación con solver de Programación Lineal
# ----------------------------------------------------------------------------
def resolver_con_solver(p: Problema) -> dict:
    """Resuelve el modelo balanceado como PL. Usa PuLP si está instalado; si no, SciPy."""
    try:
        import pulp  # noqa: F401
        return _resolver_pulp(p)
    except ImportError:
        return _resolver_scipy(p)


def _resolver_pulp(p: Problema) -> dict:
    import pulp

    modelo = pulp.LpProblem("Transporte_OptiRoute", pulp.LpMinimize)
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", lowBound=0)
         for i in range(p.m) for j in range(p.n)}
    modelo += pulp.lpSum(p.costos[i, j] * x[i, j] for i in range(p.m) for j in range(p.n))
    for i in range(p.m):
        modelo += pulp.lpSum(x[i, j] for j in range(p.n)) == p.oferta[i], f"oferta_{i}"
    for j in range(p.n):
        modelo += pulp.lpSum(x[i, j] for i in range(p.m)) == p.demanda[j], f"demanda_{j}"
    modelo.solve(pulp.PULP_CBC_CMD(msg=False))

    asign = np.array([[x[i, j].value() or 0.0 for j in range(p.n)] for i in range(p.m)])
    duales_o = np.array([modelo.constraints[f"oferta_{i}"].pi for i in range(p.m)])
    duales_d = np.array([modelo.constraints[f"demanda_{j}"].pi for j in range(p.n)])
    return {"solver": "PuLP (CBC)", "estado": pulp.LpStatus[modelo.status],
            "costo": float(pulp.value(modelo.objective)), "asignacion": asign,
            "duales_oferta": duales_o, "duales_demanda": duales_d}


def _resolver_scipy(p: Problema) -> dict:
    from scipy.optimize import linprog

    m, n = p.m, p.n
    a_eq, b_eq = [], []
    for i in range(m):
        fila = np.zeros(m * n)
        fila[i * n:(i + 1) * n] = 1
        a_eq.append(fila)
        b_eq.append(p.oferta[i])
    for j in range(n):
        fila = np.zeros(m * n)
        fila[j::n] = 1
        a_eq.append(fila)
        b_eq.append(p.demanda[j])
    res = linprog(p.costos.ravel(), A_eq=np.array(a_eq), b_eq=b_eq,
                  bounds=(0, None), method="highs")
    if not res.success:
        raise RuntimeError(f"El solver no encontró solución: {res.message}")
    duales = res.eqlin.marginals
    return {"solver": "SciPy (HiGHS)", "estado": "Optimal", "costo": float(res.fun),
            "asignacion": res.x.reshape(m, n),
            "duales_oferta": duales[:m], "duales_demanda": duales[m:]}


# ----------------------------------------------------------------------------
# Flujo completo
# ----------------------------------------------------------------------------
def resolver(p: Problema, metodo_inicial: str = "vogel") -> dict:
    """Balancea, obtiene la solución inicial, optimiza con MODI y valida con el solver."""
    pb = balancear(p)
    iniciales = {clave: f(pb) for clave, f in METODOS_INICIALES.items()}
    iteraciones = modi(pb, iniciales[metodo_inicial])
    final = iteraciones[-1]
    solver = resolver_con_solver(pb)
    return {
        "problema": pb,
        "iniciales": iniciales,
        "metodo_inicial": metodo_inicial,
        "iteraciones": iteraciones,
        "optimo": final,
        "solver": solver,
        "coincide": abs(final.costo - solver["costo"]) < 1e-6,
    }
