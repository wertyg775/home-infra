# Homeserver infrastructure

Configuration baseline imported from the running homeserver. Review and commit
changes here before copying the relevant files to their live destinations.
This repository is not automatically deployed.

## Repository layout

```text
homelab-infra/
├── .gitignore
├── README.md
├── apt/
│   ├── preferences.d/
│   │   ├── ubuntu-pro-esm-apps
│   │   └── ubuntu-pro-esm-infra
│   ├── sources.list
│   └── sources.list.d/
│       ├── docker.sources
│       ├── tailscale.list
│       └── ubuntu.sources
├── networking/
│   ├── dnsmasq.d/
│   │   └── cloud-home-arpa.conf
│   ├── nftables.conf
│   └── wifi-powersave-off.conf
├── nextcloud/
│   ├── .env.example
│   ├── compose.yaml
│   └── zz-container.config.php
├── nginx/
│   ├── conf.d/
│   │   └── nextcloud-upstream.conf
│   └── sites-available/
│       └── nextcloud
└── ssh/
    └── sshd_config
```

View the current directory tree, including untracked and hidden files but
excluding Git's internal directory:

```bash
cd /home/admin/homelab-infra
# Install once if the tree command is missing:
sudo apt install tree
tree -a -I .git
```

Git can also list paths, without the tree drawing:

```bash
# Tracked files, including newly staged files:
git ls-files

# Files in the latest commit (requires an existing commit):
git ls-tree -r --name-only HEAD
```

Untracked files appear in `tree` but not in these Git listings.

## Live destinations

| Repository path | Live path |
| --- | --- |
| nextcloud/compose.yaml | /opt/nextcloud/compose.yaml |
| nextcloud/.env.example | Template for /opt/nextcloud/.env; never deploy placeholders |
| nextcloud/zz-container.config.php | /srv/nextcloud-container/html/config/zz-container.config.php |
| nginx/ | Custom files under /etc/nginx; enable the Nextcloud site with the symlink documented below |
| networking/nftables.conf | /etc/nftables.conf |
| networking/dnsmasq.d/ | /etc/dnsmasq.d/ |
| networking/wifi-powersave-off.conf | /etc/NetworkManager/conf.d/wifi-powersave-off.conf |
| ssh/ | Corresponding files under /etc/ssh |
| apt/ | Corresponding sources and preferences under /etc/apt |

## Service ownership

Host Nginx terminates HTTPS and proxies to 127.0.0.1:8080.
Docker Compose runs Nextcloud app, cron, MariaDB and Redis.
Host systemd manages Docker, Nginx, DNS, Tailscale and the firewall.
The old host MariaDB, Redis, PHP-FPM and Nextcloud timer are retired;
verify their state with systemctl when needed.

## Separate protected backups required

- /opt/nextcloud/.env: actual database credentials and image settings.
- /srv/nextcloud-container/html/config/: full application configuration/secrets.
- /srv/nextcloud-data/: uploaded files.
- /srv/nextcloud-container/mariadb/: live database storage; use a consistent
  database backup procedure, not an ordinary copy while MariaDB is writing.
- Custom apps/themes and a consistent logical MariaDB dump.
- /etc/ssl/private/ and /root/nextcloud-pki/: TLS/CA private material.
- /etc/ssl/certs/cloud.home.arpa.crt and /etc/ssl/certs/ca.crt: certificates.
- /root/nextcloud-credentials and migration backup/state files.
- SSH host keys, Wi-Fi credentials and Tailscale state, or documented steps
  to regenerate/re-enroll them where appropriate.

Use a protected backup destination on another device and test restoration.
Git history is neither a database backup nor a credential store.

## Change workflow

Edit a repository copy, review its diff, validate, commit, then deploy only
the changed files with correct ownership and permissions. Validate the live
configuration before reload. Record the deployed commit after health checks.
Keep /opt/nextcloud as the Compose project directory to preserve project identity.
Image upgrades need their own Nextcloud/database compatibility and backup checks.

## Package defaults and site enablement

Unchanged vendor configuration is supplied by installed packages. Keep custom
configuration here; query runtime status and package inventories when needed.
The active APT sources remain tracked to document where packages come from.

The Nextcloud site uses this symlink on the live host:

```text
/etc/nginx/sites-enabled/nextcloud -> /etc/nginx/sites-available/nextcloud
```

The package default site was also enabled at capture time. Its unchanged
contents are supplied by nginx-common; this repository cleanup does not alter
that live site. The main nginx.conf and mime.types also match package defaults.

nginx/conf.d/nextcloud-upstream.conf is a custom legacy PHP-FPM upstream from
the bare-metal installation. It is retained because it is still a live custom
configuration file; reviewing its retirement is separate from repository cleanup.

Image versions are recorded in nextcloud/.env.example. Actual credentials remain
in /opt/nextcloud/.env and must be backed up separately.
