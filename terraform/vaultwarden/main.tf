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

# Uncomment only if target VM exists AND no .tfstate
# import {
#   id = "pve1/102"
#   to = proxmox_virtual_environment_vm.vaultwarden
# }

resource "proxmox_virtual_environment_vm" "vaultwarden" {
  # Guard to prevent accidental VM destroys AND re-provisions.
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [clone]
  }

  node_name = var.proxmox_node
  vm_id     = 102
  name      = "secrets"

  clone {
    vm_id = 9100
  }

  on_boot = true
  started = true

  scsi_hardware = "virtio-scsi-single"
  boot_order    = ["scsi0"]

  cpu {
    cores = 1
    type  = "host"
  }

  memory {
    dedicated = 1024
  }

  agent {
    enabled = true
  }

  operating_system {
    type = "l26"
  }

  # scsi0: local-lvm:vm-102-disk-1,size=10G
  disk {
    datastore_id = "local-lvm"
    interface    = "scsi0"
    size         = 10
  }

  network_device {
    bridge      = "vmbr0"
    model       = "virtio"
    mac_address = var.vaultwarden_mac_address
    firewall    = true
  }

  serial_device {
    device = "socket"
  }

  vga {
    type = "serial0"
  }

  # ide2 cloud-init drive is created and managed by this block.
  initialization {
    datastore_id = "local-lvm"
    interface    = "ide2"

    ip_config {
      ipv4 {
        address = "${var.vaultwarden_ip}/${var.lan_prefix_len}"
        gateway = var.lan_gateway
      }
    }

    user_account {
      username = var.vm_username
      keys     = [trimspace(file(pathexpand(var.vaultwarden_ssh_public_key_path)))]
    }
  }
}
