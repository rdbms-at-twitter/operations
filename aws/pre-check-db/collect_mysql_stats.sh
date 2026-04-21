#!/bin/bash
################################################################################
# MySQL Instance Statistics Collector for Aurora Migration Sizing
#
# Usage:
#   Run twice: (1) typical workload  (2) peak workload
#   Collects 60-second delta of Global Status / InnoDB Status,
#   plus OS metrics, binary log info, and schema metadata.
#
# Epoch time conversion:
#   SQL:   SELECT FROM_UNIXTIME(1701933453);
#   Shell: date --date "@1701933453"
################################################################################

# ── Usage ─────────────────────────────────────────────────────────────────────
if [ $# -lt 3 ]; then
  echo "Usage: $0 <hostname> <mysql_user> <mysql_password> [--local]"
  echo ""
  echo "  --local   Collect OS info (lscpu, free, iostat, etc.)"
  echo "            Required when running on the DB server itself (on-premise)."
  echo "            Omit when connecting to RDS/Aurora remotely."
  echo ""
  echo "Example (on-premise):  $0 192.168.1.1 admin MyP@ss --local"
  echo "Example (RDS/Aurora):  $0 mydb.cluster-xxx.rds.amazonaws.com admin MyP@ss"
  exit 1
fi

# ── Configuration ─────────────────────────────────────────────────────────────
INSTANCE_ENDPOINT="$1"
USER="$2"
PWD="$3"
LOCAL_OS="no"
if [ "${4:-}" = "--local" ]; then LOCAL_OS="yes"; fi
INTERVAL=60                              # Seconds between 1st and 2nd snapshot

FILE_DATE=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_PATH="/tmp/database_check/${INSTANCE_ENDPOINT}"
EXT1=".1st.log"
EXT2=".2nd.log"
ERR_LOG="${LOG_PATH}/errors_${FILE_DATE}.log"

export MYSQL_PWD="${PWD}"
MYSQL="mysql -h ${INSTANCE_ENDPOINT} -u ${USER}"

# ── Connection Test ───────────────────────────────────────────────────────────
echo "Testing MySQL connection to ${INSTANCE_ENDPOINT} ..."
if ! ${MYSQL} -Be "SELECT 1;" >/dev/null 2>&1; then
  echo "ERROR: Cannot connect to MySQL. Check hostname/user/password."
  exit 1
fi
echo "Connection OK."

# ── Helper ────────────────────────────────────────────────────────────────────
run_sql() {
  local out
  out=$(${MYSQL} -Be "$1" 2>>"${ERR_LOG}") || { echo "(query failed)" >> "${ERR_LOG}"; return 1; }
  echo "$out"
}
run_sql_v() {
  local out
  out=$(${MYSQL} -e "$1" 2>>"${ERR_LOG}") || { echo "(query failed)" >> "${ERR_LOG}"; return 1; }
  echo "$out"
}

# ── Directory Setup ───────────────────────────────────────────────────────────
DIRS=(globalvariables globalstatus enginestatus processlist innodbtrx datalock replication osinfo schema binlog perfschema)

if [ -d "${LOG_PATH}" ]; then
  echo "WARNING: ${LOG_PATH} already exists. Appending with timestamp ${FILE_DATE}."
fi
for d in "${DIRS[@]}"; do mkdir -p "${LOG_PATH}/${d}"; done
: > "${ERR_LOG}"

# ══════════════════════════════════════════════════════════════════════════════
# 1. One-time collection (run once, not affected by interval)
# ══════════════════════════════════════════════════════════════════════════════

echo "[1/5] Collecting one-time data (variables, OS, schema, binlog) ..."

# ── Global Variables ──────────────────────────────────────────────────────────
run_sql "SHOW GLOBAL VARIABLES;" > "${LOG_PATH}/globalvariables/${FILE_DATE}.log"

# ── OS / Hardware Info (on-premise only — requires local execution) ────────────
OS_LOG="${LOG_PATH}/osinfo/${FILE_DATE}.log"
IOSTAT_PID=""
VMSTAT_PID=""

if [ "${LOCAL_OS}" = "yes" ]; then
  echo "  Collecting OS info (--local mode) ..."
  {
    echo "===== hostname ====="
    hostname 2>/dev/null || true

    echo -e "\n===== uname -a ====="
    uname -a 2>/dev/null || true

    echo -e "\n===== lscpu ====="
    lscpu 2>/dev/null || echo "(lscpu not available)"

    echo -e "\n===== free -h ====="
    free -h 2>/dev/null || echo "(free not available)"

    echo -e "\n===== df -hT ====="
    df -hT 2>/dev/null || echo "(df not available)"

    echo -e "\n===== lsblk ====="
    lsblk 2>/dev/null || echo "(lsblk not available)"

    echo -e "\n===== cat /proc/cpuinfo (summary) ====="
    grep -m1 'model name' /proc/cpuinfo 2>/dev/null || true
    echo "processor count: $(grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo N/A)"

    echo -e "\n===== cat /proc/meminfo (head) ====="
    head -5 /proc/meminfo 2>/dev/null || true

    echo -e "\n===== uptime ====="
    uptime 2>/dev/null || true
  } > "${OS_LOG}"

  if command -v iostat &>/dev/null; then
    iostat -xmt 1 3 > "${LOG_PATH}/osinfo/${FILE_DATE}_iostat.log" 2>/dev/null &
    IOSTAT_PID=$!
  else
    echo "(iostat not available — install sysstat for disk I/O metrics)" >> "${OS_LOG}"
  fi

  if command -v vmstat &>/dev/null; then
    vmstat 1 5 > "${LOG_PATH}/osinfo/${FILE_DATE}_vmstat.log" 2>/dev/null &
    VMSTAT_PID=$!
  fi
else
  echo "  Skipping OS info (use --local for on-premise servers)."
fi

# ── Schema Metadata (lightweight queries) ─────────────────────────────────────
SCHEMA_LOG="${LOG_PATH}/schema/${FILE_DATE}.log"
{
  echo "===== MySQL Version ====="
  run_sql "SELECT VERSION();"

  echo -e "\n===== Database Sizes (innodb_tablespaces — lightweight) ====="
  run_sql "
    SELECT
      SUBSTRING_INDEX(NAME, '/', 1) AS schema_name,
      COUNT(*)                      AS table_count,
      ROUND(SUM(FILE_SIZE) / 1024 / 1024 / 1024, 2) AS total_gb
    FROM information_schema.innodb_tablespaces
    WHERE NAME NOT LIKE 'mysql/%'
      AND NAME NOT LIKE 'sys/%'
      AND NAME LIKE '%/%'
    GROUP BY SUBSTRING_INDEX(NAME, '/', 1)
    ORDER BY total_gb DESC;
  "

  echo -e "\n===== Top 30 Largest Tables (innodb_tablespaces) ====="
  run_sql "
    SELECT
      NAME                                            AS tablespace_name,
      ROUND(FILE_SIZE / 1024 / 1024 / 1024, 2)       AS size_gb,
      ROW_FORMAT
    FROM information_schema.innodb_tablespaces
    WHERE NAME NOT LIKE 'mysql/%'
      AND NAME NOT LIKE 'sys/%'
      AND NAME LIKE '%/%'
    ORDER BY FILE_SIZE DESC
    LIMIT 30;
  "

  echo -e "\n===== Non-InnoDB Tables (filtered — lightweight) ====="
  run_sql "
    SELECT table_schema, table_name, engine
    FROM information_schema.tables
    WHERE engine IS NOT NULL
      AND engine != 'InnoDB'
      AND table_schema NOT IN ('mysql','information_schema','performance_schema','sys');
  "

  echo -e "\n===== Event Scheduler Jobs ====="
  run_sql "SELECT event_schema, event_name, status, interval_value, interval_field, last_executed FROM information_schema.events;" || true

  echo -e "\n===== Stored Routines Count ====="
  run_sql "
    SELECT routine_schema, routine_type, COUNT(*) AS cnt
    FROM information_schema.routines
    WHERE routine_schema NOT IN ('mysql','sys')
    GROUP BY routine_schema, routine_type;
  " || true

  echo -e "\n===== Triggers Count ====="
  run_sql "
    SELECT trigger_schema, COUNT(*) AS cnt
    FROM information_schema.triggers
    WHERE trigger_schema NOT IN ('mysql','sys')
    GROUP BY trigger_schema;
  " || true
} > "${SCHEMA_LOG}"

# ── Binary Log Info ───────────────────────────────────────────────────────────
BINLOG_LOG="${LOG_PATH}/binlog/${FILE_DATE}.log"
{
  echo "===== SHOW BINARY LOGS ====="
  run_sql "SHOW BINARY LOGS;" || echo "(binary logging may be disabled)"

  echo -e "\n===== SHOW MASTER STATUS ====="
  run_sql_v "SHOW MASTER STATUS;" || true

  echo -e "\n===== binlog variables ====="
  run_sql "SHOW GLOBAL VARIABLES LIKE '%binlog%';"
  run_sql "SHOW GLOBAL VARIABLES LIKE 'log_bin%';"
  run_sql "SHOW GLOBAL VARIABLES LIKE 'expire_logs%';"
} > "${BINLOG_LOG}"

# ── Performance Schema Statistics ──────────────────────────────────────────────
PERF_LOG="${LOG_PATH}/perfschema/${FILE_DATE}.log"
{
  echo "===== Top 20 Queries by AVG Latency (events_statements_summary_by_digest) ====="
  run_sql "
    SELECT sys.format_statement(DIGEST_TEXT) AS query,
           FORMAT_PICO_TIME(AVG_TIMER_WAIT) AS avg_latency,
           FORMAT_PICO_TIME(MIN_TIMER_WAIT) AS min_latency,
           FORMAT_PICO_TIME(MAX_TIMER_WAIT) AS max_latency,
           COUNT_STAR                       AS exec_count,
           SUM_ROWS_EXAMINED                AS rows_examined,
           SUM_ROWS_SENT                    AS rows_sent,
           SUM_ROWS_AFFECTED                AS rows_affected,
           IFNULL(SCHEMA_NAME, '(none)')    AS schema_name,
           DIGEST
    FROM performance_schema.events_statements_summary_by_digest
    WHERE DIGEST_TEXT IS NOT NULL
    ORDER BY AVG_TIMER_WAIT DESC
    LIMIT 20;
  "

  echo -e "\n===== Top 20 Queries by Total Latency ====="
  run_sql "
    SELECT sys.format_statement(DIGEST_TEXT) AS query,
           FORMAT_PICO_TIME(SUM_TIMER_WAIT) AS total_latency,
           FORMAT_PICO_TIME(AVG_TIMER_WAIT) AS avg_latency,
           COUNT_STAR                       AS exec_count,
           SUM_ROWS_EXAMINED                AS rows_examined,
           SUM_ROWS_SENT                    AS rows_sent,
           IFNULL(SCHEMA_NAME, '(none)')    AS schema_name
    FROM performance_schema.events_statements_summary_by_digest
    WHERE DIGEST_TEXT IS NOT NULL
    ORDER BY SUM_TIMER_WAIT DESC
    LIMIT 20;
  "

  echo -e "\n===== Top 20 Queries by Rows Examined ====="
  run_sql "
    SELECT sys.format_statement(DIGEST_TEXT) AS query,
           SUM_ROWS_EXAMINED                AS rows_examined,
           COUNT_STAR                       AS exec_count,
           FORMAT_PICO_TIME(AVG_TIMER_WAIT) AS avg_latency,
           IFNULL(SCHEMA_NAME, '(none)')    AS schema_name
    FROM performance_schema.events_statements_summary_by_digest
    WHERE DIGEST_TEXT IS NOT NULL
    ORDER BY SUM_ROWS_EXAMINED DESC
    LIMIT 20;
  "

  echo -e "\n===== Top 20 Queries by Execution Count ====="
  run_sql "
    SELECT sys.format_statement(DIGEST_TEXT) AS query,
           COUNT_STAR                       AS exec_count,
           FORMAT_PICO_TIME(AVG_TIMER_WAIT) AS avg_latency,
           SUM_ROWS_EXAMINED                AS rows_examined,
           SUM_ROWS_SENT                    AS rows_sent,
           IFNULL(SCHEMA_NAME, '(none)')    AS schema_name
    FROM performance_schema.events_statements_summary_by_digest
    WHERE DIGEST_TEXT IS NOT NULL
    ORDER BY COUNT_STAR DESC
    LIMIT 20;
  "

  echo -e "\n===== Table I/O Waits (top 30 by COUNT_STAR) ====="
  run_sql "
    SELECT OBJECT_SCHEMA, OBJECT_NAME,
           COUNT_READ, COUNT_WRITE, COUNT_FETCH,
           COUNT_INSERT, COUNT_UPDATE, COUNT_DELETE,
           FORMAT_PICO_TIME(AVG_TIMER_READ)   AS avg_read,
           FORMAT_PICO_TIME(AVG_TIMER_WRITE)  AS avg_write,
           FORMAT_PICO_TIME(AVG_TIMER_FETCH)  AS avg_fetch,
           FORMAT_PICO_TIME(AVG_TIMER_INSERT) AS avg_insert,
           FORMAT_PICO_TIME(AVG_TIMER_UPDATE) AS avg_update,
           FORMAT_PICO_TIME(AVG_TIMER_DELETE) AS avg_delete
    FROM performance_schema.table_io_waits_summary_by_table
    WHERE OBJECT_SCHEMA NOT IN ('mysql','information_schema','performance_schema','sys')
    ORDER BY COUNT_STAR DESC
    LIMIT 30;
  "

  echo -e "\n===== InnoDB SX-Lock Waits (events_waits_history) ====="
  run_sql "
    SELECT ewhl.THREAD_ID, ewhl.EVENT_NAME, ewhl.OPERATION,
           ewhl.SOURCE,
           sys.format_statement(esc.DIGEST_TEXT) AS sql_text,
           COUNT(*) AS total
    FROM performance_schema.events_waits_history ewhl
    LEFT JOIN performance_schema.events_statements_history esc
      ON ewhl.THREAD_ID = esc.THREAD_ID
    WHERE ewhl.EVENT_NAME LIKE 'wait/synch/sxlock/innodb%'
    GROUP BY ewhl.THREAD_ID, ewhl.EVENT_NAME, ewhl.OPERATION, ewhl.SOURCE, sql_text
    ORDER BY total DESC;
  " || true

  echo -e "\n===== Top Wait Events (events_waits_summary_global_by_event_name) ====="
  run_sql "
    SELECT EVENT_NAME,
           COUNT_STAR,
           FORMAT_PICO_TIME(SUM_TIMER_WAIT)  AS total_wait,
           FORMAT_PICO_TIME(AVG_TIMER_WAIT)  AS avg_wait
    FROM performance_schema.events_waits_summary_global_by_event_name
    WHERE COUNT_STAR > 0
      AND EVENT_NAME != 'idle'
    ORDER BY SUM_TIMER_WAIT DESC
    LIMIT 20;
  " || true

  echo -e "\n===== File I/O Summary (top 20) ====="
  run_sql "
    SELECT FILE_NAME,
           COUNT_STAR,
           FORMAT_PICO_TIME(SUM_TIMER_WAIT) AS total_wait,
           FORMAT_BYTES(SUM_NUMBER_OF_BYTES_READ)    AS bytes_read,
           FORMAT_BYTES(SUM_NUMBER_OF_BYTES_WRITE)   AS bytes_written
    FROM performance_schema.file_summary_by_instance
    WHERE COUNT_STAR > 0
    ORDER BY SUM_TIMER_WAIT DESC
    LIMIT 20;
  " || true

  echo -e "\n===== Memory Usage by Event (top 20) ====="
  run_sql "
    SELECT EVENT_NAME,
           CURRENT_COUNT_USED,
           FORMAT_BYTES(CURRENT_NUMBER_OF_BYTES_USED) AS current_bytes,
           FORMAT_BYTES(HIGH_NUMBER_OF_BYTES_USED)    AS high_water_mark
    FROM performance_schema.memory_summary_global_by_event_name
    WHERE CURRENT_NUMBER_OF_BYTES_USED > 0
    ORDER BY CURRENT_NUMBER_OF_BYTES_USED DESC
    LIMIT 20;
  " || true
} > "${PERF_LOG}"

echo "[1/5] Done."

# ══════════════════════════════════════════════════════════════════════════════
# 2. First snapshot
# ══════════════════════════════════════════════════════════════════════════════
echo "[2/5] Taking 1st snapshot ..."

run_sql  "SHOW GLOBAL STATUS;"                                                  > "${LOG_PATH}/globalstatus/${FILE_DATE}${EXT1}"
run_sql_v "SHOW ENGINE INNODB STATUS\G"                                         > "${LOG_PATH}/enginestatus/${FILE_DATE}${EXT1}"
run_sql  "SELECT *, PS_THREAD_ID(ID) FROM performance_schema.processlist;"      > "${LOG_PATH}/processlist/${FILE_DATE}${EXT1}"
run_sql  "SELECT * FROM information_schema.innodb_trx;"                         > "${LOG_PATH}/innodbtrx/${FILE_DATE}${EXT1}"
run_sql  "SELECT * FROM performance_schema.data_locks;"                         > "${LOG_PATH}/datalock/${FILE_DATE}${EXT1}"

# MySQL 8.0: SHOW REPLICA STATUS; older: SHOW SLAVE STATUS
run_sql_v "SHOW REPLICA STATUS\G"  > "${LOG_PATH}/replication/${FILE_DATE}${EXT1}" 2>/dev/null \
  || run_sql_v "SHOW SLAVE STATUS\G" > "${LOG_PATH}/replication/${FILE_DATE}${EXT1}" 2>/dev/null \
  || echo "(no replication configured)" > "${LOG_PATH}/replication/${FILE_DATE}${EXT1}"

echo "[2/5] Done."

# ══════════════════════════════════════════════════════════════════════════════
# 3. Wait interval
# ══════════════════════════════════════════════════════════════════════════════
echo "[3/5] Waiting ${INTERVAL} seconds ..."
for I in $(seq 1 ${INTERVAL}); do
  sleep 1
  BAR=$(printf '%*s' "$I" '' | tr ' ' '.')
  printf "\r  [%3d/%d] %s" "${I}" "${INTERVAL}" "${BAR}"
done
printf "\n[3/5] Done.\n"

# ══════════════════════════════════════════════════════════════════════════════
# 4. Second snapshot
# ══════════════════════════════════════════════════════════════════════════════
echo "[4/5] Taking 2nd snapshot ..."

run_sql  "SHOW GLOBAL STATUS;"                                                  > "${LOG_PATH}/globalstatus/${FILE_DATE}${EXT2}"
run_sql_v "SHOW ENGINE INNODB STATUS\G"                                         > "${LOG_PATH}/enginestatus/${FILE_DATE}${EXT2}"
run_sql  "SELECT *, PS_THREAD_ID(ID) FROM performance_schema.processlist;"      > "${LOG_PATH}/processlist/${FILE_DATE}${EXT2}"
run_sql  "SELECT * FROM information_schema.innodb_trx;"                         > "${LOG_PATH}/innodbtrx/${FILE_DATE}${EXT2}"
run_sql  "SELECT * FROM performance_schema.data_locks;"                         > "${LOG_PATH}/datalock/${FILE_DATE}${EXT2}"

run_sql_v "SHOW REPLICA STATUS\G"  > "${LOG_PATH}/replication/${FILE_DATE}${EXT2}" 2>/dev/null \
  || run_sql_v "SHOW SLAVE STATUS\G" > "${LOG_PATH}/replication/${FILE_DATE}${EXT2}" 2>/dev/null \
  || echo "(no replication configured)" > "${LOG_PATH}/replication/${FILE_DATE}${EXT2}"

echo "[4/5] Done."

# ══════════════════════════════════════════════════════════════════════════════
# 5. Cleanup background jobs
# ══════════════════════════════════════════════════════════════════════════════
echo "[5/5] Finalizing ..."
[ -n "${IOSTAT_PID:-}" ] && wait "${IOSTAT_PID}" 2>/dev/null || true
[ -n "${VMSTAT_PID:-}" ] && wait "${VMSTAT_PID}" 2>/dev/null || true

echo ""
echo "=========================================="
echo " Collection complete: ${FILE_DATE}"
echo " Output directory:    ${LOG_PATH}"
if [ -s "${ERR_LOG}" ]; then
  echo " ⚠ Errors logged:    ${ERR_LOG}"
else
  echo " ✓ No errors"
  rm -f "${ERR_LOG}"
fi
echo "=========================================="
echo ""
ls -lhR "${LOG_PATH}" | head -60
