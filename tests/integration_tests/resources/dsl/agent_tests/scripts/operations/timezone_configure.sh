#!/bin/sh -e
TIMEZONE="Asia/Jerusalem"

ctx logger info "Date before timezone configuration: $(date)"
ctx logger info "Setting timezone for $(hostname) to $TIMEZONE"
rm -f /etc/localtime
ln -s /usr/share/zoneinfo/$TIMEZONE /etc/localtime
ctx logger info "Date after timezone configuration: $(date)"
