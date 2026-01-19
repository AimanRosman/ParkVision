"""
ANPR - Automatic Number Plate Recognition System
Main application with OpenCV GUI for Raspberry Pi 5
Integrated with Ultrasonic sensors, Servos, and Payment Logic

Uses YOLOv26 for plate detection and Tesseract for OCR
Fees: RM 3 (<= 1 hour), RM 5 (> 1 hour)
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
    """Main ANPR application class with Gate Control and Payment Logic"""
    
    def __init__(self):
        """Initialize ANPR system components"""
        print("=" * 50)
        print("  ANPR System - YOLOv26 on Raspberry Pi 5")
        print("  Parking Fee System: RM 3 / RM 5")
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
        self.last_exit_info = None # {plate, fee, time}
        self.exit_info_display_time = 0
        
        # FPS calculation
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = time.time()
        
        print("[Init] System ready!\n")
    
    def _init_gpio(self):
        """Initialize GPIO components for Gate Control"""
        if not GPIO_AVAILABLE:
            self.sensor1 = self.sensor2 = None
            self.servo1 = self.servo2 = None
            return
            
        try:
            print("[Init] Setting up GPIO (Ultrasonic & Servos)...")
            # Setup Sensors
            self.sensor1 = DistanceSensor(echo=ECHO_1_PIN, trigger=TRIG_1_PIN, max_distance=1)
            self.sensor2 = DistanceSensor(echo=ECHO_2_PIN, trigger=TRIG_2_PIN, max_distance=1)
            
            # Setup Servos
            self.servo1 = Servo(SERVO_1_PIN)
            self.servo2 = Servo(SERVO_2_PIN)
            
            # Initial position (closed)
            self.servo1.min()
            self.servo2.min()
            
            print("[Init] GPIO setup successful")
        except Exception as e:
            print(f"[Init] GPIO Setup Error: {e}")
            self.sensor1 = self.sensor2 = self.servo1 = self.servo2 = None

    def process_frame(self, frame: np.ndarray, at_entrance: bool = False, at_exit: bool = False) -> tuple:
        """
        Process a single frame through the ANPR pipeline
        """
        # Detect plates
        detections = self.detector.detect(frame)
        processed_plates = []
        
        for det in detections:
            # Run OCR on cropped plate
            plate_text, ocr_conf = self.ocr.read_plate(det['cropped'])
            plate_text = self.ocr.clean_plate_text(plate_text)
            
            if self.ocr.validate_plate(plate_text):
                det['plate_text'] = plate_text
                det['ocr_confidence'] = ocr_conf
                
                # ENTRANCE LOGIC
                if at_entrance:
                    self._handle_entrance(plate_text, det['confidence'], det['cropped'])
                
                # EXIT LOGIC
                if at_exit:
                    self._handle_exit(plate_text)
                
                processed_plates.append(det)
        
        # Draw detections on frame
        annotated = self.detector.draw_detections(
            frame, processed_plates, BOX_COLOR, TEXT_COLOR, BOX_THICKNESS
        )
        
        return annotated, processed_plates
    
    def _handle_entrance(self, plate_text: str, confidence: float, plate_image: np.ndarray):
        """Handle car entering: Save record and open gate"""
        # Check if recently processed (debounce)
        if plate_text in self.last_saved:
            if time.time() - self.last_saved[plate_text] < MIN_SAVE_INTERVAL:
                return

        # Save image and record entry
        image_path = self._save_plate_image(plate_text, plate_image)
        record_id = self.database.record_entry(plate_text, confidence, image_path)
        
        if record_id:
            print(f"[Entrance] Registered {plate_text}. Opening Gate 1.")
            self._open_gate(1)
            self.last_saved[plate_text] = time.time()
        else:
            # Maybe already inside, but usually we open gate anyway to let them in
            # (perhaps they were missed on previous entry attempt)
            self._open_gate(1)

    def _handle_exit(self, plate_text: str):
        """Handle car exiting: Calculate fee and open gate"""
        # Check if recently processed (debounce)
        if self.last_exit_info and self.last_exit_info['plate'] == plate_text:
            if time.time() - self.exit_info_display_time < MIN_SAVE_INTERVAL:
                return

        # Record exit and get fee info
        exit_info = self.database.record_exit(plate_text, FEE_HOUR_1, FEE_DAILY_MAX)
        
        if exit_info:
            print(f"[Exit] {plate_text} | Duration: {exit_info['duration']} min | Fee: {CURRENCY} {exit_info['fee']}")
            self.last_exit_info = exit_info
            self.exit_info_display_time = time.time()
            self._open_gate(2)
        else:
            # No entry record found for this plate
            # Still open gate for convenience in manual parking? Or keep closed?
            # Let's open it to avoid blocking exit, but log warning
            print(f"[Exit Warning] No entry record for {plate_text}. Opening anyway.")
            self._open_gate(2)

    def _save_plate_image(self, plate_text: str, plate_image: np.ndarray) -> str:
        """Helper to save plate image to disk"""
        if not SAVE_PLATE_IMAGES or plate_image is None: return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{plate_text}_{timestamp}.jpg"
        image_path = os.path.join(IMAGES_DIR, filename)
        
        os.makedirs(IMAGES_DIR, exist_ok=True)
        cv2.imwrite(image_path, plate_image)
        return image_path

    def _open_gate(self, gate_id: int):
        """Open a gate servo"""
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
        """Handle auto-closing of gates"""
        now = time.time()
        if self.gate_1_is_open and (now - self.gate_open_time_1 > GATE_AUTO_CLOSE_DELAY):
            if self.servo1: self.servo1.min()
            self.gate_1_is_open = False
        if self.gate_2_is_open and (now - self.gate_open_time_2 > GATE_AUTO_CLOSE_DELAY):
            if self.servo2: self.servo2.min()
            self.gate_2_is_open = False

    def _draw_fee_overlay(self, frame: np.ndarray):
        """Draw fee information on screen when a car exits"""
        if not self.last_exit_info or (time.time() - self.exit_info_display_time > 5):
            return
            
        info = self.last_exit_info
        # Background box for text
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (w//2 - 200, 100), (w//2 + 200, 250), (0, 0, 0), -1)
        cv2.rectangle(frame, (w//2 - 200, 100), (w//2 + 200, 250), (255, 255, 0), 2)
        
        # Text details
        text1 = f"PLATE: {info['plate']}"
        text2 = f"TIME: {info['duration']} MIN"
        text3 = f"FEE: {CURRENCY} {info['fee']:.2f}"
        
        cv2.putText(frame, "EXIT PROCESSING", (w//2 - 120, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.putText(frame, text1, (w//2 - 180, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, text2, (w//2 - 180, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, text3, (w//2 - 180, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    def _update_fps(self):
        """Calculate and update FPS"""
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()
    
    def run_camera(self, camera_index: int = CAMERA_INDEX):
        """Run ANPR with live camera feed and gate/fee monitoring"""
        print(f"[Camera] Opening camera {camera_index}...")
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened(): return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret: break
                
                # Check Sensors
                car_at_entrance = False
                car_at_exit = False
                
                if self.sensor1:
                    if self.sensor1.distance * 100 < GATE_OPEN_DISTANCE:
                        car_at_entrance = True
                
                if self.sensor2:
                    if self.sensor2.distance * 100 < GATE_OPEN_DISTANCE:
                        car_at_exit = True
                
                # Process frame
                annotated, plates = self.process_frame(frame, at_entrance=car_at_entrance, at_exit=car_at_exit)
                
                # Auto-close gates and update UI
                self._update_gates()
                self._draw_fee_overlay(annotated)
                self._update_fps()
                
                if SHOW_FPS:
                    cv2.putText(annotated, f"FPS: {self.fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Sensor status
                s1_col = (0, 0, 255) if car_at_entrance else (0, 255, 0)
                cv2.putText(annotated, f"ENTRANCE: {'DETECTED' if car_at_entrance else 'READY'}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, s1_col, 2)
                s2_col = (0, 0, 255) if car_at_exit else (0, 255, 0)
                cv2.putText(annotated, f"EXIT: {'DETECTED' if car_at_exit else 'READY'}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, s2_col, 2)
                
                cv2.imshow(WINDOW_NAME, annotated)
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
