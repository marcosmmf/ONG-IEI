"""Scraper de geolocalización con Selenium sobre https://www.coordenadas-gps.com

Sigue el esquema del T07 (Selenium WebDriver):
  (1) ir a la página  (2) localizar el elemento  (3) escribir / pulsar  (4) esperar y leer el resultado

- directo(direccion)  -> lat, lon, dirección formateada, CP, localidad   (Canarias, Catalunya)
- inverso(lat, lon)   -> dirección formateada, CP, localidad              (CV: CP y dirección que falta)

Todas las respuestas se guardan en cache/geocache.json: la web solo se consulta la
primera vez; las cargas siguientes (y la demo) salen de la caché.
"""
import json
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.coordenadas-gps.com/"
CACHE = Path(__file__).resolve().parents[2] / "cache" / "geocache.json"
ESPERA_MAX = 8          # segundos esperando a que la web responda
PAUSA = 1.0             # entre consultas, para no saturar la web


def parsear_direccion(texto):
    """'Calle X, 35019 Las Palmas de Gran Canaria, España' -> (CP, localidad)."""
    m = re.search(r"\b(\d{5})\b\s*([^,\d][^,]*)?", texto or "")
    if not m:
        return None, None
    localidad = (m.group(2) or "").strip() or None
    if localidad and localidad.lower() in ("españa", "spain"):
        localidad = None
    return m.group(1), localidad


class Geocoder:
    def __init__(self, usar_web=True, visible=False):
        self.usar_web = usar_web      # False -> solo caché (cargas rápidas para probar)
        self.visible = visible        # True  -> se ve el navegador trabajando
        self.driver = None
        self.consultas_web = 0
        try:
            self.cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self.cache = {}

    # ================================================================== API
    def directo(self, direccion):
        """Dirección -> coordenadas (botón 'Obtener Coordenadas GPS')."""
        return self._con_cache("D|" + direccion, lambda: self._buscar_coordenadas(direccion))

    def inverso(self, lat, lon):
        """Coordenadas -> dirección (botón 'Obtener Dirección')."""
        return self._con_cache(f"I|{lat:.6f},{lon:.6f}", lambda: self._buscar_direccion(lat, lon))

    def cerrar(self):
        self._guardar()
        if self.driver:
            self.driver.quit()
            self.driver = None

    # ============================================================ Selenium
    def _abrir(self):
        opciones = webdriver.ChromeOptions()
        if not self.visible:
            opciones.add_argument("--headless=new")
        opciones.add_argument("--window-size=1400,1000")
        opciones.add_argument("--no-sandbox")              # necesario en la VM Linux
        opciones.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=opciones)
        self.espera = WebDriverWait(self.driver, ESPERA_MAX)

        # (1) Ir a la página
        self.driver.get(URL)
        self._cerrar_banner_cookies()
        # La web solo crea su mapa cuando se ve en pantalla, y sin mapa no da resultados
        mapa = self.driver.find_element(By.ID, "map_canvas")
        self.driver.execute_script("arguments[0].scrollIntoView();", mapa)
        self.espera.until(lambda d: d.execute_script("return typeof gl_map !== 'undefined'"))

    def _cerrar_banner_cookies(self):
        """Rechaza las cookies no esenciales: 'Gestionar opciones' -> 'Confirmar opciones'."""
        try:
            WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.fc-cta-manage-options"))).click()
            WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.fc-confirm-choices"))).click()
        except TimeoutException:
            pass                                            # no ha salido el banner

    def _escribir(self, id_campo, texto):
        # (2) Localizar el elemento  (3) escribir en él
        campo = self.driver.find_element(By.ID, id_campo)
        campo.clear()
        campo.send_keys(texto)

    def _pulsar(self, texto_boton):
        # (2) Localizar el botón por su texto  (3) pulsarlo
        boton = self.driver.find_element(By.XPATH, f"//button[normalize-space()='{texto_boton}']")
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
        boton.click()

    def _esperar_respuesta(self, condicion):
        """(4) Esperar a que la web conteste. Si no encuentra nada saca un alert()."""
        try:
            self.espera.until(lambda d: EC.alert_is_present()(d) or condicion(d))
        except TimeoutException:
            return None
        try:
            self.driver.switch_to.alert.accept()            # "Error de geolocalización"
            return None
        except NoAlertPresentException:
            pass
        valor = lambda id_campo: self.driver.find_element(By.ID, id_campo).get_attribute("value")
        return {"lat": valor("latitude"), "lon": valor("longitude"), "direccion": valor("address")}

    def _buscar_coordenadas(self, direccion):
        self._escribir("latitude", "")                      # vacío: así sabemos cuándo llega la respuesta
        self._escribir("address", direccion)
        self._pulsar("Obtener Coordenadas GPS")
        valor = lambda d, i: d.find_element(By.ID, i).get_attribute("value")
        # La web reescribe el campo 'address' con la dirección completa (con CP) y rellena lat/long
        return self._esperar_respuesta(lambda d: valor(d, "latitude") and valor(d, "address") != direccion)

    def _buscar_direccion(self, lat, lon):
        self._escribir("latitude", f"{lat:.6f}")
        self._escribir("longitude", f"{lon:.6f}")
        self._escribir("address", "")
        self._pulsar("Obtener Dirección")
        return self._esperar_respuesta(lambda d: d.find_element(By.ID, "address").get_attribute("value"))

    # =============================================================== caché
    def _con_cache(self, clave, consulta):
        if clave not in self.cache:
            if not self.usar_web:
                return None
            try:
                if self.driver is None:
                    self._abrir()
                respuesta = consulta()
                self.consultas_web += 1
                time.sleep(PAUSA)
            except WebDriverException as e:                 # la web se cae o cambia: no se guarda
                print(f"   [geocoder] error: {e.__class__.__name__}: {str(e)[:120]}")
                return None
            self.cache[clave] = respuesta                   # None también se guarda: "no encontrado"
            self._guardar()
        return self._resultado(self.cache[clave])

    @staticmethod
    def _resultado(r):
        if not r or not r.get("lat"):
            return None
        cp, localidad = parsear_direccion(r["direccion"])
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "direccion": r["direccion"],
                "cp": cp, "localidad": localidad}

    def _guardar(self):
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
