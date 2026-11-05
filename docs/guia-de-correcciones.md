# Cómo llenar `corrections.json` y `spec.py`

**Hoy no hay que llenar nada: los dos archivos ya están completos.** Esta guía sirve si Docling lee algo distinto, si encuentras un error o si te preguntan cómo funcionan.

| Archivo | Qué contiene | Cuándo se toca |
|---|---|---|
| `backend/data/corrections.json` | Números que Docling leyó mal | Cuando `build.py` reporta un valor inválido, o el PDF contradice un dato |
| `backend/ingestion/spec.py` | Cómo son las 7 tablas | Casi nunca: si el PDF cambia o un dato de la estructura está mal |

La regla de siempre: **primero se mira el PDF.** Nunca se corrige un dato solo porque Gemini o una regla lo señalan.

## `corrections.json`

Es una lista en la que cada entrada corrige una celda.

### Ejemplo paso a paso

**1. Corres la reconstrucción desde `backend/`:**

```bash
uv run python ingest.py --build
```

**2. Te sale un problema:**

```
763C00-11300000/A.speed_60: '£3' is not a valid value
```

El mensaje dice el part number, el campo y lo que leyó Docling.

**3. Miras la celda en el PDF.** En la página 1, tabla de 110 V, la fila de `763C00` muestra 33 en "Operating Speed", columna 60 Hz.

**4. Agregas una entrada a la lista:**

```json
{
  "part_number": "763C00-11300000/A",
  "field": "speed_60",
  "read": "£3",
  "value": 33,
  "reason": "Docling misread the digit. PDF page 1, Weatherproof 110V table, shows 33."
}
```

| Campo | Qué poner | De dónde sale |
|---|---|---|
| `part_number` | El número completo, sin `*` | Del mensaje |
| `field` | El nombre de la columna | Del mensaje |
| `read` | Lo que leyó Docling, exacto. Si estaba vacío, `""` | Del mensaje |
| `value` | El valor real, como número | **Del PDF** |
| `reason` | Por qué cambia y dónde se comprobó | Lo escribes tú |

**5. Vuelves a correr `--build`.** Si no hay más problemas, se crea `actuators.json`. Después corre los tests y carga los datos, como indica la [guía de comandos](guia-de-comandos.md).

### Si encuentras un número válido pero equivocado

El código no lo reporta, así que no hay mensaje del cual copiar. Busca el campo en la tabla de abajo y el valor de `read` en `raw/docling_tables.json`. El valor debe ser exactamente el que aparece ahí, por ejemplo `"4,800"` con su coma.

### Nombres de los campos

El nombre depende del tipo de tabla.

**Tablas de 110 V y 220 V de 1 fase:**

| Columna del PDF | Campo |
|---|---|
| On/Off Output Torque, In-Lbs. / Nm | `on_off_in_lbs` / `on_off_nm` |
| On/Off Duty Cycle | `on_off_duty` |
| Cycles Per Hour | `on_off_cycles` |
| Modulating Output Torque, In-Lbs. / Nm | `mod_in_lbs` / `mod_nm` |
| Modulating Duty Cycle | `mod_duty` |
| Starts Per Hour | `mod_starts` |
| Operating Speed, 60 Hz / 50 Hz | `speed_60` / `speed_50` |
| Full Load Current, 60 Hz / 50 Hz | `fla_60` / `fla_50` |
| Locked Rotor Current, 60 Hz / 50 Hz | `lra_60` / `lra_50` |

**Tabla de 3 fases:** `in_lbs`, `nm`, `duty`, `cycles`, `starts`, y los mismos seis de velocidad y corriente.

**Tablas de 24 V:** `in_lbs`, `nm`, `duty`, `speed`, `fla`, `lra`, y además `cycles` en On/Off o `starts` en Modulating.

**La potencia no va aquí:** se corrige en `spec.py`.

### Qué pasa si te equivocas

Probé cada caso:

| Error | Qué pasa |
|---|---|
| `read` no coincide con lo que leyó Docling | Se detiene: `correction expects '33', Docling read '£3'` |
| `field` equivocado | Se detiene y sigue marcando la celda original |
| `part_number` incompleto | Se detiene: `correction for ... was not used` |
| `value` imposible, como velocidad 99 | Se detiene: `60 Hz is slower than 50 Hz` |
| **`value` creíble pero falso, como 34** | **No se detecta.** Se guarda 34 |

El último caso es la razón para copiar `value` del PDF y no de memoria. Solo la auditoría o un test podrían señalarlo después.

## `spec.py`

Describe las 7 tablas del PDF, porque hay datos que no conviene dejar en manos del OCR. Cada tabla es un `TableSpec`, y estos son sus campos con el ejemplo de la tabla de 110 V de la página 1:

```python
TableSpec(
    index=0, page=1, title="110V - Single Phase Power", enclosure="weatherproof",
    voltage_v=110, phases=1, current_type="AC", code="11300000", layout=TWO_SERVICES,
    power_groups=_WEATHERPROOF_GROUPS,
)
```

| Campo | Qué es | Cómo se llena | Ejemplo |
|---|---|---|---|
| `index` | Posición de la tabla en el orden de Docling | Contar desde 0 | `0` |
| `page` | Página del PDF | Mirar el PDF | `1` |
| `title` | Título sobre la tabla | Copiarlo exacto | `"110V - Single Phase Power"` |
| `enclosure` | Tipo de carcasa | Título rojo de la página | `"weatherproof"` |
| `voltage_v` | Voltaje | Del título | `110` |
| `phases` | Fases | Del título: "Single" es 1 | `1` |
| `current_type` | Tipo de corriente | Del título: `"AC"`, `"DC"` o `"AC/DC"` | `"AC"` |
| `code` | Parte central del part number | Lo que va después del guion | `"11300000"` |
| `layout` | Orden de las columnas | Según las columnas de la tabla | `TWO_SERVICES` |
| `power_groups` | Qué modelos tienen cada potencia | Ver abajo | `(15, ("1A", "1B"))` |
| `no_data` | Modelos con N/A | Filas que dicen N/A | `("1A", "1B", "2A", "2B")` en 3 fases |

El part number de cada fila se arma solo a partir de estos datos: `76` + alias + `00` (Weatherproof) o `30` (Explosionproof) + `-` + `code` + `/A`. Por ejemplo, `1A` en esta tabla da `761A00-11300000/A`.

### Cómo llenar `power_groups`

Esta es la parte que suele costar más. El alias son los dos caracteres que el PDF resalta en negrita: 76**1A**00 es `1A`.

**1. Mira en el PDF la columna "Motor Power".** Cada valor ocupa un bloque de filas.

**2. Fíjate en las líneas horizontales de esa columna.** Separan un bloque del siguiente.

**3. Escribe cada bloque: la potencia y los alias de sus filas.**

```
Modelo   | Motor Power
761A     |
761B     |    15        ->  (15, ("1A", "1B")),
---------+-----------
762A     |
762B     |    40        ->  (40, ("2A", "2B", "3A")),
763A     |
---------+-----------
763B     |
763C     |    90        ->  (90, ("3B", "3C")),
---------+-----------
764A     |
764B     |
765A     |   180        ->  (180, ("4A", "4B", "5A", "5B")),
765B     |
```

**Pista:** el valor queda centrado en su bloque, así que sirve para comprobar que contaste bien. Si cae entre dos filas, el bloque tiene un número par de filas.

Los modelos con N/A no van en `power_groups`, sino en `no_data`, porque no tienen potencia.

### Qué pasa si te equivocas

Probé cada caso:

| Error | Qué pasa |
|---|---|
| Falta un alias | Se detiene: `unexpected part number 761B00-11300000/A` |
| Un modelo en el grupo equivocado, en una fila donde Docling leyó el valor | Se detiene: `Docling read 40 W, declared 15 W` |
| **Un modelo en el grupo equivocado, en una fila donde Docling dejó vacío** | **No se detecta.** Se guarda la potencia errónea |

El último caso importa: el código no lo ve porque no tiene contra qué comparar. Lo detectaría la auditoría, porque Gemini lee la potencia de cada fila, siempre que Gemini la lea bien.

## Después de cualquier cambio

Desde `backend/`:

```bash
uv run python ingest.py --build
```

```bash
uv run pytest
```

```bash
uv run python ingest.py
```

Y revisa con `git diff data/processed/actuators.json` que solo cambió lo que querías, una vez que los datos estén commiteados.
