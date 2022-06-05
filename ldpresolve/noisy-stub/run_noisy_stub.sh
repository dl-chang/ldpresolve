tail -F /tmp/decoy.list | PRIMARY_RESOLVER=8.8.8.8 SENSITIVE_PATH=/tmp/sensitive_list.txt /home/pi/proj/dnsdp-prototype/dnsdist/sync_decoy.py
