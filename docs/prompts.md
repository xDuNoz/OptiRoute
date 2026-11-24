# Prompts de referencia

El motor y la interfaz de OptiRoute se desarrollaron con apoyo de un asistente de inteligencia artificial (Claude, de Anthropic). Los resultados se verificaron con pruebas automáticas y con un solver de Programación Lineal. Estos son los prompts empleados.

## 1. Motor de optimización

```text
Actúa como programador especializado en Investigación de Operaciones.
Implementa en Python un módulo para el modelo de Transporte que:
1. Reciba orígenes, destinos, oferta, demanda y matriz de costos, y valide sus dimensiones.
2. Balancee el problema agregando un destino ficticio (si sobra oferta) o un origen
   ficticio (si falta), con costo 0.
3. Calcule la solución inicial por esquina noroeste, costo mínimo y Vogel, y registre
   cada asignación como un paso legible.
4. Garantice m + n - 1 celdas básicas en casos degenerados, agregando celdas con
   asignación 0 que no formen ciclo.
5. Optimice con el método MODI, guardando en cada iteración u, v, costos reducidos,
   celda que entra, ciclo, θ y celda que sale.
Usa NumPy, nombres en español y docstrings breves.
```

## 2. Validación con solver

```text
Agrega al módulo una función que resuelva el mismo modelo balanceado como Programación
Lineal con PuLP (solver CBC). Si PuLP no está instalado, usa scipy.optimize.linprog con
el método HiGHS. Devuelve el costo, la asignación y los valores duales de las
restricciones de oferta y demanda, e indica si el costo coincide con el de MODI.
```

## 3. Pruebas

```text
Escribe pruebas con pytest para el motor de Transporte que verifiquen:
- El costo de cada método inicial en el caso de estudio (19,410; 18,810; 17,490).
- El óptimo de 17,180 y los multiplicadores u = (0, 3, 3), v = (22, 31, 16, 29, -3).
- Un caso degenerado y un caso con demanda mayor que oferta.
- 40 problemas aleatorios en los que MODI coincida con el solver desde los tres
  métodos iniciales.
```

## 4. Interfaz web

```text
Crea una aplicación web con Flask para el motor de Transporte, con una sola página:
1. Tabla editable de datos con botones para agregar o quitar orígenes y destinos, y un
   aviso que indique si el problema está balanceado.
2. Tabla comparativa de los tres métodos iniciales contra el óptimo.
3. Visor de iteraciones de MODI: matriz con costo unitario en la esquina, celdas
   básicas resaltadas, costos reducidos en las celdas vacías, u_i y v_j en los
   márgenes, y la celda que entra, la que sale y los signos del ciclo marcados.
   Debajo, una explicación de la iteración en lenguaje claro.
4. Solución óptima, plan de envíos con subtotales y validación del solver.
Usa HTML, CSS y JavaScript sin frameworks, con un diseño limpio y profesional.
```

## 5. Validación en Excel

```text
Genera un libro de Excel con el modelo del caso de estudio listo para resolverse con
Solver: matriz de costos, celdas de variables, sumas de oferta y demanda, función
objetivo con SUMAPRODUCTO e instrucciones paso a paso para configurar Solver con el
método Simplex LP y obtener los informes de respuestas y sensibilidad.
```

## 6. Análisis de sensibilidad

```text
A partir de la base óptima de MODI, implementa el análisis de sensibilidad del modelo
de Transporte expresado sobre el problema original (no balanceado):
1. Precio sombra de la capacidad de cada origen y de la demanda de cada destino,
   usando los multiplicadores u y v y compensando el cambio con el nodo ficticio.
2. Rango de validez de cada precio sombra, calculado con el camino entre los nodos
   en el árbol de la base.
3. Costos reducidos de las rutas no utilizadas y rango de variación de cada costo
   unitario dentro del cual el plan óptimo no cambia.
4. Una interpretación gerencial en lenguaje claro de los resultados más relevantes.
Verifica cada precio sombra resolviendo de nuevo el modelo con el dato modificado.
```

## 7. Escenarios y mapa

```text
Agrega a la interfaz:
1. Una sección de escenarios que guarde la solución actual como base, permita cambiar
   datos y muestre la diferencia de costo y los cambios en cada ruta.
2. Un mapa con Leaflet y OpenStreetMap que dibuje almacenes, sucursales y rutas
   usadas, con grosor proporcional al volumen enviado.
3. Una sección con las tablas de sensibilidad y su interpretación.
```

## 8. Informe y presentación

```text
Redacta el informe final del Proyecto Integrador (puntos 6.1 a 6.6) con base en los
resultados de OptiRoute: planteamiento, formulación, justificación del modelo,
implementación, validación, análisis de sensibilidad, recomendaciones y conclusiones.
Después prepara una presentación ejecutiva de 10 diapositivas y un guion de 5 a 7
minutos para la demostración en vivo.
```
