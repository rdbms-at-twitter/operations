for ip in `seq 1 254`; do ping -c 1 -w 0.5 192.168.56.$ip > /dev/null && arp -a 192.168.56.$ip | grep ether; done
