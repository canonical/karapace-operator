# CC006 mandatory outputs
output "app_name" {
  description = "Name of the Karapace application"
  value       = juju_application.karapace.name
}

output "endpoints" {
  description = "Service access endpoints"
  value = {
    # Add actual service URLs here if available
    # Could include REST API endpoints, etc.
  }
}

output "provides_endpoints" {
  description = "Relation endpoints this charm provides"
  value = [
    "karapace-client",
    "cos-agent",
    "certificates"
  ]
}

output "offers" {
  description = "offers created by this charm"
  value = {
    karapace-client = juju_offer.karapace_client.url
  }
}

output "karapace_client_offer" {
  description = "Karapace client offer URL for external applications (deprecated - use offers output)"
  value       = juju_offer.karapace_client.url
}