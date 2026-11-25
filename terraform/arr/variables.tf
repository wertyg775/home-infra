variable "proxmox_endpoint" {
  description = "Proxmox VE API endpoint URL (e.g. https://192.0.2.2:8006/)"
  type        = string
}

variable "proxmox_node" {
  description = "Target Proxmox node name"
  type        = string
  default     = "pve1"
}

variable "arr_ip" {
  description = "Static IPv4 address for the Arr / Docker VM"
  type        = string
}

variable "arr_mac_address" {
  description = "MAC address assigned to the Arr VM network interface"
  type        = string
}

variable "pihole_ip" {
  description = "Primary DNS server IPv4 address (Pi-hole)"
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

variable "vm_username" {
  description = "Cloud-init administrative username"
  type        = string
}

variable "arr_ssh_public_key_path" {
  description = "Local path to the SSH public key installed via cloud-init"
  type        = string
}
