from picamera2 import Picamera2
from ultralytics import YOLO
import cv2
import threading
import queue
import serial
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE   = 9600

try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"Connected to Arduino on {SERIAL_PORT}")
except Exception as e:
    print(f"WARNING: Could not open serial port {SERIAL_PORT}: {e}")
    arduino = None

model  = YOLO(str(BASE_DIR / "model" / "metal_sphere_detector.pt"))
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)}))
picam2.start()

WAITING   = "waiting"
DETECTING = "detecting"
RUNNING   = "running"

state       = WAITING
state_lock  = threading.Lock()
cycle_count = 0

frame_queue  = queue.Queue(maxsize=1)
boxes_lock   = threading.Lock()
latest_boxes = []
stop         = threading.Event()

FONT       = cv2.FONT_HERSHEY_SIMPLEX
BOX_COLOR  = (0, 0, 255)    # red (BGR)
TEXT_COLOR = (255, 0, 0)    # blue (BGR)


def inference_worker():
    global state, cycle_count
    while not stop.is_set():
        with state_lock:
            current_state = state

        if current_state != DETECTING:
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
            continue

        try:
            frame = frame_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        results = model(frame, conf=0.6, verbose=False)
        boxes = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            boxes.append((x1, y1, x2, y2, conf))

        with boxes_lock:
            latest_boxes[:] = boxes

        if boxes:
            if arduino:
                arduino.write(b'D')
            with state_lock:
                state = RUNNING
                cycle_count += 1


def serial_worker():
    global state
    while not stop.is_set():
        if not arduino:
            continue
        try:
            line = arduino.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not line:
            continue

        if line == "B":
            print("Beam tripped — starting detection")
            with state_lock:
                state = DETECTING
            with boxes_lock:
                latest_boxes.clear()

        elif line == "R":
            print("Servo sequence done — waiting for next marble")
            with state_lock:
                state = WAITING
            with boxes_lock:
                latest_boxes.clear()


inference_thread = threading.Thread(target=inference_worker, daemon=True)
serial_thread    = threading.Thread(target=serial_worker,    daemon=True)
inference_thread.start()
serial_thread.start()

VIDEO_PATH = str(BASE_DIR / "final_video.avi")
fourcc     = cv2.VideoWriter_fourcc(*"XVID")
video_out  = cv2.VideoWriter(VIDEO_PATH, fourcc, 30.0, (380, 380))

print("Running — press 'q' to quit.")

while True:
    frame = picam2.capture_array()

    if not frame_queue.full():
        frame_queue.put(frame.copy())

    with state_lock:
        current_state = state
        count = cycle_count
    with boxes_lock:
        boxes = list(latest_boxes)

    display = cv2.resize(frame, (380, 380))
    scale_x = 380 / 640
    scale_y = 380 / 480

    if current_state == WAITING:
        cv2.putText(display, "Waiting for beam trip",
                    (10, 30), FONT, 0.7, (0, 255, 255), 2)

    elif current_state == DETECTING:
        cv2.putText(display, "Detecting...",
                    (10, 30), FONT, 0.7, (0, 255, 0), 2)
        for x1, y1, x2, y2, conf in boxes:
            sx1 = int(x1 * scale_x); sy1 = int(y1 * scale_y)
            sx2 = int(x2 * scale_x); sy2 = int(y2 * scale_y)
            cv2.rectangle(display, (sx1, sy1), (sx2, sy2), BOX_COLOR, 2)
            label = f"marble {conf:.2f}"
            (tw, th), bl = cv2.getTextSize(label, FONT, 0.7, 2)
            cv2.rectangle(display, (sx1, sy1 - th - bl - 4), (sx1 + tw, sy1), BOX_COLOR, -1)
            cv2.putText(display, label, (sx1, sy1 - bl - 2), FONT, 0.7, TEXT_COLOR, 2)

    elif current_state == RUNNING:
        cv2.putText(display, "Marble detected - servos running",
                    (10, 30), FONT, 0.6, (0, 165, 255), 2)
        for x1, y1, x2, y2, conf in boxes:
            sx1 = int(x1 * scale_x); sy1 = int(y1 * scale_y)
            sx2 = int(x2 * scale_x); sy2 = int(y2 * scale_y)
            cv2.rectangle(display, (sx1, sy1), (sx2, sy2), BOX_COLOR, 2)
            label = f"marble {conf:.2f}"
            (tw, th), bl = cv2.getTextSize(label, FONT, 0.7, 2)
            cv2.rectangle(display, (sx1, sy1 - th - bl - 4), (sx1 + tw, sy1), BOX_COLOR, -1)
            cv2.putText(display, label, (sx1, sy1 - bl - 2), FONT, 0.7, TEXT_COLOR, 2)

    cv2.putText(display, f"Cycles: {count}",
                (10, 370), FONT, 0.7, (0, 255, 0), 2)
    video_out.write(display)
    cv2.imshow("Marble Detector", display)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

stop.set()
inference_thread.join()
video_out.release()
picam2.stop()
cv2.destroyAllWindows()
if arduino:
    arduino.close()
