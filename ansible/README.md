# Ansible playbook for homelab

Configures homelab VMs over SSH from this workstation.

## Configured VMs

| VM | Role |
|---|---|
| 192.0.2.101 | VM for hosting docker containers  |
| 192.0.2.102 | Bitwarden Lite (configuration required) |
| 192.0.2.104 | Pi-hole LXC |

## Roles (tasks)

### Media VM
| Role | State |
|---|---|
| `common` | timezone, baseline packages, unattended upgrades, SSH hardening, optional UFW |
| `docker` | Docker apt repo + key, engine/Compose packages, `/etc/docker/daemon.json`, docker group |
| `media_stack` | `/srv/media` tree (and optional NFS mount), compose file, running containers |

### Bitwarden VM

`bitwarden.yml` uses the `common`, `docker`, and `bitwarden` roles. The last
role runs the official [Bitwarden Lite image](https://bitwarden.com/help/install-and-deploy-lite/)
with SQLite, HTTPS, and persistent data. It does not build an image. Lite is
intended for personal use and home labs; its image version is pinned in the
role defaults.

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

## Configure and run Bitwarden

The playbook configures an existing Debian/Ubuntu VM; it does not create one.
Before running it, verify that `192.0.2.102` is the intended Bitwarden VM and
that ports 80 and 443 are available. Bitwarden Lite requires Docker Engine 26+,
at least 200 MB of RAM, and 1 GB of storage.

1. Set `ansible_user` and `ansible_ssh_private_key_file` for `bitwarden` in
   `inventory/hosts.yml`. Set `docker_repo_os` and `docker_arch` in
   `group_vars/bitwarden_hosts.yml` to match the VM.
2. Set `bitwarden_domain` to a DNS hostname pointing to the VM. Set
   `bitwarden_tls_cert_src` and `bitwarden_tls_key_src` to paths on the control
   machine for a matching PEM certificate chain and private key. The
   certificate must cover the hostname and be trusted by your devices.
3. Obtain an installation ID and key from <https://bitwarden.com/host/>.
   Store them in an encrypted Ansible Vault file:

   ```bash
   ansible-vault create bitwarden-secrets.yml
   ```

   Put these values in the encrypted file:

   ```yaml
   bitwarden_installation_id: "YOUR_INSTALLATION_ID"
   bitwarden_installation_key: "YOUR_INSTALLATION_KEY"
   ```

4. Configure the optional SMTP fields in `group_vars/bitwarden_hosts.yml` for
   verification emails and invitations. Put `bitwarden_smtp_password` in the
   Vault file as well. SMTP can be added after initial deployment.
5. From the `ansible` directory, test access and run:

   ```bash
   ansible bitwarden_hosts -m ping
   ansible-playbook bitwarden.yml -e @bitwarden-secrets.yml --ask-vault-pass
   ```

Open `https://<your-domain>` after the container starts. Changing certificate
paths or contents and running the playbook again updates the files and restarts
Bitwarden. The role keeps the TLS key and environment file private and runs
the container as an unprivileged user. To apply only the Bitwarden role later,
add `--tags bitwarden` to the playbook command.

The default host ports are 80 and 443. Override `bitwarden_http_port` and
`bitwarden_https_port` if needed; Bitwarden listens on those same ports inside
the container so its HTTP-to-HTTPS redirect uses the externally reachable port.

Data lives under `/opt/stacks/bitwarden/data`; the `backups` directory is mounted
for Bitwarden Lite's backup job. Copy the backups off the VM securely and test
restores; they include sensitive data-protection keys. Back up `settings.env`
separately. See the [backup and restore instructions](https://github.com/bitwarden/self-host/blob/main/bitwarden-lite/backup/README.md).
Before upgrading the pinned `bitwarden_image`, take a backup with the old
container running, then update the image version and rerun the playbook.

The optional common-role UFW rules do not reliably restrict Docker-published
ports. Apply any required network access restrictions at the network firewall
or through Docker-aware firewall rules.

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

