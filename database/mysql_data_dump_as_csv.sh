#!/bin/bash

#######################################
### テーブルデータCSVフルバックアップ
### Created: 2020-12
#######################################

date_dir=`date +"%Y%m"`
file_name=`date +"%Y-%m-%d_%H-%M-%S_afad"`
target_full_dump_dir="/backup/full/${date_dir}/"
pemfile="ca.pem"
database=testdb

if [ ! -d $target_full_dump_dir ]; then
      # フォルダーが存在しない場合は作成
      mkdir $target_full_dump_dir
      echo "フォルダーを作成しました"
else
      echo "フォルダーは既に存在しています"
fi

     table_list=(table1 table2 table3)
     i=0
			for backup_list in ${table_list[@]}
			do
			echo "${backup_list}をバックアップします"
                	/usr/local/mysql/bin/mysql --defaults-extra-file=/usr/local/mysql/secret.my.cnf -h 192.168.10.100 -u username --ssl-ca=${pemfile} ${database} -e "select * from ${backup_list}" | sed -e 's/^/"/g' | sed -e 's/$/"/g' | sed -e 's/\t/","/g'  | gzip > ${target_full_dump_dir}${backup_list}${file_name}.csv.gz

			i=`expr $i+1`
			done

echo 'テーブルのバックアップ完了しました。'
