#!/usr/bin/env bash
# Source this file to load .env and export Terraform TF_VAR_* equivalents:
#   source scripts/env.sh

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Source this script instead of executing it: source scripts/env.sh" >&2
  exit 1
fi

_homelab_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_homelab_env="${_homelab_root}/.env"

if [[ ! -f "${_homelab_env}" ]]; then
  echo "Missing ${_homelab_env}. Create it from .env.example first:" >&2
  echo "  cp ${_homelab_root}/.env.example ${_homelab_env}" >&2
  unset _homelab_root _homelab_env
  return 1
fi

set -a
# shellcheck source=/dev/null
source "${_homelab_env}"
set +a

# Map shared .env values to Terraform TF_VAR_* variables
export TF_VAR_proxmox_node="${PROXMOX_NODE:-pve1}"
export TF_VAR_proxmox_endpoint="https://${PROXMOX_HOST}:8006/"
export TF_VAR_vm_username="${HOMELAB_USER:-}"
export TF_VAR_lan_gateway="${HOMELAB_LAN_GATEWAY:-}"
export TF_VAR_lan_prefix_len="${HOMELAB_LAN_PREFIX_LEN:-24}"

export TF_VAR_arr_ip="${ARR_HOST:-}"
export TF_VAR_arr_mac_address="${ARR_MAC:-}"
export TF_VAR_arr_ssh_public_key_path="${ARR_SSH_KEY:+${ARR_SSH_KEY}.pub}"

export TF_VAR_vaultwarden_ip="${VAULTWARDEN_HOST:-}"
export TF_VAR_vaultwarden_mac_address="${VAULTWARDEN_MAC:-}"
export TF_VAR_vaultwarden_ssh_public_key_path="${VAULTWARDEN_SSH_KEY:+${VAULTWARDEN_SSH_KEY}.pub}"

export TF_VAR_pihole_ip="${PIHOLE_HOST:-}"

unset _homelab_root _homelab_env
