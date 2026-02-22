#!/bin/bash
# LinBurn Flatpak launcher
# check_root() in main.py handles elevation via /app/bin/sudo (linburn-sudo bridge)
exec /usr/bin/python3 /app/lib/linburn/main.py "$@"
