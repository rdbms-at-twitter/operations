#!/usr/bin/env python3
"""
Generate an HTML sizing report from collect_mysql_stats.sh output.

Usage:
    python3 generate_report.py /tmp/database_check/<endpoint> [timestamp]

If timestamp is omitted, the latest one is auto-detected.
Output: <log_dir>/report_<timestamp>.html
"""

import sys, os, glob, html, re
from pathlib import Path
from datetime import datetime, timedelta

# ─── Argument Parsing ─────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <log_directory> [timestamp]")
    print(f"Example: {sys.argv[0]} /tmp/database_check/myhost.rds.amazonaws.com")
    sys.exit(1)

LOG_DIR = Path(sys.argv[1])
if not LOG_DIR.is_dir():
    print(f"ERROR: {LOG_DIR} is not a directory"); sys.exit(1)

# Auto-detect timestamp from globalvariables files
if len(sys.argv) >= 3:
    TS = sys.argv[2]
else:
    gv_files = sorted(glob.glob(str(LOG_DIR / "globalvariables" / "*.log")))
    if not gv_files:
        print("ERROR: No globalvariables log found"); sys.exit(1)
    TS = Path(gv_files[-1]).stem  # latest timestamp
    print(f"Auto-detected timestamp: {TS}")

ENDPOINT = LOG_DIR.name

# ─── File Readers ─────────────────────────────────────────────────────────────
def read_file(subdir, filename):
    p = LOG_DIR / subdir / filename
    if p.exists() and p.stat().st_size > 0:
        return p.read_text(errors="replace")
    return ""

def read_tsv(subdir, filename):
    """Parse TSV into list of dicts (first row = header)."""
    text = read_file(subdir, filename)
    if not text.strip():
        return []
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        vals = line.split("\t")
        rows.append(dict(zip(headers, vals)))
    return rows

def read_kv_tsv(subdir, filename):
    """Parse 2-column TSV (Variable_name\\tValue) into dict."""
    text = read_file(subdir, filename)
    if not text.strip():
        return {}
    d = {}
    for line in text.strip().split("\n"):
        parts = line.split("\t", 1)
        if len(parts) == 2:
            d[parts[0]] = parts[1]
    return d

def read_sectioned(subdir, filename):
    """Parse ===== section_name ===== delimited file into dict of section->text."""
    text = read_file(subdir, filename)
    if not text.strip():
        return {}
    sections = {}
    current_name = "_header"
    current_lines = []
    for line in text.split("\n"):
        m = re.match(r"^=====\s*(.+?)\s*=====\s*$", line)
        if m:
            if current_lines:
                sections[current_name] = "\n".join(current_lines)
            current_name = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_name] = "\n".join(current_lines)
    return sections

def parse_tsv_block(text):
    """Parse a TSV text block into list of dicts."""
    lines = [l for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:]]

# ─── Data Loading ─────────────────────────────────────────────────────────────
variables = read_kv_tsv("globalvariables", f"{TS}.log")
status_1 = read_kv_tsv("globalstatus", f"{TS}.1st.log")
status_2 = read_kv_tsv("globalstatus", f"{TS}.2nd.log")
innodb_1 = read_file("enginestatus", f"{TS}.1st.log")
innodb_2 = read_file("enginestatus", f"{TS}.2nd.log")
osinfo = read_sectioned("osinfo", f"{TS}.log")
iostat = read_file("osinfo", f"{TS}_iostat.log")
vmstat = read_file("osinfo", f"{TS}_vmstat.log")
schema = read_sectioned("schema", f"{TS}.log")
binlog = read_sectioned("binlog", f"{TS}.log")
perfschema = read_sectioned("perfschema", f"{TS}.log")
processlist_1 = read_tsv("processlist", f"{TS}.1st.log")
processlist_2 = read_tsv("processlist", f"{TS}.2nd.log")
repl_1 = read_file("replication", f"{TS}.1st.log")
errors = read_file(".", f"errors_{TS}.log")

# ─── Compute Status Diff ─────────────────────────────────────────────────────
def status_diff():
    """Compute numeric diff between two SHOW GLOBAL STATUS snapshots."""
    diffs = []
    for key in status_1:
        v1, v2 = status_1.get(key, ""), status_2.get(key, "")
        try:
            n1, n2 = int(v1), int(v2)
            delta = n2 - n1
            if delta != 0:
                diffs.append((key, n1, n2, delta))
        except (ValueError, TypeError):
            pass
    diffs.sort(key=lambda x: abs(x[3]), reverse=True)
    return diffs

# ─── Key Variables for Sizing ─────────────────────────────────────────────────
SIZING_VARS = [
    "version", "version_comment",
    "innodb_buffer_pool_size", "innodb_buffer_pool_instances",
    "innodb_log_file_size", "innodb_log_files_in_group",
    "innodb_io_capacity", "innodb_io_capacity_max",
    "innodb_read_io_threads", "innodb_write_io_threads",
    "innodb_flush_log_at_trx_commit", "sync_binlog",
    "innodb_flush_method",
    "max_connections", "thread_cache_size",
    "table_open_cache", "table_open_cache_instances",
    "tmp_table_size", "max_heap_table_size",
    "innodb_temp_data_file_path",
    "log_bin", "binlog_format", "binlog_row_image",
    "gtid_mode", "enforce_gtid_consistency",
    "character_set_server", "collation_server",
    "default_storage_engine",
    "long_query_time", "slow_query_log",
    "performance_schema",
]

SIZING_STATUS = [
    ("Com_select", "SELECT/min"),
    ("Com_insert", "INSERT/min"),
    ("Com_update", "UPDATE/min"),
    ("Com_delete", "DELETE/min"),
    ("Innodb_rows_read", "InnoDB rows read/min"),
    ("Innodb_rows_inserted", "InnoDB rows inserted/min"),
    ("Innodb_rows_updated", "InnoDB rows updated/min"),
    ("Innodb_rows_deleted", "InnoDB rows deleted/min"),
    ("Innodb_data_reads", "InnoDB data reads/min"),
    ("Innodb_data_writes", "InnoDB data writes/min"),
    ("Innodb_os_log_written", "InnoDB redo written (bytes/min)"),
    ("Innodb_buffer_pool_read_requests", "BP read requests/min"),
    ("Innodb_buffer_pool_reads", "BP disk reads/min"),
    ("Bytes_sent", "Bytes sent/min"),
    ("Bytes_received", "Bytes received/min"),
    ("Created_tmp_tables", "Tmp tables/min"),
    ("Created_tmp_disk_tables", "Tmp disk tables/min"),
    ("Threads_connected", "Threads connected (snapshot)"),
    ("Threads_running", "Threads running (snapshot)"),
    ("Connections", "New connections/min"),
]

# ─── HTML Helpers ─────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(str(s))

def fmt_num(n):
    """Format number with comma separators."""
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)

def fmt_bytes(n):
    """Format bytes to human-readable."""
    try:
        b = int(n)
    except (ValueError, TypeError):
        return str(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024:
            return f"{b:,.1f} {unit}"
        b /= 1024
    return f"{b:,.1f} PB"

def make_table(headers, rows, row_class_fn=None):
    """Generate HTML table from list of lists."""
    h = '<table>\n<thead><tr>'
    for hdr in headers:
        align = ' class="r"' if hdr != headers[0] else ''
        h += f'<th{align}>{esc(hdr)}</th>'
    h += '</tr></thead>\n<tbody>\n'
    for i, row in enumerate(rows):
        cls = f' class="{row_class_fn(i, row)}"' if row_class_fn else ''
        h += f'<tr{cls}>'
        for j, cell in enumerate(row):
            align = ' class="r"' if j > 0 else ''
            h += f'<td{align}>{esc(str(cell))}</td>'
        h += '</tr>\n'
    h += '</tbody></table>\n'
    return h

def make_bar(value, max_val, width=200):
    """Inline CSS bar chart."""
    if max_val == 0:
        pct = 0
    else:
        pct = min(100, abs(value) / max_val * 100)
    color = "#4CAF50" if value >= 0 else "#f44336"
    return f'<div class="bar" style="width:{pct * width / 100:.0f}px;background:{color}"></div>'

def section(title, content, section_id=""):
    sid = f' id="{section_id}"' if section_id else ''
    return f'<div class="section"{sid}><h2>{esc(title)}</h2>\n{content}\n</div>\n'

def pre_block(text):
    if not text.strip():
        return '<p class="empty">No data</p>'
    return f'<pre>{esc(text)}</pre>'

def tsv_section_to_table(text):
    """Convert a TSV text block to an HTML table."""
    rows = parse_tsv_block(text)
    if not rows:
        return '<p class="empty">No data</p>'
    headers = list(rows[0].keys())
    data = [[r.get(h, "") for h in headers] for r in rows]
    return make_table(headers, data)

# ─── Build Report Sections ────────────────────────────────────────────────────
parts = []

# --- 1. Summary ---
uptime_sec = int(status_1.get("Uptime", 0))
uptime_days = uptime_sec // 86400
uptime_hours = (uptime_sec % 86400) // 3600
uptime_mins = (uptime_sec % 3600) // 60
uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_mins}m ({uptime_sec:,} sec)"
# Estimate server start time from collection timestamp and uptime
try:
    collect_dt = datetime.strptime(TS, "%Y-%m-%d_%H-%M-%S")
    start_dt = collect_dt - timedelta(seconds=uptime_sec)
    started_at = start_dt.strftime("%Y-%m-%d %H:%M:%S")
except Exception:
    started_at = "N/A"

summary_rows = [
    ["Endpoint", ENDPOINT],
    ["Timestamp", TS],
    ["MySQL Version", variables.get("version", "N/A")],
    ["Version Comment", variables.get("version_comment", "N/A")],
    ["Buffer Pool Size", fmt_bytes(variables.get("innodb_buffer_pool_size", ""))],
    ["Max Connections", variables.get("max_connections", "N/A")],
    ["Threads Connected (1st)", status_1.get("Threads_connected", "N/A")],
    ["Threads Connected (2nd)", status_2.get("Threads_connected", "N/A")],
    ["Uptime", uptime_str],
    ["Server Started At (estimated)", started_at],
]
parts.append(section("1. Instance Summary", make_table(["Item", "Value"], summary_rows), "summary"))

# --- 2. Key Variables ---
var_rows = []
for v in SIZING_VARS:
    val = variables.get(v, "")
    if v == "innodb_buffer_pool_size" and val:
        val = f"{val} ({fmt_bytes(val)})"
    if val:
        var_rows.append([v, val])
parts.append(section("2. Key Variables (Sizing)", make_table(["Variable", "Value"], var_rows), "variables"))

# --- 3. Status Diff (60s) ---
diffs = status_diff()
# Key metrics table with per-minute rate
key_rows = []
for var_name, label in SIZING_STATUS:
    v1 = status_1.get(var_name, "0")
    v2 = status_2.get(var_name, "0")
    try:
        n1, n2 = int(v1), int(v2)
        delta = n2 - n1
        # Threads_connected/running are gauges, not counters
        if var_name in ("Threads_connected", "Threads_running"):
            key_rows.append([label, fmt_num(n1), fmt_num(n2), "—"])
        else:
            key_rows.append([label, fmt_num(n1), fmt_num(n2), fmt_num(delta)])
    except (ValueError, TypeError):
        key_rows.append([label, v1, v2, "—"])

parts.append(section("3. Key Status Diff (60 sec interval)",
    "<h3>Sizing Metrics</h3>\n" +
    make_table(["Metric", "1st Snapshot", "2nd Snapshot", "Δ diff (60s)"], key_rows) +
    "<h3>All Changed Status Variables (top 50)</h3>\n" +
    make_table(["Variable", "1st", "2nd", "Δ diff"],
               [[d[0], fmt_num(d[1]), fmt_num(d[2]), fmt_num(d[3])] for d in diffs[:50]]),
    "status_diff"))

# --- 4. InnoDB Buffer Pool Hit Rate ---
bp_reads = int(status_2.get("Innodb_buffer_pool_read_requests", 0))
bp_disk = int(status_2.get("Innodb_buffer_pool_reads", 0))
if bp_reads > 0:
    hit_rate = (1 - bp_disk / bp_reads) * 100
    bp_info = f"<p>Buffer Pool Hit Rate: <strong>{hit_rate:.4f}%</strong> (read_requests={fmt_num(bp_reads)}, disk_reads={fmt_num(bp_disk)})</p>"
else:
    bp_info = "<p>Buffer Pool Hit Rate: N/A</p>"

# Dirty pages from InnoDB status
dirty_match = re.search(r"Modified db pages\s+(\d+)", innodb_2)
dirty_pages = dirty_match.group(1) if dirty_match else "N/A"
bp_info += f"<p>Modified (dirty) pages: {fmt_num(dirty_pages)}</p>"

# Redo log written per minute
try:
    redo_delta = int(status_2.get("Innodb_os_log_written", 0)) - int(status_1.get("Innodb_os_log_written", 0))
    if redo_delta > 0:
        bp_info += f"<p>REDO written (60s): {fmt_bytes(redo_delta)} → <strong>{fmt_bytes(redo_delta)} /min</strong></p>"
    else:
        bp_info += '<p>REDO written: <strong>0</strong> — Aurora 環境では <code>Innodb_os_log_written</code> は常に 0 です。'
        bp_info += ' REDO 書き込み量は CloudWatch メトリクス <strong>VolumeBytesWritten</strong> で確認してください。</p>'
except (ValueError, TypeError):
    pass

parts.append(section("4. InnoDB Buffer Pool & REDO", bp_info, "buffer_pool"))

# --- 5. Performance Schema: Top Queries ---
for sec_name, sec_title in [
    ("Top 20 Queries by AVG Latency (events_statements_summary_by_digest)", "5a. Top Queries by AVG Latency"),
    ("Top 20 Queries by Total Latency", "5b. Top Queries by Total Latency"),
    ("Top 20 Queries by Rows Examined", "5c. Top Queries by Rows Examined"),
    ("Top 20 Queries by Execution Count", "5d. Top Queries by Execution Count"),
]:
    text = perfschema.get(sec_name, "")
    parts.append(section(sec_title, tsv_section_to_table(text), sec_name.replace(" ", "_")))

# --- 6. Table I/O Waits ---
tio_text = perfschema.get("Table I/O Waits (top 30 by COUNT_STAR)", "")
parts.append(section("6. Table I/O Waits", tsv_section_to_table(tio_text), "table_io"))

# --- 7. Wait Events & Lock Contention ---
sxlock_text = perfschema.get("InnoDB SX-Lock Waits (events_waits_history)", "")
wait_text = perfschema.get("Top Wait Events (events_waits_summary_global_by_event_name)", "")
parts.append(section("7. Wait Events",
    "<h3>Top Wait Events</h3>\n" + tsv_section_to_table(wait_text) +
    "<h3>InnoDB SX-Lock Waits</h3>\n" + tsv_section_to_table(sxlock_text),
    "waits"))

# --- 8. File I/O & Memory ---
fio_text = perfschema.get("File I/O Summary (top 20)", "")
mem_text = perfschema.get("Memory Usage by Event (top 20)", "")
parts.append(section("8. File I/O & Memory",
    "<h3>File I/O Summary</h3>\n" + tsv_section_to_table(fio_text) +
    "<h3>Memory Usage by Event</h3>\n" + tsv_section_to_table(mem_text),
    "file_io_memory"))

# --- 9. Schema Info ---
schema_parts = ""
for sec_name in ["MySQL Version", "Database Sizes (innodb_tablespaces — lightweight)",
                 "Top 30 Largest Tables (innodb_tablespaces)",
                 "Non-InnoDB Tables (filtered — lightweight)",
                 "Event Scheduler Jobs", "Stored Routines Count", "Triggers Count"]:
    text = schema.get(sec_name, "")
    if text.strip():
        schema_parts += f"<h3>{esc(sec_name)}</h3>\n" + tsv_section_to_table(text)
parts.append(section("9. Schema & Metadata", schema_parts or '<p class="empty">No data</p>', "schema"))

# --- 10. Binary Log ---
binlog_parts = ""
for sec_name in ["SHOW BINARY LOGS", "SHOW MASTER STATUS", "binlog variables"]:
    text = binlog.get(sec_name, "")
    if text.strip():
        binlog_parts += f"<h3>{esc(sec_name)}</h3>\n" + tsv_section_to_table(text)
parts.append(section("10. Binary Log", binlog_parts or '<p class="empty">No data</p>', "binlog"))

# --- 11. OS Info ---
os_parts = ""
for sec_name in ["hostname", "uname -a", "lscpu", "free -h", "df -hT", "lsblk",
                 "cat /proc/cpuinfo (summary)", "cat /proc/meminfo (head)", "uptime"]:
    text = osinfo.get(sec_name, "")
    if text.strip():
        os_parts += f"<h3>{esc(sec_name)}</h3>\n" + pre_block(text)
if iostat.strip():
    os_parts += "<h3>iostat</h3>\n" + pre_block(iostat)
if vmstat.strip():
    os_parts += "<h3>vmstat</h3>\n" + pre_block(vmstat)
parts.append(section("11. OS / Hardware Info", os_parts or '<p class="empty">No data</p>', "osinfo"))

# --- 12. InnoDB Engine Status ---
parts.append(section("12. InnoDB Engine Status (1st snapshot)", pre_block(innodb_1), "innodb_1"))
parts.append(section("13. InnoDB Engine Status (2nd snapshot)", pre_block(innodb_2), "innodb_2"))

# --- 13b. InnoDB Engine Status Diff Analysis ---
def innodb_diff_analysis():
    """Compare key metrics from two SHOW ENGINE INNODB STATUS outputs."""
    def extract_val(text, pattern):
        m = re.search(pattern, text)
        return int(m.group(1)) if m else None

    def extract_float(text, pattern):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else None

    metrics = []

    # History list length (purge lag)
    for label, pat in [
        ("History list length", r"History list length\s+(\d+)"),
        ("Modified db pages", r"Modified db pages\s+(\d+)"),
        ("Database pages", r"Database pages\s+(\d+)"),
        ("Free buffers", r"Free buffers\s+(\d+)"),
        ("Pending reads", r"Pending reads\s+(\d+)"),
        ("Pending writes: LRU", r"Pending writes:\s*LRU\s+(\d+)"),
    ]:
        v1 = extract_val(innodb_1, pat)
        v2 = extract_val(innodb_2, pat)
        if v1 is not None and v2 is not None:
            delta = v2 - v1
            metrics.append((label, fmt_num(v1), fmt_num(v2), f"{delta:+,}" if delta != 0 else "± 0"))

    # Buffer pool hit rate from InnoDB status
    for label, pat in [
        ("Buffer pool hit rate", r"Buffer pool hit rate\s+(\d+)\s*/\s*(\d+)"),
    ]:
        m1 = re.search(pat, innodb_1)
        m2 = re.search(pat, innodb_2)
        if m1 and m2:
            r1 = f"{int(m1.group(1))}/{int(m1.group(2))}"
            r2 = f"{int(m2.group(1))}/{int(m2.group(2))}"
            metrics.append((label, r1, r2, "—"))

    # Log sequence number (not available on Aurora — shared storage manages REDO)
    lsn_available = False
    for label, pat in [
        ("Log sequence number", r"Log sequence number\s+(\d+)"),
        ("Log flushed up to", r"Log flushed up to\s+(\d+)"),
        ("Pages flushed up to", r"Pages flushed up to\s+(\d+)"),
        ("Last checkpoint at", r"Last checkpoint at\s+(\d+)"),
    ]:
        v1 = extract_val(innodb_1, pat)
        v2 = extract_val(innodb_2, pat)
        if v1 is not None and v2 is not None:
            lsn_available = True
            delta = v2 - v1
            metrics.append((label, fmt_num(v1), fmt_num(v2), fmt_bytes(delta) if delta != 0 else "± 0"))

    # Rows operations from InnoDB status
    for label, pat in [
        ("Rows inserted", r"(\d+)\s+inserts"),
        ("Rows updated", r"(\d+)\s+updates"),
        ("Rows deleted", r"(\d+)\s+deletes"),
        ("Rows read", r"(\d+)\s+reads"),
    ]:
        v1 = extract_val(innodb_1, pat)
        v2 = extract_val(innodb_2, pat)
        if v1 is not None and v2 is not None:
            delta = v2 - v1
            metrics.append((label, fmt_num(v1), fmt_num(v2), f"{delta:+,}" if delta != 0 else "± 0"))

    if not metrics:
        return '<p class="empty">Could not parse InnoDB status for comparison</p>'

    h = make_table(["Metric", "1st Snapshot", "2nd Snapshot", "Δ diff (60s)"], metrics)

    # ── Auto-generated observations ──
    obs = []

    # History list length trend
    hl1 = extract_val(innodb_1, r"History list length\s+(\d+)")
    hl2 = extract_val(innodb_2, r"History list length\s+(\d+)")
    if hl1 is not None and hl2 is not None:
        if hl2 > hl1:
            obs.append(f"🟡 History list length が増加 ({hl1:,} → {hl2:,})。Purge が書き込みに追いついていない可能性があります。長時間トランザクションの有無を確認してください。")
        elif hl2 > 1000:
            obs.append(f"🟡 History list length が高い ({hl2:,})。Undo ログの肥大化に注意してください。")
        else:
            obs.append(f"🟢 History list length は安定 ({hl2:,})。Purge は正常に動作しています。")

    # Dirty pages ratio
    dirty = extract_val(innodb_2, r"Modified db pages\s+(\d+)")
    total_pages = extract_val(innodb_2, r"Database pages\s+(\d+)")
    if dirty is not None and total_pages and total_pages > 0:
        dirty_pct = dirty / total_pages * 100
        if dirty_pct > 50:
            obs.append(f"🔴 Dirty page ratio が高い ({dirty_pct:.1f}%)。I/O サブシステムがフラッシュに追いついていない可能性があります。")
        elif dirty_pct > 25:
            obs.append(f"🟡 Dirty page ratio: {dirty_pct:.1f}%。書き込み負荷がやや高い状態です。")
        else:
            obs.append(f"🟢 Dirty page ratio: {dirty_pct:.1f}%。正常範囲です。")

    # Free buffers
    free_buf = extract_val(innodb_2, r"Free buffers\s+(\d+)")
    if free_buf is not None and total_pages and total_pages > 0:
        free_pct = free_buf / (free_buf + total_pages) * 100
        if free_pct < 5:
            obs.append(f"🟡 Free buffers が少ない ({free_pct:.1f}%)。Buffer Pool の拡張を検討してください。")

    # Log checkpoint lag
    if not lsn_available:
        obs.append("ℹ️ Log sequence number / Checkpoint 情報は取得できませんでした。Aurora 環境では共有ストレージ層が REDO を管理するため、これらの値は出力されません。REDO 書き込み量は CloudWatch メトリクス VolumeBytesWritten / VolumeWriteIOPs で確認してください。")
    else:
        lsn = extract_val(innodb_2, r"Log sequence number\s+(\d+)")
        ckpt = extract_val(innodb_2, r"Last checkpoint at\s+(\d+)")
        if lsn is not None and ckpt is not None:
            lag_mb = (lsn - ckpt) / (1024 * 1024)
            if lag_mb > 500:
                obs.append(f"🟡 Checkpoint lag: {lag_mb:,.0f} MB。REDO ログの書き込みが多い状態です。")
            else:
                obs.append(f"🟢 Checkpoint lag: {lag_mb:,.1f} MB。正常範囲です。")

    # Pending I/O
    pending_r = extract_val(innodb_2, r"Pending reads\s+(\d+)")
    if pending_r is not None and pending_r > 0:
        obs.append(f"🟡 Pending reads: {pending_r}。ディスクI/Oがボトルネックの可能性があります。")

    if obs:
        h += '<h3>🔍 InnoDB Status 考察</h3>\n<ul class="notes">\n'
        for o in obs:
            h += f'<li>{esc(o)}</li>\n'
        h += '</ul>\n'

    return h

parts.append(section("13b. InnoDB Engine Status — Diff Analysis", innodb_diff_analysis(), "innodb_diff"))

# --- 14. Processlist ---
if processlist_1:
    headers = list(processlist_1[0].keys())
    data = [[r.get(h, "") for h in headers] for r in processlist_1]
    pl_html = make_table(headers, data)
else:
    pl_html = '<p class="empty">No active queries</p>'
parts.append(section("14. Processlist (1st snapshot)", pl_html, "processlist"))

# --- 15. Replication ---
parts.append(section("15. Replication Status", pre_block(repl_1), "replication"))

# --- 16. Aurora Sizing Recommendation ---
def sizing_recommendation():
    """Generate Aurora instance sizing recommendation based on collected metrics."""
    # ── Gather inputs ──
    bp_size = int(variables.get("innodb_buffer_pool_size", 0))
    bp_gb = bp_size / (1024**3)
    max_conn = int(variables.get("max_connections", 0))
    threads_conn = max(int(status_1.get("Threads_connected", 0)),
                       int(status_2.get("Threads_connected", 0)))

    # REDO per minute (from 60s delta)
    try:
        redo_delta = int(status_2.get("Innodb_os_log_written", 0)) - int(status_1.get("Innodb_os_log_written", 0))
        redo_mb_min = redo_delta / (1024 * 1024)
    except (ValueError, TypeError):
        redo_delta = 0
        redo_mb_min = 0

    # InnoDB row ops per second (from 60s delta)
    def ops_per_sec(key):
        try:
            return (int(status_2.get(key, 0)) - int(status_1.get(key, 0))) / 60
        except (ValueError, TypeError):
            return 0

    reads_s  = ops_per_sec("Innodb_rows_read")
    inserts_s = ops_per_sec("Innodb_rows_inserted")
    updates_s = ops_per_sec("Innodb_rows_updated")
    deletes_s = ops_per_sec("Innodb_rows_deleted")
    writes_s = inserts_s + updates_s + deletes_s

    # ── Aurora instance catalog ──
    # (class, vCPU, memory_gb, max_bandwidth_mbps, network_gbps, generation)
    AURORA_INSTANCES = [
        ("db.r6g.large",      2,    16,   4750,  10,    "Graviton2"),
        ("db.r6g.xlarge",     4,    32,   4750,  10,    "Graviton2"),
        ("db.r6g.2xlarge",    8,    64,   4750,  10,    "Graviton2"),
        ("db.r6g.4xlarge",   16,   128,   4750,  10,    "Graviton2"),
        ("db.r6g.8xlarge",   32,   256,   9500,  12,    "Graviton2"),
        ("db.r6g.12xlarge",  48,   384,  14250,  20,    "Graviton2"),
        ("db.r6g.16xlarge",  64,   512,  19000,  25,    "Graviton2"),
        ("db.r7g.large",      2,    16,  10000,  12.5,  "Graviton3"),
        ("db.r7g.xlarge",     4,    32,  10000,  12.5,  "Graviton3"),
        ("db.r7g.2xlarge",    8,    64,  10000,  15,    "Graviton3"),
        ("db.r7g.4xlarge",   16,   128,  10000,  15,    "Graviton3"),
        ("db.r7g.8xlarge",   32,   256,  10000,  15,    "Graviton3"),
        ("db.r7g.12xlarge",  48,   384,  15000,  22.5,  "Graviton3"),
        ("db.r7g.16xlarge",  64,   512,  20000,  30,    "Graviton3"),
        ("db.r8g.large",      2,    16,  10000,  12.5,  "Graviton4 ★最新"),
        ("db.r8g.xlarge",     4,    32,  10000,  12.5,  "Graviton4 ★最新"),
        ("db.r8g.2xlarge",    8,    64,  10000,  15,    "Graviton4 ★最新"),
        ("db.r8g.4xlarge",   16,   128,  10000,  15,    "Graviton4 ★最新"),
        ("db.r8g.8xlarge",   32,   256,  10000,  15,    "Graviton4 ★最新"),
        ("db.r8g.12xlarge",  48,   384,  15000,  22.5,  "Graviton4 ★最新"),
        ("db.r8g.16xlarge",  64,   512,  20000,  30,    "Graviton4 ★最新"),
        ("db.r8g.24xlarge",  96,   768,  30000,  40,    "Graviton4 ★最新"),
        ("db.r8g.48xlarge", 192,  1536,  40000,  50,    "Graviton4 ★最新"),
    ]

    # ── Sizing logic ──
    # Memory: BP + OS overhead (~20%) + connection memory
    conn_mem_gb = threads_conn * 16 / 1024  # ~16MB per connection estimate
    required_mem_gb = bp_gb * 1.2 + conn_mem_gb + 2  # +2GB OS/Aurora overhead

    # Prefer r8g (latest Graviton4), fallback to r7g, then r6g
    r8g = [(c, v, m, b, n, g) for c, v, m, b, n, g in AURORA_INSTANCES if "r8g." in c and m >= required_mem_gb]
    r7g = [(c, v, m, b, n, g) for c, v, m, b, n, g in AURORA_INSTANCES if "r7g." in c and m >= required_mem_gb]
    r6g = [(c, v, m, b, n, g) for c, v, m, b, n, g in AURORA_INSTANCES if "r6g." in c and m >= required_mem_gb]
    candidates = r8g or r7g or r6g or [AURORA_INSTANCES[-1]]

    rec = candidates[0]  # smallest r8g that fits

    h = '<div class="sizing">\n'
    h += '<h3>📊 Collected Metrics Summary</h3>\n'
    h += '<table>\n<tbody>\n'
    metrics = [
        ("Buffer Pool Size", f"{bp_gb:,.1f} GB"),
        ("Max Connections (setting)", f"{max_conn:,}"),
        ("Threads Connected (peak observed)", f"{threads_conn:,}"),
        ("Estimated connection memory", f"{conn_mem_gb:,.1f} GB"),
        ("Required memory (BP×1.2 + conn + overhead)", f"{required_mem_gb:,.1f} GB"),
        ("REDO written", f"{redo_mb_min:,.1f} MB/min" if redo_mb_min > 0 else "N/A (Aurora: CloudWatch VolumeBytesWritten を参照)"),
        ("InnoDB reads/sec", f"{reads_s:,.0f}"),
        ("InnoDB writes/sec (ins+upd+del)", f"{writes_s:,.0f}"),
        ("  inserts/sec", f"{inserts_s:,.0f}"),
        ("  updates/sec", f"{updates_s:,.0f}"),
        ("  deletes/sec", f"{deletes_s:,.0f}"),
    ]
    for label, val in metrics:
        h += f'<tr><td>{esc(label)}</td><td class="r">{esc(val)}</td></tr>\n'
    h += '</tbody></table>\n'

    h += '<h3>💡 Recommended Aurora Instance</h3>\n'
    h += '<table>\n<thead><tr><th>Item</th><th>Value</th></tr></thead>\n<tbody>\n'
    h += f'<tr><td>Recommended Class</td><td><strong>{rec[0]}</strong></td></tr>\n'
    h += f'<tr><td>Processor</td><td>{rec[5]}</td></tr>\n'
    h += f'<tr><td>vCPU</td><td class="r">{rec[1]}</td></tr>\n'
    h += f'<tr><td>Memory</td><td class="r">{rec[2]} GB</td></tr>\n'
    h += f'<tr><td>Max Bandwidth</td><td class="r">{rec[3]:,} Mbps</td></tr>\n'
    h += f'<tr><td>Network</td><td class="r">{rec[4]} Gbps</td></tr>\n'
    h += '</tbody></table>\n'

    # ── Sizing notes ──
    notes = []
    notes.append("⚠️ この推奨はスナップショット（60秒間）のデータに基づく暫定値です。ピーク時データでの再評価を推奨します。")
    notes.append("⚠️ データ収集中は SHOW GLOBAL STATUS, SHOW ENGINE INNODB STATUS, performance_schema クエリ等がサーバーリソースを消費するため、一時的に負荷が上昇する場合があります。本番環境での実行はメンテナンスウィンドウまたは低負荷時間帯を推奨します。")

    if bp_gb > rec[2] * 0.75:
        notes.append(f"🔴 Buffer Pool ({bp_gb:,.0f}GB) がインスタンスメモリの75%を超えています。1サイズ上のインスタンスを検討してください。")

    if threads_conn > 500:
        notes.append(f"🟡 接続数が多い ({threads_conn:,}) ため、RDS Proxy の導入を検討してください。")

    if redo_mb_min > 100:
        notes.append(f"🟡 REDO書き込み量が多い ({redo_mb_min:,.0f} MB/min)。Aurora I/Oコストに注意してください。Aurora I/O-Optimized の検討を推奨します。")
    elif redo_mb_min > 50:
        notes.append(f"ℹ️ REDO書き込み量: {redo_mb_min:,.0f} MB/min。Aurora Standard で問題ないレベルです。")
    elif redo_mb_min == 0:
        notes.append("ℹ️ Innodb_os_log_written が 0 です。Aurora 環境では常に 0 になります。REDO 書き込み量は CloudWatch メトリクス VolumeBytesWritten / VolumeWriteIOPs で確認してください。")

    if writes_s > 10000:
        notes.append(f"🔴 書き込みが非常に多い ({writes_s:,.0f}/sec)。Aurora I/O-Optimized を強く推奨します。")

    bp_reads_total = int(status_2.get("Innodb_buffer_pool_read_requests", 0))
    bp_disk_total = int(status_2.get("Innodb_buffer_pool_reads", 0))
    if bp_reads_total > 0:
        hit = (1 - bp_disk_total / bp_reads_total) * 100
        if hit < 99.0:
            notes.append(f"🟡 Buffer Pool Hit Rate が低い ({hit:.2f}%)。メモリ不足の可能性があります。1サイズ上を検討してください。")

    tmp_disk_1 = int(status_1.get("Created_tmp_disk_tables", 0))
    tmp_disk_2 = int(status_2.get("Created_tmp_disk_tables", 0))
    tmp_disk_delta = tmp_disk_2 - tmp_disk_1
    if tmp_disk_delta > 10:
        notes.append(f"🟡 ディスクtempテーブルが60秒間に {tmp_disk_delta} 回作成されています。tmp_table_size / max_heap_table_size の調整を検討してください。")

    # Non-InnoDB check
    non_innodb = schema.get("Non-InnoDB Tables (filtered — lightweight)", "")
    if non_innodb.strip() and len(non_innodb.strip().split("\n")) > 1:
        notes.append("🔴 Non-InnoDB テーブルが検出されました。Aurora は InnoDB のみサポートします。移行前にエンジン変換が必要です。")

    h += '<h3>📝 Sizing Notes</h3>\n<ul class="notes">\n'
    for note in notes:
        h += f'<li>{esc(note)}</li>\n'
    h += '</ul>\n'

    # ── All candidates table ──
    h += '<h3>📋 Aurora Instance Comparison</h3>\n'
    h += '<table>\n<thead><tr><th>Instance Class</th><th>Processor</th><th class="r">vCPU</th><th class="r">Memory (GB)</th>'
    h += '<th class="r">Max BW (Mbps)</th><th class="r">Network (Gbps)</th><th>Fit</th></tr></thead>\n<tbody>\n'
    for c, v, m, b, n, g in AURORA_INSTANCES:
        fit = "✅" if m >= required_mem_gb else "❌ mem不足"
        bold = ' style="background:#d4edda"' if c == rec[0] else ''
        h += f'<tr{bold}><td>{c}</td><td>{g}</td><td class="r">{v}</td><td class="r">{m}</td>'
        h += f'<td class="r">{b:,}</td><td class="r">{n}</td><td>{fit}</td></tr>\n'
    h += '</tbody></table>\n'
    h += '</div>\n'
    return h

parts.append(section("16. Aurora Sizing Recommendation", sizing_recommendation(), "sizing"))

# --- 17. Errors ---
if errors.strip():
    # Filter out password warnings
    real_errors = [l for l in errors.split("\n")
                   if l.strip() and "Using a password on the command line" not in l]
    if real_errors:
        parts.append(section("17. Collection Errors", pre_block("\n".join(real_errors)), "errors"))

# ─── TOC ──────────────────────────────────────────────────────────────────────
toc_items = re.findall(r'<h2>(.+?)</h2>', "\n".join(parts))
toc = '<nav class="toc"><h2>Contents</h2><ul>\n'
for item in toc_items:
    anchor = re.sub(r'[^a-zA-Z0-9]', '_', item)
    toc += f'  <li><a href="#{anchor}">{item}</a></li>\n'
toc += '</ul></nav>\n'

# Re-add anchors to section headers
for item in toc_items:
    anchor = re.sub(r'[^a-zA-Z0-9]', '_', item)
    old = f'<h2>{item}</h2>'
    new = f'<h2 id="{anchor}">{item}</h2>'
    parts = [p.replace(old, new, 1) for p in parts]

# ─── Assemble HTML ────────────────────────────────────────────────────────────
report_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MySQL Sizing Report — {esc(ENDPOINT)} — {esc(TS)}</title>
<style>
:root {{ --bg: #f8f9fa; --card: #fff; --border: #dee2e6; --accent: #0d6efd; --text: #212529; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
        background: var(--bg); color: var(--text); line-height: 1.5; padding: 20px; }}
h1 {{ text-align: center; margin: 20px 0; font-size: 1.4em; }}
h2 {{ color: var(--accent); border-bottom: 2px solid var(--accent); padding-bottom: 4px;
      margin: 0 0 12px 0; font-size: 1.15em; }}
h3 {{ margin: 16px 0 8px 0; font-size: 1em; color: #495057; }}
.toc {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px;
        padding: 16px 24px; margin: 0 auto 24px auto; max-width: 700px; }}
.toc h2 {{ border: none; margin-bottom: 8px; }}
.toc ul {{ columns: 2; column-gap: 24px; list-style: none; padding: 0; }}
.toc li {{ padding: 2px 0; }}
.toc a {{ color: var(--accent); text-decoration: none; font-size: 0.9em; }}
.toc a:hover {{ text-decoration: underline; }}
.section {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px;
            padding: 16px 20px; margin-bottom: 16px; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.85em; margin: 8px 0; }}
th, td {{ border: 1px solid var(--border); padding: 5px 8px; text-align: left;
          white-space: nowrap; }}
th {{ background: #e9ecef; position: sticky; top: 0; }}
td.r, th.r {{ text-align: right; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
tr:hover {{ background: #e2e6ea; }}
pre {{ background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px;
       overflow-x: auto; font-size: 0.82em; line-height: 1.4; white-space: pre-wrap;
       word-break: break-all; }}
.bar {{ height: 14px; border-radius: 2px; display: inline-block; vertical-align: middle; }}
.empty {{ color: #6c757d; font-style: italic; }}
.sizing strong {{ color: var(--accent); }}
.notes {{ list-style: none; padding: 0; }}
.notes li {{ padding: 6px 0; border-bottom: 1px solid var(--border); }}
.notes li:last-child {{ border-bottom: none; }}
.header-info {{ text-align: center; color: #6c757d; margin-bottom: 20px; font-size: 0.9em; }}
@media print {{
  body {{ padding: 0; }}
  .section {{ break-inside: avoid; }}
  pre {{ white-space: pre-wrap; }}
}}
</style>
</head>
<body>
<h1>MySQL Instance Sizing Report</h1>
<p class="header-info">Endpoint: {esc(ENDPOINT)}<br>
Collected: {esc(TS)} &nbsp;|&nbsp; Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
{toc}
{"".join(parts)}
</body>
</html>
"""

# ─── Write Output ─────────────────────────────────────────────────────────────
out_path = LOG_DIR / f"report_{TS}.html"
out_path.write_text(report_html)
print(f"Report generated: {out_path}")
print(f"Size: {out_path.stat().st_size:,} bytes")
