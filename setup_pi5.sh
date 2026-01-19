#!/bin/bash
# Setup script for ANPR System on Raspberry Pi 5
# Run with: bash setup_pi5.sh

echo "=========================================="
echo "  ANPR System Setup for Raspberry Pi 5"
echo "=========================================="

# Update system
echo "[1/5] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo "[2/5] Installing system dependencies..."
sudo apt install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgtk-3-0

# Create virtual environment
echo "[3/5] Creating Python virtual environment..."
python3 -m venv --system-site-packages anpr_env

# Activate and install packages
echo "[4/5] Installing Python packages..."
source anpr_env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create data directories
echo "[5/5] Creating data directories..."
mkdir -p data/plates
mkdir -p models

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "To run the ANPR system:"
echo "  1. source anpr_env/bin/activate"
echo "  2. python main.py"
echo ""
echo "Commands:"
echo "  - Press 'q' to quit"
echo "  - Press 's' to show statistics"
echo "  - Press 'c' to capture frame"
echo ""
