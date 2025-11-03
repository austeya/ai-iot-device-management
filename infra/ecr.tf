resource "aws_ecr_repository" "dashboard" {
  name = "${var.project}-dashboard"
  image_scanning_configuration { scan_on_push = true }
  force_delete = true
}

resource "aws_ecr_repository" "simulator" {
  name = "${var.project}-simulator"
  image_scanning_configuration { scan_on_push = true }
  force_delete = true
}

output "ecr_dashboard_repo_url" {
  value = aws_ecr_repository.dashboard.repository_url
}

output "ecr_simulator_repo_url" {
  value = aws_ecr_repository.simulator.repository_url
}
