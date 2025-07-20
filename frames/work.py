from flask import Flask, Response, render_template_string, url_for
import os
import cv2
import time
import logging

app = Flask(__name__)

# ─── Point at the photos/ folder inside frames/ ───────────────────────────────
FRAME_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'photos'))
if not os.path.isdir(FRAME_DIR):
    raise RuntimeError(f'Frame directory not found: {FRAME_DIR}')

# ─── Generator for MJPEG streaming ────────────────────────────────────────────
def gen_frames():
    seen = set()
    while True:
        try:
            # find JPEGs, BMPs sorted by modification time
            files = sorted(
                (f for f in os.listdir(FRAME_DIR)
                 if f.lower().endswith(('.jpg', '.jpeg', '.bmp'))),
                key=lambda f: os.path.getmtime(os.path.join(FRAME_DIR, f))
            )
            for fname in files:
                if fname in seen:
                    continue
                seen.add(fname)

                path = os.path.join(FRAME_DIR, fname)
                img = cv2.imread(path)
                if img is None:
                    logging.warning(f'Couldn’t read image: {path}')
                    continue

                ok, buf = cv2.imencode('.jpg', img)
                if not ok:
                    logging.warning(f'cv2.imencode failed for: {path}')
                    continue

                frame = buf.tobytes()
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' +
                    frame +
                    b'\r\n'
                )

            # throttle to ~30 FPS
            time.sleep(1/30)

        except Exception:
            logging.exception('Error in gen_frames()')
            time.sleep(1)

# ─── Simple inline HTML for the homepage ─────────────────────────────────────
HTML = """
<!doctype html>
<html>
  <head><title>Live Stream</title></head>
  <body>
    <h1>Live Stream</h1>
    <img src="{{ url_for('video_feed') }}" width="640" height="480">
  </body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/video_feed')
def video_feed():
    return Response(
        gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

if __name__ == '__main__':
    print(">> Running:", __file__)
    print(">> URL map:\n", app.url_map)
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)

