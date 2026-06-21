# =============================================================================
# anonimizar.py — Anonimizador multi-jurisdiccional v2.1
#
# Jurisdicciones soportadas:
#   rgpd      — UE (RGPD/GDPR 2016/679)
#   chile     — Ley 21.719 / Ley 19.628 (Chile)
#   brasil    — LGPD Lei 13.709/2018 (Brasil)
#   mexico    — LFPDPPP 2010 (México)
#   colombia  — Ley 1581/2012 + Decreto 1377/2013 (Colombia)
#   argentina — Ley 25.326 (Argentina)
#   uk        — UK GDPR / Data Protection Act 2018
#   ccpa      — CCPA/CPRA (California, EE.UU.)
#   todo      — Activa todas las jurisdicciones simultáneamente
#
# Uso:
#   python anonimizar.py archivo.csv                  → genera archivo_anon.csv
#   python anonimizar.py *.docx --ley chile           → varios archivos
#   python anonimizar.py C:/exports/ --ley rgpd       → carpeta completa
#   python anonimizar.py datos.csv --salida limpio.csv → salida explícita
#   python anonimizar.py C:/exports/ --carpeta-salida C:/anon/
#   python anonimizar.py --lista-leyes
#
# Formatos soportados: .csv, .xlsx, .md, .docx
# Salida por defecto: [nombre]_anon.[ext] en la misma carpeta del original
# =============================================================================

import os
import re
import sys
import argparse
import spacy
import pandas as pd
from docx import Document
from langdetect import detect, LangDetectException

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider

# =============================================================================
# PARTE 0: Argumentos de línea de comandos
# =============================================================================

JURISDICCIONES_DISPONIBLES = ["rgpd", "chile", "brasil", "mexico", "colombia", "argentina", "uk", "ccpa"]

parser = argparse.ArgumentParser(
    description="Anonimizador multi-jurisdiccional de datos personales.",
    formatter_class=argparse.RawTextHelpFormatter,
    epilog=(
        "Ejemplos:\n"
        "  python anonimizar.py informe.docx\n"
        "  python anonimizar.py datos.csv clientes.xlsx --ley chile\n"
        "  python anonimizar.py C:/exports/ --ley rgpd\n"
        "  python anonimizar.py datos.csv --salida datos_limpio.csv --ley rgpd\n"
        "  python anonimizar.py C:/exports/ --carpeta-salida C:/anon/ --ley todo\n"
    )
)
parser.add_argument(
    "entradas", nargs="*", metavar="ARCHIVO_O_CARPETA",
    help="Archivos o carpetas a procesar. Acepta varios a la vez."
)
parser.add_argument(
    "--ley", nargs="+", default=["rgpd"],
    metavar="LEY",
    help=(
        "Jurisdicción(es) a aplicar:\n"
        "  rgpd       UE — RGPD/GDPR 2016/679\n"
        "  chile      Chile — Ley 21.719 / 19.628\n"
        "  brasil     Brasil — LGPD Lei 13.709/2018\n"
        "  mexico     México — LFPDPPP 2010\n"
        "  colombia   Colombia — Ley 1581/2012\n"
        "  argentina  Argentina — Ley 25.326\n"
        "  uk         UK GDPR / Data Protection Act 2018\n"
        "  ccpa       California — CCPA/CPRA\n"
        "  todo       Activa todas las anteriores\n"
    )
)
parser.add_argument(
    "--salida", metavar="ARCHIVO",
    help="Ruta de salida explícita (solo válido con un único archivo de entrada)."
)
parser.add_argument(
    "--carpeta-salida", metavar="CARPETA",
    help="Carpeta de destino para todos los archivos procesados."
)
parser.add_argument(
    "--lista-leyes", action="store_true",
    help="Muestra las jurisdicciones disponibles y termina."
)
args = parser.parse_args()

if args.lista_leyes:
    print("Jurisdicciones disponibles:")
    for ley in JURISDICCIONES_DISPONIBLES:
        print(f"  {ley}")
    sys.exit(0)

leyes_activas = set(JURISDICCIONES_DISPONIBLES if "todo" in args.ley else args.ley)
leyes_invalidas = leyes_activas - set(JURISDICCIONES_DISPONIBLES)
if leyes_invalidas:
    print(f"[ERROR] Jurisdicción(es) desconocida(s): {', '.join(leyes_invalidas)}")
    print(f"Valores válidos: {', '.join(JURISDICCIONES_DISPONIBLES)}, todo")
    sys.exit(1)

print(f"Jurisdicciones activas: {', '.join(sorted(leyes_activas))}\n")

# =============================================================================
# PARTE 1: Modelos de lenguaje — spaCy multilingüe
# =============================================================================
# Los modelos se cargan de forma gradual. Cualquier combinación funciona siempre
# que haya al menos uno instalado.

MODELOS_IDIOMA = {
    "es": "es_core_news_lg",  # español
    "en": "en_core_web_lg",   # inglés
    "fr": "fr_core_news_lg",  # francés
    "de": "de_core_news_lg",  # alemán
    "it": "it_core_news_lg",  # italiano
    "pt": "pt_core_news_lg",  # portugués (cubre LGPD Brasil)
    "nl": "nl_core_news_lg",  # neerlandés
}

print("Comprobando modelos de idioma disponibles:")
modelos_cargados = []
idiomas_disponibles = []

for lang_code, model_name in MODELOS_IDIOMA.items():
    try:
        spacy.load(model_name)
        modelos_cargados.append({"lang_code": lang_code, "model_name": model_name})
        idiomas_disponibles.append(lang_code)
        print(f"  OK  {lang_code} ({model_name})")
    except OSError:
        print(f"  --  {lang_code} ({model_name}) no instalado — omitido")

if not modelos_cargados:
    raise RuntimeError(
        "No hay ningún modelo de spaCy instalado.\n"
        "Instala al menos uno con: python -m spacy download es_core_news_lg"
    )

idioma_por_defecto = idiomas_disponibles[0]

provider = NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": modelos_cargados
})
nlp_engine = provider.create_engine()
analyzer = AnalyzerEngine(
    nlp_engine=nlp_engine,
    supported_languages=idiomas_disponibles
)

print(f"\nMotor listo. Idiomas activos: {', '.join(idiomas_disponibles)}\n")

# =============================================================================
# PARTE 2: Mapa de etiquetas y entidades universales
# =============================================================================
# Las etiquetas con prefijo de jurisdicción facilitan la trazabilidad en auditorías.

ETIQUETAS = {
    # Entidades universales (todas las jurisdicciones)
    "PERSON":          "<PERSONA>",
    "EMAIL_ADDRESS":   "<EMAIL>",
    "PHONE_NUMBER":    "<TELEFONO>",
    "IBAN_CODE":       "<IBAN>",
    "CREDIT_CARD":     "<TARJETA>",
    "DATE_TIME":       "<FECHA>",
    "IP_ADDRESS":      "<IP>",
    "LOCATION":        "<UBICACION>",
    # España / RGPD
    "DNI_NIE":         "<DNI-ES>",
    # Chile — Ley 21.719
    "RUT_CL":          "<RUT-CL>",
    # Brasil — LGPD
    "CPF_BR":          "<CPF-BR>",
    "CNPJ_BR":         "<CNPJ-BR>",
    # México — LFPDPPP
    "CURP_MX":         "<CURP-MX>",
    "RFC_MX":          "<RFC-MX>",
    # Colombia — Ley 1581
    "NIT_CO":          "<NIT-CO>",
    # Argentina — Ley 25.326
    "CUIT_AR":         "<CUIT-AR>",
    "DNI_AR":          "<DNI-AR>",
    # UK — UK GDPR / DPA 2018
    "NINO_UK":         "<NINO-UK>",
    # EE.UU. — CCPA/CPRA
    "SSN_US":          "<SSN-US>",
    "DL_US":           "<DL-US>",
}

ENTIDADES_BASE = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
    "IBAN_CODE", "CREDIT_CARD", "DATE_TIME", "IP_ADDRESS", "LOCATION",
]

FALSOS_POSITIVOS_PERSONA = {
    "hola", "buenos", "buenas", "días", "tardes", "noches",
    "estimado", "estimada", "estimados", "estimadas",
    "querido", "querida", "saludos", "atentamente", "cordialmente",
    "señor", "señora", "señorita", "don", "doña",
    "presidente", "director", "gerente", "cliente", "usuario",
}

# =============================================================================
# PARTE 3: Reconocedores por jurisdicción
# =============================================================================

def _para_todos(name_prefix, patterns, entity):
    """Registra un PatternRecognizer con la entidad dada en todos los idiomas."""
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"{name_prefix}_{lang}",
            patterns=patterns,
            supported_language=lang,
            supported_entity=entity,
        ))


# ── RGPD (España / UE) ────────────────────────────────────────────────────────

def activar_rgpd():
    # DNI / NIE españoles
    analyzer.registry.add_recognizer(PatternRecognizer(
        name="DNI_NIE_ES",
        patterns=[
            Pattern("DNI", r"\b\d{8}[A-HJ-NP-TV-Za-hj-np-tv-z]\b", 0.85),
            Pattern("NIE", r"\b[XYZxyz]\d{7}[A-HJ-NP-TV-Za-hj-np-tv-z]\b", 0.85),
        ],
        supported_language="es",
        supported_entity="DNI_NIE",
    ))
    # Teléfonos españoles + internacionales
    patrones_tel_es = [
        Pattern("Tel_ES_intl",  r"(?<!\d)(?:\+34|0034)[\s.\-]?[6-9]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}\b", 0.95),
        Pattern("Movil_ES",     r"\b[67]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}\b", 0.80),
        Pattern("Fijo_ES",      r"\b9\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}\b", 0.75),
        Pattern("Tel_intl_gen", r"(?<!\d)\+(?!34|0034)\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{2,4}[\s.\-]?\d{2,4}[\s.\-]?\d{0,4}\b", 0.85),
    ]
    _registrar_para_todos(None, "Telefono_ES", patrones_tel_es)
    print("  [RGPD] Reconocedores DNI/NIE + teléfonos ES activados.")


# ── Chile — Ley 21.719 ────────────────────────────────────────────────────────
# RUT/RUN: hasta 8 dígitos + guion + dígito verificador (0-9 o K/k).
# Formato habitual: 12.345.678-9 o 12345678-9. También sin puntos: 12345678K.
# La Ley 21.719 (publicada diciembre 2023, vigencia plena 2026) amplía las
# categorías de datos sensibles e introduce nuevas obligaciones para responsables
# y encargados. El RUT sigue siendo el identificador nacional único.

def activar_chile():
    patrones_rut = [
        Pattern("RUT_puntos",   r"\b\d{1,2}\.\d{3}\.\d{3}-[\dKk]\b", 0.95),
        Pattern("RUT_sin_pts",  r"\b\d{7,8}-[\dKk]\b",               0.85),
    ]
    _registrar_para_todos(None, "RUT_CL", [
        Pattern("RUT_CL", p.regex, p.score) for p in patrones_rut
    ])
    # Sobrescribir entity: los patterns anteriores necesitan entity=RUT_CL
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"RUT_CL_{lang}",
            patterns=patrones_rut,
            supported_language=lang,
            supported_entity="RUT_CL",
        ))
    # Teléfonos chilenos
    patrones_tel_cl = [
        Pattern("Tel_CL_movil", r"(?:\+56|0056)?[\s\-]?9[\s\-]?\d{4}[\s\-]?\d{4}\b", 0.90),
        Pattern("Tel_CL_fijo",  r"(?:\+56|0056)[\s\-]?[2-9]\d{7}\b", 0.85),
    ]
    _registrar_para_todos(None, "Telefono_CL_tmp", patrones_tel_cl)
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_CL_{lang}",
            patterns=patrones_tel_cl,
            supported_language=lang,
            supported_entity="PHONE_NUMBER",
        ))
    print("  [Chile — Ley 21.719] Reconocedores RUT/RUN + teléfonos CL activados.")


# ── Brasil — LGPD ─────────────────────────────────────────────────────────────
# CPF: XXX.XXX.XXX-XX (persona física). CNPJ: XX.XXX.XXX/XXXX-XX (persona jurídica).
# La LGPD (Lei 13.709/2018) entró en vigor en agosto 2020. Exige base legal para
# tratamiento, aplica a datos de brasileños independientemente de dónde se procesen.

def activar_brasil():
    patrones_cpf = [
        Pattern("CPF_puntos", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", 0.95),
        Pattern("CPF_sin",    r"\b\d{11}\b",                     0.60),
    ]
    patrones_cnpj = [
        Pattern("CNPJ_fmt", r"\b\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}\b", 0.95),
        Pattern("CNPJ_sin", r"\b\d{14}\b",                            0.55),
    ]
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"CPF_BR_{lang}", patterns=patrones_cpf,
            supported_language=lang, supported_entity="CPF_BR",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"CNPJ_BR_{lang}", patterns=patrones_cnpj,
            supported_language=lang, supported_entity="CNPJ_BR",
        ))
        # Teléfonos brasileños
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_BR_{lang}",
            patterns=[
                Pattern("Tel_BR_movil", r"(?:\+55|0055)?[\s\-]?\(?\d{2}\)?[\s\-]?9\d{4}[\s\-]?\d{4}\b", 0.90),
                Pattern("Tel_BR_fijo",  r"(?:\+55|0055)?[\s\-]?\(?\d{2}\)?[\s\-]?\d{4}[\s\-]?\d{4}\b", 0.80),
            ],
            supported_language=lang, supported_entity="PHONE_NUMBER",
        ))
    print("  [Brasil — LGPD] Reconocedores CPF, CNPJ + teléfonos BR activados.")


# ── México — LFPDPPP ──────────────────────────────────────────────────────────
# CURP: identificador de 18 caracteres alfanuméricos (persona física).
# RFC: identificador fiscal. Persona física: 13 chars. Persona moral: 12 chars.
# La LFPDPPP (2010) y su reglamento rigen el tratamiento de datos en el sector privado.
# Para sector público: Ley General de Protección de Datos (2017).

def activar_mexico():
    patrones_curp = [
        Pattern("CURP_MX",
            r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[B-DF-HJ-NP-TV-Z\d]\d\b",
            0.92),
    ]
    patrones_rfc = [
        Pattern("RFC_fisica",
            r"\b[A-Z&Ñ]{4}\d{6}[A-Z0-9]{3}\b",
            0.85),
        Pattern("RFC_moral",
            r"\b[A-Z&Ñ]{3}\d{6}[A-Z0-9]{3}\b",
            0.80),
    ]
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"CURP_MX_{lang}", patterns=patrones_curp,
            supported_language=lang, supported_entity="CURP_MX",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"RFC_MX_{lang}", patterns=patrones_rfc,
            supported_language=lang, supported_entity="RFC_MX",
        ))
        # Teléfonos mexicanos
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_MX_{lang}",
            patterns=[
                Pattern("Tel_MX",
                    r"(?:\+52|0052)?[\s\-]?\(?\d{2,3}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}\b",
                    0.80),
            ],
            supported_language=lang, supported_entity="PHONE_NUMBER",
        ))
    print("  [México — LFPDPPP] Reconocedores CURP, RFC + teléfonos MX activados.")


# ── Colombia — Ley 1581/2012 ──────────────────────────────────────────────────
# NIT: identificador tributario de 9 dígitos + dígito de verificación (XX-X).
# Cédula de ciudadanía (CC): 6-10 dígitos. Alta tasa de falsos positivos si
# no hay contexto; se activa solo cuando va precedida de abreviaturas comunes.
# La Ley 1581 y su Decreto reglamentario 1377/2013 regulan la protección de datos.

def activar_colombia():
    patrones_nit = [
        Pattern("NIT_CO", r"\b\d{9}-\d\b", 0.90),
    ]
    # Cédula con contexto previo (cc., c.c., cédula, documento)
    patrones_cc = [
        Pattern("CC_CO_contexto",
            r"(?:C\.?C\.?|cédula|documento)\s*:?\s*(\d{6,10})\b",
            0.85),
    ]
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"NIT_CO_{lang}", patterns=patrones_nit,
            supported_language=lang, supported_entity="NIT_CO",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"CC_CO_{lang}", patterns=patrones_cc,
            supported_language=lang, supported_entity="DNI_NIE",
        ))
        # Teléfonos colombianos
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_CO_{lang}",
            patterns=[
                Pattern("Tel_CO_movil", r"(?:\+57|0057)?[\s\-]?3\d{2}[\s\-]?\d{3}[\s\-]?\d{4}\b", 0.90),
                Pattern("Tel_CO_fijo",  r"(?:\+57|0057)?[\s\-]?\(?\d{1,3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b", 0.75),
            ],
            supported_language=lang, supported_entity="PHONE_NUMBER",
        ))
    print("  [Colombia — Ley 1581] Reconocedores NIT, CC + teléfonos CO activados.")


# ── Argentina — Ley 25.326 ────────────────────────────────────────────────────
# DNI argentino: 7-8 dígitos, habitualmente con puntos: XX.XXX.XXX.
# CUIT/CUIL: 11 dígitos con guiones: XX-XXXXXXXX-X.
# La Ley 25.326 (2000) sigue vigente; el proyecto PIDIA de reforma aún no fue aprobado.

def activar_argentina():
    patrones_dni_ar = [
        Pattern("DNI_AR_puntos", r"\b\d{2}\.\d{3}\.\d{3}\b", 0.85),
        Pattern("DNI_AR_sin",    r"\b[1-9]\d{6,7}\b",         0.55),
    ]
    patrones_cuit = [
        Pattern("CUIT_AR", r"\b\d{2}-\d{8}-\d\b", 0.95),
    ]
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"DNI_AR_{lang}", patterns=patrones_dni_ar,
            supported_language=lang, supported_entity="DNI_AR",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"CUIT_AR_{lang}", patterns=patrones_cuit,
            supported_language=lang, supported_entity="CUIT_AR",
        ))
        # Teléfonos argentinos
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_AR_{lang}",
            patterns=[
                Pattern("Tel_AR",
                    r"(?:\+54|0054)?[\s\-]?\(?\d{2,4}\)?[\s\-]?1{0,1}\d{4}[\s\-]?\d{4}\b",
                    0.80),
            ],
            supported_language=lang, supported_entity="PHONE_NUMBER",
        ))
    print("  [Argentina — Ley 25.326] Reconocedores DNI, CUIT/CUIL + teléfonos AR activados.")


# ── UK — UK GDPR / DPA 2018 ───────────────────────────────────────────────────
# National Insurance Number (NINO): formato AA 99 99 99 A (7 chars sin espacios: AA999999A).
# El UK GDPR entró en vigor post-Brexit el 1 enero 2021, idéntico en estructura al RGPD.

def activar_uk():
    patrones_nino = [
        Pattern("NINO_UK",
            r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z]{2}[\s]?\d{2}[\s]?\d{2}[\s]?\d{2}[\s]?[A-D]\b",
            0.92),
    ]
    patrones_tel_uk = [
        Pattern("Tel_UK",
            r"(?:\+44|0044|0)[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}\b",
            0.85),
    ]
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"NINO_UK_{lang}", patterns=patrones_nino,
            supported_language=lang, supported_entity="NINO_UK",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_UK_{lang}", patterns=patrones_tel_uk,
            supported_language=lang, supported_entity="PHONE_NUMBER",
        ))
    print("  [UK — UK GDPR/DPA 2018] Reconocedores NINO + teléfonos UK activados.")


# ── CCPA / CPRA — California ──────────────────────────────────────────────────
# Social Security Number (SSN): XXX-XX-XXXX.
# California Driver's License: letra + 7 dígitos.
# La CCPA (2018) y su extensión CPRA (2020, vigente 2023) aplican a empresas que
# operan en California con umbrales de ingresos o volúmenes de datos específicos.

def activar_ccpa():
    patrones_ssn = [
        Pattern("SSN_US",   r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b", 0.95),
    ]
    patrones_dl = [
        Pattern("DL_CA_US", r"\b[A-Z]\d{7}\b", 0.70),
    ]
    patrones_tel_us = [
        Pattern("Tel_US",
            r"(?:\+1|001)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b",
            0.80),
    ]
    for lang in idiomas_disponibles:
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"SSN_US_{lang}", patterns=patrones_ssn,
            supported_language=lang, supported_entity="SSN_US",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"DL_US_{lang}", patterns=patrones_dl,
            supported_language=lang, supported_entity="DL_US",
        ))
        analyzer.registry.add_recognizer(PatternRecognizer(
            name=f"Telefono_US_{lang}", patterns=patrones_tel_us,
            supported_language=lang, supported_entity="PHONE_NUMBER",
        ))
    print("  [CCPA/CPRA — California] Reconocedores SSN, DL + teléfonos US activados.")


# =============================================================================
# PARTE 4: Activar reconocedores según jurisdicciones seleccionadas
# =============================================================================

ACTIVADORES = {
    "rgpd":      activar_rgpd,
    "chile":     activar_chile,
    "brasil":    activar_brasil,
    "mexico":    activar_mexico,
    "colombia":  activar_colombia,
    "argentina": activar_argentina,
    "uk":        activar_uk,
    "ccpa":      activar_ccpa,
}

print("Activando reconocedores:")
for ley in sorted(leyes_activas):
    ACTIVADORES[ley]()

# Construir lista de entidades activas a partir de las etiquetas registradas
ENTIDADES = ENTIDADES_BASE + [
    e for e in ETIQUETAS
    if e not in ENTIDADES_BASE and any(
        rec.supported_entities and e in rec.supported_entities
        for rec in analyzer.registry.recognizers
    )
]

# =============================================================================
# PARTE 5: Detección de exports de Screaming Frog
# =============================================================================

COLUMNAS_TEXTO_SF = {
    "title 1", "title 2",
    "meta description 1", "meta description 2",
    "h1-1", "h1-2", "h2-1", "h2-2", "h3-1", "h3-2",
    "meta keywords 1", "snippet",
}

def es_archivo_screaming_frog(df: pd.DataFrame) -> bool:
    cabeceras = {c.lower() for c in df.columns}
    return {"address", "content type", "status code"}.issubset(cabeceras)

# =============================================================================
# PARTE 6: Función principal de anonimización de texto
# =============================================================================

def _detectar_idioma(texto: str) -> str:
    if len(texto.split()) < 4:
        return idioma_por_defecto
    try:
        idioma = detect(texto)
        return idioma if idioma in idiomas_disponibles else idioma_por_defecto
    except LangDetectException:
        return idioma_por_defecto


def _normalizar_mayusculas(texto: str) -> str:
    palabras = texto.split()
    if not palabras:
        return texto
    prop = sum(1 for p in palabras if p.isalpha() and p.isupper()) / len(palabras)
    return texto.title() if prop > 0.5 else texto


def anonimizar_texto(texto: str) -> str:
    if not texto or not texto.strip():
        return texto

    texto_para_analisis = _normalizar_mayusculas(texto)
    idioma = _detectar_idioma(texto_para_analisis)

    resultados = analyzer.analyze(
        text=texto_para_analisis,
        entities=ENTIDADES,
        language=idioma
    )

    # Descartar falsos positivos de PERSON
    resultados = [
        r for r in resultados
        if not (
            r.entity_type == "PERSON" and
            texto[r.start:r.end].lower() in FALSOS_POSITIVOS_PERSONA
        )
    ]

    # LOCATION solo si aparece cerca de una PERSON (≤120 caracteres)
    personas = [r for r in resultados if r.entity_type == "PERSON"]
    resultados = [
        r for r in resultados
        if r.entity_type != "LOCATION" or any(
            abs(r.start - p.end) <= 120 or abs(p.start - r.end) <= 120
            for p in personas
        )
    ]

    # EMAIL_ADDRESS tiene prioridad sobre URL cuando se solapan
    for r in resultados:
        if r.entity_type == "EMAIL_ADDRESS":
            r.score = 1.0

    # Eliminar solapamientos: conservar la entidad con mayor score
    resultados_sin_solapamiento = []
    for r in sorted(resultados, key=lambda x: x.score, reverse=True):
        solapado = any(
            r.start < e.end and r.end > e.start
            for e in resultados_sin_solapamiento
        )
        if not solapado:
            resultados_sin_solapamiento.append(r)

    resultados = sorted(resultados_sin_solapamiento, key=lambda r: r.start, reverse=True)

    texto_anon = texto
    for resultado in resultados:
        etiqueta = ETIQUETAS.get(resultado.entity_type, f"<{resultado.entity_type}>")
        texto_anon = texto_anon[:resultado.start] + etiqueta + texto_anon[resultado.end:]

    return texto_anon

# =============================================================================
# PARTE 7: Procesadores por formato de archivo
# =============================================================================

def procesar_csv(ruta_entrada: str, ruta_salida: str):
    df = pd.read_csv(ruta_entrada, dtype=str)
    if es_archivo_screaming_frog(df):
        print("  Detectado formato Screaming Frog — procesando solo columnas de texto libre.")
        for columna in df.columns:
            if columna.lower() in COLUMNAS_TEXTO_SF:
                df[columna] = df[columna].apply(
                    lambda c: anonimizar_texto(c) if isinstance(c, str) else c
                )
    else:
        df = df.map(lambda c: anonimizar_texto(c) if isinstance(c, str) else c)
    df.to_csv(ruta_salida, index=False)
    print(f"  CSV guardado: {ruta_salida}")


def procesar_xlsx(ruta_entrada: str, ruta_salida: str):
    hojas = pd.read_excel(ruta_entrada, sheet_name=None, dtype=str)
    hojas_anon = {}
    for nombre, df in hojas.items():
        df = df.map(lambda c: anonimizar_texto(c) if isinstance(c, str) else c)
        hojas_anon[nombre] = df
    with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
        for nombre, df in hojas_anon.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
    print(f"  XLSX guardado: {ruta_salida}")


def procesar_md(ruta_entrada: str, ruta_salida: str):
    with open(ruta_entrada, "r", encoding="utf-8") as f:
        lineas = f.readlines()
    lineas_anon = [anonimizar_texto(l) for l in lineas]
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.writelines(lineas_anon)
    print(f"  MD guardado: {ruta_salida}")


def procesar_docx(ruta_entrada: str, ruta_salida: str):
    doc = Document(ruta_entrada)
    for parrafo in doc.paragraphs:
        for run in parrafo.runs:
            run.text = anonimizar_texto(run.text)
    for tabla in doc.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    for run in parrafo.runs:
                        run.text = anonimizar_texto(run.text)
    doc.save(ruta_salida)
    print(f"  DOCX guardado: {ruta_salida}")

# =============================================================================
# PARTE 8: Resolución de rutas y bucle principal
# =============================================================================

PROCESADORES = {
    ".csv":  procesar_csv,
    ".xlsx": procesar_xlsx,
    ".md":   procesar_md,
    ".docx": procesar_docx,
}


def ruta_salida_para(ruta_entrada: str) -> str:
    """
    Calcula la ruta de salida para un archivo dado.
    Orden de prioridad:
      1. --salida  (solo con un único archivo)
      2. --carpeta-salida / nombre_anon.ext
      3. misma carpeta que el original / nombre_anon.ext
    """
    if args.salida:
        return args.salida
    nombre, ext = os.path.splitext(os.path.basename(ruta_entrada))
    nombre_anon = f"{nombre}_anon{ext}"
    if args.carpeta_salida:
        os.makedirs(args.carpeta_salida, exist_ok=True)
        return os.path.join(args.carpeta_salida, nombre_anon)
    return os.path.join(os.path.dirname(os.path.abspath(ruta_entrada)), nombre_anon)


def recopilar_archivos(entradas: list) -> list:
    """
    Expande la lista de argumentos (archivos y/o carpetas) en rutas absolutas
    de archivos con extensión soportada.
    """
    rutas = []
    for entrada in entradas:
        entrada = os.path.abspath(entrada)
        if os.path.isdir(entrada):
            for nombre in os.listdir(entrada):
                ruta = os.path.join(entrada, nombre)
                if os.path.isfile(ruta):
                    rutas.append(ruta)
        elif os.path.isfile(entrada):
            rutas.append(entrada)
        else:
            print(f"  [AVISO] No encontrado: {entrada}")
    return rutas


# ── Validaciones previas ──────────────────────────────────────────────────────

if not args.entradas:
    parser.print_help()
    sys.exit(0)

if args.salida and len(args.entradas) > 1:
    print("[ERROR] --salida solo es válido con un único archivo de entrada.")
    sys.exit(1)

archivos = recopilar_archivos(args.entradas)

if not archivos:
    print("No se encontraron archivos para procesar.")
    sys.exit(0)

# ── Procesado ─────────────────────────────────────────────────────────────────

print(f"Archivos a procesar: {len(archivos)}\n")
for ruta_entrada in archivos:
    _, extension = os.path.splitext(ruta_entrada)
    extension = extension.lower()
    if extension not in PROCESADORES:
        print(f"  [OMITIDO] {ruta_entrada} (extensión no soportada)")
        continue
    ruta_salida = ruta_salida_para(ruta_entrada)
    print(f"Procesando: {ruta_entrada}")
    try:
        PROCESADORES[extension](ruta_entrada, ruta_salida)
    except Exception as e:
        print(f"  [ERROR] {e}")

print("\nAnonimización completada.")
