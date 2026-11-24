# OptiRoute · Sistema de optimización de distribución (Modelo de Transporte)

Proyecto Integrador Final de **Investigación de Operaciones** (Unidad 6).

OptiRoute resuelve el problema de transporte de una red de almacenes y sucursales. Reproduce el procedimiento visto en clase (balanceo, soluciones iniciales y método MODI) y valida el resultado con un solver de Programación Lineal.

## Funcionalidad

| Módulo | Descripción |
| --- | --- |
| Captura y balanceo | Tabla editable de orígenes, destinos, oferta, demanda y costos. Si el problema está desbalanceado, agrega un origen o destino ficticio con costo 0. |
| Soluciones iniciales | Esquina noroeste, costo mínimo y aproximación de Vogel, con su procedimiento paso a paso y su diferencia contra el óptimo. Maneja la degeneración agregando celdas básicas con asignación 0. |
| Optimización MODI | Cálculo de u<sub>i</sub> y v<sub>j</sub>, costos reducidos, celda que entra, ciclo, θ y celda que sale, en cada iteración. Detecta óptimos alternos. |
| Validación | Resuelve el mismo modelo como PL con PuLP (CBC) o, si PuLP no está instalado, con SciPy (HiGHS), y compara ambos costos. |
| Análisis de sensibilidad | Precios sombra de oferta y demanda con su rango de validez, holguras, costos reducidos y rango de variación de cada costo unitario, con interpretación gerencial automática. |
| Escenarios | Guarda una solución como base, permite cambiar cualquier dato y compara costo y plan de envíos contra la base. |
| Mapa de rutas | Mapa con Leaflet y OpenStreetMap; el grosor de cada ruta es proporcional al volumen enviado (requiere internet). |

## Modelo matemático

Variables: x<sub>ij</sub> = unidades enviadas del origen *i* al destino *j*.

```
min Z = Σ_i Σ_j c_ij · x_ij
s.a.  Σ_j x_ij = s_i     (oferta de cada origen)
      Σ_i x_ij = d_j     (demanda de cada destino)
      x_ij ≥ 0
```

## Caso de estudio

Distribuidora del Noreste S.A. de C.V.: 3 almacenes (Monterrey, Saltillo, Nuevo Laredo) y 4 sucursales (Reynosa, Matamoros, Monclova, Cd. Victoria). Datos en `data/distribuidora_noreste.json`.

| Método | Costo semanal |
| --- | --- |
| Esquina noroeste | $19,410 |
| Costo mínimo | $18,810 |
| Vogel | $17,490 |
| **Óptimo (MODI y solver)** | **$17,180** |

## Instalación y uso

Requisitos: Python 3.10 o superior.

```bash
pip install -r requirements.txt
python app.py
```

Abrir `http://127.0.0.1:5000` en el navegador. La aplicación carga el caso de estudio automáticamente.

Pruebas automáticas:

```bash
python -m pytest -q
```

## Estructura del repositorio

```
optiroute/
├── app.py                         # Servidor web (Flask) y API JSON
├── engine/
│   ├── transporte.py              # Motor: balanceo, métodos iniciales, MODI y solver
│   └── sensibilidad.py            # Precios sombra, rangos y costos reducidos
├── templates/index.html           # Interfaz
├── static/                        # Estilos y lógica de la interfaz
├── data/distribuidora_noreste.json
├── tests/test_transporte.py       # 82 pruebas (motor, degeneración, sensibilidad, casos aleatorios)
└── docs/
    ├── validacion_excel_solver.xlsx   # Modelo listo para Excel Solver
    ├── capturas/                      # Capturas de la aplicación
    └── prompts.md                     # Prompts de referencia
```

## Validación

1. **Pruebas automáticas:** el resultado de MODI coincide con el solver en el caso de estudio, en casos degenerados, en problemas desbalanceados en ambos sentidos y en 40 problemas aleatorios, partiendo de los tres métodos iniciales.
2. **Excel Solver:** `docs/validacion_excel_solver.xlsx` contiene el modelo y las instrucciones para resolverlo con Solver (Simplex LP). El costo esperado es $17,180.

## Resultados del análisis de sensibilidad (caso de estudio)

| Concepto | Resultado |
| --- | --- |
| Precio sombra de Monterrey | −$3 por tarima (válido con capacidad entre 250 y 350) |
| Precio sombra de Saltillo y Nuevo Laredo | $0 (40 y 50 tarimas ociosas) |
| Costo marginal de la demanda | Monclova $19, Reynosa $25, Cd. Victoria $32, Matamoros $34 |
| Ruta no usada más cercana a convenir | Monterrey → Matamoros, si su tarifa baja de $32 a menos de $31 |
| Ruta más sensible del plan | Monterrey → Reynosa, estable entre $18 y $23 |

## API

`POST /api/resolver`

```json
{
  "origenes": ["Monterrey", "Saltillo"],
  "destinos": ["Reynosa", "Matamoros"],
  "oferta": [300, 200],
  "demanda": [250, 250],
  "costos": [[22, 32], [30, 39]],
  "metodo": "vogel"
}
```

`metodo` acepta `noroeste`, `costo_minimo` o `vogel`. La respuesta incluye las soluciones iniciales, todas las iteraciones de MODI, el óptimo y la validación del solver.
