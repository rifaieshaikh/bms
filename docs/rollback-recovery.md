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

## Restore Data from Backup ZIP

### Via the application

1. Open **Export / Backup**
2. Under **Restore from backup**, upload a backup ZIP
3. Run a **dry run** first to validate
4. Uncheck dry run and click **Restore**

### Via CLI

```powershell
cd "C:\Program Files\VayBooks-BMS\app"
..\python\python.exe -m vaybooks.bms.infrastructure.backup.cli backup
```

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
