# Output for unique_identifier
output "unique_identifier" {
  description = "Unique identifier for the deployment"
  value       = var.unique_identifier
}

output "scylla_nodes_public_dns" {
  description = "Public DNS names of ScyllaDB nodes"
  value       = [for instance in aws_instance.scylladb_node : instance.public_dns]
}

output "demo_portal" {
  value = format("http://%s:5000", aws_instance.loader_node[0].public_dns)
  description = "URL of the Demo Portal"
}

output "loader_nodes_public_dns" {
  description = "Public DNS names of Loader nodes"
  value       = [for instance in aws_instance.loader_node : instance.public_dns]
}

