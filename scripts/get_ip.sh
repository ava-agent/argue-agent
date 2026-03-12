#!/bin/bash

# 获取本机 IP地址 (macOS)
IP=$(ifconfig getifconfig en0 | grep "inet " | head -1)

# 如果第一个IP
PUBLICIP=""

for ip in "${IP[@]}"; do
    echo "Local IP: ${ip}"
done
