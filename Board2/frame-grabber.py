#!/usr/bin/env python3
import subprocess, time, os
from datetime import datetime

# --- CONFIGURE THESE ---
WIN_USER       = 'daiya'
WIN_HOST       = '10.33.61.190'        # your Windows machine’s IP
WIN_TARGET_DIR = '/frames'             # the C:\frames share in your SSH server
INTERVAL       = 0.2                   # seconds between captures
TMP_DIR        = '/tmp/frames_qnx'     # temp store on QNX
# ------------------------

os.makedirs(TMP_DIR, exist_ok=True)

try:
    while True:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        fname = f"frame_{ts}.png"
        local = os.path.join(TMP_DIR, fname)
        remote = f"{WIN_USER}@{WIN_HOST}:{WIN_TARGET_DIR}/{fname}"

        # 1) Take the screenshot locally
        subprocess.run(['screenshot', local], check=True)

        # 2) Copy it over to Windows
        subprocess.run(['scp', local, remote], check=True)

        # 3) Remove the local temp
        os.remove(local)

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("⏹️  Capture stopped by user")
