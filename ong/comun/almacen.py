"""Acceso al almacén de datos (SQLite).

Es lo único que sabe SQL: los extractores solo llaman a insertar_entidad().
"""
import sqlite3
from pathlib import Path

from ong.comun.normalizar import sin_tildes

RAIZ = Path(__file__).resolve().parents[2]
BD = RAIZ / "almacen.db"
ESQUEMA = RAIZ / "sql" / "schema.sql"


class Almacen:
    def __init__(self, ruta=BD):
        self.con = sqlite3.connect(ruta)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA.read_text(encoding="utf-8"))
        self.ambitos = {nombre: id_ for id_, nombre in self.con.execute("SELECT id, nombre FROM ambito")}
        self.provincias = dict(self.con.execute("SELECT codigo, nombre FROM provincia"))

    def borrar(self, fuente=None):
        """Borra las entidades (de una fuente o todas) y las localidades que quedan huérfanas."""
        if fuente:
            self.con.execute("DELETE FROM entidad WHERE fuente = ?", (fuente,))
        else:
            self.con.execute("DELETE FROM entidad")
        self.con.execute("DELETE FROM localidad WHERE codigo NOT IN (SELECT cod_localidad FROM entidad)")
        self.con.commit()

    def localidad(self, nombre, cod_provincia):
        """Devuelve el código (autonumérico) de la localidad, creándola si no existe.
        Compara sin tildes ni mayúsculas: 'Valencia' (CAN) es la misma que 'València' (CV)."""
        for codigo, existente in self.con.execute("SELECT codigo, nombre FROM localidad WHERE cod_provincia = ?",
                                                  (cod_provincia,)):
            if sin_tildes(existente) == sin_tildes(nombre):
                return codigo
        return self.con.execute("INSERT INTO localidad (nombre, cod_provincia) VALUES (?, ?)",
                                (nombre, cod_provincia)).lastrowid

    def insertar_entidad(self, e, fuente):
        """Inserta la entidad (dict con los campos del esquema global).
        Devuelve False si ya existía (mismo nombre, dirección y localidad)."""
        cod_localidad = self.localidad(e["localidad"], e["cod_provincia"])
        cur = self.con.execute(
            """INSERT OR IGNORE INTO entidad
               (nombre, ambito, direccion, codigo_postal, longitud, latitud,
                descripcion, contacto, url, cod_localidad, fuente)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (e["nombre"], self.ambitos[e["ambito"]], e["direccion"], e.get("codigo_postal"),
             e.get("longitud"), e.get("latitud"), e.get("descripcion"), e.get("contacto"),
             e.get("url"), cod_localidad, fuente))
        return cur.rowcount == 1

    def commit(self):
        self.con.commit()

    def cerrar(self):
        self.con.commit()
        self.con.close()
