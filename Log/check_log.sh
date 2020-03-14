cat access_log | awk '{print $7}'  | sort | uniq -c | sort -nr
