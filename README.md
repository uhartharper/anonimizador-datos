# Multi-Jurisdiction PII Anonymizer

A Python tool for detecting and replacing personally identifiable information (PII)
in CSV, XLSX, Markdown, and DOCX files — with jurisdiction-specific rules for 8
data protection frameworks.

Built for SEO agencies, data analysts, and consultants who share client data with
AI tools and need a clean, auditable anonymization step before exporting files.

- **Jurisdictions**: RGPD/GDPR (EU), Ley 21.719 (Chile), LGPD (Brazil), LFPDPPP (Mexico), Ley 1581 (Colombia), Ley 25.326 (Argentina), UK GDPR, CCPA/CPRA (California)
- **Formats**: `.csv`, `.xlsx`, `.md`, `.docx`
- **NLP engine**: [spaCy](https://spacy.io/) + [Microsoft Presidio](https://microsoft.github.io/presidio/), multilingual
- **Screaming Frog aware**: auto-detects SF exports and only processes free-text columns

---

## Jurisdictions

### EU — RGPD / GDPR (Regulation 2016/679)

**Key:** `rgpd`

- **DNI** (8 digits + check letter): `12345678Z` → `<DNI-ES>`
- **NIE** (X/Y/Z + 7 digits + letter): `X1234567Z` → `<DNI-ES>`
- Spanish landlines and mobiles, including `+34` prefix
- Universal: names, emails, IBAN codes, credit cards, dates, IPs, locations near names

---

### Chile — Ley 21.719 / Ley 19.628

**Key:** `chile`

Ley 21.719 (published December 2023, full enforcement from 2026) modernizes Ley 19.628.
Introduces a Data Protection Delegate, expands sensitive data categories (biometric,
continuous geolocation, data of minors under 14), and applies extraterritorially
to processing that affects people in Chile.

- **RUT/RUN** with dots: `12.345.678-9` → `<RUT-CL>`
- **RUT/RUN** without dots: `12345678-K` → `<RUT-CL>`
- Chilean mobiles (`9XXXXXXXX`) and landlines with `+56` prefix

---

### Brazil — LGPD (Lei 13.709/2018)

**Key:** `brasil`

In force since August 2020. Requires an explicit legal basis for each processing
activity. Applies to any organization processing data of people in Brazil,
regardless of where the organization is located. Supervisory authority: ANPD.

- **CPF** (individual taxpayer): `123.456.789-09` → `<CPF-BR>`
- **CNPJ** (legal entity): `12.345.678/0001-95` → `<CNPJ-BR>`
- Brazilian mobiles (9-digit with DDD) and landlines with `+55` prefix

---

### Mexico — LFPDPPP (2010)

**Key:** `mexico`

Applies to the private sector. The public sector is governed by the separate
Ley General de Protección de Datos en Posesión de Sujetos Obligados (2017).
Supervisory authority: INAI.

- **CURP** (18-char alphanumeric): `PELJ800101HDFRRN09` → `<CURP-MX>`
- **RFC** persona física (13 chars): `PELJ800101XX9` → `<RFC-MX>`
- **RFC** persona moral (12 chars): `ABC123456XX9` → `<RFC-MX>`
- Mexican phones with area code and `+52` prefix

---

### Colombia — Ley 1581/2012 + Decreto 1377/2013

**Key:** `colombia`

Supervisory authority: Superintendencia de Industria y Comercio (SIC).
The CC (cédula de ciudadanía) is only detected when preceded by `C.C.`,
`cédula`, or `documento` to avoid false positives from bare number sequences.

- **NIT** (9 digits + check digit): `123456789-1` → `<NIT-CO>`
- **CC** with context prefix: `C.C. 1234567890` → `<DNI-ES>`
- Colombian mobiles (3XX) and landlines with `+57` prefix

---

### Argentina — Ley 25.326 (2000)

**Key:** `argentina`

Supervisory authority: AAIP (Agencia de Acceso a la Información Pública).
Reform bill PIDIA was under parliamentary consideration as of June 2026 and
had not yet been enacted. DNI without dots has a lower confidence score (0.55)
due to high false-positive risk from bare number sequences.

- **DNI** with dots: `12.345.678` → `<DNI-AR>`
- **CUIT / CUIL**: `20-12345678-9` → `<CUIT-AR>`
- Argentine phones with area code and `+54` prefix

---

### UK — UK GDPR / Data Protection Act 2018

**Key:** `uk`

UK GDPR entered into force on 1 January 2021 (post-Brexit). Structurally
identical to EU GDPR but with growing divergences. Supervisory authority: ICO.

- **NINO** (National Insurance Number): `AB 12 34 56 C` → `<NINO-UK>`
- UK phones: `+44`, `0044`, or leading `0` formats

---

### California — CCPA / CPRA

**Key:** `ccpa`

CCPA (2018) extended by CPRA (in force January 2023). Applies to for-profit
businesses meeting any of: >$25M annual revenue; ≥100,000 consumers' data
processed; ≥50% revenue from selling data. Supervisory authority: CPPA.
California DL pattern (`[A-Z]\d{7}`) has score 0.70 — review output manually
if documents contain unrelated alphanumeric codes.

- **SSN**: `123-45-6789` → `<SSN-US>`
- **California Driver's License**: `A1234567` → `<DL-US>`
- US phones with `+1` or local format

---

## Replacement labels

| Label        | Replaced entity                    | Jurisdiction        |
|--------------|------------------------------------|---------------------|
| `<PERSONA>`  | Person name (NER)                  | All                 |
| `<EMAIL>`    | Email address                      | All                 |
| `<TELEFONO>` | Phone number                       | All                 |
| `<IBAN>`     | IBAN bank code                     | All                 |
| `<TARJETA>`  | Credit card number                 | All                 |
| `<FECHA>`    | Date                               | All                 |
| `<IP>`       | IP address                         | All                 |
| `<UBICACION>`| Location near a person name        | All                 |
| `<DNI-ES>`   | Spanish DNI or NIE                 | RGPD                |
| `<RUT-CL>`   | Chilean RUT / RUN                  | Chile               |
| `<CPF-BR>`   | Brazilian CPF                      | Brasil              |
| `<CNPJ-BR>`  | Brazilian CNPJ                     | Brasil              |
| `<CURP-MX>`  | Mexican CURP                       | Mexico              |
| `<RFC-MX>`   | Mexican RFC                        | Mexico              |
| `<NIT-CO>`   | Colombian NIT                      | Colombia            |
| `<CUIT-AR>`  | Argentine CUIT / CUIL              | Argentina           |
| `<DNI-AR>`   | Argentine DNI                      | Argentina           |
| `<NINO-UK>`  | UK National Insurance Number       | UK                  |
| `<SSN-US>`   | US Social Security Number          | CCPA                |
| `<DL-US>`    | California Driver's License        | CCPA                |

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

---

## Usage

Pass files or folders directly as arguments. Output is written to the same
location as the input with `_anon` appended to the filename. The original
is never modified.

```bash
# Single file — produces informe_anon.docx in the same folder
python anonimizar.py informe.docx

# Single file with RGPD rules
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

### Output naming

| Input | Output |
|---|---|
| `datos.csv` | `datos_anon.csv` (same folder) |
| `informe.docx` | `informe_anon.docx` (same folder) |
| `datos.csv --salida limpio.csv` | `limpio.csv` |
| `C:/exports/ --carpeta-salida C:/anon/` | `C:/anon/[name]_anon.[ext]` |

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

---


## License

MIT — see [LICENSE](LICENSE).

Free to use, modify, and distribute. Attribution appreciated but not required.

---

## Privacy

This repository contains no client data, no domain names, and no identifying
information. All patterns are anonymized. The tool is designed precisely to
help others achieve the same standard.

---

## Contributing

Add real-world patterns as new edge cases appear.
Rule: knowledge is contributed anonymized — the pattern matters, not the source.

Useful contributions:
- New jurisdiction recognizers (PDPA Thailand, PIPL China, LGPD adaptations)
- Additional false-positive filters per language
- New file format processors (JSON, TXT, HTML)
- Edge cases for existing ID patterns (formatting variants, regional exceptions)
