# Reglas: formulario de contacto serverless (costo cero)

Leé este archivo completo antes de tocar nada. Es la referencia de esta tarea.

## Contexto

- El sitio es HTML, CSS y JS puros, sin framework y sin build, desplegado en Vercel (`https://gechenique-dataeng.vercel.app/`).
- Hoy el footer tiene un botón "Escribime →" que abre LinkedIn.
- Objetivo: que "Escribime" abra un panel lateral con un formulario y que el mensaje me llegue por mail, mediante AWS Lambda y SES, con **costo cero en la práctica**.

## Lo que NO se toca

- El diseño actual: paleta, tipografías, hero, secciones, textos y animaciones.
- El resto del sitio. El cambio se limita al footer y a los archivos nuevos del panel.
- El link a LinkedIn: no desaparece, queda como opción secundaria dentro del panel.

## Frontend: el panel lateral (drawer)

- El botón "Escribime →" deja de ser un link y pasa a abrir un panel que **se desliza desde la derecha** sobre la página, con un fondo oscurecido detrás. No cambia de pantalla ni de URL.
- En celular, el panel ocupa el ancho completo.
- Campos:
  1. **Nombre**: obligatorio, máximo 100 caracteres.
  2. **Mail o LinkedIn**: obligatorio, máximo 200 caracteres. Es la forma de responder.
  3. **Asunto**: obligatorio, máximo 150 caracteres.
  4. **Mensaje**: opcional, máximo 2000 caracteres, con contador.
  5. **Honeypot**: un campo oculto (por ejemplo `website`), invisible para las personas y fuera del orden de tabulación. Si llega completo, es un bot.
- Estados del botón de envío: normal, "Enviando…" (deshabilitado), éxito ("¡Gracias! Te respondo pronto.") y error. El mensaje de error ofrece LinkedIn como alternativa.
- Accesibilidad:
  - Se cierra con Esc, con un clic en el fondo y con una X.
  - El foco queda dentro del panel mientras está abierto y vuelve al botón al cerrarlo.
  - El panel tiene `role="dialog"` y `aria-modal="true"`, y cada campo tiene su label.
- Validación también en el front (campos obligatorios y largos), pero la que manda es la del backend.
- La URL de la Lambda va como constante en el JS. No es un secreto.
- Estilo: usar los colores y componentes que ya existen en el sitio, sin agregar librerías.

## Backend: Lambda + SES

### Arquitectura (y nada más)

`navegador → Lambda Function URL (POST) → Lambda → SES → mi casilla`

### Lambda

- Runtime Python 3.12, arquitectura arm64, 128 MB de memoria, timeout de 5 s.
- **Function URL** con `auth_type = NONE`, sin API Gateway.
- CORS de la Function URL:
  - `allow_origins`: solo `https://gechenique-dataeng.vercel.app` (y el dominio propio, si se agrega más adelante, por variable).
  - `allow_methods`: `POST`.
  - `max_age`: 86400.
- Validaciones del lado del servidor:
  - El body tiene como máximo 4 KB y tiene que ser JSON válido. Si no, responde 400.
  - Si el honeypot llega completo, responde **200 sin enviar el mail**, para no darle pistas al bot.
  - Controla que los obligatorios estén y que respeten los largos.
  - Saca el HTML y los saltos de línea de los campos que van en el asunto, para evitar la inyección de headers.
  - Rechaza las llamadas cuyo header `Origin` no esté en la lista permitida, como segunda barrera además del CORS.
- El mail:
  - El remitente y el destinatario son mi dirección verificada en SES.
  - Asunto: `[Sitio] <asunto> — <nombre>`.
  - El cuerpo en texto plano lleva nombre, contacto, asunto y mensaje, más la fecha.
  - Si el campo de contacto es un mail válido, va también como `Reply-To`.
- Variables de entorno: `MAIL_DESTINO`, `ORIGENES_PERMITIDOS`. No hay ningún secreto.
- Concurrencia reservada en 2, para que ni un ataque la haga escalar. **Antes**, revisá `aws lambda get-account-settings`. Si el límite de la cuenta es 10, AWS no deja reservar. En ese caso no la configures y avisame: se puede pedir un aumento de cuota, que es gratis, o seguir sin reservar.

### SES

- Región `us-east-1`, la misma que la Lambda.
- Identidad de mail: mi dirección (`<MAIL_DESTINO>`). La verificación la hago yo con el clic en el mail que manda AWS.
- Queda en **modo sandbox**: alcanza, porque solo me manda mails a mí. No pidas acceso de producción.

### IAM (mínimo privilegio)

- El rol de la Lambda solo puede:
  - `ses:SendEmail` y `ses:SendRawEmail`, solo sobre el ARN de mi identidad.
  - Escribir en su propio log group.

### Logs

- El log group `/aws/lambda/<nombre>` se crea explícitamente en Terraform, con **retención de 7 días**.
- No se loguea el contenido de los mensajes: solo el resultado (enviado, descartado por honeypot o error de validación) y el código de estado.

## Prohibido (es lo que genera cobros)

- Secrets Manager (USD 0,40 por mes por secreto).
- API Gateway, VPC, NAT Gateway (unos USD 30 por mes), claves de KMS propias, DynamoDB, ECR y CloudFront.
- Logs sin retención.
- Captchas de terceros, por ahora. Queda como mejora opcional futura: Cloudflare Turnstile, que es gratis.

## Infraestructura como código

- Terraform en `infra/contacto/`, con el provider de AWS y `profile = "tesseract"`, región `us-east-1`.
- Tags en todos los recursos: `proyecto = "web-contacto"`.
- `terraform.tfvars` ignorado por git, más un `terraform.tfvars.example` con placeholders (`<MAIL_DESTINO>`).
- El state es local y no se versiona.
- El código de la Lambda va en `infra/contacto/lambda/handler.py` y se empaqueta con `archive_file`.

## Cómo trabajamos

1. Primero el plan de Terraform: me lo mostrás y esperás mi OK.
2. Si el clasificador te bloquea el `apply`, dame el comando exacto y lo corro yo en PowerShell.
3. Después del apply, me pedís que verifique el mail de SES (el clic en el mail de AWS) antes de probar.
4. Tests del handler (con SES simulado):
   - Un envío válido manda el mail.
   - El honeypot responde 200 y no envía nada.
   - Un campo faltante o muy largo da 400.
   - Un origen no permitido es rechazado.
   - Un body de más de 4 KB da 400.
   - Un asunto con saltos de línea queda limpio.
5. Recién con todo en verde, el cambio del front, y lo pruebo en local antes del deploy a Vercel.

## Criterio de terminado

- Desde el sitio publicado, un mensaje real me llega a la casilla, con `Reply-To` cuando dejé un mail.
- El envío con el honeypot completo no genera mail.
- Una llamada desde otro origen es rechazada.
- Concurrencia reservada configurada, o documentado por qué no.
- `docs/contacto.md` con: arquitectura, costos esperados (Lambda USD 0, SES USD 0,10 cada mil mails, logs USD 0), cómo probarlo y el **destroy**: `terraform destroy` más el borrado de la identidad de SES.
- Commit y push.
