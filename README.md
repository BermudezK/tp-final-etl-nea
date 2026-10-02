# Pipeline ETL de exportaciones del NEA

**TP Final — Unidad II · Fundamentos de la Programación**
Diplomatura en Data Analytics e IA Aplicada — UNNE / Extender
Autora: Karina Soledad Bermúdez

---

## Qué hace el pipeline

Descarga de la API de Series de Tiempo pública las exportaciones de las cuatro provincias del NEA (Chaco, Corrientes, Formosa y Misiones) entre 1993 y 2024, las transforma en un dataset analítico y lo valida antes de guardarlo.


**Extract** — pide a la API las series de exportaciones por país de destino
y por rubro de cada provincia, y guarda las respuestas en `data/raw/`.

**Transform** — convierte los datos del formato ancho de la API (una columna
por país) a formato largo (una fila por año, provincia y destino), y agrega
columnas:

- región geoeconómica del destino y década;
- participación del destino en el total exportado por la provincia ese año;
- variación interanual respecto del año anterior (mismo destino y provincia);
- ranking de destinos dentro de cada provincia y año, y marca de top 3;
- rubro principal del año y peso de los productos primarios, mediante un
  *left join* con las series por rubro.

**Load** — antes de guardar corre controles de calidad. Si falla uno
crítico, el pipeline se detiene y no publica nada:

| Control | Qué verifica | Si falla |
|---|---|---|
| Cantidad | Que haya al menos 1.000 filas | Corta |
| Columnas | Que todas las filas tengan las 13 columnas del contrato | Corta |
| Unicidad | Que no se repita la clave (provincia, año, destino) | Corta |
| Rangos | Que ningún valor sea negativo ni mayor a 10.000 M USD | Corta |
| Cobertura | Cuántos nulos quedaron en las columnas derivadas | Solo avisa |

Después genera tres salidas:

`data/processed/exportaciones_nea.csv` para el analisis
`data/processed/resumen.json` para los directivos, con los resumenes relevantes
`logs/pipeline.log` para hacer auditorias

El CSV y el JSON se sobrescriben en cada corrida (correrlo dos veces da el
mismo resultado); el log se acumula, porque es un historial que nos permite hacer auditorias.

Desde la carpeta raíz del proyecto:

```bash
python --version                     # verificar que sea 3.8+
python src/main.py                   # descarga los datos y corre todo
```

La primera corrida necesita internet. Después se puede trabajar sin
conexión, reutilizando lo que ya quedó en `data/raw/`:

```bash
python src/main.py --sin-internet
```

Para correr los tests de las transformaciones:

```bash
python tests/test_transform.py
```

### Estructura

```
├── config.py              IDs de series, rutas, mapeo de regiones y umbrales
├── src/
│   ├── extract.py         Descarga de la API -> data/raw/
│   ├── transform.py       Ancho -> largo, columnas derivadas y join
│   ├── load.py            Controles de calidad y escritura de las salidas
│   └── main.py            Orquesta Extract -> Transform -> Load
├── tests/
│   └── test_transform.py  Tests de las funciones del Transform
├── data/
│   ├── raw/               Respuestas crudas de la API
│   └── processed/         CSV y resumen JSON
└── logs/                  Historial de corridas
```

---

## De dónde salen los datos

Los datos son del **INDEC** y se obtienen a través de la
[API de Series de Tiempo](https://apis.datos.gob.ar/series/api/) del portal
de datos abiertos del Estado argentino (datos.gob.ar):

- **Dataset 357.1** — Exportaciones por provincia y por país de destino.
- **Dataset 350.1** — Exportaciones por provincia y por rubro: Productos
  primarios, MOA (Manufacturas de Origen Agropecuario), MOI (Manufacturas
  de Origen Industrial) y CyE (Combustibles y Energía).

Unidad: millones de dólares FOB. Frecuencia anual, de 1993 a 2024.

Para cada provincia la API publica los principales destinos por separado; el
resto de los países llega agrupado en una serie llamada **"Resto"**. Por eso
"Resto" aparece en el CSV como un destino más, pero lo excluí del top de
destinos del resumen: no es un país y no es comparable con los demás.

