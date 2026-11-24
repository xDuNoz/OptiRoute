"""OptiRoute: aplicación web del modelo de Transporte (Flask)."""
import json
import math
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from engine.sensibilidad import analizar
from engine.transporte import Problema, resolver

BASE = Path(__file__).resolve().parent
app = Flask(__name__)


def _limpio(valor):
    """Convierte arreglos de NumPy y NaN a tipos que JSON acepta."""
    if hasattr(valor, "tolist"):
        valor = valor.tolist()
    if isinstance(valor, dict):
        return {k: _limpio(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_limpio(v) for v in valor]
    if hasattr(valor, "item") and not hasattr(valor, "__len__"):
        valor = valor.item()
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, float):
        return None if (math.isnan(valor) or math.isinf(valor)) else round(valor, 6)
    return valor


def _celdas(conjunto):
    return sorted([list(c) for c in conjunto])


@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/api/ejemplo")
def ejemplo():
    datos = json.loads((BASE / "data" / "distribuidora_noreste.json").read_text(encoding="utf-8"))
    return jsonify(datos)


@app.post("/api/resolver")
def api_resolver():
    d = request.get_json(force=True)
    try:
        p = Problema(d["origenes"], d["destinos"],
                     [float(v) for v in d["oferta"]], [float(v) for v in d["demanda"]],
                     [[float(c) for c in fila] for fila in d["costos"]])
        r = resolver(p, d.get("metodo", "vogel"))
        sens = analizar(r["problema"], r["optimo"])
    except (KeyError, ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error interno: {type(e).__name__}: {e}"}), 500

    try:
        return jsonify(_respuesta(r, p, sens))
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error al preparar la respuesta: {type(e).__name__}: {e}"}), 500


def _respuesta(r, p, sens):
    pb = r["problema"]
    return _limpio({
        "problema": {
            "origenes": pb.origenes, "destinos": pb.destinos,
            "oferta": _limpio(list(pb.oferta)), "demanda": _limpio(list(pb.demanda)),
            "costos": _limpio(pb.costos), "ficticio": pb.ficticio,
            "oferta_total": sum(p.oferta), "demanda_total": sum(p.demanda),
        },
        "iniciales": {
            k: {"metodo": s.metodo, "costo": s.costo, "asignacion": _limpio(s.asignacion),
                "basicas": _celdas(s.basicas), "pasos": s.pasos}
            for k, s in r["iniciales"].items()
        },
        "metodo_inicial": r["metodo_inicial"],
        "iteraciones": [
            {"numero": it.numero, "costo": it.costo, "asignacion": _limpio(it.asignacion),
             "basicas": _celdas(it.basicas), "u": _limpio(it.u), "v": _limpio(it.v),
             "reducidos": _limpio(it.costos_reducidos),
             "entra": list(it.entra) if it.entra else None,
             "ciclo": [list(c) for c in it.ciclo] if it.ciclo else None,
             "theta": it.theta, "sale": list(it.sale) if it.sale else None}
            for it in r["iteraciones"]
        ],
        "optimo": {"costo": r["optimo"].costo, "asignacion": _limpio(r["optimo"].asignacion)},
        "solver": {"nombre": r["solver"]["solver"], "estado": r["solver"]["estado"],
                   "costo": r["solver"]["costo"], "asignacion": _limpio(r["solver"]["asignacion"])},
        "coincide": r["coincide"],
        "sensibilidad": sens,
    })


if __name__ == "__main__":
    app.run(debug=True)
