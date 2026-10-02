# Formulario de contacto serverless

El botón "Escribime →" del footer abre un panel lateral con un formulario. El mensaje llega por mail mediante
AWS Lambda y SES, con costo cero en la práctica. Reglas de la tarea: [`reglas/reglas-contacto-serverless.md`](../reglas/reglas-contacto-serverless.md).

## Arquitectura

```
navegador → Lambda Function URL (POST) → Lambda → SES → mi casilla
```

| Pieza | Dónde | Detalle |
|---|---|---|
| Panel (drawer) | `js/contacto.js`, `css/contacto.css` | Validación en el front, honeypot `website`, foco atrapado, Esc / fondo / X cierran |
| Function URL | `infra/contacto/main.tf` | `auth_type = NONE`, CORS solo para `https://gechenique-dataeng.vercel.app`, `POST`, `max_age` 86400 |
| Lambda `web-contacto` | `infra/contacto/lambda/handler.py` | Python 3.12, arm64, 128 MB, timeout 5 s |
| SES | `us-east-1` | Identidad de mail verificada, en **sandbox** (solo me manda mails a mí) |
| Logs | `/aws/lambda/web-contacto` | Retención de 7 días; solo resultado y código de estado, nunca el contenido |
| IAM | rol `web-contacto` | `ses:SendEmail`/`SendRawEmail` sobre el ARN de la identidad y escritura en su log group |

Lo que valida el handler (la validación que manda es esta, no la del front):

| Caso | Respuesta |
|---|---|
| `Origin` fuera de `ORIGENES_PERMITIDOS` | 403 (segunda barrera además del CORS) |
| Método distinto de POST | 405 |
| Body de más de 4 KB o JSON inválido | 400 |
| Honeypot completo | **200 sin enviar el mail** |
| Obligatorio faltante, tipo incorrecto o largo excedido | 400 |
| SES falla o tarda (timeouts del cliente de 2 s + 2 s) | 502 |
| Válido | 200 y mail con asunto `[Sitio] <asunto> — <nombre>`; `Reply-To` si el contacto es un mail |

Nombre, asunto y contacto pierden HTML y saltos de línea antes de ir al asunto o al `Reply-To`, para evitar la
inyección de headers. El cliente de SES se crea al importar el módulo, en la fase de init de Lambda: creado
dentro de la invocación, el cold start consumía los 5 s del timeout (hay un test de regresión para eso).

## Concurrencia reservada: no configurada

La regla pedía reservar 2. La cuenta tiene un límite de **10** ejecuciones concurrentes
(`aws lambda get-account-settings`), y AWS exige dejar al menos 10 sin reservar, así que no deja reservar nada.
Quedó como variable (`concurrencia_reservada`, por defecto `-1` = sin reservar).

Para activarla: pedir el aumento de *Concurrent executions* en Service Quotas (es gratis) y, cuando se apruebe,
agregar `concurrencia_reservada = 2` al `terraform.tfvars` y aplicar.

## Costos esperados

| Servicio | Costo | Por qué |
|---|---|---|
| Lambda | USD 0 | Muy por debajo del free tier permanente (1 M de invocaciones y 400.000 GB-s por mes) |
| SES | USD 0,10 cada mil mails | Un formulario personal manda unos pocos por mes |
| CloudWatch Logs | USD 0 | Pocos KB por mes, con retención de 7 días |

No se usa nada de lo que genera cobros fijos: ni Secrets Manager, ni API Gateway, ni VPC/NAT, ni KMS propio,
DynamoDB, ECR o CloudFront.

## Despliegue

Requisitos: Terraform, AWS CLI con el perfil `tesseract`.

```powershell
cd infra/contacto
copy terraform.tfvars.example terraform.tfvars   # completar <MAIL_DESTINO>
terraform init
terraform plan -out contacto.tfplan
terraform apply contacto.tfplan
terraform output function_url                    # va como ENDPOINT en js/contacto.js
```

Después del primer apply, AWS manda un mail de verificación a `MAIL_DESTINO`: hay que hacer clic en el link
antes de probar. El state es local y no se versiona; `terraform.tfvars` está en `.gitignore`.

## Cómo probarlo

**Tests del handler** (SES simulado, sin dependencias):

```powershell
python -m unittest discover -s infra/contacto/tests -v
```

**Contra la Function URL** (reemplazar `<URL>` por `terraform output function_url`):

```bash
# Otro origen: 403
curl -s -X POST -H "Origin: https://malicioso.example" -H "Content-Type: application/json" \
  -d '{"nombre":"x","contacto":"x","asunto":"x"}' <URL>

# Honeypot: 200 y no llega mail
curl -s -X POST -H "Origin: https://gechenique-dataeng.vercel.app" -H "Content-Type: application/json" \
  -d '{"nombre":"x","contacto":"x","asunto":"x","website":"bot"}' <URL>
```

**Logs** (en Git Bash, `MSYS_NO_PATHCONV=1` evita que convierta la ruta del log group):

```bash
MSYS_NO_PATHCONV=1 aws logs filter-log-events --profile tesseract --region us-east-1 \
  --log-group-name /aws/lambda/web-contacto --filter-pattern resultado --query "events[].message" --output text
```

**Desde el sitio publicado:** abrir "Escribime →", enviar un mensaje con un mail en "Mail o LinkedIn" y
verificar que llega con ese `Reply-To`. Desde `localhost` el envío falla a propósito: el CORS solo permite el
dominio publicado.

## Destroy

```powershell
cd infra/contacto
terraform destroy
```

`terraform destroy` borra la Lambda, la Function URL, el rol, el log group y **la identidad de SES**
(`aws_sesv2_email_identity`). Para confirmar que la identidad no quedó:

```powershell
aws sesv2 list-email-identities --profile tesseract --region us-east-1
```

Si todavía figura (por ejemplo, si se creó a mano), borrarla con:

```powershell
aws sesv2 delete-email-identity --profile tesseract --region us-east-1 --email-identity <MAIL_DESTINO>
```

Por último, volver el botón "Escribime →" a un link a LinkedIn y quitar `css/contacto.css` y `js/contacto.js`.
