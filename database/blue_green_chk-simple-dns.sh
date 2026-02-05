#!/bin/bash

RDSINSTANCE=<Database Endpoint>

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Connection parameters optimized for ~4-5 second switchover
CONNECT_TIMEOUT=2            # 接続タイムアウト（1秒）
COMMAND_TIMEOUT=2            # コマンド全体のタイムアウト（2秒→1秒に短縮）
RETRY_INTERVAL=0.5           # 再試行間隔（0.2秒→0.1秒に短縮）
MAX_CONSECUTIVE_FAILURES=15  # 連続失敗の閾値（10回→5回に削減）

# Variable to store the previous hostname
LAST_HOSTNAME=""
LAST_IP=""
CONSECUTIVE_FAILURES=0

# Display IP/TTL information at startup
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Connection target: ${RDSINSTANCE}${NC}"
echo -e "${CYAN}Connection timeout: ${CONNECT_TIMEOUT}s, Command timeout: ${COMMAND_TIMEOUT}s, Retry interval: ${RETRY_INTERVAL}s${NC}"
echo -e "${CYAN}Max consecutive failures threshold: ${MAX_CONSECUTIVE_FAILURES}${NC}"
echo -e "${CYAN}========================================${NC}"

# Retrieve IP address and TTL information
DNS_INFO=$(dig +noall +answer $RDSINSTANCE 2>/dev/null)
if [ ! -z "$DNS_INFO" ]; then
    echo -e "${CYAN}DNS information:${NC}"
    echo "$DNS_INFO" | while read line; do
        echo -e "${CYAN}  $line${NC}"
    done

    # Extract only IP address (only the last A record)
    CURRENT_IP=$(dig +short $RDSINSTANCE 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | tail -1)
    echo -e "${CYAN}Current IP address: ${CURRENT_IP}${NC}"
else
    echo -e "${YELLOW}Failed to retrieve DNS information${NC}"
    CURRENT_IP=$(dig +short $RDSINSTANCE 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | tail -1)
fi
echo -e "${CYAN}========================================${NC}"
echo ""

while true
do
    DATETIME=$(date "+%Y-%m-%d %T.%N")

    # DNS解決を毎回実行（TTL効果を回避）
    CURRENT_IP=$(dig +short $RDSINSTANCE 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | tail -1)

    if [ -z "$CURRENT_IP" ]; then
        echo -e "${YELLOW}${DATETIME} - DNS resolution failed${NC}"
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        sleep $RETRY_INTERVAL
        continue
    fi

    # IP変更検出時は即座に通知し、失敗カウンタをリセット
    if [ ! -z "$LAST_IP" ] && [ "$CURRENT_IP" != "$LAST_IP" ]; then
        echo ""
        echo -e "${CYAN}========================================${NC}"
        echo -e "${CYAN}IP change detected! ${LAST_IP} -> ${CURRENT_IP}${NC}"
        echo -e "${CYAN}========================================${NC}"
        NEW_DNS_INFO=$(dig +noall +answer $RDSINSTANCE 2>/dev/null)
        if [ ! -z "$NEW_DNS_INFO" ]; then
            echo -e "${CYAN}DNS information:${NC}"
            echo "$NEW_DNS_INFO" | while read line; do
                echo -e "${CYAN}  $line${NC}"
            done
        fi
        echo -e "${CYAN}========================================${NC}"
        echo ""

        # IP変更時は失敗カウンタをリセット
        CONSECUTIVE_FAILURES=0
    fi

    LAST_IP=$CURRENT_IP

    # 解決されたIPアドレスに直接接続（タイムアウトを短縮）
    result=$(timeout ${COMMAND_TIMEOUT}s echo "select '${DATETIME}', now(3), @@hostname, @@read_only, '${CURRENT_IP}';" | mysql -u <user> -p<password> -h $CURRENT_IP --connect-timeout=${CONNECT_TIMEOUT} -s                                     2>/dev/null)

    if [ $? -eq 0 ] && [ ! -z "$result" ]; then
        # 成功時の処理
        # ホスト名を抽出（5番目のフィールド）
        current_hostname=$(echo $result | awk '{print $5}')

        # 成功時は失敗カウンタをリセット
        if [ $CONSECUTIVE_FAILURES -gt 0 ]; then
            elapsed_time=$(echo "scale=1; $CONSECUTIVE_FAILURES * $RETRY_INTERVAL + $CONSECUTIVE_FAILURES * $COMMAND_TIMEOUT" | bc)
            echo -e "${GREEN}Connection recovered after ${CONSECUTIVE_FAILURES} failures (approximately ${elapsed_time} seconds)${NC}"
            CONSECUTIVE_FAILURES=0
        fi

        # 前回と異なるホスト名の場合は色を切り替え
        if [ "$current_hostname" != "$LAST_HOSTNAME" ]; then
            if [ "$LAST_HOSTNAME" = "" ] || [ "$color" = "$RED" ]; then
                color=$GREEN
            else
                color=$RED
            fi

            # ホスト名変更時に通知
            if [ "$LAST_HOSTNAME" != "" ]; then
                echo ""
                echo -e "${CYAN}========================================${NC}"
                echo -e "${CYAN}Failover detected! Hostname changed${NC}"
                echo -e "${CYAN}${LAST_HOSTNAME} -> ${current_hostname}${NC}"
                echo -e "${CYAN}========================================${NC}"
                echo ""
            fi
        fi

        # 結果を色付きで表示（IPアドレスを含む）
        echo -e "${color}${result}${NC}"

        LAST_HOSTNAME=$current_hostname
    else
        # エラー時の処理
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        echo -e "${YELLOW}${DATETIME} - Connection error or timeout (IP: ${CURRENT_IP}) [Failure #${CONSECUTIVE_FAILURES}]${NC}"

        # 連続失敗が閾値を超えた場合に警告
        if [ $CONSECUTIVE_FAILURES -eq $MAX_CONSECUTIVE_FAILURES ]; then
            elapsed_time=$(echo "scale=1; $CONSECUTIVE_FAILURES * $RETRY_INTERVAL + $CONSECUTIVE_FAILURES * $COMMAND_TIMEOUT" | bc)
            echo -e "${RED}WARNING: ${MAX_CONSECUTIVE_FAILURES} consecutive failures detected! (approximately ${elapsed_time} seconds)${NC}"
        fi

        # 長期間の失敗に対する重大警告
        if [ $CONSECUTIVE_FAILURES -eq 15 ]; then
            elapsed_time=$(echo "scale=1; $CONSECUTIVE_FAILURES * $RETRY_INTERVAL + $CONSECUTIVE_FAILURES * $COMMAND_TIMEOUT" | bc)
            echo -e "${RED}CRITICAL: 15 consecutive failures detected! (approximately ${elapsed_time} seconds) - Possible DNS TTL issue${NC}"
        fi

        # 3回失敗ごとに強制的にDNS再解決を促す（次のループで自動実行）
        if [ $((CONSECUTIVE_FAILURES % 3)) -eq 0 ]; then
            echo -e "${YELLOW}Forcing DNS re-resolution on next iteration...${NC}"
        fi
    fi

    sleep $RETRY_INTERVAL
done
