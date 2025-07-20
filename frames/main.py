#!/usr/bin/env python3
import json
import threading
import time
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from motor import RobotController
from ultrasonic import Ultrasonic

HOST = ''        # listen on all interfaces
PORT = 50000     # port for injury alerts

# Patrol parameters
CLEAR_DISTANCE_CM = 50
ROTATE_STEP_SEC   = 0.2
APPROACH_SEC      = 1.0

# This event tells the main loop “do rescue now”
injury_event = threading.Event()

def handle_injured():
    print("🚨 Survivor detected! Engaging rescue…")
    injury_event.set()

class InjuryHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        if self.path != '/injury':
            return self.send_error(404, "Not Found")

        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return self.send_error(400, "Invalid JSON")

        if data.get('injury') is True:
            handle_injured()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"no-injury"}')

    def log_message(self, *args):
        # suppress default logging
        pass

def start_http_server():
    httpd = HTTPServer((HOST, PORT), InjuryHandler)
    print(f"Listening for injury alerts on port {PORT}…")
    httpd.serve_forever()

def initial_grab(robot: RobotController):
    print("📦 Grabbing initial payload…")
    robot.arm.down();   time.sleep(0.5)
    robot.arm.grab();   time.sleep(0.5)
    robot.arm.up();     time.sleep(0.5)
    print("✅ Payload secured.")

def rescue_and_shutdown(robot: RobotController):
    """Approach, drop payload, then stop everything and exit."""
    print("🚗 Approaching survivor…")
    robot.drive.stop()
    robot.drive.forward()
    time.sleep(APPROACH_SEC)
    robot.drive.stop()

    print("📦 Dropping payload…")
    robot.arm.down();     time.sleep(0.5)
    robot.arm.release();  time.sleep(0.5)
    robot.arm.up();       time.sleep(0.5)
    robot.drive.stop()

    print("🎉 Payload delivered. Shutting down.")
    # Clean up and exit
    robot.cleanup()
    sys.exit(0)

def patrol_step(robot: RobotController, sonar: Ultrasonic):
    """One cycle of obstacle avoidance (one pivot if blocked)."""
    dist = sonar.get_distance()
    if dist is None:
        print("No echo – stopping")
        robot.drive.stop()
    elif dist >= CLEAR_DISTANCE_CM:
        print(f"{dist:.1f} cm clear – moving forward")
        robot.drive.forward()
    else:
        print(f"Obstacle at {dist:.1f} cm – pivoting")
        robot.drive.stop()
        robot.drive.right()
        time.sleep(ROTATE_STEP_SEC)

    time.sleep(0.05)

def main():
    # 1) Start HTTP listener in background (shares the same robot instance)
    threading.Thread(target=start_http_server, daemon=True).start()

    # 2) Init robot + sonar
    robot = RobotController()
    sonar = Ultrasonic(trigger_pin=27, echo_pin=22)

    # 3) Grab the payload at startup
    initial_grab(robot)

    # 4) Patrol loop
    try:
        while True:
            if injury_event.is_set():
                # do rescue and exit
                rescue_and_shutdown(robot)

            patrol_step(robot, sonar)

    except KeyboardInterrupt:
        print("\nInterrupted, shutting down")
    finally:
        robot.drive.stop()
        sonar.close()
        robot.cleanup()

if __name__ == "__main__":
    main()
