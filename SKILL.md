---
name: anonimizar
description: >
  Anonimiza o restaura datos personales (PII) en archivos CSV, XLSX, MD y DOCX.
  Por defecto aplica todas las jurisdicciones simultáneamente (máxima cobertura).
  El usuario puede restringir a una jurisdicción concreta en lenguaje natural.
  Solo invocar con /anonimizar — no activar de forma automática.
user-invokable: true
argument-hint: "[restaurar] [ruta-archivo-o-carpeta] [para <jurisdicción>]"
license: MIT
metadata:
  author: PubliUp SEO
  version: "2.3.0"
  category: privacy
---

# Anonimizador multi-jurisdiccional

Detecta y reemplaza datos personales identificables (PII) en documentos con
tokens numerados (`<PERSONA-1>`, `<EMAIL-2>`, `<DNI-ES-1>`, etc.), generando
un mapa `.key.json` que permite restaurar los valores originales en cualquier
momento.

---

## Modos de uso

### Anonimizar

```
/anonimizar clientes.csv
/anonimizar C:/exports/
/anonimizar informe.docx para rgpd
/anonimizar datos.xlsx solo para Chile
/anonimizar clientes.csv para LGPD Brasil
```

### Restaurar

```
/anonimizar restaurar clientes_anon.csv
/anonimizar restaurar C:/anon/informe_anon.docx
/anonimizar restaurar C:/anon/                 (carpeta completa)
/anonimizar restaurar resultado_ia.docx        (archivo devuelto por una IA)
```

Flujo completo previsto: **anonimizar → procesar el `_anon` con una IA → restaurar el resultado**.
La restauración funciona sobre cualquier archivo que conserve los tokens, aunque
la IA lo haya devuelto con otro nombre (ver resolución del mapa más abajo).

---

## Interpretación de la instrucción del usuario

### Paso 1 — Detectar modo

Si la instrucción contiene "restaurar", "desanonimizar", "revertir" o similar → **modo restauración**.
En cualquier otro caso → **modo anonimización**.

### Paso 2 — Extraer ruta

Identificar la ruta del archivo o carpeta en el texto del usuario.
Si no hay ruta, preguntar: "¿Qué archivo o carpeta quieres procesar?"

### Paso 3 — Determinar jurisdicción (solo anonimización)

Leer el texto del usuario buscando menciones de jurisdicción:

| Si el usuario menciona...                        | Usar flag          |
|--------------------------------------------------|--------------------|
| "rgpd", "gdpr", "españa", "ue", "europa"         | `--ley rgpd`       |
| "chile", "rut", "ley 21.719"                     | `--ley chile`      |
| "brasil", "brazil", "lgpd", "cpf"               | `--ley brasil`     |
| "mexico", "méxico", "curp", "lfpdppp"            | `--ley mexico`     |
| "colombia", "nit", "ley 1581"                    | `--ley colombia`   |
| "argentina", "cuit", "ley 25.326"               | `--ley argentina`  |
| "uk", "reino unido", "nino", "dpa"               | `--ley uk`         |
| "california", "ccpa", "cpra", "ssn"              | `--ley ccpa`       |
| Sin mención de jurisdicción                      | `--ley todo`       |

**Default siempre es `--ley todo`.** Solo restringir si el usuario lo indica.

---

## Ejecución

Script: `anonimizar.py`. Ubicación de referencia:
`D:\OneDrive\Escritorio\Yo\Papitas SEO\anonimizador_rgpd\anonimizar.py`.
Si no está ahí, localizarlo (`anonimizar.py` en el proyecto) o clonar
`github.com/uhartharper/anonimizador-datos`. Ejecutar desde su carpeta con `py`/`python`.

### Anonimización

```bash
# Default — todas las jurisdicciones
py anonimizar.py [ruta] --ley todo

# Con jurisdicción específica detectada del texto
py anonimizar.py [ruta] --ley rgpd
py anonimizar.py [ruta] --ley chile brasil

# Cifrar el mapa (opcional): protege la PII del .key.json con una clave
py anonimizar.py [ruta] --cifrar-mapa --clave "<clave>"
```

Genera dos archivos por cada entrada:
- `[nombre]_anon.[ext]` — archivo con tokens, sin PII
- `[nombre]_anon.[ext].key.json` — mapa `{token → valor original}` (cifrado si se usó `--cifrar-mapa`)

Tras anonimizar el script imprime un **reporte de cobertura** (tipos detectados + conteo),
crea un `.gitignore` con `*.key.json` y avisa si el mapa cae en una carpeta sincronizada.

### Restauración

```bash
# Un archivo
py anonimizar.py [ruta_anon] --restaurar

# Una carpeta (procesa primer nivel; ignora .key.json y *_restaurado previos)
py anonimizar.py [carpeta] --restaurar

# Mapa explícito (necesario si hay varios .key.json en la carpeta)
py anonimizar.py [archivo] --restaurar --mapa [ruta.key.json]

# Mapa cifrado: aportar la misma clave usada al anonimizar
py anonimizar.py [archivo] --restaurar --clave "<clave>"
```

No carga modelos NLP — es inmediato. Genera `[nombre]_restaurado.[ext]`.
Tras restaurar, el script **avisa de tokens del mapa que no aparecían** en el archivo
(no restaurados, p.ej. alterados por la IA) y de tokens residuales sin mapear.

**Resolución del mapa `.key.json`** (en este orden):
1. `--mapa` explícito → se aplica a todas las entradas.
2. `[archivo].key.json` con nombre exacto, junto al archivo (caso anonimización directa).
3. Si en la carpeta hay un único `.key.json`, se usa ese — esto cubre el caso de
   un archivo devuelto por una IA con nombre distinto pero situado junto a su mapa.
4. Si hay varios `.key.json` y ninguno coincide por nombre → error pidiendo `--mapa`
   (para no mezclar tokens de archivos distintos: `<PERSONA-1>` no significa lo mismo
   en dos mapas diferentes).

Requisito: el archivo a restaurar debe **conservar los tokens** (`<PERSONA-1>`, etc.).
Si la IA los borró o alteró, esos valores no se recuperan.

---

## Verificar entorno antes de ejecutar

```bash
py anonimizar.py --lista-leyes
```

Si falla con `ModuleNotFoundError`:
```bash
pip install -r requirements.txt
python -m spacy download es_core_news_lg   # mínimo requerido
python -m spacy download en_core_web_lg    # para uk / ccpa
python -m spacy download pt_core_news_lg   # para brasil
```

La restauración no requiere modelos instalados.

---

## Qué reportar al usuario

**Tras anonimizar:**
- Archivos generados (ruta del `_anon` y del `.key.json`)
- Advertencia: el `.key.json` contiene PII — protegerlo con el mismo nivel de acceso que el original

**Tras restaurar:**
- Archivo generado (ruta del `_restaurado`)
- Número de tokens reemplazados (viene en la salida del script)

---

## Formatos soportados

| Extensión | Comportamiento                                                        |
|-----------|-----------------------------------------------------------------------|
| `.csv`    | Todas las celdas. Detecta exports Screaming Frog: solo texto libre.   |
| `.xlsx`   | Todas las hojas, celda a celda.                                       |
| `.md`     | Línea a línea; preserva formato Markdown.                             |
| `.docx`   | Párrafo por run; preserva estilos (negrita, cursiva, etc.).           |

---

## Tokens generados

Numerados por tipo, reutilizados si el mismo valor aparece varias veces:

`<PERSONA-1>` `<EMAIL-1>` `<TELEFONO-1>` `<DIRECCION-1>` `<DNI-ES-1>` `<RUT-CL-1>`
`<CPF-BR-1>` `<CURP-MX-1>` `<NIT-CO-1>` `<CUIT-AR-1>` `<NINO-UK-1>` `<SSN-US-1>`

---

## Limitaciones conocidas

- **Precisión NER:** spaCy puede generar falsos positivos en nombres comunes (saludos, títulos). El script filtra los más frecuentes en español.
- **Ubicaciones según contexto:** una ubicación solo se anonimiza si hay una persona cerca. En texto libre (.md, .docx), "cerca" es ≤120 caracteres en la misma línea/párrafo. En tablas (.csv, .xlsx) el contexto es la **fila**: si cualquier celda de la fila tiene un nombre, las ubicaciones de las demás columnas también se anonimizan; una tabla sin personas deja las ubicaciones intactas. Los exports de Screaming Frog se tratan como texto libre por celda.
- **Cédula colombiana:** se detecta solo con contexto previo (`C.C.`, `cédula`, `documento`).
- **DNI argentino sin puntos:** score 0,55 — revisar salida si hay códigos numéricos en el archivo.
- **CPF brasileño sin formato:** score 0,60 — usar formato con puntos y guiones si es posible.
- **Textos cortos (<4 palabras):** detección de idioma no fiable; usa el modelo por defecto.
- **Direcciones:** cubre vías hispanas comunes (Calle, Avenida, Plaza...) + número. Formatos atípicos o no hispanos pueden escaparse.
- **`.docx`:** procesa cuerpo, tablas, encabezados, pies y cuadros de texto (a nivel de párrafo, capta nombres partidos en runs). **No** procesa notas al pie ni comentarios.
- **`--ley todo`:** máxima cobertura pero más falsos positivos en códigos numéricos (SKUs, IDs). El script avisa con 4+ jurisdicciones; restringir si el archivo tiene muchos números.
