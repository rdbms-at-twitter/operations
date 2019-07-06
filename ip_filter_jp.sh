#!/bin/sh

DIR=$(cd $(dirname $0); pwd)
cd $DIR

aggregate=`which aggregate 2> /dev/null | wc -l`
if [ $aggregate -ne 1 ]; then
        echo "aggregate: command not found" >&2
        exit 1
fi

# Get IP Address List from Each RIP.
rm -f ./delegated-*
wget ftp://ftp.arin.net/pub/stats/arin/delegated-arin-latest > /dev/null 2>&1
wget ftp://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest > /dev/null 2>&1
wget ftp://ftp.apnic.net/pub/stats/apnic/delegated-apnic-latest > /dev/null 2>&1
wget ftp://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest > /dev/null 2>&1
wget ftp://ftp.afrinic.net/pub/stats/afrinic/delegated-afrinic-latest > /dev/null 2>&1

if [ ! -f delegated-apnic-latest ]; then
        echo "delegated-apnic-latest was not found." >&2
        exit 1
fi

# Obtain JP related IP Address Range and Convert it to Subnet Mask.

cat delegated-* | perl ./convert_ip.pl | grep -E 'JP$' | awk {'print $1'} | sort -n | aggregate > jp_ip_address_and_subnetmast.txt


# CIDR 表記をサブネットマスク表記に変換
sed -i 's/\/8$/\/255.0.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/9$/\/255.128.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/10$/\/255.192.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/11$/\/255.224.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/12$/\/255.240.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/13$/\/255.248.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/14$/\/255.252.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/15$/\/255.254.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/16$/\/255.255.0.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/17$/\/255.255.128.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/18$/\/255.255.192.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/19$/\/255.255.224.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/20$/\/255.255.240.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/21$/\/255.255.248.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/22$/\/255.255.252.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/23$/\/255.255.254.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/24$/\/255.255.255.0 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/25$/\/255.255.255.128 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/26$/\/255.255.255.192 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/27$/\/255.255.255.224 /' ./jp_ip_address_and_subnetmast.txt
sed -i 's/\/28$/\/255.255.255.240 /' ./jp_ip_address_and_subnetmast.txt

# Creating JP address list for hosts.allow with sshd Process.
cat ./jp_ip_address_and_subnetmast.txt | awk '{print "sshd: "$1}' > hosts.allow.data.jp
