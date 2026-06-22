# Multi-Jurisdiction PII Anonymizer

A Python tool for detecting and replacing personally identifiable information (PII)
in CSV, XLSX, Markdown, and DOCX files — with jurisdiction-specific rules for 8
data protection frameworks.

Built for SEO agencies, data analysts, and consultants who share client data with
AI tools and need a clean, auditable anonymization step before exporting files.

- **Jurisdictions**: RGPD/GDPR (EU), Ley 21.719 (Chile), LGPD (Brazil), LFPDPPP (Mexico), Ley 1581 (Colombia), Ley 25.326 (Argentina), UK GDPR, CCPA/CPRA (California)
- **Formats**: `.csv`, `.xlsx`, `.md`, `.docx`
- **NLP engine**: [spaCy](https://spacy.io/) + [Microsoft Presidio](https://microsoft.github.io/presidio/), multilingual, runs entirely local — no data leaves the machine
- **Screaming Frog aware**: auto-detects SF exports and only processes free-text columns
- **Reversible**: every anonymization run produces a `.key.json` map for full restoration

---

## How it works

### Anonymization

```
original.csv
     │
     ▼
python anonimizar.py original.csv --ley rgpd
     │
     ├── spaCy + Presidio scan every cell / paragraph / line
     │   and detect names, emails, IDs, phones, IBANs...
     │
     ├── Each unique value gets a numbered token
     │   "Juan García"       →  <PERSONA-1>
     │   "juan@mail.com"     →  <EMAIL-1>
     │   "12345678Z"         →  <DNI-ES-1>
     │   "Juan García" (2nd) →  <PERSONA-1>   ← same token reused
     │
     ├── original_anon.csv          ← file with tokens, no PII
     └── original_anon.csv.key.json ← map {token → original value}
```

### The full round-trip: anonymize → process with AI → restore

The intended workflow is to anonymize a file, hand the tokenized version to an
AI tool (which never sees the real data), and restore the tokens in whatever the
AI returns:

```
1. ANONYMIZE
   informe.docx  →  informe_anon.docx  +  informe_anon.docx.key.json

2. PROCESS WITH AI
   informe_anon.docx  →  [ChatGPT / Claude / ...]  →  result.docx
                         (the AI only ever sees tokens, never real PII)

3. RESTORE
   result.docx  →  result_restaurado.docx
                   (tokens replaced back with real values)
```

```bash
# Restore a single file (auto-locates the .key.json next to it)
python anonimizar.py informe_anon.docx --restaurar

# Restore an entire folder (first level; skips .key.json and *_restaurado files)
python anonimizar.py C:/anon/ --restaurar

# Restore an AI-returned file that was renamed — point to the original map
python anonimizar.py result.docx --restaurar --mapa informe_anon.docx.key.json
```

No NLP models are loaded during restoration — it starts in under a second.

**Map resolution order** for restoration:

1. `--mapa` explicit → applied to every input.
2. `[file].key.json` exact name match next to the file (direct anonymization case).
3. A single `.key.json` in the folder → used for any token-bearing file. This
   covers an AI-returned file with a different name placed next to its original map.
4. Multiple `.key.json` with no name match → error asking for `--mapa`, to avoid
   mixing tokens across files (`<PERSONA-1>` is not the same value in two maps).

> Restoration works on any file that still contains the tokens. If the AI deleted
> or altered a token, that value cannot be recovered. The result is the processed
> file with real values reinserted — not necessarily byte-identical to the source.

### The .key.json map

```json
{
  "version": "2.2",
  "ley": ["rgpd"],
  "fecha": "2026-06-21T10:00:00+00:00",
  "archivo_origen": "original.csv",
  "advertencia": "Este archivo contiene datos personales originales...",
  "mapa": {
    "<PERSONA-1>": "Juan García",
    "<EMAIL-1>": "juan@mail.com",
    "<DNI-ES-1>": "12345678Z"
  }
}
```

**The `.key.json` file contains the original PII in plaintext. Protect it with
the same access controls as the source file. If it is lost, restoration is
not possible.**

---

## Jurisdictions

### EU — RGPD / GDPR (Regulation 2016/679)

**Key:** `rgpd`

- **DNI** (8 digits + check letter): `12345678Z` → `<DNI-ES-N>`
- **NIE** (X/Y/Z + 7 digits + letter): `X1234567Z` → `<DNI-ES-N>`
- Spanish landlines and mobiles, including `+34` prefix
- Universal: names, emails, IBAN codes, credit cards, dates, IPs, locations near names

---

### Chile — Ley 21.719 / Ley 19.628

**Key:** `chile`

Ley 21.719 was published on 13 December 2024 and enters into full force on
1 December 2026, replacing Ley 19.628 entirely. Creates the APDP (Agencia de
Protección de Datos Personales) as an autonomous enforcement authority with powers
to investigate, fine (up to 20,000 UTM), and suspend processing. Expands sensitive
data categories (biometric, continuous geolocation, data of minors under 14) and
introduces a Data Protection Delegate requirement. Applies extraterritorially to
processing that affects people in Chile.

- **RUT/RUN** with dots: `12.345.678-9` → `<RUT-CL-N>`
- **RUT/RUN** without dots: `12345678-K` → `<RUT-CL-N>`
- Chilean mobiles (`9XXXXXXXX`) and landlines with `+56` prefix

---

### Brazil — LGPD (Lei 13.709/2018)

**Key:** `brasil`

In force since August 2020. Requires an explicit legal basis for each processing
activity. Applies to any organization processing data of people in Brazil,
regardless of where the organization is located. Supervisory authority: ANPD.

- **CPF** (individual taxpayer): `123.456.789-09` → `<CPF-BR-N>`
- **CNPJ** (legal entity): `12.345.678/0001-95` → `<CNPJ-BR-N>`
- Brazilian mobiles (9-digit with DDD) and landlines with `+55` prefix

---

### Mexico — LFPDPPP (2010)

**Key:** `mexico`

Original law enacted in 2010. A November 2024 constitutional reform eliminated
the INAI (the former data protection authority). A reformed LFPDPPP entered into
force on 21 March 2025, designating the SABG (Secretaría Anticorrupción y Buen
Gobierno) as the new supervisory authority. The 2025 reform adds obligations
around automated decision-making and AI — one of the first in Latin America to
do so directly in statute. Implementing regulations were under stakeholder
consultation as of early 2026. The public sector is governed by the separate
Ley General de Protección de Datos en Posesión de Sujetos Obligados (2017).

- **CURP** (18-char alphanumeric): `PELJ800101HDFRRN09` → `<CURP-MX-N>`
- **RFC** persona física (13 chars): `PELJ800101XX9` → `<RFC-MX-N>`
- **RFC** persona moral (12 chars): `ABC123456XX9` → `<RFC-MX-N>`
- Mexican phones with area code and `+52` prefix

---

### Colombia — Ley 1581/2012 + Decreto 1377/2013

**Key:** `colombia`

Supervisory authority: Superintendencia de Industria y Comercio (SIC).
The CC (cédula de ciudadanía) is only detected when preceded by `C.C.`,
`cédula`, or `documento` to avoid false positives from bare number sequences.

- **NIT** (9 digits + check digit): `123456789-1` → `<NIT-CO-N>`
- **CC** with context prefix: `C.C. 1234567890` → `<DNI-ES-N>`
- Colombian mobiles (3XX) and landlines with `+57` prefix

---

### Argentina — Ley 25.326 (2000)

**Key:** `argentina`

Supervisory authority: AAIP (Agencia de Acceso a la Información Pública).
Reform bill PIDIA was under parliamentary consideration as of June 2026 and
had not yet been enacted. DNI without dots has a lower confidence score (0.55)
due to high false-positive risk from bare number sequences.

- **DNI** with dots: `12.345.678` → `<DNI-AR-N>`
- **CUIT / CUIL**: `20-12345678-9` → `<CUIT-AR-N>`
- Argentine phones with area code and `+54` prefix

---

### UK — UK GDPR / DPA 2018 / DUAA 2025

**Key:** `uk`

The UK framework now comprises three instruments: UK GDPR (in force 1 January
2021), Data Protection Act 2018, and the Data (Use and Access) Act 2025 (DUAA),
which received Royal Assent on 19 June 2025 with its main provisions in force
from 5 February 2026. The DUAA introduced the first material divergences from
EU GDPR: analytics cookies exempt from consent, a recognised-legitimate-interests
schedule (no balancing test required), and a stop-the-clock mechanism for subject
access requests. Supervisory authority: ICO. The EU renewed the UK adequacy
decision until December 2031.

- **NINO** (National Insurance Number): `AB 12 34 56 C` → `<NINO-UK-N>`
- UK phones: `+44`, `0044`, or leading `0` formats

---

### California — CCPA / CPRA

**Key:** `ccpa`

CCPA (2018) extended by CPRA (in force January 2023). Applies to for-profit
businesses meeting any of: >$25M annual revenue; ≥100,000 consumers' data
processed; ≥50% revenue from selling data. Supervisory authority: CPPA.
New CPPA regulations approved September 2025 and in force since 1 January 2026:
neural data added as sensitive personal information; data of consumers under 16
automatically classified as sensitive; Global Privacy Control (GPC) signals must
be honoured as a valid opt-out from sale/sharing. California DL pattern
(`[A-Z]\d{7}`) has score 0.70 — review output manually if documents contain
unrelated alphanumeric codes.

- **SSN**: `123-45-6789` → `<SSN-US-N>`
- **California Driver's License**: `A1234567` → `<DL-US-N>`
- US phones with `+1` or local format

---

## Replacement labels

Tokens are numbered per entity type (`N` = sequential integer starting at 1).
The same original value always maps to the same token within a file.

| Label          | Replaced entity                    | Jurisdiction        |
|----------------|------------------------------------|---------------------|
| `<PERSONA-N>`  | Person name (NER)                  | All                 |
| `<EMAIL-N>`    | Email address                      | All                 |
| `<TELEFONO-N>` | Phone number                       | All                 |
| `<IBAN-N>`     | IBAN bank code                     | All                 |
| `<TARJETA-N>`  | Credit card number                 | All                 |
| `<FECHA-N>`    | Date                               | All                 |
| `<IP-N>`       | IP address                         | All                 |
| `<UBICACION-N>`| Location near a person name        | All                 |
| `<DNI-ES-N>`   | Spanish DNI or NIE                 | RGPD                |
| `<RUT-CL-N>`   | Chilean RUT / RUN                  | Chile               |
| `<CPF-BR-N>`   | Brazilian CPF                      | Brasil              |
| `<CNPJ-BR-N>`  | Brazilian CNPJ                     | Brasil              |
| `<CURP-MX-N>`  | Mexican CURP                       | Mexico              |
| `<RFC-MX-N>`   | Mexican RFC                        | Mexico              |
| `<NIT-CO-N>`   | Colombian NIT                      | Colombia            |
| `<CUIT-AR-N>`  | Argentine CUIT / CUIL              | Argentina           |
| `<DNI-AR-N>`   | Argentine DNI                      | Argentina           |
| `<NINO-UK-N>`  | UK National Insurance Number       | UK                  |
| `<SSN-US-N>`   | US Social Security Number          | CCPA                |
| `<DL-US-N>`    | California Driver's License        | CCPA                |

---

## Installation

### 1. Clone the repository

```bash
git clone --depth 1 https://github.com/uhartharper/anonimizador-datos.git
cd anonimizador-datos
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install spaCy language models

Minimum required (Spanish):

```bash
python -m spacy download es_core_news_lg
```

Additional models by jurisdiction:

```bash
# English — required for UK GDPR and CCPA
python -m spacy download en_core_web_lg

# Portuguese — required for LGPD (Brazil)
python -m spacy download pt_core_news_lg

# Other EU languages (optional)
python -m spacy download fr_core_news_lg
python -m spacy download de_core_news_lg
python -m spacy download it_core_news_lg
python -m spacy download nl_core_news_lg
```

The script loads whichever models are installed and skips the rest with a notice.
It works with any combination, as long as at least one model is available.

> Restoration mode (`--restaurar`) does not load any NLP models and has no model requirement.

---

## Usage

### Anonymization

Pass files or folders directly as arguments. Output is written to the same
location as the input with `_anon` appended to the filename. The original
is never modified.

```bash
# Single file — produces informe_anon.docx + informe_anon.docx.key.json
python anonimizar.py informe.docx

# Single file with explicit jurisdiction
python anonimizar.py informe.docx --ley rgpd

# Multiple files
python anonimizar.py datos.csv clientes.xlsx notas.md --ley chile

# Entire folder
python anonimizar.py C:/exports/ --ley rgpd

# Explicit output file (single input only)
python anonimizar.py datos.csv --salida datos_limpio.csv --ley rgpd

# Explicit output folder (multiple files or folder input)
python anonimizar.py C:/exports/ --carpeta-salida C:/anon/ --ley todo

# Multiple jurisdictions at once
python anonimizar.py datos.csv --ley rgpd chile brasil

# All jurisdictions
python anonimizar.py datos.csv --ley todo

# List available jurisdictions
python anonimizar.py --lista-leyes
```

### Restoration

```bash
# Auto-locate map (exact [input].key.json, or the single .key.json in the folder)
python anonimizar.py datos_anon.csv --restaurar

# Entire folder (first level; skips .key.json and *_restaurado files)
python anonimizar.py C:/anon/ --restaurar

# Explicit map file (required if the folder holds several .key.json maps)
python anonimizar.py datos_anon.csv --restaurar --mapa /secure/datos_anon.csv.key.json

# AI-returned file renamed — restore it with the original map
python anonimizar.py result.docx --restaurar --mapa informe_anon.docx.key.json

# Restore to a specific folder
python anonimizar.py datos_anon.csv --restaurar --carpeta-salida C:/restored/
```

See [Map resolution order](#the-full-round-trip-anonymize--process-with-ai--restore)
above for how the `.key.json` is located when not passed explicitly.

### Output naming

| Operation | Input | Output |
|-----------|-------|--------|
| Anonymize | `datos.csv` | `datos_anon.csv` + `datos_anon.csv.key.json` |
| Anonymize | `informe.docx` | `informe_anon.docx` + `informe_anon.docx.key.json` |
| Anonymize | `datos.csv --salida limpio.csv` | `limpio.csv` + `limpio.csv.key.json` |
| Restore   | `datos_anon.csv` | `datos_anon_restaurado.csv` |

### Supported file formats

| Extension | Behavior                                                               |
|-----------|------------------------------------------------------------------------|
| `.csv`    | All cells. Auto-detects Screaming Frog exports: only free-text columns.|
| `.xlsx`   | All sheets, cell by cell.                                              |
| `.md`     | Line by line. Markdown formatting preserved.                           |
| `.docx`   | Run by run. Bold, italic, and other styles preserved.                  |

---

## Claude Code skill

The `SKILL.md` file is a [Claude Code](https://claude.ai/code) skill definition.
Install it to invoke the anonymizer directly from Claude Code with `/anonimizar`.

```bash
# Unix / macOS / Linux
mkdir -p ~/.claude/skills/anonimizar
cp SKILL.md ~/.claude/skills/anonimizar/SKILL.md

# Windows (PowerShell)
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills\anonimizar"
Copy-Item SKILL.md "$env:USERPROFILE\.claude\skills\anonimizar\SKILL.md"
```

The skill is invocation-only — it does not auto-trigger.

---

## Known limitations

- **NER false positives**: spaCy may tag common Spanish words (greetings, titles) as person names. The script filters the most frequent ones; the rest appear in output.
- **Colombian CC (cédula)**: bare 6–10 digit sequences produce too many false positives. Detection is activated only when preceded by `C.C.`, `cédula`, or `documento`.
- **Argentine DNI without dots**: confidence score 0.55. Any 7–8 digit sequence qualifies. Manually review output when documents contain numeric codes (order IDs, product SKUs).
- **Brazilian CPF without formatting**: confidence 0.60 for bare 11-digit sequences. Formatted input (`123.456.789-09`) scores 0.95.
- **Short texts (<4 words)**: language detection is unreliable. The script falls back to the first available model.
- **JavaScript-rendered content**: the tool processes static file content only. It does not fetch or render URLs.
- **Restoration fidelity**: if the same original value appears with different casing across the file, each variant is stored as a separate token and restored independently.

---

## License

MIT — see [LICENSE](LICENSE).

Free to use, modify, and distribute. Attribution appreciated but not required.

---

## Privacy

This repository contains no client data, no domain names, and no identifying
information. All patterns are anonymized. The tool is designed precisely to
help others achieve the same standard.

The `.key.json` files generated during anonymization are never committed to
this repository. Add `*.key.json` to your `.gitignore` if you work in a
git-tracked folder.

---

## Contributing

Add real-world patterns as new edge cases appear.
Rule: knowledge is contributed anonymized — the pattern matters, not the source.

Useful contributions:
- New jurisdiction recognizers (PDPA Thailand, PIPL China, LGPD adaptations)
- Additional false-positive filters per language
- New file format processors (JSON, TXT, HTML)
- Edge cases for existing ID patterns (formatting variants, regional exceptions)
