# API IPS Cédulas — Consulta y Exportación

Este proyecto consulta documentos (cédulas, registro civil y tarjeta de identidad) en la API de Horus y exporta los resultados a CSV, con opción de unificar a Excel.

## Requisitos

- Python 3.11 (u otra versión compatible)
- Entorno virtual creado en `venv` con `requests` instalado
- Para exportar Excel: `openpyxl` (opcional; el script principal intentará usarlo)

## Archivos de entrada

- `Datos_utenticacion.txt`: Debe contener tus credenciales y opcionalmente un token.
  - Ejemplo mínimo:
    ```
    usuario: tu_correo@dominio.com
    contraseña: TuContraseñaExacta
    ```
  - Opcionalmente, puedes incluir un bloque `token: "JWT..."` copiado del navegador.
- `identificacion_codigos.txt`: Mapa de tipos de documento a código.
  - Ejemplo:
    ```
    cedula: 1
    tarjeta identidad: 2
    registro civil: 3
    ```
- Documentos a consultar (una identificación por línea):
  - `cedulas.txt`
  - `registrocivil.txt`
  - `tarjetasid.txt`

## Salidas

- CSV por cada archivo de entrada:
  - `cedulas.csv`
  - `registrocivil.csv`
  - `tarjetasid.csv`
- Columnas CSV:
  - `cedula`, `tipo_documento_codigo`, `tipo_documento_nombre`, `estado`, `estado_afiliado`, `ips_nombre`, `mensaje`, `http_status`
- Unificación automática (al finalizar la ejecución):
  - `unificado.csv`
  - `unificado.xlsx` (si `openpyxl` está instalado)

## Cómo ejecutar

1) Preparar entradas
- Llena `Datos_utenticacion.txt` con `usuario` y `contraseña` (y opcionalmente `token`).
- Revisa `identificacion_codigos.txt` tiene los códigos correctos.
- Agrega los números en `cedulas.txt`, `registrocivil.txt`, y/o `tarjetasid.txt`.

2) Ejecutar consultas
- En Windows (PowerShell) desde el directorio del proyecto:
  ```powershell
  .\venv\Scripts\python.exe cedulas.py
  ```
- El script:
  - Obtiene token automáticamente (leyendo del archivo o logueando con `usuario`/`contraseña`).
  - Procesa en orden: `cedulas.txt` → `registrocivil.txt` → `tarjetasid.txt`.
  - Exporta `cedulas.csv`, `registrocivil.csv`, `tarjetasid.csv`.
  - Si el token vence, lo renueva y reintenta la consulta.
  - Al finalizar, unifica automáticamente y genera `unificado.csv` y `unificado.xlsx`.

3) Script alternativo de unificación (opcional)
- Si prefieres ejecutar la unificación por separado, usa:
  ```powershell
  .\venv\Scripts\python.exe -m pip install openpyxl
  .\venv\Scripts\python.exe unificar_csv_excel.py
  ```
  Generará `unificado.csv` y `unificado.xlsx`.

## Detalles técnicos

- Endpoint login: `https://backend.horus-health.com/api/auth/validar-usuario`
- Consulta afiliado: `https://backend.horus-health.com/api/afiliados/consultar-afiliado/{documento}/{tipo}`
- Cabeceras de login incluyen `Origin` y `Referer` para emular el navegador.
- Respeta límite de tasa con una pausa breve entre consultas.

## Solución de problemas

- “No fue posible obtener token”: Revisa `Datos_utenticacion.txt` (correo/contraseña exactos). Si el sitio requiere token del navegador, incluye el bloque `token`.
- CSV “archivo en uso”: Si un CSV está abierto, el script guarda un alterno con timestamp (ej. `cedulas_1730000000.csv`).
- Códigos de documento incorrectos: Verifica `identificacion_codigos.txt`.
- Respuestas 401: El script intenta renovar el token y reintenta automáticamente.

## Seguridad

- No subas credenciales ni tokens reales a GitHub.
- Añade a tu `.gitignore` los archivos sensibles (`Datos_utenticacion.txt`, CSVs con datos personales).

### Ejemplo `.gitignore`

```
# Archivos sensibles
Datos_utenticacion.txt

# Archivos de datos generados
*.csv
unificado.xlsx

# Entorno virtual
venv/
```

## Estructura

- `cedulas.py`: consultas a la API, selección de archivo/`DOC_TYPE`, exportación CSV.
- `unificar_csv_excel.py`: unión de CSVs y exportación a Excel.
- Archivos `.txt`: insumos (credenciales, mapas y listas de documentos).

## Ejemplo rápido

```powershell
# Ejecutar consultas
echo 1044918053 > cedulas.txt
.\venv\Scripts\python.exe cedulas.py

# Unificación se genera automáticamente al terminar
```
