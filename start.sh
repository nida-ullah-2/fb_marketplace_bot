#!/bin/bash

# Path to your virtual environment activate script
VENV_PATH="C:/Users/Administrator/Documents/fb_marketplace_bot/env/Scripts/activate.bat"

# Command for Waitress
WAITRESS_CMD="cmd.exe /k \"call $VENV_PATH && waitress-serve --listen=0.0.0.0:9000 --threads=32 --backlog=4096 --channel-timeout=120 bot_core.wsgi:application\""

# Command for Cloudflare Tunnel
CLOUDFLARE_CMD="cmd.exe /k \"cloudflared tunnel run django-backend\""

# Open 2 separate terminals using Windows Terminal (wt)
wt.exe -w 0 nt -d . "$WAITRESS_CMD" ; \
wt.exe -w 0 nt -d . "$CLOUDFLARE_CMD"
