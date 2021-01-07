#!/bin/bash

### passwordファイルを指定
export PGPASSFILE="./pgpass_file"

SOURCE_DB_NAME="データベース名"
SOURCE_USER_NAME="ユーザー名"
SOURCE_HOST_NAME="移行元データベースホスト"
SOURCE_PORT="5432"
SOURCE_OPTIONS="-U $SOURCE_USER_NAME -h $SOURCE_HOST_NAME -p $SOURCE_PORT  -d $SOURCE_DB_NAME"

TARGET_DB_NAME="データベース名"
TARGET_USER_NAME="ユーザー名"
TARGET_HOST_NAME="移行先データベースホスト"
TARGET_PORT="5432"
TARGET_OPTIONS="-U $TARGET_USER_NAME -h $TARGET_HOST_NAME -p $TARGET_PORT -d $TARGET_DB_NAME"


### 指定したデーベースのテーブル名を全て取得

CMD="echo 'select relname as TABLE_NAME from pg_stat_user_tables;' | psql $TARGET_OPTIONS -t"
TABLES=(`eval $CMD`)

### 各テーブルごとのcount(*)の結果を比較

export TOTAL_ERROR_CODE=0
for table in "${TABLES[@]}"
do
    SOURCE_SQL="select count(*) FROM $table;"
    SOURCE_CMD="echo '${SOURCE_SQL};' | psql ${SOURCE_OPTIONS} | head -3 | tail -n 1"
    SOURCE_TABLECOUNT=(`eval $SOURCE_CMD`)

    TARGET_SQL="select count(*) FROM $table"
    TARGET_CMD="echo '${TARGET_SQL};' | psql ${TARGET_OPTIONS} | head -3 | tail -n 1"
    TARGET_TABLECOUNT=(`eval $TARGET_CMD`)

    if [ $SOURCE_TABLECOUNT = $TARGET_TABLECOUNT ]; then
      echo "OK is $table"
    else
      echo "NOT EQUAL $table SOURCE_DB count $SOURCE_TABLECOUNT  :  TARGET_DB count $TARGET_TABLECOUNT"
      export TOTAL_ERROR_CODE=1
    fi
done
if [ "$TOTAL_ERROR_CODE" -gt "0" ];then
  echo '-----> データの件数の整合性に問題があります。確認してください。'
else
  echo '-----> データ件数の整合性が確認されました。他にも確認事項があればチェックして下さい。'
fi
