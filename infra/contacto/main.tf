terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  profile = "tesseract"
  region  = "us-east-1"

  default_tags {
    tags = {
      proyecto = "web-contacto"
    }
  }
}

data "aws_caller_identity" "actual" {}

locals {
  nombre        = "web-contacto"
  identidad_arn = "arn:aws:ses:us-east-1:${data.aws_caller_identity.actual.account_id}:identity/${var.mail_destino}"
}

# --- SES: identidad de mail (queda en sandbox; la verificación es el clic en el mail de AWS) ---

resource "aws_sesv2_email_identity" "mail" {
  email_identity = var.mail_destino
}

# --- Logs: log group explícito, con retención ---

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.nombre}"
  retention_in_days = 7
}

# --- IAM: mínimo privilegio ---

data "aws_iam_policy_document" "asumir" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = local.nombre
  assume_role_policy = data.aws_iam_policy_document.asumir.json
}

data "aws_iam_policy_document" "permisos" {
  statement {
    sid       = "EnviarMail"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = [local.identidad_arn]
  }
  statement {
    sid       = "EscribirLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = local.nombre
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.permisos.json
}

# --- Lambda + Function URL ---

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/handler.py"
  output_path = "${path.module}/build/handler.zip"
}

resource "aws_lambda_function" "contacto" {
  function_name    = local.nombre
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  memory_size      = 128
  timeout          = 5
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  # -1 = sin reservar. Ver docs/contacto.md: la cuenta tiene límite 10 y AWS no deja reservar.
  reserved_concurrent_executions = var.concurrencia_reservada

  environment {
    variables = {
      MAIL_DESTINO        = var.mail_destino
      ORIGENES_PERMITIDOS = join(",", var.origenes_permitidos)
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
}

resource "aws_lambda_function_url" "contacto" {
  function_name      = aws_lambda_function.contacto.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = var.origenes_permitidos
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
    max_age       = 86400
  }
}

# Function URL pública: AWS exige los dos permisos (InvokeFunctionUrl e InvokeFunction vía URL).
resource "aws_lambda_permission" "url_publica" {
  statement_id           = "FunctionUrlPublica"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.contacto.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invocar_via_url" {
  statement_id             = "InvocarViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.contacto.function_name
  principal                = "*"
  invoked_via_function_url = true
}
