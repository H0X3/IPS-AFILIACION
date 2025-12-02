#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import csv
import re
import requests
from typing import List, Dict, Optional

# ==============================
# CONFIGURACIÓN
# ==============================

BASE_URL = "https://backend.horus-health.com/api/afiliados/consultar-afiliado"
AUTH_URL = "https://backend.horus-health.com/api/auth/validar-usuario"
DOC_TYPE = "1"  # 1 = Cédula, (probablemente 2 = TI u otro tipo)
CEDULAS_FILE = "cedulas.txt"
SALIDA_CSV = "resultado_afiliados.csv"

TOKEN = os.environ.get("HORUS_TOKEN")
AUTH_FILE = "Datos_utenticacion.txt"
CREDS = None
DOC_TYPE_MAP_FILE = "identificacion_codigos.txt"
DOC_TYPE_MAP = {}
DOC_TYPE_REVERSE = {}

# Límite: el servidor indica X-RateLimit-Limit: 60
# Por seguridad, ponemos una pequeña pausa entre requests.
PAUSA_SEGUNDOS = 0.2  # 5 por segundo aprox. (300/min)
PREFERRED_COLUMNS = [
    "cedula",
    "tipo_documento_codigo",
    "tipo_documento_nombre",
    "estado",
    "estado_afiliado",
    "ips_nombre",
    "mensaje",
    "http_status",
]


# ==============================
# FUNCIONES AUXILIARES
# ==============================

def cargar_cedulas(path: str) -> List[str]:
    cedulas = []
    with open(path, "r", encoding="utf-8") as f:
        for linea in f:
            ced = linea.strip()
            if not ced:
                continue
            cedulas.append(ced)
    return cedulas


def consultar_afiliado(cedula: str,
                       doc_type: str = DOC_TYPE,
                       token: Optional[str] = None) -> Dict[str, str]:
    """
    Consulta un afiliado por cédula.
    Devuelve un dict con:
        cedula, estado, mensaje, http_status
    """
    if token is None:
        token = _ensure_token(False)

    url = f"{BASE_URL}/{cedula}/{doc_type}"
    headers = {"Accept": "application/json, text/plain, */*"}
    if token:
        auth_value = token if isinstance(token, str) and token.lower().startswith("bearer ") else f"Bearer {token}"
        headers["Authorization"] = auth_value

    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as e:
        return {
            "cedula": cedula,
            "estado": "ERROR_REQUEST",
            "mensaje": f"Error de red: {e}",
            "http_status": ""
        }

    status_code = resp.status_code

    # Intentar interpretar el cuerpo como JSON (puede fallar)
    try:
        data = resp.json()
    except ValueError:
        data = None

    # Caso típico: afiliado NO encontrado
    # {"error":"El afiliado no se encuentra registrado en la base de datos!"}
    if status_code == 404:
        mensaje = ""
        if isinstance(data, dict):
            mensaje = data.get("error", "")
        if not mensaje:
            mensaje = "No encontrado (HTTP 404)"
        return {
            "cedula": cedula,
            "estado": "NO_REGISTRADO",
            "mensaje": mensaje,
            "http_status": str(status_code),
        }

    # Si viene "error" en el JSON, aunque sea 200, lo marcamos como NO_REGISTRADO
    if isinstance(data, dict) and "error" in data:
        return {
            "cedula": cedula,
            "estado": "NO_REGISTRADO",
            "mensaje": data.get("error", ""),
            "http_status": str(status_code),
        }

    # Si es 200 sin "error", extraemos detalles
    if status_code == 200:
        estado_afiliado_nombre = ""
        ips_nombre = ""
        if isinstance(data, dict):
            est = data.get("estado_afiliado") or data.get("estadoAfiliado")
            if isinstance(est, dict):
                estado_afiliado_nombre = str(est.get("nombre", ""))
            ips = data.get("ips") or data.get("prestador")
            if isinstance(ips, dict):
                ips_nombre = str(ips.get("nombre", ""))
        return {
            "cedula": cedula,
            "tipo_documento_codigo": str(doc_type),
            "tipo_documento_nombre": DOC_TYPE_REVERSE.get(str(doc_type), ""),
            "estado": "REGISTRADO",
            "estado_afiliado": estado_afiliado_nombre,
            "ips_nombre": ips_nombre,
            "mensaje": "Afiliado encontrado",
            "http_status": str(status_code),
        }

    if status_code == 401:
        mensaje = "No autorizado"
        if isinstance(data, dict):
            mensaje = data.get("message", mensaje) or mensaje
        new_tok = _ensure_token(True)
        if new_tok:
            auth_value = new_tok if new_tok.lower().startswith("bearer ") else f"Bearer {new_tok}"
            headers["Authorization"] = auth_value
            try:
                retry = requests.get(url, headers=headers, timeout=15)
                status_code = retry.status_code
                try:
                    data = retry.json()
                except ValueError:
                    data = None
            except requests.RequestException:
                pass
            if status_code == 200 and not (isinstance(data, dict) and "error" in data):
                estado_afiliado_nombre = ""
                ips_nombre = ""
                if isinstance(data, dict):
                    est = data.get("estado_afiliado") or data.get("estadoAfiliado")
                    if isinstance(est, dict):
                        estado_afiliado_nombre = str(est.get("nombre", ""))
                    ips = data.get("ips") or data.get("prestador")
                    if isinstance(ips, dict):
                        ips_nombre = str(ips.get("nombre", ""))
                return {
                    "cedula": cedula,
                    "tipo_documento_codigo": str(doc_type),
                    "tipo_documento_nombre": DOC_TYPE_REVERSE.get(str(doc_type), ""),
                    "estado": "REGISTRADO",
                    "estado_afiliado": estado_afiliado_nombre,
                    "ips_nombre": ips_nombre,
                    "mensaje": "Afiliado encontrado",
                    "http_status": str(status_code),
                }
            if status_code == 404:
                men = ""
                if isinstance(data, dict):
                    men = data.get("error", "")
                if not men:
                    men = "No encontrado (HTTP 404)"
                return {
                    "cedula": cedula,
                    "tipo_documento_codigo": str(doc_type),
                    "tipo_documento_nombre": DOC_TYPE_REVERSE.get(str(doc_type), ""),
                    "estado": "NO_REGISTRADO",
                    "estado_afiliado": "",
                    "ips_nombre": "",
                    "mensaje": men,
                    "http_status": str(status_code),
                }
        return {
            "cedula": cedula,
            "tipo_documento_codigo": str(doc_type),
            "tipo_documento_nombre": DOC_TYPE_REVERSE.get(str(doc_type), ""),
            "estado": "NO_AUTORIZADO",
            "estado_afiliado": "",
            "ips_nombre": "",
            "mensaje": mensaje,
            "http_status": str(status_code),
        }
    # Otros códigos (403, 500, 429, etc.)
    return {
        "cedula": cedula,
        "tipo_documento_codigo": str(doc_type),
        "tipo_documento_nombre": DOC_TYPE_REVERSE.get(str(doc_type), ""),
        "estado": "ERROR_HTTP",
        "estado_afiliado": "",
        "ips_nombre": "",
        "mensaje": f"HTTP {status_code}",
        "http_status": str(status_code),
    }


def guardar_csv(resultados: List[Dict[str, str]], path: str) -> None:
    campos = [
        "cedula",
        "tipo_documento_codigo",
        "tipo_documento_nombre",
        "estado",
        "estado_afiliado",
        "ips_nombre",
        "mensaje",
        "http_status",
    ]
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            for fila in resultados or []:
                writer.writerow(fila)
    except PermissionError:
        base, ext = os.path.splitext(path)
        alt = f"{base}_{int(time.time())}{ext or '.csv'}"
        with open(alt, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            for fila in resultados or []:
                writer.writerow(fila)
        print(f"Archivo en uso. Guardado en: {alt}")


def _get_credentials() -> Optional[Dict[str, str]]:
    global CREDS
    if CREDS:
        return CREDS
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            contenido = f.read()
        m_email = re.search(r'["\']([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})["\']', contenido)
        if not m_email:
            m_email = re.search(r'usuario\s*:\s*([^\r\n]+)', contenido, flags=re.IGNORECASE)
        email = m_email.group(1).strip() if m_email else None
        m_pwd = re.search(r'password\s*:\s*["\']([^"\']+)["\']', contenido, flags=re.IGNORECASE)
        if not m_pwd:
            m_pwd = re.search(r'contraseña\s*:\s*([^\r\n]+)', contenido, flags=re.IGNORECASE)
        password = m_pwd.group(1).strip() if m_pwd else None
        if email and password:
            CREDS = {"email": email, "password": password}
            return CREDS
    except FileNotFoundError:
        pass
    return None


def _login_get_token(creds: Dict[str, str]) -> Optional[str]:
    try:
        resp = requests.post(
            AUTH_URL,
            json={"email": creds["email"], "password": creds["password"]},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://horus2.horus-health.com",
                "Referer": "https://horus2.horus-health.com/",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                tok = data.get("token")
                if tok:
                    return tok
            except ValueError:
                return None
    except requests.RequestException:
        return None
    return None


def _ensure_token(force: bool) -> Optional[str]:
    global TOKEN
    if not force and TOKEN:
        return TOKEN
    creds = _get_credentials()
    if not creds:
        return None
    tok = _login_get_token(creds)
    if tok:
        TOKEN = tok
    return tok


def _load_doc_types() -> None:
    global DOC_TYPE_MAP, DOC_TYPE_REVERSE
    DOC_TYPE_MAP = {}
    DOC_TYPE_REVERSE = {}
    try:
        with open(DOC_TYPE_MAP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                name, code = [p.strip() for p in line.split(":", 1)]
                if name and code:
                    DOC_TYPE_MAP[name.lower()] = code
                    DOC_TYPE_REVERSE[code] = name
    except FileNotFoundError:
        DOC_TYPE_MAP = {}
        DOC_TYPE_REVERSE = {}


def _select_input_and_doc_type() -> Dict[str, str]:
    files_order = ["cedulas.txt", "tarjetas.txt", "registrocivil.txt"]
    name_map = {
        "cedulas.txt": "cedula",
        "tarjetas.txt": "tarjeta identidad",
        "registrocivil.txt": "registro civil",
    }
    for fname in files_order:
        if os.path.exists(fname):
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    name = name_map[fname]
                    code = str(DOC_TYPE_MAP.get(name.lower(), DOC_TYPE))
                    return {"file": fname, "code": code, "name": name}
            except Exception:
                pass
    name = name_map["cedulas.txt"]
    code = str(DOC_TYPE_MAP.get(name.lower(), DOC_TYPE))
    return {"file": CEDULAS_FILE, "code": code, "name": name}


# ==============================
# MAIN
# ==============================

def main():
    global TOKEN, CREDS
    creds = _get_credentials()
    if not creds:
        print("⚠️  No se pudieron leer credenciales desde Datos_utenticacion.txt")
        return
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            contenido = f.read()
        m_tok = re.search(r'"token"\s*:\s*"([^"]+)"', contenido)
        if not m_tok:
            m_tok = re.search(r'token\s*:\s*"([^"]+)"', contenido)
        if m_tok:
            TOKEN = m_tok.group(1).strip()
    except FileNotFoundError:
        pass
    if not TOKEN:
        tok = _login_get_token(creds)
        if tok:
            TOKEN = tok
        else:
            print("⚠️  No fue posible obtener token de autenticación.")
            return

    _load_doc_types()
    tasks = [
        ("cedulas.txt", "cedula", "cedulas.csv"),
        ("registrocivil.txt", "registro civil", "registrocivil.csv"),
        ("tarjetasid.txt", "tarjeta identidad", "tarjetasid.csv"),
    ]
    for input_file, doc_name, output_file in tasks:
        if not os.path.exists(input_file):
            continue
        ids = cargar_cedulas(input_file)
        doc_code = str(DOC_TYPE_MAP.get(doc_name.lower(), DOC_TYPE))
        print(f"Se cargaron {len(ids)} cédulas desde {input_file}")
        resultados = []
        if ids:
            for i, ced in enumerate(ids, start=1):
                print(f"[{i}/{len(ids)}] Consultando cédula {ced} ...", end=" ", flush=True)
                res = consultar_afiliado(ced, doc_type=doc_code, token=TOKEN)
                resultados.append(res)
                print(f"{res['estado']} - {res['mensaje']}")
                time.sleep(PAUSA_SEGUNDOS)
        guardar_csv(resultados, output_file)
        print(f"\nListo. Resultados guardados en: {output_file}")

    try:
        files_to_merge = [
            "cedulas.csv",
            "registrocivil.csv",
            "tarjetasid.csv",
        ]
        rows = []
        cols = set()
        for p in files_to_merge:
            if not os.path.exists(p):
                continue
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    rows.append(dict(r))
                    cols.update(r.keys())
        order = [c for c in PREFERRED_COLUMNS if c in cols]
        for c in cols:
            if c not in order:
                order.append(c)
        with open("unificado.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=order)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in order})
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(order)
            for r in rows:
                ws.append([r.get(k, "") for k in order])
            wb.save("unificado.xlsx")
            print("Excel generado: unificado.xlsx")
        except Exception:
            print("⚠️ No fue posible crear Excel. Instala 'openpyxl' e intenta de nuevo.")
        print("CSV unificado: unificado.csv")
    except Exception as e:
        print(f"⚠️ Error unificando CSVs: {e}")


if __name__ == "__main__":
    main()
