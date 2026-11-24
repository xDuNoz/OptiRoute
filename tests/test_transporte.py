import json
from pathlib import Path

import numpy as np
import pytest

from engine.transporte import (Problema, balancear, costo_minimo, esquina_noroeste,
                               resolver, vogel)

DATOS = Path(__file__).resolve().parent.parent / "data" / "distribuidora_noreste.json"


def caso_estudio() -> Problema:
    d = json.loads(DATOS.read_text(encoding="utf-8"))
    return Problema(d["origenes"], d["destinos"], d["oferta"], d["demanda"], d["costos"])


def validar_factible(p: Problema, x: np.ndarray):
    assert np.all(x >= -1e-9)
    assert np.allclose(x.sum(axis=1), p.oferta)
    assert np.allclose(x.sum(axis=0), p.demanda)


# --- Caso de estudio (Entregable 1) -----------------------------------------
def test_balanceo_agrega_destino_ficticio():
    pb = balancear(caso_estudio())
    assert pb.ficticio == "destino"
    assert pb.destinos[-1] == "Ficticio"
    assert pb.demanda[-1] == 90
    assert pb.balanceado


@pytest.mark.parametrize("metodo, costo", [(esquina_noroeste, 19410),
                                           (costo_minimo, 18810),
                                           (vogel, 17490)])
def test_soluciones_iniciales(metodo, costo):
    pb = balancear(caso_estudio())
    s = metodo(pb)
    validar_factible(pb, s.asignacion)
    assert s.costo == pytest.approx(costo)
    assert len(s.basicas) == pb.m + pb.n - 1


@pytest.mark.parametrize("inicial", ["noroeste", "costo_minimo", "vogel"])
def test_optimo_caso_estudio(inicial):
    r = resolver(caso_estudio(), inicial)
    assert r["optimo"].costo == pytest.approx(17180)
    assert r["coincide"]
    esperado = np.array([[130, 0, 0, 170, 0],
                         [0, 0, 160, 0, 40],
                         [50, 150, 0, 0, 50]])
    assert np.allclose(r["optimo"].asignacion, esperado)


def test_multiplicadores_modi():
    opt = resolver(caso_estudio())["optimo"]
    assert np.allclose(opt.u, [0, 3, 3])
    assert np.allclose(opt.v, [22, 31, 16, 29, -3])
    assert np.nanmin(opt.costos_reducidos) == pytest.approx(1)


# --- Casos especiales -------------------------------------------------------
def test_demanda_mayor_que_oferta_agrega_origen_ficticio():
    p = Problema(["A", "B"], ["X", "Y", "Z"], [50, 40], [30, 40, 50],
                 [[4, 6, 9], [5, 3, 8]])
    r = resolver(p)
    assert r["problema"].ficticio == "origen"
    assert r["coincide"]


def test_caso_degenerado():
    # Oferta y demanda se agotan al mismo tiempo en la esquina noroeste.
    p = Problema(["A", "B", "C"], ["X", "Y", "Z"], [20, 30, 50], [20, 30, 50],
                 [[8, 6, 10], [9, 12, 13], [14, 9, 16]])
    for inicial in ["noroeste", "costo_minimo", "vogel"]:
        r = resolver(p, inicial)
        assert len(r["iniciales"][inicial].basicas) == 5
        assert r["coincide"]


@pytest.mark.parametrize("semilla", range(40))
def test_aleatorios_contra_solver(semilla):
    rng = np.random.default_rng(semilla)
    m, n = rng.integers(2, 7), rng.integers(2, 7)
    oferta = rng.integers(5, 100, m).tolist()
    demanda = rng.integers(5, 100, n).tolist()
    costos = rng.integers(1, 50, (m, n)).tolist()
    p = Problema([f"O{i}" for i in range(m)], [f"D{j}" for j in range(n)],
                 oferta, demanda, costos)
    for inicial in ["noroeste", "costo_minimo", "vogel"]:
        r = resolver(p, inicial)
        validar_factible(r["problema"], r["optimo"].asignacion)
        assert r["coincide"], (inicial, r["optimo"].costo, r["solver"]["costo"])


def test_datos_invalidos():
    with pytest.raises(ValueError):
        Problema(["A"], ["X", "Y"], [10], [5, 5], [[1, 2, 3]])


# --- Análisis de sensibilidad -----------------------------------------------
from engine.sensibilidad import analizar  # noqa: E402


def test_sensibilidad_caso_estudio():
    r = resolver(caso_estudio())
    a = analizar(r["problema"], r["optimo"])
    oferta = {o["nombre"]: o for o in a["oferta"]}
    assert oferta["Monterrey"]["precio_sombra"] == pytest.approx(-3)
    assert oferta["Monterrey"]["rango"] == pytest.approx([250, 350])
    assert oferta["Saltillo"]["precio_sombra"] == pytest.approx(0)
    assert oferta["Saltillo"]["holgura"] == pytest.approx(40)
    demanda = {d["nombre"]: d["precio_sombra"] for d in a["demanda"]}
    assert demanda == pytest.approx({"Reynosa": 25, "Matamoros": 34,
                                     "Monclova": 19, "Cd. Victoria": 32})
    rutas = {(x["origen"], x["destino"]): x for x in a["rutas"]}
    assert rutas[("Monterrey", "Matamoros")]["minimo"] == pytest.approx(31)
    assert rutas[("Monterrey", "Reynosa")]["minimo"] == pytest.approx(18)
    assert rutas[("Monterrey", "Reynosa")]["maximo"] == pytest.approx(23)


@pytest.mark.parametrize("semilla", range(30))
def test_precios_sombra_contra_resolver_de_nuevo(semilla):
    """El cambio en el costo óptimo al mover una unidad de oferta o demanda debe
    ser igual al precio sombra, siempre que el cambio quede dentro de su rango."""
    from engine.transporte import resolver_con_solver
    rng = np.random.default_rng(1000 + semilla)
    m, n = rng.integers(2, 6), rng.integers(2, 6)
    base = dict(origenes=[f"O{i}" for i in range(m)], destinos=[f"D{j}" for j in range(n)],
                oferta=rng.integers(10, 100, m).tolist(), demanda=rng.integers(10, 100, n).tolist(),
                costos=rng.integers(1, 60, (m, n)).tolist())
    r = resolver(Problema(**base))
    a = analizar(r["problema"], r["optimo"])
    z0 = r["optimo"].costo
    for clave, lista in (("oferta", a["oferta"]), ("demanda", a["demanda"])):
        for k, item in enumerate(lista):
            if item["rango"] is None or item["rango"][1] < item["valor"] + 1:
                continue
            datos = {**base, clave: [v + 1 if t == k else v for t, v in enumerate(base[clave])]}
            z1 = resolver_con_solver(balancear(Problema(**datos)))["costo"]
            assert z1 - z0 == pytest.approx(item["precio_sombra"])
