# ANPR Configuration
import os

# ============ PATHS ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov26n_plate.pt")
DATABASE_PATH = os.path.join(BASE_DIR, "data", "plates.db")
IMAGES_DIR = os.path.join(BASE_DIR, "data", "plates")

# ============ CAMERA ============
CAMERA_INDEX = 0  # USB webcam index
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# ============ DETECTION ============
CONFIDENCE_THRESHOLD = 0.5
IOU_THRESHOLD = 0.45  # For YOLOv26, NMS-free but still useful for filtering

# ============ OCR ============
# Tesseract config for license plates
TESSERACT_CONFIG = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

# ============ DISPLAY ============
WINDOW_NAME = "ANPR - License Plate Recognition"

# ============ GPIO (Pi 5) ============
# Ultrasonic 1 (Entrance)
TRIG_1_PIN = 14
ECHO_1_PIN = 13

# Ultrasonic 2 (Exit)
TRIG_2_PIN = 26
ECHO_2_PIN = 27

# Servos
SERVO_1_PIN = 22  # Entrance Gate
SERVO_2_PIN = 23  # Exit Gate

# Thresholds
GATE_OPEN_DISTANCE = 10  # cm
GATE_AUTO_CLOSE_DELAY = 5  # seconds

SHOW_FPS = True
BOX_COLOR = (0, 255, 0)  # Green
TEXT_COLOR = (255, 255, 255)  # White
BOX_THICKNESS = 2

# ============ LOGGING ============
SAVE_PLATE_IMAGES = True
MIN_SAVE_INTERVAL = 5  # Seconds between saving same plate

# ============ PARKING FEES ============
FEE_HOUR_1 = 3.0       # RM 3 for <= 1 hour
FEE_DAILY_MAX = 5.0    # RM 5 for > 1 hour (daily)
CURRENCY = "RM"
