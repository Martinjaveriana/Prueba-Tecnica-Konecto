# Decisiones de diseño

Qué se decidió en el proyecto, por qué y qué se descartó. Este documento se actualiza en cada fase. Los comandos están en [guia-de-comandos.md](guia-de-comandos.md).

## Cómo funciona la ingesta

```
series_76_electric_data.pdf
        │  Docling lee las imágenes (--extract)
        ▼
data/raw/docling_tables.json          lo que leyó Docling, sin tocar
        │  spec.py: estructura declarada de las 7 tablas
        │  corrections.json: arreglos revisados contra el PDF
        │  build.py: limpia y valida (--build)
        ▼
data/processed/actuators.json         EL RESULTADO: los datos finales
        │  load.py carga en la base de datos (sin opciones)
        ▼
PostgreSQL                            lo que consultará el agente


Aparte, solo como verificación (--audit):

PDF + actuators.json
        │  Gemini lee el PDF por su cuenta
        ▼
data/audit/pages/*.json               lo que Gemini leyó, una por página
data/audit/report.json                en qué se diferencia de nuestros datos
```

La auditoría no cambia ningún dato. Solo indica qué celdas hay que mirar en el PDF.

## El flujo paso a paso

Nada escribe en `corrections.json` ni en `spec.py` de forma automática: ambos los edita una persona después de mirar el PDF, como explica [guia-de-correcciones.md](guia-de-correcciones.md).

1. **Extraer (`--extract`).** Docling lee el PDF y guarda `raw/`. Al terminar, corre `build.py`.
2. **Detectar errores (`build.py`).** Valida cada celda y, si algo falla, lista los problemas y no escribe `actuators.json`. La primera vez listó las 6 velocidades, por ejemplo `'£3' is not a valid value`.
3. **Corregir a mano.** Se mira cada celda en el PDF y se anota en `corrections.json`.
4. **Reconstruir (`--build`).** Ya sin problemas, `build.py` crea `actuators.json`.
5. **Auditar (`--audit`).** Gemini lee el PDF por su cuenta y se compara con `actuators.json`. Las diferencias quedan en `report.json`, sin cambiar nada.
6. **Revisar la auditoría.** Se mira cada diferencia en el PDF. Si nuestro dato está bien, no se cambia nada. Si está mal, se corrige en `corrections.json` o `spec.py` y se vuelve al paso 4.
7. **Cargar (sin opciones).** `actuators.json` pasa a PostgreSQL.

Estos pasos ya se hicieron y sus resultados están en el repo, así que para usar los datos solo hace falta el paso 7.

### Dónde se arregla cada cosa

| Qué pasa | Ejemplo | Dónde se resuelve |
|---|---|---|
| Error con una sola respuesta posible | `1133OC0O` → `11330C00`, `"4,800"` → 4800 | Código, en `build.py` |
| Dato que Docling no da de forma fiable | Potencia, voltaje, tipo de carcasa | Declarado a mano, en `spec.py` |
| Número mal leído | `£3` → 33 | Declarado a mano, en `corrections.json` |
| Gemini ve algo distinto | 90 W en vez de 180 W | Nada automático: se mira el PDF |

### Cómo sale bien la potencia si en `raw/` se ve incompleta

El valor de potencia es una celda combinada, y Docling lo deja solo en una fila del grupo. Así queda en la tabla de 110 V de la página 1:

| Modelo | En `raw/` | Grupo declarado en `spec.py` | En `actuators.json` |
|---|---|---|---|
| `761A00` | 15 | 15 W: 1A, 1B | 15 |
| `761B00` | vacío | 15 W | 15 |
| `762A00` | vacío | 40 W: 2A, 2B, 3A | 40 |
| `762B00` | 40 | 40 W | 40 |
| `763A00` | vacío | 40 W | 40 |
| `763B00` | vacío | 90 W: 3B, 3C | 90 |
| `763C00` | 90 | 90 W | 90 |
| `764A00` | vacío | 180 W: 4A, 4B, 5A, 5B | 180 |
| `764B00` | 180 | 180 W | 180 |
| `765A00` | vacío | 180 W | 180 |
| `765B00` | vacío | 180 W | 180 |

La potencia final sale de `spec.py`, no de `raw/`. No se rellena con el valor de arriba porque fallaría: `762A00` recibiría 15 W, y en realidad tiene 40 W.

Los grupos se escribieron a mano, mirando en el PDF las líneas que separan cada bloque. Tienen dos comprobaciones: si Docling leyó un valor en una fila, debe coincidir con el grupo, o el proceso se detiene; y Gemini leyó la potencia por su cuenta y coincidió en 63 de 64 modelos. La excepción fue el error suyo en `764Y30-11300000/A`.

## Qué hay en cada archivo

Todos están en `backend/data/`. El ejemplo sigue al modelo `763C00-11300000/A`, cuya velocidad a 60 Hz Docling leyó mal.

| Archivo | Qué contiene | ¿Quién lo escribe? | En el ejemplo |
|---|---|---|---|
| `raw/docling_tables.json` | Las filas tal como las leyó Docling, con errores | Docling (`--extract`) | Velocidad: `"£3"` |
| `corrections.json` | Los valores que Docling leyó mal, cuál es el correcto y por qué | Una persona, tras mirar el PDF | `"read": "£3", "value": 33` |
| **`processed/actuators.json`** | **El resultado final:** los 68 modelos limpios y validados | `build.py` | `"speed_sec": 33` |
| `audit/pages/<modelo>_page_N.json` | Lo que Gemini leyó en esa página | La auditoría (`--audit`) | `"33"` |
| `audit/report.json` | El resultado de la auditoría; lo importante es `differences` | La auditoría (`--audit`) | No aparece: coincide |

### `processed/actuators.json`: quién lo crea

Lo crea `backend/ingestion/build.py`, sin ningún LLM, cada vez que se corre `--build` o `--extract`. Toma tres entradas:

| Entrada | Qué aporta | En el ejemplo |
|---|---|---|
| `raw/docling_tables.json` | Los números leídos del PDF | Torque 550 Nm, FLA 4.8 |
| `ingestion/spec.py` | Lo que Docling no da de forma fiable: enclosure, voltaje, fases, orden de columnas, grupos de potencia | Weatherproof, 110 V, 90 W |
| `corrections.json` | Los valores que Docling leyó mal | Velocidad 33 en vez de `£3` |

`build.py` limpia los part numbers, aplica las correcciones, convierte el texto en números, calcula el alias y valida las reglas. Si algo falla, no escribe el archivo.

### `corrections.json`: los errores de Docling, no los de Gemini

Contiene las 6 velocidades que Docling leyó mal. Cada entrada dice qué leyó, cuál es el valor real y dónde se comprobó:

```json
{
  "part_number": "763C00-11300000/A",
  "field": "speed_60",
  "read": "£3",
  "value": 33,
  "reason": "Docling misread the digit. PDF page 1, Weatherproof 110V table, shows 33."
}
```

Si Docling llegara a leer otra cosa en esa celda, `read` ya no coincide y el proceso se detiene en vez de aplicar una corrección vieja.

### `audit/report.json`: dónde ver lo que Gemini ve distinto

- `model`: el modelo usado.
- `rows_read`: cuántas filas leyó.
- **`differences`: las celdas en las que Gemini y nuestros datos no coinciden.**
- `readings`: una copia de todo lo que leyó.

```json
"differences": [
  { "part_number": "764Y30-11300000/A", "field": "motor_power_w", "ours": 180, "model": "90" }
]
```

### `processed/actuators.json`: una entrada por modelo

```json
{
  "part_number": "763C00-11300000/A",
  "alias": "3C",
  "enclosure": "weatherproof",
  "voltage_v": 110,
  "phases": 1,
  "motor_power_w": 90,
  "service_ratings": [
    { "service": "on_off", "torque_nm": 550, "duty_cycle_pct": 30, "cycles_per_hour": 13 },
    { "service": "modulating", "torque_nm": 400, "duty_cycle_pct": 40, "starts_per_hour": 960 }
  ],
  "electrical_ratings": [
    { "frequency_hz": 60, "speed_sec": 33, "fla_a": 4.8, "lra_a": 5.0 },
    { "frequency_hz": 50, "speed_sec": 39, "fla_a": 4.6, "lra_a": 4.9 }
  ]
}
```

El ejemplo está resumido. Cada parte corresponde a una tabla de PostgreSQL: los datos generales a `actuators`, `service_ratings` a la tabla del mismo nombre y `electrical_ratings` a la suya.

## Comandos

Se ejecutan desde `backend/`, con la base de datos arriba si van a cargar datos.

| Quiero... | Comando | Qué cambia |
|---|---|---|
| Cargar los datos en la base | `uv run python ingest.py` | PostgreSQL |
| Leer el PDF otra vez | `uv run --group extract python ingest.py --extract` | `raw/` y `processed/` |
| Reconstruir tras editar correcciones | `uv run python ingest.py --build` | `processed/` |
| Auditar | `uv run --group extract python ingest.py --audit` | `audit/` |

Detalles a tener en cuenta:

- **`--extract` no carga en la base.** Para eso hay que correr después `ingest.py` sin opciones.
- **`--audit` reutiliza lo ya leído.** Si `audit/pages/` tiene las páginas de ese modelo, no vuelve a consultar a Gemini. Para repetir la lectura, borra esos archivos o cambia `AUDIT_MODEL`.
- **Si hay un problema, `--build` y `--extract` no escriben `processed/`.** Muestran la lista de problemas en la terminal.

## Decisiones

### Datos

| Decisión | Por qué | Descartado | Costo |
|---|---|---|---|
| SQL con filtros exactos | "Torque ≥ 500 Nm" necesita una comparación exacta | RAG: puede traer una fila parecida pero incorrecta | Las preguntas deben traducirse a filtros |
| Sin pgvector | No hay búsqueda semántica que hacer; el summary cabe en el prompt | pgvector: agrega una pieza sin uso | Habría que agregarlo si aparece esa necesidad |
| Tres tablas | Un dato depende del servicio y otro de la frecuencia | Una tabla con más de 20 columnas y muchos vacíos | Las consultas necesitan JOIN |
| `NUMERIC` para FLA y LRA | 2.3 debe seguir siendo exactamente 2.3 | `FLOAT`: guarda aproximaciones | Ninguno relevante |
| Campo `hazardous_classification` en modelos Explosionproof | Permite responder sobre zonas peligrosas con lo que dicen las notas del PDF, no de memoria. Los textos se copiaron a mano en `spec.py` | Omitirlo: el agente no tendría ese dato | Ni las reglas ni la auditoría lo verifican; se comparó a ojo |
| Campo `size` calculado del alias (`1X` → 1) | Sirve para aplicar la nota "Sizes 6 and 7 are not CSA Certified"; el `*` del PDF lo comprueba en esos dos tamaños | Omitirlo y marcar el CSA modelo por modelo | Que del 1 al 5 también sean tamaños es una deducción, no lo dice el PDF. No debe usarse para comparar capacidad: para eso está el torque |
| Alias como `1A` | Es la forma corta de nombrar un modelo; se calcula con código | Usarlo como identificador: no es único (`1A` son 3 modelos, `1X` son 4) | El agente debe mostrar opciones o preguntar |

### Ingesta

| Decisión | Por qué | Descartado | Costo |
|---|---|---|---|
| Docling como lector | Encontró las 7 tablas, sin clave y con el mismo resultado al repetir | Ver la tabla siguiente | Pesa varios GB, por eso es opcional |
| Estructura declarada en `spec.py` | Si algo no coincide, falla en vez de guardar un dato errado | Detectar columnas: fue lo que falló en el prototipo | No sirve para otro PDF con otro formato |
| Potencia declarada por grupos | Docling solo da el valor en la fila central del grupo | Deducirla: el prototipo la asignó mal sin avisar | Hay que mantenerla a mano |
| Las reglas marcan, no corrigen | Una regla sabe que algo está mal, pero no qué celda | Corregir solo: puede inventar números | Cada error requiere revisión humana |
| Corregir solo lo evidente con código | La letra O en un part number solo tiene una lectura posible | Cambiar `761800` por `761B00`: podría devolver otro producto | Ninguno relevante |
| Datos revisados en el repo | Cargarlos no requiere clave, Docling ni descargas | Correr Docling siempre: varios GB para cargar 68 filas | Hay dos pasos en vez de uno |
| Auditoría con Gemini | Docling usa RapidOCR por dentro; un modelo de visión es una lectura independiente | Auditar con RapidOCR: no sería independiente | Necesita clave y depende de que el modelo esté disponible |

**Lectores probados con el PDF real:**

| Lector | Resultado |
|---|---|
| pdfplumber | 0 líneas y 0 tablas: el PDF son imágenes |
| Tesseract | Cambia dígitos sin avisar (31,000 → 33.000) |
| pymupdf4llm | Tablas dañadas; encontró 58 de 68 part numbers |
| RapidOCR solo | 68 filas, pero cruza columnas y leyó 06 en vez de 90 |
| **Docling** | **7 tablas y columnas correctas; 6 velocidades mal leídas, todas detectables** |

### Comportamiento del agente (se implementa en la Fase 2)

| Decisión | Por qué | Descartado |
|---|---|---|
| Comparar el torque en la columna de la unidad pedida | El PDF redondea: 880 in-lbs figura como 100 Nm, y 100 Nm son unos 885 in-lbs. Convertir descartaría un modelo que sí cumple | Convertir todo a una unidad |
| Convertir solo lo que el PDF no trae, con código | El LLM no debe calcular números | Dejar la conversión al LLM |
| Las tablas de 3 fases se guardan con servicio "sin especificar" | El PDF da un solo torque y no dice a qué modo aplica | Copiarlo a On/Off y Modulating: afirma algo que el PDF no dice |
| Mostrarlas al filtrar por modo, con un aviso | Si no, ningún modelo de 3 fases aparecería al pedir un modo | Buscar solo la etiqueta exacta |
| Un part number inexistente se trata como inexistente | `761A00-11380000/A`, el ejemplo del summary, no está en las tablas | Corregirlo solo |

Texto del aviso de 3 fases: "Encontré `763B00-11330C00/A`, de 500 Nm. Ojo: la tabla no indica si ese valor aplica a Modulating."

### Proyecto

| Decisión | Por qué | Descartado |
|---|---|---|
| Un repo con `backend/` y `android/` | Lo pide el enunciado | Repos separados |
| Android con Kotlin | SwiftUI exige Mac y el desarrollo es en Linux | iOS |
| Puerto 5433 para Postgres | El 5432 suele estar ocupado, como en esta máquina | Usar 5432 |
| Modelos configurables por `.env` | `gemini-2.5-flash` dejó de estar disponible y solo hubo que cambiar una variable | Dejarlo fijo en el código |

## Cómo se verificaron los datos

1. **Reglas automáticas:** formato de cada valor, 68 filas, proporción entre in-lbs y Nm (±5 %), LRA ≥ FLA, y que 60 Hz no sea más lento que 50 Hz. Solo fallaron las 6 velocidades mal leídas.
2. **Repetición:** correr `--extract` dos veces dio archivos idénticos, en una sola máquina.
3. **Revisión contra las imágenes:** todas las filas comparadas a ojo con el PDF.
4. **Auditoría:** `gemini-3.5-flash` leyó las 68 filas y se compararon 869 celdas, con una diferencia: la potencia de `764Y30-11300000/A` (nosotros 180 W, Gemini 90 W). El PDF confirma 180 W: el 90 está centrado en un bloque de dos filas que no incluye ese modelo.
5. **Tests:** 37 pruebas, incluidos valores comprobados a mano y casos en los que el proceso debe detenerse.

**Límite conocido:** esto reduce el riesgo, pero no prueba que no quede ningún error, porque dos lectores y una persona pueden equivocarse en la misma celda.

## Pendiente de decidir

- **Modelo del agente:** se elige en la Fase 3, con los precios de ese momento.
