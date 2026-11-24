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

# Comment out after initial import of pve1/101 so future runs against empty
# state provision fresh from template 9100.
import {
  id = "pve1/101"
  to = proxmox_virtual_environment_vm.arr
}

resource "proxmox_virtual_environment_vm" "arr" {
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [clone]
  }

  node_name = "pve1"
  vm_id     = 101
  name      = "containers"

  clone {
    vm_id = 9100
  }

  on_boot = true
  started = true

  scsi_hardware = "virtio-scsi-single"
  boot_order    = ["scsi0"]

  cpu {
    cores = 2
    type  = "host"
  }

  memory {
    dedicated = 4096
  }

  agent {
    enabled = true
  }

  operating_system {
    type = "l26"
  }

  # scsi0: local-lvm:vm-101-disk-0,size=32G
  disk {
    datastore_id = "local-lvm"
    interface    = "scsi0"
    size         = 32
  }

  # net0: virtio=BC:24:11:00:00:01,bridge=vmbr0,firewall=1
  network_device {
    bridge      = "vmbr0"
    model       = "virtio"
    mac_address = "BC:24:11:00:00:01"
    firewall    = true
  }

  serial_device {
    device = "socket"
  }

  vga {
    type = "serial0"
  }

  # ide2 cloud-init drive is created and managed by this block.
  # ipconfig0: ip=192.0.2.101/24,gw=192.0.2.1
  # nameserver: 192.0.2.104 1.1.1.1 
  initialization {
    datastore_id = "local-lvm"
    interface    = "ide2"

    dns {
      servers = ["192.0.2.104", "1.1.1.1"]
    }

    ip_config {
      ipv4 {
        address = "192.0.2.101/24"
        gateway = "192.0.2.1"
      }
    }

    # TODO: On the existing VM 101, `terraform apply` updates Proxmox's
    # cloud-init `sshkeys`, but cloud-init will NOT prune old keys from
    # `/home/admin/.ssh/authorized_keys` inside 192.0.2.101 — remove
    # `workstation` (and `root@pve1` if unwanted) there manually.
    user_account {
      username = "admin"
      keys     = [trimspace(file(pathexpand("~/.ssh/container_vm.pub")))]
    }
  }
}
