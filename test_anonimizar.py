# =============================================================================
# test_anonimizar.py — Suite de regresión del anonimizador
#
# Ejecuta el script real (subprocess) sobre fixtures con PII conocida de cada
# jurisdicción y verifica que:
#   - cada identificador se tokeniza (no aparece literal en la salida)
#   - el round-trip anonimizar -> restaurar devuelve el original
#   - el cifrado del mapa protege la PII y la clave es obligatoria al restaurar
#
# Uso:  python -m unittest test_anonimizar       (requiere modelos de spaCy)
#       python test_anonimizar.py
#
# Nota: cada anonimización carga los modelos NLP (~10-20 s). La suite agrupa los
# casos para minimizar el número de cargas.
# =============================================================================

import os
import sys
import json
import shutil
import tempfile
import subprocess
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(DIR, "anonimizar.py")

# Identificadores por jurisdicción: deben desaparecer del archivo anonimizado.
IDENTIFICADORES = {
    "DNI-ES":   "12345678Z",
    "RUT-CL":   "12.345.678-5",
    "CPF-BR":   "123.456.789-09",
    "CNPJ-BR":  "12.345.678/0001-95",
    "CURP-MX":  "PELJ800101HDFRRN09",
    "NIT-CO":   "123456789-1",
    "CUIT-AR":  "20-12345678-9",
    "NINO-UK":  "AB123456C",
    "SSN-US":   "123-45-6789",
    "EMAIL":    "juan.perez@empresa.com",
    "DIRECCION": "Calle Mayor 3",
}


def _run(args, cwd=DIR):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd, capture_output=True, text=True,
    )


class TestAnonimizacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="anon_test_")
        cls.csv = os.path.join(cls.tmp, "fixture.csv")
        filas = ["nombre,email,documento,direccion"]
        for i, (_, valor) in enumerate(IDENTIFICADORES.items(), 1):
            # Cada fila tiene un nombre (activa contexto) + un identificador.
            filas.append(f"Persona Ejemplo {i},juan.perez@empresa.com,{valor},Calle Mayor 3")
        with open(cls.csv, "w", encoding="utf-8") as f:
            f.write("\n".join(filas) + "\n")
        cls.res = _run([cls.csv, "--ley", "todo"])
        cls.anon = os.path.join(cls.tmp, "fixture_anon.csv")
        cls.key = cls.anon + ".key.json"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_proceso_termina_ok(self):
        self.assertEqual(self.res.returncode, 0, self.res.stderr)
        self.assertTrue(os.path.isfile(self.anon))
        self.assertTrue(os.path.isfile(self.key))

    def test_identificadores_tokenizados(self):
        with open(self.anon, encoding="utf-8") as f:
            contenido = f.read()
        for etiqueta, valor in IDENTIFICADORES.items():
            with self.subTest(identificador=etiqueta):
                self.assertNotIn(valor, contenido,
                                 f"{etiqueta} ({valor}) NO se anonimizó — fuga de PII")

    def test_mapa_recupera_valores(self):
        with open(self.key, encoding="utf-8") as f:
            mapa = json.load(f)["mapa"]
        originales = set(mapa.values())
        for etiqueta, valor in IDENTIFICADORES.items():
            with self.subTest(identificador=etiqueta):
                self.assertIn(valor, originales, f"{etiqueta} no está en el mapa")

    def test_reporte_cobertura_en_salida(self):
        self.assertIn("Cobertura de detección", self.res.stdout)

    def test_roundtrip_restaura_original(self):
        r = _run([self.anon, "--restaurar"])
        self.assertEqual(r.returncode, 0, r.stderr)
        restaurado = os.path.join(self.tmp, "fixture_anon_restaurado.csv")
        with open(self.csv, encoding="utf-8") as f:
            original = f.read()
        with open(restaurado, encoding="utf-8") as f:
            self.assertEqual(f.read(), original)


class TestCifrado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="anon_cifr_")
        cls.csv = os.path.join(cls.tmp, "datos.csv")
        with open(cls.csv, "w", encoding="utf-8") as f:
            f.write("nombre,documento\nAna Ruiz,12345678Z\n")
        cls.res = _run([cls.csv, "--ley", "rgpd", "--cifrar-mapa", "--clave", "secreta123"])
        cls.anon = os.path.join(cls.tmp, "datos_anon.csv")
        cls.key = cls.anon + ".key.json"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_mapa_cifrado_sin_pii_en_claro(self):
        self.assertEqual(self.res.returncode, 0, self.res.stderr)
        with open(self.key, encoding="utf-8") as f:
            sobre = json.load(f)
        self.assertTrue(sobre.get("cifrado"))
        self.assertNotIn("12345678Z", json.dumps(sobre))

    def test_restaurar_sin_clave_falla(self):
        # Aislar de otros tests: borrar cualquier restaurado previo
        restaurado = os.path.join(self.tmp, "datos_anon_restaurado.csv")
        if os.path.isfile(restaurado):
            os.remove(restaurado)
        r = _run([self.anon, "--restaurar"])
        self.assertIn("cifrado", (r.stdout + r.stderr).lower())
        self.assertFalse(os.path.isfile(restaurado),
                         "No debe generarse el restaurado sin la clave")

    def test_restaurar_con_clave_ok(self):
        r = _run([self.anon, "--restaurar", "--clave", "secreta123"])
        self.assertEqual(r.returncode, 0, r.stderr)
        restaurado = os.path.join(self.tmp, "datos_anon_restaurado.csv")
        with open(restaurado, encoding="utf-8") as f:
            self.assertIn("12345678Z", f.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
