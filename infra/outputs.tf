output "cluster_name" {
  value = aws_ecs_cluster.cluster.name
}

output "broker_dns" {
  value = "broker.${aws_service_discovery_private_dns_namespace.ns.name}"
}
