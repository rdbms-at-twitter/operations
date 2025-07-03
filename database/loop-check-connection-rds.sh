#!/bin/bash

# 引数チェック
if [ $# -ne 3 ]; then
    echo "Usage: $0 <hostname> <username> <password>"
    echo "Example: $0 mydb.cluster-xxx.region.rds.amazonaws.com admin mypassword"
    exit 1
fi

# 引数を変数に代入
RDSINSTANCE=$1
DB_USER=$2
DB_PASS=$3

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# 前回のホスト名を保存する変数
LAST_HOSTNAME=""

# 接続試行の最大回数
MAX_RETRIES=3
# リトライ間隔（秒）
RETRY_INTERVAL=2

while true
do
  DATETIME=$(date "+%Y-%m-%d %T.%N")

  # DNSキャッシュをクリア
  nslookup $RDSINSTANCE >/dev/null 2>&1

  # リトライロジック
  for ((i=1; i<=$MAX_RETRIES; i++))
  do
    result=$(timeout 5s echo "select '${DATETIME}', now(3), @@hostname, @@read_only;" | mysql -u"$DB_USER" -p"$DB_PASS" -h "$RDSINSTANCE" -s --connect-timeout=5 2>/dev/null)

    if [ $? -eq 0 ] && [ ! -z "$result" ]; then
      # 成功した場合の処理
      current_hostname=$(echo $result | awk '{print $5}')

      if [ "$current_hostname" != "$LAST_HOSTNAME" ]; then
        if [ "$LAST_HOSTNAME" = "" ] || [ "$color" = "$RED" ]; then
          color=$GREEN
        else
          color=$RED
        fi
      fi

      echo -e "${color}${result}${NC}"
      LAST_HOSTNAME=$current_hostname
      break
    else
      # エラーの場合
      if [ $i -eq $MAX_RETRIES ]; then
        echo -e "${YELLOW}${DATETIME} - Connection error or timeout after ${MAX_RETRIES} retries${NC}"
      else
        echo -e "${YELLOW}${DATETIME} - Connection error, retrying (${i}/${MAX_RETRIES})...${NC}"
        sleep $RETRY_INTERVAL
      fi
    fi
  done

  sleep 0.5
done
