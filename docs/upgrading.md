# VayBooks-BMS Upgrading Guide

## In-App Update (Desktop)

1. Open **System → Updates** in the sidebar
2. Click **Check for Updates**
3. If a new version is available, review release notes
4. Click **Download & Install**
5. The installer runs silently — service stops, data is backed up, app files are replaced, service restarts

## Manual Update (Windows)

1. Download the latest `VayBooks-BMS-Setup-{version}.exe` from GitHub Releases
2. Run the installer — it detects the existing installation
3. Pre-upgrade backup is created automatically at:
   `C:\ProgramData\VayBooks-BMS\data\backups\pre_upgrade_{version}_{timestamp}.zip`

## What Is Preserved

| Data | Preserved |
|------|-----------|
| `config.toml` | Yes (backed up before upgrade) |
| MongoDB data (local) | Yes — never overwritten |
| Uploads | Yes |
| Backups | Yes |
| Logs | Yes (appended) |

## What Is Replaced

| Data | Replaced |
|------|----------|
| `C:\Program Files\VayBooks-BMS\` | Yes — app binaries, Python, tools |

## Database Migrations

Migrations run automatically on next startup after upgrade. History is stored in the `schema_migrations` MongoDB collection.

## Cloud Deployments

For Streamlit Cloud, AWS, or Azure: redeploy the `bms/` app from the new git tag. Set `MONGODB_URI` via secrets/env. Migrations run on startup.

See [cloud-deployment.md](cloud-deployment.md).
