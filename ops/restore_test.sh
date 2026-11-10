#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test "$#" -eq 1 || { printf 'Usage: bash ops/restore_test.sh backups/file.sql\n'; exit 1; }
test -f "$1"
# Fresh separate database; fails if it already exists. Never drops live data.
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "CREATE DATABASE timetable_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"'
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot timetable_restore' < "$1"
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot timetable_restore -e "SELECT * FROM terms; SELECT COUNT(*) AS lesson_count FROM lessons;"'
