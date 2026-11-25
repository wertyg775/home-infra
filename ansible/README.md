# Ansible playbook for homelab

Configures homelab VMs over SSH from this workstation.

## Configured VMs

Host IP addresses, SSH users, and key paths are loaded from the repository root
`.env` file (see `../.env.example` and `group_vars/all/env.yml`).

| Inventory host | `.env` variable | Role |
|---|---|---|
| `pve1` | `PROXMOX_HOST` | Proxmox VE host |
| `containers` | `ARR_HOST` | VM for hosting docker containers |
| `vaultwarden` | `VAULTWARDEN_HOST` | Vaultwarden |
| `proxy` | `NGINX_PROXY_HOST` | Nginx reverse proxy LXC |
| `pihole` | `PIHOLE_HOST` | Pi-hole LXC |

## Roles (tasks)

### Media VM
| Role | State |
|---|---|
| `common` | timezone, baseline packages, unattended upgrades, SSH hardening, optional UFW |
| `docker` | Docker apt repo + key, engine/Compose packages, `/etc/docker/daemon.json`, docker group |
| `media_stack` | `/srv/media` tree (and optional NFS mount), compose file, running containers |

### Vaultwarden VM and Nginx proxy

`vaultwarden.yml` runs [Vaultwarden](https://github.com/dani-garcia/vaultwarden)
on the VM and configures the existing Nginx proxy to serve HTTPS. Vaultwarden
uses SQLite and persistent data; the image version is pinned in role defaults.

## Prerequisites

Install Ansible on control node:

```bash
# Debian/Ubuntu
sudo apt install -y ansible-core

# Fedora/RHEL
sudo dnf install ansible-core

# Install requirements.yaml
ansible-galaxy collection install -r requirements.yml
```

Configure VM with SSH key via cloud-init.

## Configure

1. Copy `../.env.example` to `../.env` and set your host IPs, `HOMELAB_USER`,
   SSH key paths, LAN CIDR, and CA paths.
2. Load `.env` into your shell before running Ansible:

```bash
source ../scripts/env.sh
```

## Run

```bash
cd ~/homelab/ansible

# 1. reachability
ansible docker_hosts -m ping

# 2. baseline + Docker (idempotent)
ansible-playbook site.yml --tags common,docker --check --diff
ansible-playbook site.yml --tags common,docker

# 3. dry run: shows the compose diff (the adoption guard is skipped in
#    check mode, so this works even before adopting)
ansible-playbook site.yml --tags stack --check --diff

# 4. apply. First run adopts the existing compose file (overwrites it with
#    the rendered template, after which it is Ansible-managed):
ansible-playbook site.yml --tags stack -e compose_adopt=true

# 5. later runs:
ansible-playbook site.yml
```

The adoption guard rewrites a `docker-compose.yml` that carries the
`Ansible managed` marker. On the first run, review the diff and pass
`compose_adopt=true` to mark your existing file as managed.

## Updating images

`compose_pull` defaults to `missing`, so images stay put until you ask.
To upgrade:

```bash
ansible-playbook site.yml --tags stack -e compose_pull=always
```

Pin a version in `group_vars` for a fixed release
(`lscr.io/linuxserver/sonarr:4`).

## Configure the media stack proxy

`nginx.yml` enables HTTP sites for `sonarr.home.arpa`, `qbittorrent.home.arpa`,
and `prowlarr.home.arpa` on the Nginx proxy. Point those DNS records at
`NGINX_PROXY_HOST`. The hostnames are configured in `group_vars/nginx_proxy.yml`,
and the upstream ports come from the media VM's inventory variables.

```bash
ansible-playbook nginx.yml --tags nginx
```

### Enable the proxy firewall

The `common` role allows TCP ports `22`, `80`, and `443` from `HOMELAB_LAN_CIDR`
and sets UFW's default inbound policy to deny. The rules are in
`group_vars/nginx_proxy.yml`. Run the firewall tasks from a LAN workstation
with SSH access to the proxy.

```bash
ansible-playbook nginx.yml --tags firewall --ask-become-pass
```

Verify a fresh SSH connection and the expected HTTP and HTTPS sites. Check
`sudo ufw status verbose` on the proxy for any pre-existing rules. The role
adds its rules alongside existing ones.

## Configure and run Vaultwarden

The playbook configures the existing Vaultwarden VM (`VAULTWARDEN_HOST`) and the
Nginx proxy (`NGINX_PROXY_HOST`). It does not create either host or alter existing
proxy sites. The proxy provides HTTPS and forwards requests to Vaultwarden.

1. Set the SSH user, host IPs, and key paths in `../.env` and run
   `source ../scripts/env.sh`. Check `docker_repo_os` and `docker_arch` in
   `group_vars/vaultwarden_hosts.yml` against the app VM.
2. Set `VAULTWARDEN_CA_CERT` and `VAULTWARDEN_CA_KEY` in `../.env` to the root
   CA certificate and signing key paths on the control machine. Ansible needs
   read access to both PEM files. Set `vaultwarden_domain` if needed; its DNS
   record must point to the Nginx proxy (`NGINX_PROXY_HOST`). Install the root
   CA certificate in the trust store of each client device. The role signs
   directly with a root CA.
3. Install the collections from `requirements.yml` and ensure the Ansible
   control machine's Python has `cryptography` installed. The proxy role
   installs `python3-cryptography` on the proxy VM. If the CA key has a
   passphrase, store `vaultwarden_ca_key_passphrase` in an encrypted Ansible
   Vault file; use `-e @vaultwarden-secrets.yml --ask-vault-pass` below.
4. From the `ansible` directory, run the two plays. Run them separately if the
   two target hosts have different sudo passwords:

   ```bash
   ansible-playbook vaultwarden.yml --limit vaultwarden --ask-become-pass
   ansible-playbook vaultwarden.yml --limit proxy --ask-become-pass
   ```

Open `https://vault.home.arpa` after both plays complete. Signups are enabled
for the initial account. Once the account is created, set
`vaultwarden_signups_allowed: false` in `group_vars/vaultwarden_hosts.yml` and
rerun the app play. SMTP is optional; configure its fields there and store
`vaultwarden_smtp_password` in Ansible Vault if needed. Mobile push is disabled
by default, so no Bitwarden installation ID or key is required.

The proxy generates its TLS private key on the proxy VM at
`/etc/nginx/vaultwarden-tls/ssl.key`; the CA key stays on the control machine.
The certificate is valid for 365 days and is renewed when the proxy play runs
within 30 days of expiry. Ansible does not schedule renewal by itself. The root
CA must remain valid for the full lifetime of a new certificate. Certificate
provisioning is skipped in check mode.

Vaultwarden data is under `/opt/stacks/vaultwarden/data` on the app VM. Follow
the [Vaultwarden backup instructions](https://github.com/dani-garcia/vaultwarden/wiki/Backing-up-your-vault)
for a consistent SQLite backup and the other data files; keep backups off the
VM and test restores. Take a backup before updating `vaultwarden_image`.

Clients connect to the Nginx proxy over HTTPS. The proxy connects to the app VM
over HTTP on port `8080`, so that traffic is unencrypted on the LAN. Restrict
access to this backend port to the proxy with a network or Docker-aware
firewall; Docker-published ports may bypass UFW. Change
`vaultwarden_backend_port` and `vaultwarden_https_port` in the shared settings
if needed.

## Configure the Docker VM firewalls in Proxmox

`proxmox-firewall.yml` uses the Proxmox SSH connection to configure VM `102`
(Vaultwarden) and VM `101` (Arr). Their rules are in
`group_vars/proxmox_hosts.yml`. Both allow SSH from the LAN and their web
backends from Nginx. The Arr VM also allows qBittorrent peer port `6881` over
TCP and UDP. Each VM has an inbound `DROP` policy.

```bash
ansible-playbook proxmox-firewall.yml --check
ansible-playbook proxmox-firewall.yml
```

With datacenter enforcement off, the second command stages the guest rules
and selects the nftables backend on `pve1`. After switching backends, stop
and start the running VMs and containers on the node so Proxmox recreates
their virtual network interfaces. Review the other node and guest policies,
then enable datacenter enforcement with host input and output accepted:

```bash
ansible-playbook proxmox-firewall.yml -e proxmox_firewall_enable_datacenter=true
```

Verify fresh SSH connections to the Proxmox host and both VMs. Check that the
sites still work through Nginx and that a LAN client cannot reach the published
web ports directly. Inspect the active rules with `nft list ruleset` on `pve1`.

## Configure and run Pi-hole

`pihole.yml` installs [Pi-hole](https://docs.pi-hole.net/main/basic-install/)
directly in the existing Debian LXC in `pihole_hosts`. The LXC needs a static
IP (`PIHOLE_HOST` in `../.env`) and working network access. If necessary, first
run `ansible-playbook bootstrap-pihole.yml` to create the SSH user; this uses
the Proxmox host and container ID in `pihole_bootstrap`. The bootstrap password
is also the user's sudo password.

Create an encrypted Vault file for the admin password:

```bash
cd ansible
ansible-vault create pihole-secrets.yml
```

Add a nonempty, single-line password to the Vault file:

```yaml
pihole_admin_password: "YOUR_PASSWORD"
```

Verify that TCP and UDP port 53 and TCP ports 80 and 443 are free on the LXC.
Set `HOMELAB_ADMIN_IP` in `../.env` (`pihole_admin_ip`) to your admin device's
fixed LAN IP to allow it to reach the web dashboard. With that variable empty,
the common role adds only SSH and DNS rules for the LAN. Then run:

```bash
ansible pihole_hosts -m ping --ask-become-pass
ansible-playbook pihole.yml -e @pihole-secrets.yml --ask-vault-pass --ask-become-pass
```

On an existing Pi-hole, apply just the firewall with
`ansible-playbook pihole.yml --tags firewall --ask-become-pass`. Review
`sudo ufw status numbered` on the LXC and remove any older web rules that
allow other sources. If the admin device's IP changes, remove its old UFW
allow rule after applying the new one.

Open `http://<PIHOLE_HOST>/admin/` and test DNS, for example with
`dig @<PIHOLE_HOST> example.com`. Once verified, configure clients or the
router's DHCP settings to use that address for DNS. Initial upstreams are
Cloudflare (`1.1.1.1` and `1.0.0.1`); customize `pihole_upstreams` in group
vars before installation, then manage upstreams in Pi-hole. Pi-hole does not
automatically inherit existing local DNS records, so configure any required
local names before switching clients.

Settings and query data live in `/etc/pihole`. The playbook applies the Vault
password on each run; update it in Vault when changing the password. Back up
the configuration before upgrading with `sudo pihole -up`. This setup does not
enable Pi-hole's DHCP server.

