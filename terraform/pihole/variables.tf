variable "proxmox_endpoint" {
  description = "Proxmox VE API endpoint URL (e.g. https://192.0.2.2:8006/)"
  type        = string
}

variable "proxmox_node" {
  description = "Target Proxmox node name"
  type        = string
  default     = "pve1"
}

variable "pihole_ip" {
  description = "Static IPv4 address for the Pi-hole LXC"
  type        = string
}

variable "lan_prefix_len" {
  description = "IPv4 prefix length for the LAN subnet"
  type        = number
  default     = 24
}

variable "lan_gateway" {
  description = "IPv4 gateway address for the LAN"
  type        = string
}
