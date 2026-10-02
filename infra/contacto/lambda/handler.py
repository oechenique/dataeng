"""Formulario de contacto: Lambda Function URL -> SES.

No loguea el contenido de los mensajes, solo el resultado y el código de estado.
"""
import base64
import json
import os
import re
from datetime import datetime, timezone

MAX_BODY_BYTES = 4096
LIMITES = {"nombre": 100, "contacto": 200, "asunto": 150, "mensaje": 2000}
OBLIGATORIOS = ("nombre", "contacto", "asunto")
HONEYPOT = "website"

RE_HTML = re.compile(r"<[^>]*>")
RE_SALTOS = re.compile(r"[\r\n\t\x00-\x1f\x7f]+")
RE_MAIL = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[A-Za-z]{2,}$")

# El cliente se crea en la fase de init (no cuenta para el timeout de 5 s de la invocación).
# Timeouts cortos para que un SES lento termine en 502 y no en un timeout de la Lambda.
try:
    import boto3
    from botocore.config import Config

    _ses = boto3.client("sesv2", config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}))
except ImportError:  # tests locales sin boto3: inyectan un cliente simulado
    _ses = None


def _cliente_ses():
    return _ses


def _respuesta(status, resultado, cuerpo=None):
    print(json.dumps({"resultado": resultado, "status": status}))
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(cuerpo or {"ok": status == 200}),
    }


def _origenes_permitidos():
    return {o.strip().rstrip("/") for o in os.environ.get("ORIGENES_PERMITIDOS", "").split(",") if o.strip()}


def limpiar_linea(texto):
    """Saca HTML y saltos de línea: para lo que va en el asunto del mail."""
    sin_html = RE_HTML.sub("", texto)
    return RE_SALTOS.sub(" ", sin_html).strip()


def _leer_body(event):
    body = event.get("body") or ""
    crudo = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("utf-8")
    if len(crudo) > MAX_BODY_BYTES:
        return None, "body_muy_grande"
    try:
        datos = json.loads(crudo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "json_invalido"
    if not isinstance(datos, dict):
        return None, "json_invalido"
    return datos, None


def _validar(datos):
    campos = {}
    for campo, limite in LIMITES.items():
        valor = datos.get(campo, "")
        if not isinstance(valor, str):
            return None
        valor = valor.strip()
        if campo in OBLIGATORIOS and not valor:
            return None
        if len(valor) > limite:
            return None
        campos[campo] = valor
    return campos


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    metodo = event.get("requestContext", {}).get("http", {}).get("method", "POST")

    if headers.get("origin", "").rstrip("/") not in _origenes_permitidos():
        return _respuesta(403, "origen_rechazado")
    if metodo != "POST":
        return _respuesta(405, "metodo_invalido")

    datos, error = _leer_body(event)
    if error:
        return _respuesta(400, error)

    # Bot: se responde 200 para no darle pistas.
    if str(datos.get(HONEYPOT, "")).strip():
        return _respuesta(200, "descartado_honeypot")

    campos = _validar(datos)
    if campos is None:
        return _respuesta(400, "validacion")

    nombre = limpiar_linea(campos["nombre"])
    asunto = limpiar_linea(campos["asunto"])
    contacto = limpiar_linea(campos["contacto"])
    if not nombre or not asunto or not contacto:
        return _respuesta(400, "validacion")

    destino = os.environ["MAIL_DESTINO"]
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    texto = (
        f"Nombre: {nombre}\n"
        f"Contacto: {contacto}\n"
        f"Asunto: {asunto}\n"
        f"Fecha: {fecha}\n\n"
        f"{campos['mensaje'] or '(sin mensaje)'}\n"
    )
    envio = {
        "FromEmailAddress": destino,
        "Destination": {"ToAddresses": [destino]},
        "Content": {
            "Simple": {
                "Subject": {"Data": f"[Sitio] {asunto} — {nombre}", "Charset": "UTF-8"},
                "Body": {"Text": {"Data": texto, "Charset": "UTF-8"}},
            }
        },
    }
    if RE_MAIL.match(contacto):
        envio["ReplyToAddresses"] = [contacto]

    try:
        _cliente_ses().send_email(**envio)
    except Exception as exc:  # noqa: BLE001 — se loguea solo el tipo, nunca el contenido
        print(json.dumps({"resultado": "error_ses", "tipo": type(exc).__name__}))
        return _respuesta(502, "error_ses", {"ok": False})

    return _respuesta(200, "enviado")
