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

  node_name = "pve1"
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

  # net0: virtio=BC:24:11:00:00:02,bridge=vmbr0,firewall=1
  network_device {
    bridge      = "vmbr0"
    model       = "virtio"
    mac_address = "BC:24:11:00:00:02"
    firewall    = true
  }

  serial_device {
    device = "socket"
  }

  vga {
    type = "serial0"
  }

  # ide2 cloud-init drive is created and managed by this block.
  # ipconfig0: ip=192.0.2.102/24,gw=192.0.2.1
  # ciuser: admin  +  sshkeys: homelab_guest
  initialization {
    datastore_id = "local-lvm"
    interface    = "ide2"

    ip_config {
      ipv4 {
        address = "192.0.2.102/24"
        gateway = "192.0.2.1"
      }
    }

    user_account {
      username = "admin"
      keys     = [trimspace(file(pathexpand("~/.ssh/homelab_guest.pub")))]
    }
  }
}
