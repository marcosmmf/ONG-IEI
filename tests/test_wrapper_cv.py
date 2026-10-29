"""El wrapper cambia el formato sin aplicar el mapping de CV."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ong.extractores.extractor_cv import wrapper


class WrapperCVTests(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.ruta = Path(temporal.name) / "fuente.csv"
        self.ruta.write_text(
            'id,nombre,domici,cod_ine_mun,email,telefono,leyenda\n'
            '24,"  Centro, València 🏠  "," Calle Mayor\n1 ",03001, ZERO@GVA.ES ,0,Entidad Local\n'
            '25,Otro centro,,03002,,,Entidad Privada\n',
            encoding="utf-8-sig", newline="",
        )

    def test_conserva_texto_original_codigos_y_valores_vacios(self):
        registros = wrapper(self.ruta)
        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0], {
            "id": "24", "nombre": "  Centro, València 🏠  ", "domici": " Calle Mayor\n1 ",
            "cod_ine_mun": "03001", "email": " ZERO@GVA.ES ", "telefono": "0",
            "leyenda": "Entidad Local",
        })
        self.assertEqual(registros[1]["domici"], "")
        self.assertNotIn("ambito", registros[0])
        self.assertNotIn("codigo_postal", registros[0])

    def test_ejecucion_como_modulo_emite_json_utf8(self):
        resultado = subprocess.run(
            [sys.executable, "-B", "-m", "ong.extractores.extractor_cv", str(self.ruta)],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
            capture_output=True, check=True,
        )
        registros = json.loads(resultado.stdout.decode("utf-8"))
        self.assertEqual(registros[0]["nombre"], "  Centro, València 🏠  ")
        self.assertEqual(registros[0]["cod_ine_mun"], "03001")


if __name__ == "__main__":
    unittest.main()
