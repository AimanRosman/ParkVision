"""
ANPR - Automatic Number Plate Recognition System
Main application with OpenCV GUI for Raspberry Pi 5
Integrated with Ultrasonic sensors, Servos, and Clickable Buttons

Uses YOLOv26 for plate detection and Tesseract for OCR
"""
import cv2
import time
import os
import argparse
from datetime import datetime
import numpy as np

# GPIO Libraries for Pi 5
try:
    from gpiozero import DistanceSensor, Servo
    from gpiozero.pins.pigpio import PiGPIOFactory
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[Warning] GPIO libraries not found. Running in simulation mode.")

from config import *
from plate_detector import PlateDetector
from ocr_reader import OCRReader
from database import PlateDatabase


class ANPRSystem:
    """Main ANPR application class with Gate Control and Clickable Buttons"""
    
    def __init__(self):
        """Initialize ANPR system components"""
        print("=" * 50)
        print("  ParkVision - YOLOv26 on Raspberry Pi 5")
        print("  Control: Clickable GUI Buttons")
        print("=" * 50)
        
        # Initialize detector
        print("\n[Init] Loading YOLOv26 model...")
        self.detector = PlateDetector(
            model_path=MODEL_PATH if os.path.exists(MODEL_PATH) else None,
            confidence=CONFIDENCE_THRESHOLD
        )
        
        # Initialize OCR
        print("[Init] Initializing OCR reader...")
        self.ocr = OCRReader(TESSERACT_CONFIG)
        
        # Initialize database
        print("[Init] Connecting to database...")
        self.database = PlateDatabase(DATABASE_PATH, IMAGES_DIR)
        
        # Initialize GPIO
        self._init_gpio()
        
        # Tracking for gate and payment logic
        self.last_saved = {}  # plate -> timestamp
        self.gate_open_time_1 = 0
        self.gate_open_time_2 = 0
        self.gate_1_is_open = False
        self.gate_2_is_open = False
        
        # Exit fee display tracking
        self.last_exit_info = None 
        self.exit_info_display_time = 0
        
        # GUI State
        self.running = True
        self.mouse_pos = (0, 0)
        self.buttons = [
            {"id": "capture", "label": "CAPTURE", "rect": (0, 0, 0, 0)},
            {"id": "stats", "label": "STATS", "rect": (0, 0, 0, 0)},
            {"id": "quit", "label": "QUIT", "rect": (0, 0, 0, 0)}
        ]
        
        # FPS calculation
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = time.time()
        
        print("[Init] System ready!\n")
    
    def _init_gpio(self):
        """Initialize GPIO components for Gate Control"""
        if not GPIO_AVAILABLE:
            self.sensor1 = self.sensor2 = self.servo1 = self.servo2 = None
            return
            
        try:
            print("[Init] Setting up GPIO...")
            self.sensor1 = DistanceSensor(echo=ECHO_1_PIN, trigger=TRIG_1_PIN, max_distance=1)
            self.sensor2 = DistanceSensor(echo=ECHO_2_PIN, trigger=TRIG_2_PIN, max_distance=1)
            self.servo1 = Servo(SERVO_1_PIN)
            self.servo2 = Servo(SERVO_2_PIN)
            self.servo1.min()
            self.servo2.min()
            print("[Init] GPIO setup successful")
        except Exception as e:
            print(f"[Init] GPIO Setup Error: {e}")
            self.sensor1 = self.sensor2 = self.servo1 = self.servo2 = None

    def on_mouse(self, event, x, y, flags, param):
        """Handle mouse events for clickable buttons"""
        self.mouse_pos = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            for btn in self.buttons:
                bx, by, bw, bh = btn['rect']
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    self._handle_button_click(btn['id'])

    def _handle_button_click(self, btn_id: str):
        """Execute actions based on button clicks"""
        if btn_id == "capture":
            print("[GUI] Capture button clicked")
            # This will be handled in the next frame cycle by a flag if needed, 
            # or we can pass a 'trigger_capture' flag. 
            # For now, let's just trigger a capture directly if we had the frame.
            # We'll set a flag to capture the next available frame.
            self.trigger_capture = True
        elif btn_id == "stats":
            print("[GUI] Stats button clicked")
            self._print_stats()
        elif btn_id == "quit":
            print("[GUI] Quit button clicked")
            self.running = False

    def _draw_buttons(self, frame: np.ndarray):
        """Draw clickable buttons on the control bar"""
        h, w = frame.shape[:2]
        control_bar_y = h - CONTROL_BAR_HEIGHT
        
        # Draw control bar background
        cv2.rectangle(frame, (0, control_bar_y), (w, h), (30, 30, 30), -1)
        cv2.line(frame, (0, control_bar_y), (w, control_bar_y), (100, 100, 100), 2)
        
        # Calculate button positions
        total_buttons_width = (len(self.buttons) * BUTTON_WIDTH) + ((len(self.buttons) - 1) * BUTTON_MARGIN)
        start_x = (w - total_buttons_width) // 2
        
        for i, btn in enumerate(self.buttons):
            bx = start_x + i * (BUTTON_WIDTH + BUTTON_MARGIN)
            by = control_bar_y + (CONTROL_BAR_HEIGHT - BUTTON_HEIGHT) // 2
            btn['rect'] = (bx, by, BUTTON_WIDTH, BUTTON_HEIGHT)
            
            # Check for hover
            mx, my = self.mouse_pos
            is_hover = bx <= mx <= bx + BUTTON_WIDTH and by <= my <= by + BUTTON_HEIGHT
            color = BUTTON_HOVER_COLOR if is_hover else BUTTON_COLOR
            
            # Draw button
            cv2.rectangle(frame, (bx, by), (bx + BUTTON_WIDTH, by + BUTTON_HEIGHT), color, -1)
            cv2.rectangle(frame, (bx, by), (bx + BUTTON_WIDTH, by + BUTTON_HEIGHT), (150, 150, 150), 1)
            
            # Draw text
            text_size = cv2.getTextSize(btn['label'], cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            tx = bx + (BUTTON_WIDTH - text_size[0]) // 2
            ty = by + (BUTTON_HEIGHT + text_size[1]) // 2
            cv2.putText(frame, btn['label'], (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, BUTTON_TEXT_COLOR, 2)

    def process_frame(self, frame: np.ndarray, at_entrance: bool = False, at_exit: bool = False) -> tuple:
        """Process a single frame through the ANPR pipeline"""
        detections = self.detector.detect(frame)
        processed_plates = []
        for det in detections:
            plate_text, ocr_conf = self.ocr.read_plate(det['cropped'])
            plate_text = self.ocr.clean_plate_text(plate_text)
            if self.ocr.validate_plate(plate_text):
                det['plate_text'] = plate_text
                det['ocr_confidence'] = ocr_conf
                if at_entrance: self._handle_entrance(plate_text, det['confidence'], det['cropped'])
                if at_exit: self._handle_exit(plate_text)
                processed_plates.append(det)
        annotated = self.detector.draw_detections(frame, processed_plates, BOX_COLOR, TEXT_COLOR, BOX_THICKNESS)
        return annotated, processed_plates

    def _handle_entrance(self, plate_text: str, confidence: float, plate_image: np.ndarray):
        """Handle car entering"""
        if plate_text in self.last_saved and time.time() - self.last_saved[plate_text] < MIN_SAVE_INTERVAL:
            return
        image_path = self._save_plate_image(plate_text, plate_image)
        if self.database.record_entry(plate_text, confidence, image_path):
            print(f"[Entrance] Registered {plate_text}. Opening Gate 1.")
            self._open_gate(1)
            self.last_saved[plate_text] = time.time()
        else:
            self._open_gate(1)

    def _handle_exit(self, plate_text: str):
        """Handle car exiting"""
        if self.last_exit_info and self.last_exit_info['plate'] == plate_text:
            if time.time() - self.exit_info_display_time < MIN_SAVE_INTERVAL:
                return
        exit_info = self.database.record_exit(plate_text, FEE_HOUR_1, FEE_DAILY_MAX)
        if exit_info:
            print(f"[Exit] {plate_text} | Fee: {CURRENCY} {exit_info['fee']}")
            self.last_exit_info = exit_info
            self.exit_info_display_time = time.time()
            self._open_gate(2)
        else:
            print(f"[Exit Warning] No entry record for {plate_text}. Opening anyway.")
            self._open_gate(2)

    def _save_plate_image(self, plate_text: str, plate_image: np.ndarray) -> str:
        if not SAVE_PLATE_IMAGES or plate_image is None: return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{plate_text}_{timestamp}.jpg"
        image_path = os.path.join(IMAGES_DIR, filename)
        os.makedirs(IMAGES_DIR, exist_ok=True)
        cv2.imwrite(image_path, plate_image)
        return image_path

    def _open_gate(self, gate_id: int):
        if gate_id == 1:
            if not self.gate_1_is_open:
                if self.servo1: self.servo1.max()
                self.gate_1_is_open = True
            self.gate_open_time_1 = time.time()
        elif gate_id == 2:
            if not self.gate_2_is_open:
                if self.servo2: self.servo2.max()
                self.gate_2_is_open = True
            self.gate_open_time_2 = time.time()

    def _update_gates(self):
        now = time.time()
        if self.gate_1_is_open and (now - self.gate_open_time_1 > GATE_AUTO_CLOSE_DELAY):
            if self.servo1: self.servo1.min()
            self.gate_1_is_open = False
        if self.gate_2_is_open and (now - self.gate_open_time_2 > GATE_AUTO_CLOSE_DELAY):
            if self.servo2: self.servo2.min()
            self.gate_2_is_open = False

    def _draw_fee_overlay(self, frame: np.ndarray):
        if not self.last_exit_info or (time.time() - self.exit_info_display_time > 5):
            return
        info = self.last_exit_info
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (w//2 - 200, 100), (w//2 + 200, 250), (0, 0, 0), -1)
        cv2.rectangle(frame, (w//2 - 200, 100), (w//2 + 200, 250), (255, 255, 0), 2)
        cv2.putText(frame, "EXIT PROCESSING", (w//2 - 120, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.putText(frame, f"PLATE: {info['plate']}", (w//2 - 180, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"TIME: {info['duration']} MIN", (w//2 - 180, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"FEE: {CURRENCY} {info['fee']:.2f}", (w//2 - 180, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    def _update_fps(self):
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()

    def _print_stats(self):
        stats = self.database.get_statistics()
        print("\n" + "=" * 40)
        print("  DATABASE STATISTICS")
        print("=" * 40)
        print(f"  Total detections: {stats['total_detections']}")
        print(f"  Unique plates:    {stats['unique_plates']}")
        print(f"  Today's count:    {stats['today_detections']}")
        print(f"  Avg confidence:   {stats['average_confidence']:.2%}")
        print("=" * 40 + "\n")

    def _capture_frame(self, frame: np.ndarray, plates: list = []):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(IMAGES_DIR, f"capture_{timestamp}.jpg")
        os.makedirs(IMAGES_DIR, exist_ok=True)
        cv2.imwrite(filepath, frame)
        print(f"[Capture] Saved: {filepath}")
        
        # Show plates on terminal
        if plates:
            print(f"[Capture] Detected {len(plates)} plate(s):")
            for i, p in enumerate(plates):
                print(f"  {i+1}. {p['plate_text']} (conf: {p['ocr_confidence']:.2%})")
        else:
            print("[Capture] No plates detected in this frame.")

    def run_camera(self, camera_index: int = CAMERA_INDEX):
        """Run ANPR with live camera feed and interactive buttons"""
        print(f"[Camera] Opening camera {camera_index}...")
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened(): return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        
        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, self.on_mouse)
        
        self.trigger_capture = False
        
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret: break
                
                # Check Sensors
                car_at_entrance = False
                car_at_exit = False
                if self.sensor1 and self.sensor1.distance * 100 < GATE_OPEN_DISTANCE: car_at_entrance = True
                if self.sensor2 and self.sensor2.distance * 100 < GATE_OPEN_DISTANCE: car_at_exit = True
                
                # Process frame
                annotated, plates = self.process_frame(frame, at_entrance=car_at_entrance, at_exit=car_at_exit)
                
                # Handle GUI capture trigger
                if self.trigger_capture:
                    self._capture_frame(frame, plates)
                    self.trigger_capture = False
                
                # Auto-close gates and update UI
                self._update_gates()
                self._draw_fee_overlay(annotated)
                self._update_fps()
                
                # Create a black bar at the bottom for controls if not part of frame
                # We'll just draw directly on the frame but make sure it's tall enough
                final_display = cv2.copyMakeBorder(annotated, 0, CONTROL_BAR_HEIGHT, 0, 0, cv2.BORDER_CONSTANT, value=(0,0,0))
                self._draw_buttons(final_display)
                
                if SHOW_FPS:
                    cv2.putText(final_display, f"FPS: {self.fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Sensor status
                s1_col = (0, 0, 255) if car_at_entrance else (0, 255, 0)
                cv2.putText(final_display, f"ENTRANCE: {'DETECTED' if car_at_entrance else 'READY'}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, s1_col, 2)
                s2_col = (0, 0, 255) if car_at_exit else (0, 255, 0)
                cv2.putText(final_display, f"EXIT: {'DETECTED' if car_at_exit else 'READY'}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, s2_col, 2)
                
                cv2.imshow(WINDOW_NAME, final_display)
                if cv2.waitKey(1) & 0xFF == ord('q'): break
                    
        except KeyboardInterrupt: pass
        finally:
            cap.release()
            cv2.destroyAllWindows()
            if self.sensor1: self.sensor1.close()
            if self.sensor2: self.sensor2.close()
            if self.servo1: self.servo1.close()
            if self.servo2: self.servo2.close()


def main():
    anpr = ANPRSystem()
    anpr.run_camera(CAMERA_INDEX)

if __name__ == "__main__":
    main()
