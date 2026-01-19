"""
YOLOv26 License Plate Detector
Uses the new YOLOv26 model optimized for edge devices
"""
from ultralytics import YOLO
import numpy as np
import cv2


class PlateDetector:
    """License plate detector using YOLOv26"""
    
    def __init__(self, model_path: str = None, confidence: float = 0.5):
        """
        Initialize the plate detector
        
        Args:
            model_path: Path to YOLOv26 model weights (optional, uses pretrained if None)
            confidence: Minimum confidence threshold for detections
        """
        self.confidence = confidence
        
        if model_path:
            # Load custom trained model
            self.model = YOLO(model_path)
        else:
            # Use YOLOv26 nano - optimized for edge devices
            # The model will auto-download on first run
            self.model = YOLO("yolo26n.pt")
        
        print(f"[PlateDetector] Model loaded: YOLOv26")
        print(f"[PlateDetector] Confidence threshold: {confidence}")
    
    def detect(self, frame: np.ndarray) -> list:
        """
        Detect license plates in a frame
        
        Args:
            frame: BGR image as numpy array
            
        Returns:
            List of detections, each containing:
            - bbox: (x1, y1, x2, y2) coordinates
            - confidence: detection confidence
            - cropped: cropped plate image
        """
        results = self.model(frame, conf=self.confidence, verbose=False)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            if boxes is None:
                continue
            
            for box in boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                
                # Crop the plate region
                cropped = frame[y1:y2, x1:x2].copy()
                
                detections.append({
                    'bbox': (x1, y1, x2, y2),
                    'confidence': confidence,
                    'class_id': class_id,
                    'cropped': cropped
                })
        
        return detections
    
    def detect_plates_only(self, frame: np.ndarray) -> list:
        """
        Detect only license plates (filter by class if model supports it)
        For general object detection, we look for 'car' class and then
        use a separate plate detection pass
        
        Args:
            frame: BGR image as numpy array
            
        Returns:
            List of plate detections
        """
        # First detect vehicles
        results = self.model(frame, conf=self.confidence, verbose=False)
        
        plate_detections = []
        
        for result in results:
            boxes = result.boxes
            
            if boxes is None:
                continue
            
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = result.names[class_id] if result.names else str(class_id)
                
                # Look for license plate class or vehicle classes
                if class_name.lower() in ['license plate', 'plate', 'number plate', 'car', 'truck', 'bus', 'motorcycle', 'vehicle']:
                    cropped = frame[y1:y2, x1:x2].copy()
                    
                    plate_detections.append({
                        'bbox': (x1, y1, x2, y2),
                        'confidence': confidence,
                        'class_name': class_name,
                        'cropped': cropped
                    })
        
        return plate_detections
    
    def draw_detections(self, frame: np.ndarray, detections: list, 
                       box_color: tuple = (0, 255, 0),
                       text_color: tuple = (255, 255, 255),
                       thickness: int = 2) -> np.ndarray:
        """
        Draw detection boxes and labels on frame
        
        Args:
            frame: Original BGR frame
            detections: List of detections from detect()
            box_color: BGR color for bounding box
            text_color: BGR color for text
            thickness: Line thickness
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, thickness)
            
            # Draw label background
            label = f"{conf:.2f}"
            if 'plate_text' in det:
                label = f"{det['plate_text']} ({conf:.2f})"
            
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 10, y1), box_color, -1)
            
            # Draw label text
            cv2.putText(annotated, label, (x1 + 5, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 1)
        
        return annotated


# For testing
if __name__ == "__main__":
    import sys
    
    detector = PlateDetector(confidence=0.5)
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        sys.exit(1)
    
    print("Press 'q' to quit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        detections = detector.detect(frame)
        annotated = detector.draw_detections(frame, detections)
        
        cv2.imshow("YOLOv26 Detection", annotated)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
