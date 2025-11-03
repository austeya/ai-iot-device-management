resource "aws_service_discovery_private_dns_namespace" "ns" {
  name = "${var.project}.local"
  vpc  = aws_vpc.vpc.id
}

output "service_discovery_namespace" {
  value = aws_service_discovery_private_dns_namespace.ns.name
}
