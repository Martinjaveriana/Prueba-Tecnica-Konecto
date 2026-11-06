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

### Tools del agente (Fase 2)

La lógica está en `backend/app/catalog.py` y se prueba sin LLM. `backend/app/tools.py` solo la expone a LangChain.

| Tool | Para qué |
|---|---|
| `get_actuator_specs` | Buscar un modelo por part number, parte de él o alias |
| `recommend_actuators` | Buscar modelos por requisitos técnicos |
| `list_available_options` | Decir qué voltajes, carcasas, rangos y certificaciones existen |

**Qué responde `get_actuator_specs`:**

| El usuario escribe | `status` | Qué recibe el agente |
|---|---|---|
| `761a00-11300000/a` | `found` | Los datos del modelo |
| `1A` o `761A00` | `ambiguous` | 3 opciones, para mostrarlas o preguntar |
| `761A00-11330C00/A` | `no_data` | El modelo existe, pero la tabla dice N/A. Sugiere el mismo modelo con otra alimentación (`761A00-11300000/A`, `761A00-11320000/A`) y el menor de 3 fases con datos (`763A00-11330C00/A`) |
| `761800-11300000/A` | `not_found` | Sugiere `761B00-11300000/A`, sin cambiarlo solo |
| Nada | `invalid` | Que no se dio ningún número |

**Qué responde `recommend_actuators`:**

| Situación | `status` | Qué recibe el agente |
|---|---|---|
| Hay modelos que cumplen | `matches` | Solo esos, primero el más ajustado, y bajo qué condición cumple cada uno |
| Ninguno cumple | `no_matches` | Instrucción de decirlo primero, y los 3 más cercanos con cada diferencia |
| No dio requisitos | `needs_requirements` | Que debe preguntarlos |

| Decisión | Por qué | Descartado |
|---|---|---|
| Tools fijas, el LLM nunca escribe SQL | Una condición mal escrita daría un dato equivocado que parece correcto | SQL generado por el LLM: más flexible, pero menos fiable |
| Evaluar los requisitos en Python sobre filas leídas con SQL fijo | Una sola función decide si un modelo cumple y explica por qué no; con 68 modelos el rendimiento no importa | Filtrar con `WHERE` y explicar los rechazos aparte: dos lógicas que podrían contradecirse |
| Mostrar solo los que cumplen si hay alguno | Lo pedido primero; alternativas solo si hacen falta | Mezclar alternativas con los que cumplen |
| Primero el modelo más ajustado | Un actuador mucho mayor suele ser innecesario | Primero el más potente |
| Hasta 5 modelos, indicando el total | Evita respuestas enormes que además gastan presupuesto | Devolver todos: pueden ser decenas |
| Si no dice modo o frecuencia, mostrar e indicar la condición | `763A00-11300000/A` tarda 25 s a 60 Hz y 31 s a 50 Hz; pedir "menos de 30 s" cumple solo a 60 Hz | Preguntar siempre antes de buscar |
| Si nada cumple, decirlo y sugerir el más cercano explicando las diferencias | El usuario sabe que no es lo pedido y aun así tiene una opción | Responder solo "no hay ninguno" |
| Nunca sugerir Weatherproof si piden Explosionproof | Ese requisito suele existir por riesgo de explosión | Tratarlo como cualquier otra diferencia |
| Entre alternativas, pesa más lo que no se puede cambiar, y el voltaje por encima de todo | Una planta tolera 1 s más, pero no cambia su voltaje | Contar todas las diferencias igual: ponía un modelo de 220 V junto a uno de 110 V |
| Comparar el torque en la columna de la unidad pedida | El PDF redondea: 880 in-lbs figura como 100 Nm, y 100 Nm son unos 885 in-lbs. Convertir descartaría un modelo que sí cumple | Convertir todo a una unidad |
| Convertir solo lo que el PDF no trae, con código | 1 ft-lb son exactamente 12 in-lbs. El LLM no debe calcular números | Dejar la conversión al LLM |
| Exigir la unidad si dan un torque | "500" sin unidad puede ser 500 Nm o 500 in-lbs, una diferencia de casi 9 veces | Suponer una unidad |
| Las tablas de 3 fases se guardan con servicio "sin especificar" | El PDF da un solo torque y no dice a qué modo aplica | Copiarlo a On/Off y Modulating: afirma algo que el PDF no dice |
| Mostrarlas al filtrar por modo, con un aviso | Si no, ningún modelo de 3 fases aparecería al pedir un modo | Buscar solo la etiqueta exacta |
| Un part number inexistente se trata como inexistente | `761A00-11380000/A`, el ejemplo del summary, no está en las tablas | Corregirlo solo |

Texto del aviso de 3 fases: "Encontré `763B00-11330C00/A`, de 500 Nm. Ojo: la tabla no indica si ese valor aplica a Modulating."

**Errores que encontraron las pruebas a mano y ya están corregidos, cada uno con su test:**

| Entrada | Qué pasaba | Ahora |
|---|---|---|
| `frequency_hz=40` | El programa fallaba | Responde que las tablas solo tienen 50 y 60 Hz |
| `min_torque=100000 torque_unit=ft_lbs` | Comparaba 100 000 con 79 700 sin aclarar que el segundo está en in-lbs | Indica la unidad de cada valor |
| `min_cycles_per_hour=1000` | La alternativa decía "actual: None" porque usaba Modulating, que no tiene ciclos | Sugiere el modelo con más ciclos, 350 en `761X30-11380000/A` |
| `761` | Decía que no existía | Lista el grupo: 14 modelos |
| `voltage_v=24 current_type=AC service=modulating` | Sugería modelos de 110 V y 220 V, sin mostrar los de 24 V | Primero conserva el voltaje: sugiere `761X30-11370000/A`, de 24 V DC |

**Límite conocido:** el orden de las alternativas es una regla razonable, no una verdad de ingeniería. Cuál sirve realmente depende de la planta, y por eso cada alternativa muestra sus diferencias.

### Agente y API (Fase 3)

**Cómo se arma cada turno:** el LLM no recuerda nada entre una pregunta y otra. En cada turno, el backend le envía la conversación guardada en Postgres. Al texto de cada respuesta anterior, el código le agrega los part numbers que se consultaron:

```
Usuario: ¿Cuánto torque da el 2A a 110 V?
Agente:  El 2A da 150 Nm en On/Off.  [Modelos consultados: 762A00-11300000/A]
Usuario: ¿y cuánta potencia consume?
→ el agente vuelve a consultar 762A00-11300000/A y obtiene 40 W de la base
```

| Decisión | Por qué | Descartado |
|---|---|---|
| Elegir el modelo comparando 3 candidatos con preguntas de prueba | El más barato puede fallar al llamar tools, y eso no se ve en una tabla de precios | Elegir solo por precio u opinión |
| En los seguimientos, volver a consultar la tool | Cada número sale de la base en el turno en que se muestra, y aparece en el debug de ese turno | Guardar en el historial los datos de turnos anteriores: más tokens y números viejos que no aparecen en el debug |
| Agregar al historial los part numbers consultados, escritos por el código | El LLM sabe el modelo exacto aunque la respuesta haya dicho "el 2A", que son 3 modelos | Solo el texto: el LLM podría consultar el modelo equivocado o volver a preguntar |
| Verificar con código los números de la respuesta | Las instrucciones al LLM no son una garantía. Un número que no aparece en lo que devolvieron las tools queda marcado en el debug | No revisar; o reintentar solo, que gasta presupuesto en falsos positivos como "te muestro 3 modelos" |
| `products` sale de la salida de las tools | La app muestra números que salieron de la base, no del texto del LLM | Pedirle al LLM que arme la lista |
| Cada producto tiene siempre los mismos campos (modelo `Product`), completados con la ficha del modelo en la base | Las tools no cambian: cada una le da al LLM lo que necesita (una ficha completa, o resúmenes cortos si `761A00` nombra 3 modelos). Pero la app recibe siempre lo mismo, venga de la tool que venga: con `761A00` puede comparar el torque de las 3 opciones aunque el LLM solo vio resúmenes. Y `/docs` muestra cada campo | Dejar `products` como diccionarios libres: la app tendría que adivinar qué campos vienen según la tool, y un cambio de nombre en `catalog.py` la rompería sin que fallara ningún test del backend; o hacer que todas las tools devuelvan fichas completas, que llena el contexto del LLM con datos que no pidió |
| `focus`: el servicio y la frecuencia de la pregunta, sacados por código de los argumentos de la última llamada que funcionó a `get_actuator_specs` o `recommend_actuators` | La tabla de la app abre en lo que pediste: si pediste Modulating, no abre en On/Off. Se calcula del `debug` guardado, así que el historial también lo tiene sin cambiar la base | Que la app lea el `debug` o el texto de la respuesta; o guardarlo en una columna nueva, que obliga a migrar la base |
| Los mensajes guardados antes de `Product` se completan al leerlos | Las conversaciones viejas se siguen abriendo en la app | Migrar la base o borrar las conversaciones viejas |
| `debug` siempre en la respuesta; la app lo oculta | No contiene datos sensibles, y el historial también lo necesita | Activarlo con un parámetro: más complejidad sin beneficio, porque no hay login |
| El backend crea las tablas y carga los datos al arrancar | Quien evalúa solo corre `docker compose up` | Pedir que corran `ingest.py` a mano |
| Si la base no está, el backend arranca igual y reintenta en segundo plano (cada 2, 4, 8… hasta 30 s); mientras tanto responde 503 | La app recibe un 503 con un mensaje claro y se recupera sola cuando vuelve la base. Antes, el backend se caía a los 30 s y Docker lo reiniciaba en bucle: se vieron 102 reinicios con la base detenida | Caerse y dejar que Docker lo reinicie: ruido en `docker compose ps` y la API sin responder nada; o esperar sin límite antes de arrancar, que deja la API sin responder (conexión rechazada en vez de 503) |
| `/health` responde 503 si la base no está o los datos no se cargaron | Docker marca el contenedor `unhealthy`, que es lo que pasa de verdad, sin reiniciarlo | Responder 200 siempre: `docker compose up --wait` creería que todo está bien |
| Un turno se guarda completo o no se guarda | Si el LLM falla, no quedan preguntas sin respuesta ni conversaciones vacías | Guardar la pregunta antes de responder |
| `needs_clarification` lo decide el código, con la última llamada a cada tool | Es `true` si esa llamada respondió `ambiguous`, `not_found`, `needs_requirements` o rechazó un argumento. Si el LLM corrige un argumento en el mismo turno, la llamada fallida ya no cuenta | Pedirle al LLM que lo indique; o contar cualquier llamada, que marcaba aclaración aunque el agente ya se hubiera corregido |
| Un límite de 12 pasos por turno | Un modelo confundido no puede llamar tools sin fin y gastar presupuesto | Sin límite |
| Validar la pregunta antes de revisar la clave, quitando los espacios | Una pregunta vacía o de solo espacios es un error del cliente (422), y no debe gastar presupuesto | Revisar la clave primero, o aceptar "   ": los dos llegaban más lejos de lo debido |

**Qué hace cada archivo:**

| Archivo | Qué hace |
|---|---|
| `backend/app/api.py` | Los endpoints. Al arrancar crea las tablas y carga los datos; si la base no está, reintenta en segundo plano y responde 503 mientras tanto |
| `backend/app/products.py` | El modelo `Product`: le da a cada producto los mismos campos, desde la base, con su rol en la respuesta |
| `backend/app/agent.py` | Las instrucciones del LLM, el historial con los part numbers, `products`, `needs_clarification` y el debug |
| `backend/app/numbers.py` | El verificador de números. Entiende "2,3" y "2.3", y "4,800" y "4.800" |
| `backend/app/conversations.py` | Guarda y lee las conversaciones; un turno se guarda en una sola transacción |
| `backend/eval_agent.py` | Corre las mismas 14 preguntas con varios modelos y mide el costo real |
| `backend/tests/fake_llm.py` | Un LLM falso que repite respuestas escritas en el test, para probar sin gastar |

**El verificador de números, con ejemplos:**

| Respuesta | Lo que devolvió la tool | Resultado |
|---|---|---|
| "Consume 40 W" | `motor_power_w: 40` | Verificado |
| "Consume 2,3 A" | `fla_a: 2.3` | Verificado |
| "Te muestro 3 modelos" | Nada con 3 | Se ignora: los números enteros hasta 10 suelen ser cantidades |
| "Gira 90 grados en 18 s" | `speed_sec: 18` | Verificado: el 90 está en las instrucciones del agente, que también cuentan como fuente |
| "Consume 45 W" | `motor_power_w: 40` | **Marcado** en `debug.unverified_numbers` |

**Problemas que encontró una revisión externa, ya corregidos y con test:** un argumento corregido en el mismo turno seguía marcando `needs_clarification`; el verificador marcaba los 90 grados del giro; y una pregunta de solo espacios llegaba al LLM. También faltaba un test del seguimiento cuando el turno anterior mostró varios modelos, que funcionaba bien.

### Elección del modelo

**Elegido: `anthropic/claude-haiku-5.5`.** Se comparó con otros dos candidatos de distintos precios usando `eval_agent.py`, que hace las mismas 14 preguntas a cada modelo. Cada pregunta se califica con código a partir de lo que devolvieron las tools, no leyendo la respuesta.

**Resultado de la corrida final** (`LLM_MAX_TOKENS=3000`):

| Modelo | Aprobadas | Números que no salen de las tools | Tiempo típico por pregunta | Costo por pregunta |
|---|---|---|---|---|
| **`anthropic/claude-haiku-5.5`** | **14/14** | **0** | **3.2 s** | **USD 0.0007** |
| `openai/gpt-5-mini` | 14/14 | 0 | 13.0 s | USD 0.0022 |
| `qwen/qwen3.7-flash` | 13/14 | 0 | 7.6 s | USD 0.0001 |

| Decisión | Por qué | Descartado |
|---|---|---|
| Claude Haiku 5.5 | Aprobó todo en las dos corridas, fue el más rápido y con USD 10 alcanza para más de 10 000 preguntas | GPT-5 mini: igual de preciso en la corrida final, pero 4 veces más lento y 3 veces más caro, y la app es un chat móvil. Qwen: el más barato, pero en un seguimiento buscó por el alias "2A" en vez del part number exacto, y en la primera corrida convirtió unidades por su cuenta |
| Criterios definidos antes de correr | Evita elegir el ganador y después justificarlo | Decidir mirando las respuestas |
| `LLM_MAX_TOKENS=3000` | GPT-5 mini y Qwen razonan antes de responder y gastan tokens en eso. Con 1000, algunas respuestas salían vacías | Mantener 1000 |

**Qué enseñó la primera corrida** (con 1000 tokens), corregido antes de la final:

| Problema | Ejemplo | Arreglo |
|---|---|---|
| Respuestas vacías o cortadas | Qwen gastó 928 de 1000 tokens razonando | Límite de 3000, y `debug.finish_reason` indica si una respuesta se cortó |
| El marcador interno aparecía en las respuestas | Los 3 modelos copiaban `[Part numbers consulted: …]`; Haiku en 9 de 14 | El código lo quita, y `debug.marker_removed` lo registra |
| Respuestas fuera de tema | Haiku respondió "Paris" antes de redirigir | Las instrucciones le dicen que no responda |
| Mi script aprobaba respuestas vacías | Revisaba los productos, no el texto | Una respuesta vacía o cortada ahora reprueba |
| Conversión de unidades por su cuenta | Qwen escribió 73.3 ft-lb, que no está en la tabla | Ninguno: el verificador lo marcó, que es justo para lo que existe |

**Límites:** son 14 preguntas, una corrida por modelo. Alcanza para elegir entre tres candidatos, no es un estudio estadístico. Las dos corridas costaron USD 0.11 en total y están en `backend/eval/`.

**Un detalle de transparencia:** el asistente con el que se construyó el proyecto también es un modelo de Anthropic. Por eso los criterios se fijaron antes de correr la comparación, y cada pregunta se califica con código.

### App Android (Fase 4a: base y lista de conversaciones)

**Cómo fluye un dato:** al abrir la app, `ConversationsViewModel` pone el estado en "cargando" y le pide la lista al repositorio. El repositorio llama a `GET /api/sessions` con Retrofit y traduce cualquier falla a un `AppError`: sin conexión, 503, 404 u otro código. La pantalla solo dibuja el estado que recibe; por eso los ViewModels se prueban sin emulador.

```
Pantalla ──> ViewModel ──> ConversationRepository ──> Retrofit ──> backend
   ▲             │ estado: sessions / loading / error
   └─────────────┘
```

| Decisión | Por qué | Descartado |
|---|---|---|
| Una Activity, Compose y Navigation Compose con rutas tipadas | Pasar el `session_id` al chat es un parámetro de la ruta, revisado al compilar | Varias Activities: datos por `Intent` y más código |
| MVVM: ViewModel con un estado y una pantalla que solo lo dibuja | Los estados (cargando, vacío, error) se prueban sin emulador | Clean Architecture con casos de uso: capas de más para 3 pantallas |
| Retrofit, OkHttp y kotlinx.serialization | Es el estándar en Android y se lee fácil | Ktor client: también sirve, pero es menos común en Android |
| Inyección manual con `AppContainer` | Crea el cliente una vez; sin plugins ni anotaciones que puedan fallar al compilar en otra máquina | Hilt |
| El historial vive solo en el backend | Una sola fuente de verdad; el enunciado no pide modo sin conexión | Room: dos copias que habría que sincronizar |
| El repositorio traduce errores a `AppError` | Las pantallas no saben de HTTP: "sin conexión" y "503" son mensajes distintos para el usuario | Mostrar el mensaje de la excepción: textos técnicos en pantalla |
| Si la lista ya estaba cargada, un error aparece arriba sin borrarla | El usuario no pierde lo que ya veía cuando el backend se cae | Reemplazar la lista por la pantalla de error |
| Un 404 en el chat no ofrece "Retry" | Reintentar no puede revivir una conversación borrada; la salida es volver | El mismo botón para todos los errores |
| URL del backend en `BuildConfig`, `http://10.0.2.2:8000` por defecto, cambiable con `-PbackendUrl=` | El emulador ve el computador en 10.0.2.2; un celular necesita otra IP sin tocar el código | Escribirla fija en el código |
| HTTP sin cifrar: en debug a cualquier host, en release solo a 10.0.2.2 y localhost | El backend local no tiene HTTPS, y un celular en la red local usa una IP como 192.168.1.50 | `usesCleartextTraffic="true"` para todo, también en release |
| Pedir el permiso `ACCESS_LOCAL_NETWORK` en Android 17, con una pantalla que explica para qué | Sin él, Android 17 bloquea las conexiones de la app a IPs privadas como 10.0.2.2. La conexión no falla: se queda esperando hasta agotar el tiempo, y la app solo diría "no hay conexión" | Bajar `targetSdk` a 36 para esquivar la regla: evita el diálogo, pero es esconder el problema |
| No pedir ese permiso si la URL es `localhost` (con `adb reverse`) | localhost no es la red local | Pedirlo siempre |
| Textos de la app en inglés, en `strings.xml` | Konecto vende en Norteamérica y el agente responde en inglés | App en español: mezclaría idiomas con las respuestas |
| Versiones: plugin de Android 9.5.1 y Gradle 9.6.1, las de este Android Studio; Gradle Wrapper con checksum | Quien clona compila con `./gradlew` y la misma versión, sin instalar Gradle | Sin wrapper: cada uno compilaría con su versión |
| Un test lee una respuesta real del backend guardada en `src/test/resources` | Si el backend cambia un nombre de campo, falla un test en vez de quedar una celda vacía en la app | Probar solo con datos inventados |

**Cómo se encontró lo del permiso:** la app mostraba "Can't reach the server" con el backend arriba. Desde la consola del emulador `10.0.2.2:8000` respondía, pero con el usuario de la app (`run-as`) la conexión se quedaba esperando. Apagar el Wi-Fi del emulador no cambió nada; otorgar `ACCESS_LOCAL_NETWORK` lo resolvió.

**Qué hace cada archivo** (dentro de `android/app/src/main/java/com/series76/assistant/`, salvo los dos primeros):

| Archivo | Qué hace |
|---|---|
| `android/app/build.gradle.kts` | Versiones, dependencias y la URL del backend (`backendUrl`) |
| `res/xml/network_security_config.xml` | Dónde se permite HTTP sin cifrar (más abierto en `src/debug`) |
| `data/Dtos.kt` | Las mismas respuestas del backend en Kotlin, incluido `Product` |
| `data/ConversationRepository.kt` | Llama al backend y traduce errores a `AppError` |
| `AppContainer.kt` | Crea Retrofit y el repositorio una sola vez |
| `ui/conversations/` | La lista de conversaciones y su ViewModel |
| `ui/chat/` | Por ahora, el historial de una conversación; en la 4b, el chat completo |
| `ui/common/LocalNetworkGate.kt` | Pide el permiso de red local en Android 17 antes de mostrar la app |

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
