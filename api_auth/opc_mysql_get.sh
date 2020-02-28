#!/bin/sh

MyCOOKIE=`curl -i -X POST -H "Content-Type: application/oracle-compute-v3+json" -d '{"user":"/Compute-mycloud/admin@test.domain","password":"password"}' https://api.compute.oraclecloud.com/authenticate/|grep 'Cookie'|cut -f2- -d\ `

# echo $MyCOOKIE

echo "GET INSTANCE INFORMATION"

read -p "Press [Enter] key to resume."

# Get List
# curl -X GET -H "Cookie: $MyCOOKIE" -H "Accept: application/oracle-compute-v3+json" https://api.compute.oraclecloud.com/instance/Compute-mycloud/admin@test.domain/paas/MySQLCS/MYTEST/1/mysql/vm-1/

# Get Detail information from Instance.
curl -X GET -H "Cookie: $MyCOOKIE" -H "Accept: application/oracle-compute-v3+json" https://api.compute.oraclecloud.com/instance/Compute-mycloud/admin@test.domain/paas/MySQLCS/MYTEST/mysql/vm-1/233656b4-4ec0-4a16-babd-4a31d9d7a373
