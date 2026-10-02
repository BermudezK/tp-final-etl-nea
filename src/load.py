"""
LOAD — Quality checks y persistencia   *** PARCIALMENTE RESUELTO ***
=====================================================================

Dos responsabilidades, en este orden:

  1. CHEQUEAR: validar el dataset antes de publicarlo. Si algo crítico
     falla, cortamos: mejor no entregar nada que entregar un reporte roto.
  2. GUARDAR: escribir el CSV (para personas), el resumen JSON (para
     programas) y el log (para auditar).

Te dejamos resuelto el guardado del CSV y dos de los quality checks.
Faltan 4 TODOs (9 a 12), todos cortos.

Idempotencia: el CSV y el JSON van en modo "w", así que correr el pipeline
dos veces deja el mismo resultado. El log va en modo "a" porque un log ES
un historial: ahí sí queremos que crezca.
"""

import csv
import json
import logging
import os
from datetime import datetime

import config
from transform import COLUMNAS


# ======================================================================
# QUALITY CHECKS
# ======================================================================
def chequear_cantidad(filas, minimo=None):
    """¿Tenemos todas las filas que esperábamos?  [RESUELTO — de ejemplo]

    Fijate el patrón: devuelve una tupla (bool, mensaje). Todos los
    checks tienen que devolver lo mismo para que validar() los trate igual.
    """
    if minimo is None:
        minimo = config.MINIMO_FILAS_ESPERADAS
    ok = len(filas) >= minimo
    return ok, f"cantidad: {len(filas)} filas (mínimo esperado {minimo})"


def chequear_columnas(filas):
    """¿Todas las filas tienen exactamente las columnas del contrato?
    [RESUELTO — de ejemplo]
    """
    esperadas = set(COLUMNAS)
    for fila in filas:
        if set(fila.keys()) != esperadas:
            faltan = esperadas - set(fila.keys())
            return False, f"columnas: una fila no cumple el esquema (faltan {faltan})"
    return True, f"columnas: las {len(COLUMNAS)} del contrato en todas las filas"


def chequear_unicidad(filas):
    """¿Hay duplicados? La clave del dataset es (provincia, anio, destino).

    Debe devolver (bool, mensaje), igual que los checks de arriba.
    """
    # TODO 9 --------------------------------------------------------------
    # Pista: es el patrón del set que viste en la Clase 3. Armá la lista de
    # claves (una tupla por fila) y compará len(lista) con len(set(lista)).
    # ---------------------------------------------------------------------
    seen = set()
    for fila in filas:
        clave = (fila["provincia"], fila["anio"], fila["destino"])
        if clave in seen:
            return False, f"unicidad: fila duplicada {clave}"
        seen.add(clave)
    return True, f"unicidad: todas las filas son únicas"


def chequear_rangos(filas):
    """¿Los valores son plausibles?

    Un valor negativo o mayor a config.VALOR_MAXIMO_RAZONABLE es
    sospechoso: no existen exportaciones negativas.
    """
    # TODO 10 -------------------------------------------------------------
    # Pista: una comprensión de lista con la condición al final te da
    # directamente las filas fuera de rango; después mirás cuántas son.
    # ---------------------------------------------------------------------
    fuera_de_rango = [
        f for f in filas
        if f["valor_musd"] is not None and
           (f["valor_musd"] < 0 or f["valor_musd"] > config.VALOR_MAXIMO_RAZONABLE)
    ]
    ok = len(fuera_de_rango) == 0
    return ok, f"rangos: {len(fuera_de_rango)} filas fuera de rango (valor_musd < 0 o > {config.VALOR_MAXIMO_RAZONABLE})"   


def chequear_cobertura(filas):
    """Advertencia (no crítica): ¿cuántos nulos quedaron en las derivadas?
    [RESUELTO]
    """
    sin_variacion = sum(1 for f in filas if f["var_interanual_pct"] is None)
    sin_rubro = sum(1 for f in filas if f["rubro_principal"] is None)
    ok = sin_rubro == 0
    return ok, (f"cobertura: {sin_variacion} filas sin variación interanual "
                f"(esperable en el primer año), {sin_rubro} sin rubro")


def validar(filas):
    """Corre todos los checks.  [RESUELTO]

    Los CRÍTICOS cortan el pipeline lanzando una excepción ("fallar
    temprano y ruidosamente"). La cobertura solo deja una advertencia.

    Retorna una lista de dicts con el detalle, para el resumen JSON.
    """
    criticos = [
        chequear_cantidad(filas),
        chequear_columnas(filas),
        chequear_unicidad(filas),
        chequear_rangos(filas),
    ]

    detalle = []
    for ok, mensaje in criticos:
        detalle.append({"check": mensaje, "estado": "OK" if ok else "FALLO"})
        if ok:
            logging.info("  check OK    | %s", mensaje)
        else:
            logging.error("  check FALLO | %s", mensaje)
            raise ValueError(f"Quality check crítico falló -> {mensaje}")

    ok, mensaje = chequear_cobertura(filas)
    detalle.append({"check": mensaje, "estado": "OK" if ok else "AVISO"})
    if ok:
        logging.info("  check OK    | %s", mensaje)
    else:
        logging.warning("  check AVISO | %s", mensaje)

    return detalle


# ======================================================================
# PERSISTENCIA
# ======================================================================
def guardar_csv(filas, carpeta=None, nombre=None):
    """Escribe el dataset final. Modo 'w': cada corrida lo reemplaza.
    [RESUELTO — usalo de modelo para el resto]
    """
    carpeta = carpeta or config.DIR_PROCESSED
    nombre = nombre or config.ARCHIVO_SALIDA_CSV
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)

    logging.info("  CSV: %s (%s filas)", ruta, len(filas))
    return ruta


def construir_resumen(filas, detalle_checks):
    """Arma el resumen del proceso: metadatos + estadísticas descriptivas.

    Este JSON es la "ficha técnica" del dataset: quien lo reciba tiene que
    poder saber de dónde salió, cuándo y qué contiene, SIN abrir el CSV.

    CONTRATO: devolvé un dict que incluya al menos estas claves:

        dataset            (str)  nombre descriptivo
        fuente             (str)  de dónde salieron los datos
        unidad             (str)  "millones de dólares FOB"
        generado           (str)  fecha y hora de esta corrida
        filas              (int)
        columnas           (int)
        periodo            (dict) {"desde": anio_min, "hasta": anio_max}
        provincias         (list) ordenada
        valor_musd         (dict) {"minimo":…, "maximo":…, "promedio":…}
        quality_checks     (list) el detalle_checks que recibís
    """
    # TODO 11 -------------------------------------------------------------
    # Pistas:
    #   - Para la lista de valores: [f["valor_musd"] for f in filas]
    #   - min(), max() y sum()/len() ya los conocés.
    #   - Para provincias únicas y ordenadas: sorted({f["provincia"] for f in filas})
    #   - Para la fecha: datetime.now().strftime("%Y-%m-%d %H:%M")
    #   - Podés agregar más claves si querés (suma puntos en la rúbrica).
    # ---------------------------------------------------------------------

    # Totales acumulados del período. Se suma valor_musd (no
    # total_provincia_musd, que se repite en cada destino del mismo año).
    total_por_provincia = {}
    total_por_destino = {}
    for f in filas:
        total_por_provincia[f["provincia"]] = total_por_provincia.get(f["provincia"], 0) + f["valor_musd"]
        total_por_destino[f["destino"]] = total_por_destino.get(f["destino"], 0) + f["valor_musd"]

    # "Resto" agrupa a todos los países sin serie propia: no es un destino
    # comparable, así que queda fuera del top (pero sí suma en los totales).
    total_por_destino.pop("Resto", None)
    destinos_ordenados = sorted(total_por_destino.items(), key=lambda par: par[1], reverse=True)
    top_destinos = [
        {"destino": destino, "total_musd": round(total, 2)}
        for destino, total in destinos_ordenados[:config.TOP_DESTINOS_RESUMEN]
    ]

    return {
        "dataset": "Exportaciones argentinas por provincia y destino",
        "fuente": "INDEC vía la API de Series de Tiempo https://apis.datos.gob.ar/series/api/ de datos.gob.ar (datasets 357.1 y 350.1)",
        "unidad": "millones de dólares FOB",
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filas": len(filas),
        "columnas": len(COLUMNAS),
        "periodo": {
            "desde": min(f["anio"] for f in filas),
            "hasta": max(f["anio"] for f in filas)
        },
        "provincias": sorted({f["provincia"] for f in filas}),
        "valor_musd": {
            "minimo": min(f["valor_musd"] for f in filas if f["valor_musd"] is not None),
            "maximo": max(f["valor_musd"] for f in filas if f["valor_musd"] is not None),
            "promedio": round(sum(f["valor_musd"] for f in filas if f["valor_musd"] is not None) / len([f for f in filas if f["valor_musd"] is not None]), 2)
        },
        "total_por_provincia": {
            provincia: round(total, 2)
            for provincia, total in sorted(total_por_provincia.items())
        },
        "top_destinos": top_destinos,
        "quality_checks": detalle_checks
    }   


def guardar_resumen(resumen, carpeta=None, nombre=None):
    """Escribe el resumen en JSON, legible por humanos y por programas.

    Acordate de los dos argumentos que vimos: ensure_ascii=False para que
    las tildes se guarden bien, e indent=2 para que sea legible.
    """
    # TODO 12a ------------------------------------------------------------
    # Muy parecido a guardar_csv(), pero con json.dump().
    raise NotImplementedError("TODO 12a: implementá guardar_resumen()")
    # ---------------------------------------------------------------------


def escribir_log_corrida(resumen, carpeta=None, nombre=None):
    """Agrega UNA línea al historial del pipeline.

    Modo "a" (append): nunca borra lo anterior. Cada corrida deja su rastro.
    Sugerencia de formato:

        2026-08-02 14:30 | OK | 1408 filas | 1993-2024
    """
    # TODO 12b ------------------------------------------------------------
    raise NotImplementedError("TODO 12b: implementá escribir_log_corrida()")
    # ---------------------------------------------------------------------


def cargar(filas):
    """CONTRATO: recibe las filas finales; valida y persiste las 3 salidas.
    [RESUELTO]
    """
    logging.info("LOAD: validando")
    detalle = validar(filas)

    logging.info("LOAD: guardando")
    guardar_csv(filas)
    resumen = construir_resumen(filas, detalle)
    guardar_resumen(resumen)
    escribir_log_corrida(resumen)

    logging.info("LOAD OK")
    return resumen
