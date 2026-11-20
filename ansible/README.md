# Ansible playbook for homelab

Configures homelab VMs over SSH from this workstation.

## Configured VMs

| VM | Role |
|---|---|
| 192.0.2.101 | VM for hosting docker containers  |
| 192.0.2.102 | Vaultwarden (configuration required) |
| 192.0.2.103 | Nginx reverse proxy |
| 192.0.2.104 | Pi-hole LXC |

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

1. `inventory/hosts.yml` :  set ansible_host, user and ssh private key filepath.

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

## Configure and run Vaultwarden

The playbook configures the existing Vaultwarden VM at `192.0.2.102` and the
Nginx proxy at `192.0.2.103`. It does not create either host or alter existing
proxy sites. The proxy provides HTTPS and forwards requests to Vaultwarden.

1. Set the SSH user and key in `inventory/hosts.yml`. Check `docker_repo_os` and
   `docker_arch` in `group_vars/vaultwarden_hosts.yml` against the app VM.
2. In `group_vars/all/vaultwarden.yml`, set the root CA certificate and signing
   key paths on the control machine. Ansible needs read access to both PEM
   files. Set `vaultwarden_domain` if needed; its DNS record must point to the
   Nginx proxy (`192.0.2.103`). Install the root CA certificate in the trust
   store of each client device. The role signs directly with a root CA.
3. Install the collections from `requirements.yml` and ensure the Ansible
   control machine's Python has `cryptography` installed. The proxy role
   installs `python3-cryptography` on the proxy VM. If the CA key has a
   passphrase, store `vaultwarden_ca_key_passphrase` in an encrypted Ansible
   Vault file; use `-e @vaultwarden-secrets.yml --ask-vault-pass` below.
4. From the `ansible` directory, run the two plays. Run them separately if the
   two `admin` accounts have different sudo passwords:

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

## Configure and run Pi-hole

`pihole.yml` installs [Pi-hole](https://docs.pi-hole.net/main/basic-install/)
directly in the existing Debian LXC in `pihole_hosts`. The LXC needs a static
IP and working network access. The inventory and Terraform configuration use
`192.0.2.104`. If necessary, first run `ansible-playbook bootstrap-pihole.yml`
to create the SSH user; this uses the Proxmox host and container ID in
`pihole_bootstrap`. The bootstrap password is also the user's sudo password.

Create an encrypted Vault file for the admin password:

```bash
cd ansible
ansible-vault create pihole-secrets.yml
```

Add a nonempty, single-line password to the Vault file:

```yaml
pihole_admin_password: "YOUR_PASSWORD"
```

Verify that TCP and UDP port 53 and TCP ports 80 and 443 are free on the LXC,
and restrict access to trusted networks with a firewall. Then run:

```bash
ansible pihole_hosts -m ping --ask-become-pass
ansible-playbook pihole.yml -e @pihole-secrets.yml --ask-vault-pass --ask-become-pass
```

Open `http://192.0.2.104/admin/` and test DNS, for example with
`dig @192.0.2.104 example.com`. Once verified, configure clients or the
router's DHCP settings to use that address for DNS. Initial upstreams are
Cloudflare (`1.1.1.1` and `1.0.0.1`); customize `pihole_upstreams` in group
vars before installation, then manage upstreams in Pi-hole. Pi-hole does not
automatically inherit existing local DNS records, so configure any required
local names before switching clients.

Settings and query data live in `/etc/pihole`. The playbook applies the Vault
password on each run; update it in Vault when changing the password. Back up
the configuration before upgrading with `sudo pihole -up`. This setup does not
enable Pi-hole's DHCP server.

