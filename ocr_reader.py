"""
OCR Reader for License Plates
Uses Tesseract for fast character recognition
"""
import cv2
import numpy as np
import pytesseract
import re
import os
import sys

# Windows: Set Tesseract path if not in PATH
if sys.platform == 'win32':
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe',
    ]
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break


class OCRReader:
    """OCR reader for extracting text from license plates"""
    
    def __init__(self, tesseract_config: str = None):
        """
        Initialize OCR reader
        
        Args:
            tesseract_config: Custom Tesseract configuration string
        """
        # Default config optimized for license plates
        self.config = tesseract_config or r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
        # Check Tesseract installation
        try:
            pytesseract.get_tesseract_version()
            print("[OCRReader] Tesseract initialized successfully")
        except Exception as e:
            print(f"[OCRReader] Warning: Tesseract not found - {e}")
            print("[OCRReader] Install with: sudo apt install tesseract-ocr")
    
    def preprocess(self, plate_image: np.ndarray) -> np.ndarray:
        """
        Preprocess plate image for better OCR accuracy
        
        Args:
            plate_image: Cropped license plate BGR image
            
        Returns:
            Preprocessed grayscale image
        """
        if plate_image is None or plate_image.size == 0:
            return None
        
        # Resize for better OCR (height ~100px)
        height, width = plate_image.shape[:2]
        if height < 50:
            scale = 100 / height
            plate_image = cv2.resize(plate_image, None, fx=scale, fy=scale, 
                                     interpolation=cv2.INTER_CUBIC)
        
        # Convert to grayscale
        gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Apply adaptive threshold
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return thresh
    
    def read_plate(self, plate_image: np.ndarray) -> tuple:
        """
        Read text from license plate image
        
        Args:
            plate_image: Cropped license plate BGR image
            
        Returns:
            Tuple of (plate_text, confidence)
        """
        if plate_image is None or plate_image.size == 0:
            return "", 0.0
        
        # Preprocess the image
        processed = self.preprocess(plate_image)
        
        if processed is None:
            return "", 0.0
        
        try:
            # Get OCR result with confidence data
            data = pytesseract.image_to_data(
                processed, 
                config=self.config,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and confidence
            texts = []
            confidences = []
            
            for i, text in enumerate(data['text']):
                conf = int(data['conf'][i])
                if conf > 0 and text.strip():
                    texts.append(text.strip())
                    confidences.append(conf)
            
            if texts:
                plate_text = ''.join(texts)
                avg_conf = sum(confidences) / len(confidences) / 100.0
                return plate_text, avg_conf
            
            return "", 0.0
            
        except Exception as e:
            print(f"[OCRReader] Error: {e}")
            return "", 0.0
    
    def clean_plate_text(self, text: str) -> str:
        """
        Clean and validate plate text
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned plate text
        """
        # Remove non-alphanumeric characters
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        # Common OCR corrections
        corrections = {
            '0': 'O',  # In letter positions
            'O': '0',  # In number positions
            '1': 'I',
            'I': '1',
            '5': 'S',
            'S': '5',
            '8': 'B',
            'B': '8',
        }
        
        # Apply basic cleanup - remove single characters
        if len(cleaned) < 3:
            return ""
        
        return cleaned
    
    def validate_plate(self, text: str, min_length: int = 2, max_length: int = 15) -> bool:
        """
        Validate if text looks like a valid recordable string
        """
        if not text:
            return False
        
        length = len(text)
        if length < min_length or length > max_length:
            return False
        
        # More lenient: allow anything that has at least one alphanumeric character
        # (Already cleaned to only A-Z0-9 by clean_plate_text)
        return any(c.isalnum() for c in text)


# For testing
if __name__ == "__main__":
    import sys
    
    reader = OCRReader()
    
    # Test with an image file
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        image = cv2.imread(image_path)
        
        if image is not None:
            text, conf = reader.read_plate(image)
            cleaned = reader.clean_plate_text(text)
            valid = reader.validate_plate(cleaned)
            
            print(f"Raw text: {text}")
            print(f"Cleaned: {cleaned}")
            print(f"Confidence: {conf:.2f}")
            print(f"Valid: {valid}")
        else:
            print(f"Could not read image: {image_path}")
    else:
        print("Usage: python ocr_reader.py <plate_image.jpg>")
