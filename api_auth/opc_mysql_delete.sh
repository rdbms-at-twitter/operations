#!/bin/sh

MyCOOKIE=`curl -i -X POST -H "Content-Type: application/oracle-compute-v3+json" -d '{"user":"/Compute-mycloud/admin@test.domain","password":"password"}' https://api.compute.oraclecloud.com/authenticate/|grep 'Cookie'|cut -f2- -d\ `

echo $MyCOOKIE

echo "DELETE INSTANCE"
read -p "Press [Enter] key to resume."

# curl -i -X DELETE -H "Cookie: $MyCOOKIE" https://api.compute.oraclecloud.com/instance/Compute-mycloud/admin@test.domain/paas/MySQLCS/MYTEST/mysql/vm-1/233656b4-4ec0-4a16-babd-4a31d9d7a373

curl -i -X DELETE -H "Cookie: $MyCOOKIE" https://api.compute.oraclecloud.com/instance/Compute-mycloud/admin@test.domain/paas/MySQLCS/MYTEST/mysql/vm-1/233656b4-4ec0-4a16-babd-4a31d9d7a373
