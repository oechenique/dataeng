output "function_url" {
  description = "URL que va como constante en js/contacto.js."
  value       = aws_lambda_function_url.contacto.function_url
}
