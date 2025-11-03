locals {
  cwlogs = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.lg.name
      awslogs-region        = var.aws_region
      awslogs-stream-prefix = var.project
    }
  }

  dashboard_image = "${aws_ecr_repository.dashboard.repository_url}:${var.dashboard_tag}"
  simulator_image = "${aws_ecr_repository.simulator.repository_url}:${var.simulator_tag}"
  namespace       = aws_service_discovery_private_dns_namespace.ns.name
  mqtt_host       = "broker.${aws_service_discovery_private_dns_namespace.ns.name}"
}

resource "aws_ecs_task_definition" "dashboard" {
  family                   = "${var.project}-dashboard"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([
    {
      name      = "dashboard"
      image     = local.dashboard_image
      essential = true
      portMappings = [
        { containerPort = 5000, hostPort = 5000, protocol = "tcp" }
      ]
      environment = [
        { name = "MQTT_BROKER", value = local.mqtt_host },
        { name = "IOT_TOPIC", value = "iot/devices/sensor" },
        { name = "ADMIN_USER", value = var.admin_user },
        { name = "ADMIN_PASSWORD", value = var.admin_password },
        { name = "AUTH_DISABLE", value = "0" }
      ]
      logConfiguration = local.cwlogs
    }
  ])
}

resource "aws_ecs_task_definition" "broker" {
  family                   = "${var.project}-broker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([
    {
      name      = "broker"
      image     = var.broker_image
      essential = true
      portMappings = [
        { containerPort = 1883, hostPort = 1883, protocol = "tcp" }
      ]
      logConfiguration = local.cwlogs
    }
  ])
}

resource "aws_ecs_task_definition" "simulator" {
  family                   = "${var.project}-simulator"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([
    {
      name      = "simulator"
      image     = local.simulator_image
      essential = true
      environment = [
        { name = "MQTT_BROKER", value = local.mqtt_host },
        { name = "IOT_TOPIC", value = "iot/devices/sensor" },
        { name = "DEVICES", value = "device-001,device-002" }
      ]
      logConfiguration = local.cwlogs
    }
  ])
}

resource "aws_service_discovery_service" "broker_sd" {
  name = "broker"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.ns.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_ecs_service" "dashboard" {
  name            = "${var.project}-dashboard"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.tg.arn
    container_name   = "dashboard"
    container_port   = 5000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "broker" {
  name            = "${var.project}-broker"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.broker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.broker_sd.arn
  }
}

resource "aws_ecs_service" "simulator" {
  name            = "${var.project}-simulator"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.simulator.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
  }

  depends_on = [aws_ecs_service.broker]
}
