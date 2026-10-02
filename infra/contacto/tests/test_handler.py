"""Tests del handler con SES simulado. Correr: python -m unittest discover -s infra/contacto/tests"""
import base64
import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))
import handler  # noqa: E402

ORIGEN = "https://gechenique-dataeng.vercel.app"


class SesFalso:
    def __init__(self):
        self.enviados = []

    def send_email(self, **kwargs):
        self.enviados.append(kwargs)
        return {"MessageId": "falso"}


def evento(datos=None, origen=ORIGEN, body=None, metodo="POST", b64=False):
    if body is None:
        body = json.dumps(datos)
    if b64:
        body = base64.b64encode(body.encode("utf-8")).decode("ascii")
    return {
        "headers": {"origin": origen, "content-type": "application/json"},
        "requestContext": {"http": {"method": metodo}},
        "body": body,
        "isBase64Encoded": b64,
    }


def valido(**cambios):
    datos = {"nombre": "Ana", "contacto": "ana@example.com", "asunto": "Hola", "mensaje": "Te escribo por...", "website": ""}
    datos.update(cambios)
    return datos


class TestHandler(unittest.TestCase):
    def setUp(self):
        os.environ["MAIL_DESTINO"] = "yo@example.com"
        os.environ["ORIGENES_PERMITIDOS"] = ORIGEN + ",https://otro-permitido.dev"
        self.ses = SesFalso()
        handler._ses = self.ses
        self.logs = io.StringIO()
        self._redir = contextlib.redirect_stdout(self.logs)
        self._redir.__enter__()

    def tearDown(self):
        self._redir.__exit__(None, None, None)

    def llamar(self, ev):
        return handler.handler(ev, None)

    def test_envio_valido_manda_el_mail(self):
        r = self.llamar(evento(valido()))
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(len(self.ses.enviados), 1)
        mail = self.ses.enviados[0]
        self.assertEqual(mail["FromEmailAddress"], "yo@example.com")
        self.assertEqual(mail["Destination"]["ToAddresses"], ["yo@example.com"])
        self.assertEqual(mail["Content"]["Simple"]["Subject"]["Data"], "[Sitio] Hola — Ana")
        self.assertEqual(mail["ReplyToAddresses"], ["ana@example.com"])
        self.assertIn("Te escribo por...", mail["Content"]["Simple"]["Body"]["Text"]["Data"])

    def test_body_base64_se_acepta(self):
        r = self.llamar(evento(body=json.dumps(valido()), b64=True))
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(len(self.ses.enviados), 1)

    def test_contacto_linkedin_no_lleva_reply_to(self):
        r = self.llamar(evento(valido(contacto="linkedin.com/in/ana")))
        self.assertEqual(r["statusCode"], 200)
        self.assertNotIn("ReplyToAddresses", self.ses.enviados[0])

    def test_mensaje_es_opcional(self):
        datos = valido()
        del datos["mensaje"]
        self.assertEqual(self.llamar(evento(datos))["statusCode"], 200)

    def test_honeypot_responde_200_sin_enviar(self):
        r = self.llamar(evento(valido(website="http://spam.example")))
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(self.ses.enviados, [])

    def test_campo_faltante_da_400(self):
        for campo in ("nombre", "contacto", "asunto"):
            datos = valido()
            del datos[campo]
            self.assertEqual(self.llamar(evento(datos))["statusCode"], 400, campo)
            self.assertEqual(self.llamar(evento(valido(**{campo: "   "})))["statusCode"], 400, campo)
        self.assertEqual(self.ses.enviados, [])

    def test_campo_muy_largo_da_400(self):
        for campo, limite in handler.LIMITES.items():
            r = self.llamar(evento(valido(**{campo: "x" * (limite + 1)})))
            self.assertEqual(r["statusCode"], 400, campo)
        self.assertEqual(self.ses.enviados, [])

    def test_tipo_no_string_da_400(self):
        self.assertEqual(self.llamar(evento(valido(nombre=["Ana"])))["statusCode"], 400)

    def test_origen_no_permitido_es_rechazado(self):
        for origen in ("https://malicioso.example", "", "https://gechenique-dataeng.vercel.app.malicioso.example"):
            r = self.llamar(evento(valido(), origen=origen))
            self.assertEqual(r["statusCode"], 403, origen)
        self.assertEqual(self.ses.enviados, [])

    def test_otro_origen_de_la_lista_se_acepta(self):
        self.assertEqual(self.llamar(evento(valido(), origen="https://otro-permitido.dev"))["statusCode"], 200)

    def test_body_de_mas_de_4kb_da_400(self):
        grande = json.dumps(valido(mensaje="x" * 1500, relleno="y" * 3000))
        self.assertGreater(len(grande.encode("utf-8")), 4096)
        self.assertEqual(self.llamar(evento(body=grande))["statusCode"], 400)
        self.assertEqual(self.ses.enviados, [])

    def test_json_invalido_da_400(self):
        self.assertEqual(self.llamar(evento(body="{no es json"))["statusCode"], 400)
        self.assertEqual(self.llamar(evento(body="[1, 2]"))["statusCode"], 400)

    def test_asunto_con_saltos_de_linea_queda_limpio(self):
        datos = valido(asunto="Hola\r\nBcc: victima@example.com", nombre="<b>Ana</b>\nX-Header: y")
        r = self.llamar(evento(datos))
        self.assertEqual(r["statusCode"], 200)
        asunto = self.ses.enviados[0]["Content"]["Simple"]["Subject"]["Data"]
        self.assertNotIn("\r", asunto)
        self.assertNotIn("\n", asunto)
        self.assertNotIn("<b>", asunto)
        self.assertEqual(asunto, "[Sitio] Hola Bcc: victima@example.com — Ana X-Header: y")

    def test_contacto_con_salto_no_va_como_reply_to(self):
        r = self.llamar(evento(valido(contacto="ana@example.com\r\nBcc: x@example.com")))
        self.assertEqual(r["statusCode"], 200)
        self.assertNotIn("ReplyToAddresses", self.ses.enviados[0])

    def test_metodo_distinto_de_post_da_405(self):
        self.assertEqual(self.llamar(evento(valido(), metodo="GET"))["statusCode"], 405)

    def test_logs_no_incluyen_el_contenido(self):
        self.llamar(evento(valido(mensaje="SECRETO-DEL-MENSAJE", nombre="NombreUnico")))
        salida = self.logs.getvalue()
        self.assertIn('"resultado": "enviado"', salida)
        self.assertNotIn("SECRETO-DEL-MENSAJE", salida)
        self.assertNotIn("NombreUnico", salida)

    def test_error_de_ses_da_502(self):
        class SesRoto:
            def send_email(self, **kwargs):
                raise RuntimeError("caido")

        handler._ses = SesRoto()
        self.assertEqual(self.llamar(evento(valido()))["statusCode"], 502)


class TestClienteEnInit(unittest.TestCase):
    """Regresión: el primer envío real dio timeout (5 s) porque boto3 se importaba y el cliente
    se creaba dentro de la invocación, en el cold start. Tiene que crearse al importar el módulo
    (fase de init de Lambda) y con timeouts que entren en el timeout de la función."""

    def setUp(self):
        import importlib
        import re
        import types

        self.creados = []
        creados = self.creados

        class ConfigFalsa:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        boto3_falso = types.ModuleType("boto3")
        boto3_falso.client = lambda servicio, config=None: creados.append((servicio, config)) or SesFalso()
        botocore_config = types.ModuleType("botocore.config")
        botocore_config.Config = ConfigFalsa

        self.modulos_previos = {m: sys.modules.get(m) for m in ("boto3", "botocore", "botocore.config")}
        sys.modules.update({"boto3": boto3_falso, "botocore": types.ModuleType("botocore"), "botocore.config": botocore_config})
        self.modulo = importlib.reload(handler)

        main_tf = open(os.path.join(os.path.dirname(__file__), "..", "main.tf"), encoding="utf-8").read()
        self.timeout_lambda = int(re.search(r"^\s*timeout\s*=\s*(\d+)", main_tf, re.M).group(1))

    def tearDown(self):
        import importlib

        for nombre, modulo in self.modulos_previos.items():
            if modulo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = modulo
        importlib.reload(handler)

    def test_cliente_se_crea_al_importar_y_no_en_la_invocacion(self):
        self.assertEqual(len(self.creados), 1)
        self.assertEqual(self.creados[0][0], "sesv2")

        os.environ["MAIL_DESTINO"] = "yo@example.com"
        os.environ["ORIGENES_PERMITIDOS"] = ORIGEN
        with contextlib.redirect_stdout(io.StringIO()):
            r = self.modulo.handler(evento(valido()), None)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(len(self.creados), 1, "la invocación no debe crear otro cliente")

    def test_timeouts_del_cliente_entran_en_el_timeout_de_la_lambda(self):
        config = self.creados[0][1].kwargs
        self.assertEqual(config["retries"]["max_attempts"], 1)
        self.assertLess(config["connect_timeout"] + config["read_timeout"], self.timeout_lambda)


if __name__ == "__main__":
    unittest.main()
