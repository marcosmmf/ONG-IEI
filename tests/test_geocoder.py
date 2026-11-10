"""Gestión de caché y fallos temporales sin abrir Chrome ni consultar la web."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException

from ong.comun.geocoder import Geocoder


class GeocoderTests(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.cache = Path(temporal.name) / "cache" / "geocache.json"
        parche_cache = patch("ong.comun.geocoder.CACHE", self.cache)
        parche_cache.start()
        self.addCleanup(parche_cache.stop)
        parche_pausa = patch("ong.comun.geocoder.time.sleep")
        parche_pausa.start()
        self.addCleanup(parche_pausa.stop)
        self.respuesta = {"lat": "38.027297", "lon": "-0.743485",
                          "direccion": "Plaza del Sagrado Corazón, 7, 03187 Los Montesinos, España"}

    def geocoder(self, usar_web=True):
        geo = Geocoder(usar_web=usar_web)
        geo._abrir = Mock(side_effect=lambda: setattr(geo, "driver", Mock()))
        return geo

    def test_respuesta_correcta_se_guarda_y_se_reutiliza(self):
        geo = self.geocoder()
        consulta = Mock(return_value=self.respuesta)
        primero = geo._con_cache("I|prueba", consulta)
        segundo = geo._con_cache("I|prueba", consulta)
        self.assertEqual(primero, segundo)
        self.assertEqual(primero["cp"], "03187")
        consulta.assert_called_once()
        self.assertEqual(json.loads(self.cache.read_text(encoding="utf-8"))["I|prueba"], self.respuesta)

    def test_null_antiguo_se_reintenta_sin_perder_respuestas_validas(self):
        geo = self.geocoder()
        geo.cache = {"I|fallida": None, "I|valida": self.respuesta.copy()}
        consulta = Mock(return_value=self.respuesta)
        self.assertEqual(geo._con_cache("I|fallida", consulta)["cp"], "03187")
        consulta.assert_called_once()
        self.assertEqual(geo.cache["I|valida"], self.respuesta)
        self.assertEqual(geo.cache["I|fallida"], self.respuesta)

    def test_modo_solo_cache_no_abre_navegador_para_null_o_ausente(self):
        geo = self.geocoder(usar_web=False)
        geo.cache = {"I|fallida": None}
        consulta = Mock()
        self.assertIsNone(geo._con_cache("I|fallida", consulta))
        self.assertIsNone(geo._con_cache("I|ausente", consulta))
        geo._abrir.assert_not_called()
        consulta.assert_not_called()

    def test_modo_solo_cache_reutiliza_respuesta_valida(self):
        geo = self.geocoder(usar_web=False)
        geo.cache = {"I|prueba": self.respuesta.copy()}
        consulta = Mock()
        self.assertEqual(geo._con_cache("I|prueba", consulta)["cp"], "03187")
        consulta.assert_not_called()
        geo._abrir.assert_not_called()

    def test_respuesta_vacia_no_se_guarda_y_puede_reintentarse(self):
        geo = self.geocoder()
        consulta = Mock(side_effect=[None, self.respuesta])
        self.assertIsNone(geo._con_cache("I|prueba", consulta))
        self.assertNotIn("I|prueba", geo.cache)
        self.assertFalse(self.cache.exists())
        self.assertEqual(geo._con_cache("I|prueba", consulta)["cp"], "03187")

    def test_timeout_de_inicio_cierra_navegador_y_reintenta(self):
        geo = self.geocoder()
        navegador_fallido = Mock()

        def abrir_con_fallo():
            geo.driver = navegador_fallido
            raise TimeoutException("mapa lento")

        def abrir_correcto():
            geo.driver = Mock()

        aperturas = iter([abrir_con_fallo, abrir_correcto])
        geo._abrir.side_effect = lambda: next(aperturas)()
        consulta = Mock(return_value=self.respuesta)
        self.assertEqual(geo._con_cache("I|prueba", consulta)["cp"], "03187")
        navegador_fallido.quit.assert_called_once()
        self.assertEqual(geo._abrir.call_count, 2)
        consulta.assert_called_once()

    def test_timeout_de_consulta_reinicia_navegador_antes_de_reintentar(self):
        geo = self.geocoder()
        navegador_fallido = Mock()
        geo.driver = navegador_fallido
        consulta = Mock(side_effect=[TimeoutException("respuesta lenta"), self.respuesta])
        self.assertEqual(geo._con_cache("I|prueba", consulta)["cp"], "03187")
        navegador_fallido.quit.assert_called_once()
        geo._abrir.assert_called_once()
        self.assertEqual(consulta.call_count, 2)

    def test_timeouts_persistentes_no_se_guardan_en_cache(self):
        geo = self.geocoder()
        consulta = Mock(side_effect=TimeoutException("sin respuesta"))
        self.assertIsNone(geo._con_cache("I|prueba", consulta))
        self.assertEqual(consulta.call_count, 2)
        self.assertIsNone(geo.driver)
        self.assertFalse(self.cache.exists())

    def test_espera_propaga_timeout_para_activar_reintento(self):
        geo = self.geocoder()
        geo.espera = Mock()
        geo.espera.until.side_effect = TimeoutException("respuesta lenta")
        with self.assertRaises(TimeoutException):
            geo._esperar_respuesta(lambda driver: False)

    def test_respuestas_malformadas_no_se_guardan(self):
        for respuesta in (None, {}, {**self.respuesta, "lat": "NaN"},
                          {**self.respuesta, "lon": None}, {**self.respuesta, "lat": "texto"}):
            with self.subTest(respuesta=respuesta):
                geo = self.geocoder()
                self.assertIsNone(geo._con_cache("I|prueba", Mock(return_value=respuesta)))
                self.assertNotIn("I|prueba", geo.cache)

    def test_consulta_directa_admite_direccion_sin_cambios(self):
        geo = self.geocoder()
        direccion = self.respuesta["direccion"]
        valores = {"latitude": "38.027297", "longitude": "-0.743485", "address": direccion}
        geo.driver = Mock()
        geo.driver.find_element.side_effect = lambda by, campo: Mock(get_attribute=lambda _: valores[campo])
        geo._escribir = Mock()
        geo._pulsar = Mock()
        geo._esperar_respuesta = Mock(side_effect=lambda condicion: bool(condicion(geo.driver)))
        self.assertTrue(geo._buscar_coordenadas(direccion))
        geo._escribir.assert_any_call("latitude", "")
        geo._escribir.assert_any_call("longitude", "")


if __name__ == "__main__":
    unittest.main()
