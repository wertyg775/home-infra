terraform {
  required_version = ">= 1.7"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.122.0"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint
}

resource "proxmox_virtual_environment_container" "pihole" {
  node_name = var.proxmox_node
  vm_id     = 104

  unprivileged = true

  start_on_boot = true
  
  startup {
    order    = 1
    up_delay = 15
    down_delay = 30
  }

  cpu {
    cores = 1
  }

  memory {
    dedicated = 1024
  }

  disk {
    datastore_id = "local-lvm"
    size         = 8
  }

  operating_system {
    type             = "debian"
    template_file_id = "local:vztmpl/debian-13-standard_13.6-1_amd64.tar.zst"
  }

  initialization {
    hostname = "pihole"

    dns {
      servers = ["1.1.1.1", "1.0.0.1"]
    }

    ip_config {
      ipv4 {
        address = "${var.pihole_ip}/${var.lan_prefix_len}"
        gateway = var.lan_gateway
      }
    }
  }

  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
  }

  features {
    nesting = true
  }
}
