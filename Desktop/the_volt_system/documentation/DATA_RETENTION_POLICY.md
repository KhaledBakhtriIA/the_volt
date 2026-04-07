# Data Retention and Archival Policy

## Purpose

Control storage growth under `data_api/data` while preserving recent operational data and keeping an auditable archive trail.

## Scope

- `data_api/data/raw`
- `data_api/data/processed`
- `data_api/data/exports`
- `data_api/data/archive`

## Default retention windows

- Raw datasets: 14 days
- Processed datasets: 30 days
- Export datasets: 60 days
- Archived datasets: 180 days

## Execution schedule

Run once per day at 02:30 local time.

## Job module

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.data_retention --prune-archive
```

Recommended first run (preview only):

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.data_retention --prune-archive --dry-run
```

## Environment variables

- `DATA_API_RETENTION_RAW_DAYS` (default `14`)
- `DATA_API_RETENTION_PROCESSED_DAYS` (default `30`)
- `DATA_API_RETENTION_EXPORTS_DAYS` (default `60`)
- `DATA_API_RETENTION_ARCHIVE_DAYS` (default `180`)
- `DATA_API_ARCHIVE_ROOT` (default `<DATA_API_DATA_ROOT>/archive`)

## Output behavior

The retention job prints a JSON summary including:

- execution mode (`archive/delete`, `dry_run`, `prune_archive`)
- policy windows used
- counts/bytes archived and deleted
- archive prune counts/bytes

## Safety policy

- Archive mode is the default behavior.
- Use `--delete-only` only when archive storage is not required.
- Always run `--dry-run` before changing retention windows in production.

## Scheduler examples

Windows Task Scheduler action:

```text
Program/script: C:\Users\user\Desktop\the_volt_system\.venv\Scripts\python.exe
Arguments: -m data_api.jobs.data_retention --prune-archive
Start in: C:\Users\user\Desktop\the_volt_system
```

Linux cron example:

```bash
30 2 * * * /path/to/the_volt_system/.venv/bin/python -m data_api.jobs.data_retention --prune-archive
```
