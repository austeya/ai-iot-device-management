variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "project" {
  type    = string
  default = "ai-iot"
}

variable "admin_user" {
  type = string
}

variable "admin_password" {
  type      = string
  sensitive = true
}

variable "dashboard_tag" {
  type    = string
  default = "latest"
}

variable "simulator_tag" {
  type    = string
  default = "latest"
}

variable "broker_image" {
  type    = string
  default = "eclipse-mosquitto:2"
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}
