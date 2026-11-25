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

  node_name = var.proxmox_node
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

  network_device {
    bridge      = "vmbr0"
    model       = "virtio"
    mac_address = var.arr_mac_address
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

    dns {
      servers = [var.pihole_ip, "1.1.1.1"]
    }

    ip_config {
      ipv4 {
        address = "${var.arr_ip}/${var.lan_prefix_len}"
        gateway = var.lan_gateway
      }
    }

    # TODO: On the existing VM 101, `terraform apply` updates Proxmox's
    # cloud-init `sshkeys`, but cloud-init will NOT prune old keys from
    # `~/.ssh/authorized_keys` inside the VM — remove stale keys manually.
    user_account {
      username = var.vm_username
      keys     = [trimspace(file(pathexpand(var.arr_ssh_public_key_path)))]
    }
  }
}
