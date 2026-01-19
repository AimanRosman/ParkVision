# Smart Parking & ANPR System (YOLOv26)

> [!NOTE]  
> This project is a significant upgrade from the original design by **Nur Aiman** (see `Poster Nur Aiman.pdf`). The previous flow used a basic ESP32-only setup for gate control. This version upgrades the architecture to use **Raspberry Pi 5** and **YOLOv26** for high-speed, intelligent ANPR and automated fee management.

Automatic Number Plate Recognition system using **YOLOv26** - the latest YOLO release optimized for edge devices.

## Features

- 🚗 **Real-time plate detection** using YOLOv26 Nano
- 🔤 **OCR text extraction** using Tesseract
- 💾 **SQLite database** for storing detected plates
- 🖼️ **Auto-save plate images** with timestamps
- 📊 **Statistics dashboard** (press 's')
- ⚡ **Optimized for Raspberry Pi 5** - 43% faster CPU inference

## Quick Start

### On Raspberry Pi 5

```bash
# 1. Run setup script
bash setup_pi5.sh

# 2. Activate environment
source anpr_env/bin/activate

# 3. Run ANPR
python main.py
```

### On Windows (for testing)

```bash
# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki

# Run
python main.py
```

## Usage

### Live Camera Mode
```bash
python main.py                    # Default camera (index 0)
python main.py --camera 1         # Specific camera
```

### Single Image Mode
```bash
python main.py --image car.jpg
```

### Export Database
```bash
python main.py --export plates.csv
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `s` | Show statistics |
| `c` | Capture current frame |

## Project Structure

```
ANPR/
├── main.py            # Main application
├── plate_detector.py  # YOLOv26 detection
├── ocr_reader.py      # Tesseract OCR
├── database.py        # SQLite storage
├── config.py          # Configuration
├── requirements.txt   # Dependencies
├── setup_pi5.sh      # Pi 5 setup script
└── data/
    ├── plates.db     # Database
    └── plates/       # Saved images
```

## Configuration

Edit `config.py` to customize:

- Camera resolution
- Confidence threshold
- Display settings
- Save options

## Performance

| Device | Expected FPS |
|--------|-------------|
| Raspberry Pi 5 | 3-5 FPS |
| Raspberry Pi 5 + Coral USB | 14+ FPS |
| Desktop GPU | 30+ FPS |

## License

MIT License
