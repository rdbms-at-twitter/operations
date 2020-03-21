#!/bin/sh

for ADDRESS in `cat $1`

do

	echo ”---- $ADDRESS ----”

	whois  $ADDRESS | grep -ie inetnum -ie country -ie Net

done
