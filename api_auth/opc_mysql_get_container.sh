#!/bin/sh

MyCOOKIE=`curl -i -X POST -H "Content-Type: application/oracle-compute-v3+json" -d '{"user":"/Compute-mycloud/admin@test.domain","password":"password"}' https://api.compute.oraclecloud.com/authenticate/|grep 'Cookie'|cut -f2- -d\ `
# echo $MyCOOKIE

# echo "GET"

curl -X GET -H "Cookie: $MyCOOKIE" -H "Accept: application/oracle-compute-v3+directory+json" https://api.compute.oraclecloud.com/instance/Compute-mycloud/
