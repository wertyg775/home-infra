#!/usr/bin/env bash
# Render *.template networking config files using values from .env.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${repo_root}/scripts/env.sh"

required_vars=(TAILSCALE_IP HOMELAB_LAN_GATEWAY HOMELAB_LAN_CIDR)
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Error: ${var} must be set in .env" >&2
    exit 1
  fi
done

vars='$TAILSCALE_IP:$HOMELAB_LAN_GATEWAY:$HOMELAB_LAN_CIDR'
envsubst "${vars}" < "${repo_root}/networking/dnsmasq.d/cloud-home-arpa.conf.template" \
  > "${repo_root}/networking/dnsmasq.d/cloud-home-arpa.conf"
envsubst "${vars}" < "${repo_root}/networking/nftables.conf.template" \
  > "${repo_root}/networking/nftables.conf"

echo "Rendered networking/dnsmasq.d/cloud-home-arpa.conf and networking/nftables.conf"
