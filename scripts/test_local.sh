#!/bin/bash
for ip in 185.143.233.64 185.143.234.64; do
  curl -sS --max-time 15 \
    --resolve "www.raja.ir:443:$ip" \
    -D - -o /dev/null \
    -w "\ntarget=$ip status=%{http_code} remote_ip=%{remote_ip}\n\n" \
    https://www.raja.ir/
done
