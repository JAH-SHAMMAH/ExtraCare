# Fairview School Portal — Backup & Restore Runbook

The portal holds irreplaceable records (students, attendance, results, fees, HR).
This document is the agreed backup strategy and the **restore** procedure. A
backup you have never restored is not a backup — run the drill (bottom).

## Mechanism

`backend/scripts/backup_db.py` produces a timestamped, **consistent** snapshot
from `DATABASE_URL` (no app downtime):

- **SQLite** (dev): `VACUUM INTO` → gzipped `.db.gz`
- **MySQL / TiDB** (prod): `mysqldump --single-transaction` → `.sql.gz`
- **PostgreSQL**: `pg_dump --format=custom` → `.dump`

```bash
# default: ./backups, 14-day retention
python scripts/backup_db.py
# production example
BACKUP_DIR=/var/backups/fairview BACKUP_RETENTION_DAYS=30 python scripts/backup_db.py
```

## Strategy (production)

| Item | Policy |
|---|---|
| **Schedule** | Nightly full backup (cron/systemd timer/CI), 02:00 Africa/Lagos |
| **Frequency** | Nightly full + (TiDB/MySQL) binlog or managed PITR for point-in-time |
| **Retention** | 14 daily, 8 weekly, 6 monthly (adjust `BACKUP_RETENTION_DAYS`) |
| **Off-box** | Copy every snapshot to object storage in a **different region** (S3/GCS/R2). Never rely on the DB host's local disk. |
| **Encryption** | Encrypt at rest (SSE) + in transit; restrict bucket access |
| **Monitoring** | Alert if a nightly backup is missing or 0 bytes |
| **Pre-deploy** | Take an on-demand backup **before every migration/deploy** |

### Example nightly cron (Linux prod)
```cron
0 2 * * *  cd /app/backend && BACKUP_DIR=/var/backups/fairview BACKUP_RETENTION_DAYS=30 \
           /app/backend/venv/bin/python scripts/backup_db.py >> /var/log/fairview-backup.log 2>&1 && \
           aws s3 cp --recursive /var/backups/fairview s3://fairview-backups/$(date +\%F)/
```

> Keep backups **out of OneDrive/Dropbox sync** folders (use a local or mounted path).

## Restore

**SQLite**
```bash
gunzip -c backups/fairview-<ts>.db.gz > restored.db
# point DATABASE_URL at it, or replace the live file while the app is stopped
```

**MySQL / TiDB**
```bash
gunzip -c fairview-<ts>.sql.gz | mysql -h <host> -P 3306 -u <user> -p <database>
```

**PostgreSQL**
```bash
pg_restore --clean --no-owner --dbname "postgresql://<user>:<pw>@<host>:5432/<db>" fairview-<ts>.dump
```

After restore, run `alembic current` to confirm the schema revision, then smoke-test `/health` and a login.

## Quarterly restore drill (do not skip)

1. Provision a throwaway DB.
2. Restore the **latest** off-box backup into it.
3. Point a staging app at it; `alembic current` shows `002_add_attendance_events` (or head).
4. Log in as the principal; verify student count, recent attendance, and a fee record.
5. Record the **RTO** (time to restore) and **RPO** (data-loss window) actually achieved.
6. File the result; fix anything that made the drill slow or lossy.
