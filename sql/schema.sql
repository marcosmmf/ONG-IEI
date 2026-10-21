-- =====================================================================
--  Almacén de datos - Buscador de ONGD (IEI 2026-27)
--  Dialecto: SQLite (lo usa el código). Versión PostgreSQL en schema_postgres.sql
--
--  Cambios respecto a la versión anterior:
--   * entidad.cod_entidad y localidad.codigo son AUTONUMÉRICOS (corrección del profesor:
--     "olvidarse de los códigos de entidad y localidad").
--   * provincia.codigo se mantiene: son los 2 primeros dígitos del CP / código INE,
--     y viene precargada con las 52 provincias (diccionario CP -> provincia).
--   * localidad: UNIQUE(nombre, cod_provincia) para no duplicar municipios.
--   * entidad.direccion NOT NULL (corrección CV: si falta se saca de las coordenadas).
--   * CHECKs de formato/rango (CP de 5 dígitos, lat/long válidas).
--   * UNIQUE(nombre, direccion, cod_localidad) para no duplicar entidades al recargar.
--   * Columna técnica 'fuente' (CV/CAT/CAN) para trazabilidad y borrar por fuente.
--   * Quitada la coma final que daba error de sintaxis.
-- =====================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS provincia (
    codigo  CHAR(2)      PRIMARY KEY CHECK (codigo GLOB '[0-9][0-9]'),
    nombre  VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS localidad (
    codigo         INTEGER      PRIMARY KEY AUTOINCREMENT,
    nombre         VARCHAR(150) NOT NULL,
    cod_provincia  CHAR(2)      NOT NULL REFERENCES provincia(codigo),
    UNIQUE (nombre, cod_provincia)
);

CREATE TABLE IF NOT EXISTS ambito (
    id      SMALLINT    PRIMARY KEY,
    nombre  VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entidad (
    cod_entidad    INTEGER      PRIMARY KEY AUTOINCREMENT,
    nombre         VARCHAR(250) NOT NULL,
    ambito         SMALLINT     NOT NULL REFERENCES ambito(id),
    direccion      VARCHAR(250) NOT NULL,
    codigo_postal  CHAR(5)      CHECK (codigo_postal GLOB '[0-9][0-9][0-9][0-9][0-9]'),
    longitud       NUMERIC(9,6) CHECK (longitud BETWEEN -180 AND 180),
    latitud        NUMERIC(9,6) CHECK (latitud  BETWEEN  -90 AND  90),
    descripcion    TEXT,
    contacto       VARCHAR(250),
    url            VARCHAR(500),
    cod_localidad  INTEGER      NOT NULL REFERENCES localidad(codigo),
    fuente         VARCHAR(3)   NOT NULL CHECK (fuente IN ('CV', 'CAT', 'CAN')),
    UNIQUE (nombre, direccion, cod_localidad)
);

CREATE INDEX IF NOT EXISTS idx_entidad_coord     ON entidad(latitud, longitud);  -- búsqueda por mapa
CREATE INDEX IF NOT EXISTS idx_entidad_cp        ON entidad(codigo_postal);
CREATE INDEX IF NOT EXISTS idx_entidad_ambito    ON entidad(ambito);
CREATE INDEX IF NOT EXISTS idx_entidad_localidad ON entidad(cod_localidad);
CREATE INDEX IF NOT EXISTS idx_localidad_nombre  ON localidad(nombre);

-- ---------------------------------------------------------------------
-- Datos fijos
-- ---------------------------------------------------------------------
INSERT OR IGNORE INTO ambito (id, nombre) VALUES
 (1,'MAYORES'),(2,'DISCAPACIDAD'),(3,'SALUD_MENTAL'),
 (4,'INFANCIA_Y_JUVENTUD'),(5,'MUJER'),(6,'MIGRACION'),
 (7,'INCLUSION_SOCIAL'),(8,'EDUCACION_Y_FORMACION'),
 (9,'EMPLEO_E_INSERCION_LABORAL'),
 (10,'SALUD_Y_ATENCION_SOCIOSANITARIA'),
 (11,'VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA'),
 (12,'CULTURA_Y_DESARROLLO_COMUNITARIO');

-- Diccionario de provincias (código INE = 2 primeros dígitos del CP)
INSERT OR IGNORE INTO provincia (codigo, nombre) VALUES
 ('01','Araba/Álava'),('02','Albacete'),('03','Alicante/Alacant'),('04','Almería'),
 ('05','Ávila'),('06','Badajoz'),('07','Illes Balears'),('08','Barcelona'),
 ('09','Burgos'),('10','Cáceres'),('11','Cádiz'),('12','Castellón/Castelló'),
 ('13','Ciudad Real'),('14','Córdoba'),('15','A Coruña'),('16','Cuenca'),
 ('17','Girona'),('18','Granada'),('19','Guadalajara'),('20','Gipuzkoa'),
 ('21','Huelva'),('22','Huesca'),('23','Jaén'),('24','León'),
 ('25','Lleida'),('26','La Rioja'),('27','Lugo'),('28','Madrid'),
 ('29','Málaga'),('30','Murcia'),('31','Navarra'),('32','Ourense'),
 ('33','Asturias'),('34','Palencia'),('35','Las Palmas'),('36','Pontevedra'),
 ('37','Salamanca'),('38','Santa Cruz de Tenerife'),('39','Cantabria'),('40','Segovia'),
 ('41','Sevilla'),('42','Soria'),('43','Tarragona'),('44','Teruel'),
 ('45','Toledo'),('46','Valencia/València'),('47','Valladolid'),('48','Bizkaia'),
 ('49','Zamora'),('50','Zaragoza'),('51','Ceuta'),('52','Melilla');
