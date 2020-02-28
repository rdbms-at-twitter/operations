#!/bin/sh

user="admin@test.domain"
pass="password"

XAuth=`curl -is -X GET -H "X-Storage-User:Storage-mytest:$user" -H "X-Storage-Pass:$pass" https://mytest.storage.oraclecloud.com/auth/v1.0 | egrep 'X-Auth-Token' | awk '{print $2}'`

echo $XAuth

echo "GET Storage Service Information"

read -p "Press [Enter] key to resume."

# Get List
# curl -X GET -H "X-Auth-Token: $XAuth" https://mytest.storage.oraclecloud.com/v1/Storage-mytest/MYTEST001
curl -X GET -H "X-Auth-Token: $XAuth" https://mytest.storage.oraclecloud.com/v1/Storage-mytest/
