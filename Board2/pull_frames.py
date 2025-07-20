#!/usr/bin/env python3
import os, subprocess, time
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────
QNX_USER   = 'root'                # your QNX SSH user
QNX_HOST   = '192.168.1.123'       # QNX IP or hostname
REMOTE_TMP = '/tmp/frame.png'      # where to write on QNX
LOCAL_DIR  = os.path.expanduser('~/frames')
INTERVAL   = 0.2                   # seconds between shots
# ────────────────────────────────────────────────────────

os.makedirs(LOCAL_DIR, exist_ok=True)

try:
    while True:
        # timestamp for ordering
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        local_fn = f'frame_{ts}.png'
        local_p  = os.path.join(LOCAL_DIR, local_fn)
        remote   = f'{QNX_USER}@{QNX_HOST}:{REMOTE_TMP}'

        # 1) take screenshot on QNX
        subprocess.run(
            ['ssh', f'{QNX_USER}@{QNX_HOST}', 'screenshot', REMOTE_TMP],
            check=True
        )

        # 2) pull it down
        subprocess.run(['scp', remote, local_p], check=True)

        # 3) (optional) remove temp on QNX
        subprocess.run(
            ['ssh', f'{QNX_USER}@{QNX_HOST}', 'rm', REMOTE_TMP],
            check=True
        )

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\n🛑  Capture stopped by user")
