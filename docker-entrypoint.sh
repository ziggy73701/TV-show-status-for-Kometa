#!/bin/bash

echo "$CRON cd /app && python TSSK.py >> /var/log/cron.log 2>&1" > /etc/cron.d/tssk-cron
chmod 0644 /etc/cron.d/tssk-cron
crontab /etc/cron.d/tssk-cron
echo "[INFO] Starting cron with schedule: $CRON"
cron -f
