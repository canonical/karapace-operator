resource "juju_application" "karapace" {
  model = var.model
  name  = var.app_name
  
  charm {
    name     = "karapace"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }
  
  units       = var.units
  constraints = var.constraints
  config      = var.config
}

# Karapace client offer
resource "juju_offer" "karapace_client" {
  model            = var.model
  application_name = juju_application.karapace.name
  endpoints        = ["karapace"]
}