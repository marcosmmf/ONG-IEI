"""Pruebas de CV sin navegador, caché ni base de datos en disco."""
import unittest
from unittest.mock import Mock

from ong.comun.almacen import Almacen
from ong.comun.utm import utm_a_latlon
from ong.extractores.base import Extractor, Rechazo
from ong.extractores.extractor_cv import ExtractorCV, wrapper


class ExtractorCVTests(unittest.TestCase):
    def setUp(self):
        self.almacen = Almacen(":memory:")
        self.addCleanup(self.almacen.cerrar)
        self.geo = Mock()
        self.respuesta = {
            "cp": "46701", "localidad": "Gandia",
            "direccion": "Calle Mayor, 1, 46701 Gandia, Valencia, España",
            "lat": 38.967, "lon": -0.181,
        }
        self.geo.inverso.return_value = self.respuesta.copy()
        self.geo.directo.return_value = None
        self.extractor = ExtractorCV(self.almacen, self.geo)
        self.registro = {
            "id": "1508", "nombre": "Centro de prueba", "tipo_centro": "RESIDENCIA",
            "sector": "PERSONAS MAYORES", "leyenda": "Entidad Privada",
            "domici": "Calle Mayor, 1", "municipio": "Gandia", "cod_ine_mun": "46131",
            "x_25830": "744372", "y_25830": "4316940",
            "telefono": "0", "email": "zero@gva.es",
        }

    def test_carga_con_cp_descripcion_y_relacion_localidad(self):
        informe = self.extractor.cargar([self.registro])
        self.assertEqual(informe["cargados"], 1)
        fila = self.almacen.con.execute(
            "SELECT e.codigo_postal, e.descripcion, e.contacto, l.nombre, l.codigo "
            "FROM entidad e JOIN localidad l ON e.cod_localidad = l.codigo"
        ).fetchone()
        self.assertEqual(fila[:4], ("46701", "Entidad Privada - PERSONAS MAYORES", None, "Gandia"))
        self.assertNotEqual(fila[4], 46131)
        # La fuente no tiene CP: obtenerlo con Selenium no es una reparación
        self.assertEqual(informe["reparados"], [])
        self.assertEqual(informe["registros"][0]["completados"], {"codigo_postal": "Selenium"})
        self.geo.directo.assert_not_called()

    def test_recupera_direccion_vacia_y_la_informa(self):
        informe = self.extractor.cargar([{**self.registro, "domici": ""}])
        self.assertEqual(informe["cargados"], 1)
        campos = {r["campo"] for r in informe["reparados"][0]["reparaciones"]}
        self.assertEqual(campos, {"direccion"})

    def test_respuesta_solo_municipio_no_repara_direccion(self):
        for direccion in (None, "Gandia, Valencia, España", "46701 Gandia, España"):
            with self.subTest(direccion=direccion):
                self.geo.inverso.return_value = {**self.respuesta, "direccion": direccion}
                with self.assertRaisesRegex(Rechazo, "dirección verificable"):
                    self.extractor.transformar({**self.registro, "domici": ""})

    def test_rechaza_cp_ausente_malformado_o_de_otra_provincia(self):
        for cp in (None, "", "4670", "texto46701", "4670x", "03001"):
            with self.subTest(cp=cp):
                self.geo.inverso.return_value = {**self.respuesta, "cp": cp}
                self.geo.directo.return_value = {**self.respuesta, "cp": cp}
                with self.assertRaisesRegex(Rechazo, "código postal"):
                    self.extractor.transformar(self.registro)

    def test_directa_rechaza_resultado_de_otro_municipio(self):
        self.geo.inverso.return_value = None
        self.geo.directo.return_value = {**self.respuesta, "localidad": "Valencia"}
        with self.assertRaisesRegex(Rechazo, "localidad y provincia"):
            self.extractor.transformar(self.registro)

    def test_inversa_acepta_pedania_con_coordenadas_oficiales(self):
        # Selenium nombra la pedanía ("El Perelló") y no el municipio; el CP es de la provincia
        self.geo.inverso.return_value = {**self.respuesta, "localidad": "El Perelló", "cp": "46420"}
        entidad = self.extractor.transformar(self.registro)
        self.assertEqual(entidad["codigo_postal"], "46420")
        self.assertEqual(entidad["localidad"], "Gandia")
        self.geo.directo.assert_not_called()
        self.assertTrue(any("El Perelló" in i["motivo"] for i in self.extractor._incidencias))

    def test_inversa_de_otra_provincia_no_se_acepta(self):
        self.geo.inverso.return_value = {**self.respuesta, "localidad": "Alicante", "cp": "03001"}
        self.geo.directo.return_value = None
        with self.assertRaisesRegex(Rechazo, "código postal"):
            self.extractor.transformar(self.registro)

    def test_provincia_de_texto_distinta_del_ine_se_informa(self):
        self.extractor.transformar({**self.registro, "provincia": "Alacant/Alicante"})
        self.assertTrue(any(r["campo"] == "provincia" for r in self.extractor._reparaciones))
        self.extractor._reparaciones = []
        self.extractor.transformar({**self.registro, "provincia": "València/Valencia"})
        self.assertFalse(any(r["campo"] == "provincia" for r in self.extractor._reparaciones))

    def test_carretera_con_km_reintenta_sin_el_km(self):
        self.geo.inverso.return_value = None
        self.geo.directo.side_effect = [None, {**self.respuesta, "direccion": "Carretera del Pla, 46701 Gandia, España"}]
        entidad = self.extractor.transformar({**self.registro, "domici": "Carretera del Pla, Km 3"})
        self.assertEqual(entidad["codigo_postal"], "46701")
        self.assertEqual(self.geo.directo.call_args_list[1].args[0], "Carretera del Pla, Gandia, Valencia/València, España")
        self.assertTrue(any("aproximadas" in i["motivo"] for i in self.extractor._incidencias))

    def test_repara_coma_decimal_en_utm(self):
        entidad = self.extractor.transformar({**self.registro, "y_25830": self.registro["y_25830"] + ",00"})
        self.assertIsNotNone(entidad["latitud"])
        self.assertTrue(any(r["campo"] == "y_25830" for r in self.extractor._reparaciones))

    def test_admite_variantes_bilingues_y_acentos(self):
        self.geo.inverso.return_value = {**self.respuesta, "localidad": "Burriana", "cp": "12530"}
        entidad = self.extractor.transformar({**self.registro, "municipio": "Borriana/Burriana", "cod_ine_mun": "12032"})
        self.assertEqual(entidad["codigo_postal"], "12530")
        self.assertEqual(self.extractor._nombres("València"), self.extractor._nombres("Valencia"))

    def test_fallo_de_inversa_intenta_direccion_completa(self):
        self.geo.inverso.return_value = None
        self.geo.directo.return_value = self.respuesta.copy()
        entidad = self.extractor.transformar(self.registro)
        self.assertEqual(entidad["codigo_postal"], "46701")
        self.geo.directo.assert_called_once_with("Calle Mayor, 1, Gandia, Valencia/València, España")

    def test_respuesta_directa_solo_municipio_no_atribuye_cp_al_centro(self):
        self.geo.inverso.return_value = None
        self.geo.directo.return_value = {**self.respuesta, "direccion": "46701 Gandia, España"}
        with self.assertRaisesRegex(Rechazo, "solo identifica el municipio"):
            self.extractor.transformar(self.registro)

    def test_punto_generico_solo_usa_geocodificacion_directa(self):
        self.geo.directo.return_value = {**self.respuesta, "localidad": "Valencia", "cp": "46001", "lat": 39.47, "lon": -0.38}
        entidad = self.extractor.transformar({**self.registro, "municipio": "València", "cod_ine_mun": "46250",
                                             "x_25830": "725733", "y_25830": "4372816"})
        self.assertEqual((entidad["latitud"], entidad["longitud"]), (39.47, -0.38))
        self.assertEqual(entidad["codigo_postal"], "46001")
        self.geo.inverso.assert_not_called()

    def test_punto_generico_sin_direccion_se_rechaza_sin_consultas(self):
        with self.assertRaisesRegex(Rechazo, "dirección verificable"):
            self.extractor.transformar({**self.registro, "domici": "", "x_25830": "725733", "y_25830": "4372816"})
        self.geo.inverso.assert_not_called()
        self.geo.directo.assert_not_called()

    def test_no_acepta_el_punto_generico_devuelto_por_el_geocoder(self):
        lat, lon = utm_a_latlon(725733, 4372816)
        self.geo.directo.return_value = {**self.respuesta, "lat": lat, "lon": lon}
        with self.assertRaisesRegex(Rechazo, "punto genérico"):
            self.extractor.transformar({**self.registro, "x_25830": "725733", "y_25830": "4372816"})

    def test_utm_invalidas_se_recuperan_por_direccion(self):
        self.geo.directo.return_value = self.respuesta.copy()
        for x in (None, "", "NaN", "inf", "incorrecto", "1e300"):
            with self.subTest(x=x):
                entidad = self.extractor.transformar({**self.registro, "x_25830": x})
                self.assertEqual(entidad["latitud"], self.respuesta["lat"])
        self.geo.inverso.assert_not_called()

    def test_cp_valido_sin_coordenadas_se_rechaza_y_no_contamina_siguiente(self):
        # Indicación del profe: sin coordenadas se rechaza aunque haya CP.
        self.geo.directo.return_value = {**self.respuesta, "lat": None, "lon": None}
        informe = self.extractor.cargar([{**self.registro, "x_25830": None},
                                        {**self.registro, "id": "otro", "nombre": "Otro centro"}])
        self.assertEqual(informe["cargados"], 1)
        self.assertEqual(informe["rechazados"][0]["id_origen"], "1508")
        self.assertIn("coordenadas", informe["rechazados"][0]["motivo"])
        self.assertNotIn("incidencias", informe)
        self.assertEqual(self.almacen.con.execute(
            "SELECT count(*) FROM entidad WHERE latitud IS NULL").fetchone()[0], 0)

    def test_informe_rechazo_y_carga_continua_sin_insertar_cp_nulo(self):
        self.geo.inverso.side_effect = [None, self.respuesta.copy()]
        informe = self.extractor.cargar([self.registro, {**self.registro, "id": "otro", "nombre": "Otro centro"}])
        self.assertEqual((informe["cargados"], len(informe["rechazados"])), (1, 1))
        self.assertEqual(self.almacen.con.execute("SELECT count(*) FROM entidad WHERE codigo_postal IS NULL").fetchone()[0], 0)

    def test_validacion_final_no_permite_que_base_descarte_cp_y_cargue(self):
        entidad = self.extractor.transformar(self.registro)
        for cp in (None, "03001"):
            with self.subTest(cp=cp), self.assertRaisesRegex(Rechazo, "código postal"):
                self.extractor._validar({**entidad, "codigo_postal": cp})

    def test_clubs_se_cargan_como_inclusion_social_segun_sector(self):
        registro = {**self.registro, "tipo_centro": "CLUBS DE CONVIVENCIA", "email": None,
                    "sector": "POBLACIÓN EN GENERAL Y COLECTIVOS SOCIALMENTE DESFAVORECIDOS"}
        informe = self.extractor.cargar([registro])
        self.assertEqual(informe["cargados"], 1)
        ambito = self.almacen.con.execute(
            "SELECT a.nombre FROM entidad e JOIN ambito a ON e.ambito = a.id"
        ).fetchone()[0]
        self.assertEqual(ambito, "INCLUSION_SOCIAL")

    def test_clubs_reales_de_la_fuente_se_clasifican_por_sector(self):
        registros = [r for r in wrapper() if r["tipo_centro"] == "CLUBS DE CONVIVENCIA"]
        self.assertEqual(len(registros), 3)
        for registro in registros:
            with self.subTest(id_origen=registro["id"]):
                # CP simulado: comprobamos el ámbito, no la precisión geográfica.
                self.geo.inverso.return_value = {**self.respuesta, "cp": "03001",
                                                "localidad": registro["municipio"]}
                entidad = self.extractor.transformar(registro)
                self.assertEqual(entidad["ambito"], "INCLUSION_SOCIAL")

    def test_taller_prelaboral_conserva_prioridad_sobre_sector(self):
        entidad = self.extractor.transformar({**self.registro,
            "tipo_centro": "TALLER PRELABORAL DE INSERCIÓN SOCIAL",
            "sector": "POBLACIÓN EN GENERAL Y COLECTIVOS SOCIALMENTE DESFAVORECIDOS"})
        self.assertEqual(entidad["ambito"], "EMPLEO_E_INSERCION_LABORAL")

    def test_rechaza_sector_desconocido_incluso_para_clubs(self):
        with self.assertRaisesRegex(Rechazo, "sector sin correspondencia"):
            self.extractor.transformar({**self.registro, "tipo_centro": "CLUBS DE CONVIVENCIA",
                                        "sector": "DESCONOCIDO"})

    def test_limpieza_de_texto_y_duplicados_se_aplican_en_extractor(self):
        registro = {**self.registro, "nombre": "  Centro   de prueba  ",
                    "domici": " Calle   Mayor, 1 ", "municipio": " Gandia ",
                    "email": " ZERO@GVA.ES "}
        informe = self.extractor.cargar([registro, self.registro])
        self.assertEqual((informe["cargados"], informe["duplicados"]), (1, 1))
        self.assertEqual(self.almacen.con.execute(
            "SELECT nombre, direccion, contacto FROM entidad"
        ).fetchone(), ("Centro de prueba", "Calle Mayor, 1", None))

    def test_la_validacion_compartida_rechaza_sin_cp_o_sin_coordenadas(self):
        # Regla común a las 3 fuentes: sin CP o sin coordenadas no se carga.
        entidad = self.extractor.transformar(self.registro)
        otro = Extractor(self.almacen, self.geo)
        otro.FUENTE = "CAT"
        for cambio, motivo in (({"codigo_postal": None}, "código postal"),
                               ({"latitud": None, "longitud": None}, "coordenadas"),
                               ({"latitud": 60.0}, "fuera de España")):
            with self.subTest(cambio=cambio):
                otro.transformar = lambda registro, c=cambio: {**entidad, **c}
                informe = otro.cargar([{}])
                self.assertEqual(informe["cargados"], 0)
                self.assertIn(motivo, informe["rechazados"][0]["motivo"])


if __name__ == "__main__":
    unittest.main()
