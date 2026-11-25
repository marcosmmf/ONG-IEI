"""El wrapper cambia el formato sin aplicar el mapping de CV."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from servicios.wrapper_cv import convertir


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
        registros = convertir(self.ruta)
        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0], {
            "id": "24", "nombre": "  Centro, València 🏠  ", "domici": " Calle Mayor\n1 ",
            "cod_ine_mun": "03001", "email": " ZERO@GVA.ES ", "telefono": "0",
            "leyenda": "Entidad Local",
        })
        self.assertEqual(registros[1]["domici"], "")
        self.assertNotIn("ambito", registros[0])
        self.assertNotIn("codigo_postal", registros[0])

    def test_api_devuelve_el_json_del_fichero(self):
        from fastapi.testclient import TestClient
        from servicios import wrapper_cv
        with mock.patch.object(wrapper_cv, "convertir", wraps=convertir), \
                mock.patch("servicios.wrapper_base.fichero", return_value=self.ruta):
            respuesta = TestClient(wrapper_cv.app).get("/entidades")
        self.assertEqual(respuesta.status_code, 200)
        registros = respuesta.json()
        self.assertEqual(registros[0]["nombre"], "  Centro, València 🏠  ")
        self.assertEqual(registros[0]["cod_ine_mun"], "03001")

if __name__ == "__main__":
    unittest.main()
