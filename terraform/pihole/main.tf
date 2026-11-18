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
  endpoint = "https://192.0.2.2:8006/"
}

resource "proxmox_virtual_environment_container" "pihole" {
  node_name = "pve1"
  vm_id     = 104

  unprivileged = true

  start_on_boot = true

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
        address = "192.0.2.104/24"
        gateway = "192.0.2.1"
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