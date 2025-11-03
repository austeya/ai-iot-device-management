resource "aws_cloudwatch_log_group" "lg" {
  name              = "/ecs/${var.project}"
  retention_in_days = 14
}
