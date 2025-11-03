resource "aws_security_group" "alb" {
  name        = "${var.project}-alb-sg"
  description = "ALB SG"
  vpc_id      = aws_vpc.vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-alb-sg" }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project}-ecs-sg"
  description = "ECS tasks SG"
  vpc_id      = aws_vpc.vpc.id

  # ALB -> dashboard:5000
  ingress {
    description     = "ALB to dashboard"
    from_port       = 5000
    to_port         = 5000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # MQTT within tasks (self)
  ingress {
    description = "MQTT internal"
    from_port   = 1883
    to_port     = 1883
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-ecs-sg" }
}
