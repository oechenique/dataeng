variable "mail_destino" {
  description = "Mi dirección: identidad de SES, remitente y destinatario."
  type        = string
}

variable "origenes_permitidos" {
  description = "Orígenes que pueden llamar a la Function URL (CORS y chequeo en el handler)."
  type        = list(string)
  default     = ["https://gechenique-dataeng.vercel.app"]
}

variable "concurrencia_reservada" {
  description = "Concurrencia reservada de la Lambda. -1 = sin reservar (la cuenta tiene límite 10, AWS no deja reservar)."
  type        = number
  default     = -1
}
