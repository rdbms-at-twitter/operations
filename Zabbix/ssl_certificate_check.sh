#! /bin/sh

SERVER=$1
PORT=$2
TIMEOUT=25
./timeout $TIMEOUT ./ssl-cert-check -s $SERVER -p $PORT -n | sed 's/  */ /g' | cut -f6 -d" "
