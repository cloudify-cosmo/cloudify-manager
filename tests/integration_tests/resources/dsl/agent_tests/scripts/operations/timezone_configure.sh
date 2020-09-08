#!/bin/sh -e
TIMEZONE="Asia/Jerusalem"

ctx logger info "Date before timezone configuration: $(date)"
ctx logger info "Setting timezone for $(hostname) to $TIMEZONE"
export TZ=$TIMEZONE
ctx logger info "Date after timezone configuration: $(date)"
