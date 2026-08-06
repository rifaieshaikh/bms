# VayBooks-BMS Rollback & Recovery

## Pre-Upgrade Backup

Every upgrade creates a zip at:

```
C:\ProgramData\VayBooks-BMS\data\backups\pre_upgrade_{version}_{timestamp}.zip
```

Contains `config.toml` and `data/uploads/`.

## Rollback to Previous Version

1. Uninstall the current version (keep ProgramData when prompted)
2. Install the previous `VayBooks-BMS-Setup-{old-version}.exe` from GitHub Releases
3. Verify config at `C:\ProgramData\VayBooks-BMS\config\config.toml`
4. Start the service or use the desktop shortcut

## Database Backup (VayBooks-BMS)

### Modes

- **Complete** — all user MongoDB collections (excludes `system.*`)
- **Balances** — parties (`customers`, `vendors`, …) + `accounts`, plus an AR/AP outstanding summary for audit

Configure under **System Settings** (desktop): schedule (`off` / `daily` / `weekly`), mode, retention (`keep_one` / `keep_all`), and optional Google Drive upload.

### Desktop

- Local ZIPs: `{VAYBOOKS_DATA_DIR}/data/backups/`
- **Backup now** on System Settings or Export / Backup
- Scheduled via in-app scheduler job `system.db_backup` (login-triggered)
- Google Drive: set OAuth client id/secret/refresh token in System Settings; uploads use the Drive File API

### Web / cloud

- Download Complete or Balances ZIP from **Export / Backup**
- No local scheduled files or Drive upload from the browser

### Retention

- `keep_one` — only the latest **managed** backup (`backup_*` / `balances_*`) is kept
- `keep_all` — never auto-delete
- `pre_upgrade_*` and `pre_fy_close_*` archives are never removed by retention

### CLI

```powershell
..\python\python.exe -m vaybooks.bms.infrastructure.backup.cli backup --mode complete
..\python\python.exe -m vaybooks.bms.infrastructure.backup.cli prune
..\python\python.exe -m vaybooks.bms.infrastructure.backup.cli run
```

### Financial year close

Optional year-end migration lives under **Business Settings**:

- **Balances only** — snapshot `opening_balance` from closing balances; soft-lock the prior FY
- **Full pending** — same, plus settle/reopen open receivables and vendor payables with **original dates** (net-zero on party ledgers)

A desktop complete backup is taken before migrate when possible. Closed FYs reject new voucher posts tagged with that FY.

## MongoDB Recovery (Local Install)

If local MongoDB data is corrupted:

1. Stop MongoDB service: `net stop MongoDB`
2. Restore from a full backup ZIP (includes all collections)
3. Or copy `mongodump` archive if you created one manually
4. Start MongoDB: `net start MongoDB`
5. Restart VayBooksBMS service: `net start VayBooksBMS`

## Service Won't Start

1. Check `C:\ProgramData\VayBooks-BMS\logs\service.log`
2. Verify MongoDB is reachable (Settings → Test Connection)
3. Reinstall service:
   ```powershell
   powershell -File "C:\Program Files\VayBooks-BMS\nssm\install_service.ps1" `
     -InstallDir "C:\Program Files\VayBooks-BMS" `
     -DataDir "C:\ProgramData\VayBooks-BMS"
   ```

## Complete Reset (Data Loss Warning)

1. Uninstall and choose to **remove** ProgramData
2. Reinstall fresh
3. Re-enter MongoDB connection or install local MongoDB
