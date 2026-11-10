#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
chmod 700 backups
umask 077
target="backups/timetable-$(date -u +%Y%m%dT%H%M%SZ).sql"
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --no-tablespaces --set-gtid-purged=OFF timetable' \
  > "$target.tmp"
mv "$target.tmp" "$target"
printf 'Backup saved: %s\n' "$target"
