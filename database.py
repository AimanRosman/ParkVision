"""
SQLite Database for storing detected license plates
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Tuple, Optional


class PlateDatabase:
    """SQLite database for license plate records"""
    
    def __init__(self, db_path: str, images_dir: str = None):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
            images_dir: Directory to store plate images
        """
        self.db_path = db_path
        self.images_dir = images_dir
        
        # Create directories if needed
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if images_dir:
            os.makedirs(images_dir, exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        print(f"[Database] Initialized: {db_path}")
    
    def _init_db(self):
        """Create database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # New table structure for parking records
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parking_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL,
                confidence REAL,
                entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                exit_time DATETIME,
                duration_minutes INTEGER,
                fee REAL,
                status TEXT DEFAULT 'IN', -- 'IN' or 'OUT'
                image_path TEXT,
                notes TEXT
            )
        ''')
        
        # Index for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_plate ON parking_records(plate_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON parking_records(status)')
        
        conn.commit()
        conn.close()
    
    def record_entry(self, plate_number: str, confidence: float = None, 
                     image_path: str = None) -> Optional[int]:
        """
        Record a car entering the parking lot
        """
        # First check if the car is already marked as 'IN'
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM parking_records 
            WHERE plate_number = ? AND status = 'IN'
            LIMIT 1
        ''', (plate_number,))
        
        if cursor.fetchone():
            conn.close()
            return None # Already inside
            
        cursor.execute('''
            INSERT INTO parking_records (plate_number, confidence, image_path, status)
            VALUES (?, ?, ?, 'IN')
        ''', (plate_number, confidence, image_path))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def record_exit(self, plate_number: str, fee_hour_1: float = 3.0, 
                    fee_daily: float = 5.0) -> Optional[dict]:
        """
        Record a car exiting, calculate fee, and update record
        
        Returns:
            Dict containing exit details if successful, else None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find the active entry
        cursor.execute('''
            SELECT * FROM parking_records 
            WHERE plate_number = ? AND status = 'IN'
            ORDER BY entry_time DESC LIMIT 1
        ''', (plate_number,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
            
        record_id = row['id']
        entry_time = datetime.fromisoformat(row['entry_time'])
        exit_time = datetime.now()
        
        # Calculate duration
        duration = exit_time - entry_time
        duration_minutes = int(duration.total_seconds() / 60)
        
        # Calculate fee: RM 3 for <= 1 hour, RM 5 for > 1 hour
        fee = fee_hour_1 if duration_minutes <= 60 else fee_daily
        
        # Update record
        cursor.execute('''
            UPDATE parking_records 
            SET exit_time = ?, duration_minutes = ?, fee = ?, status = 'OUT'
            WHERE id = ?
        ''', (exit_time.isoformat(), duration_minutes, fee, record_id))
        
        conn.commit()
        conn.close()
        
        return {
            'id': record_id,
            'plate': plate_number,
            'entry': entry_time,
            'exit': exit_time,
            'duration': duration_minutes,
            'fee': fee
        }

    def get_recent(self, limit: int = 50) -> List[Tuple]:
        """
        Get recent parking records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT plate_number, entry_time, exit_time, fee, status
            FROM parking_records
            ORDER BY entry_time DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_statistics(self) -> dict:
        """
        Get database statistics
        
        Returns:
            Dictionary with stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total count
        cursor.execute('SELECT COUNT(*) FROM plates')
        total = cursor.fetchone()[0]
        
        # Unique plates
        cursor.execute('SELECT COUNT(DISTINCT plate_number) FROM plates')
        unique = cursor.fetchone()[0]
        
        # Today's count
        cursor.execute('''
            SELECT COUNT(*) FROM plates
            WHERE DATE(timestamp) = DATE('now')
        ''')
        today = cursor.fetchone()[0]
        
        # Average confidence
        cursor.execute('SELECT AVG(confidence) FROM plates WHERE confidence IS NOT NULL')
        avg_conf = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_detections': total,
            'unique_plates': unique,
            'today_detections': today,
            'average_confidence': round(avg_conf, 3)
        }
    
    def export_csv(self, output_path: str) -> int:
        """
        Export database to CSV
        
        Args:
            output_path: Path for CSV file
            
        Returns:
            Number of records exported
        """
        import csv
        
        records = self.get_recent(limit=10000)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Plate Number', 'Confidence', 'Timestamp', 'Image Path'])
            writer.writerows(records)
        
        return len(records)


# For testing
if __name__ == "__main__":
    db = PlateDatabase("data/test_plates.db", "data/test_images")
    
    # Add test records
    db.add_plate("ABC1234", 0.95)
    db.add_plate("XYZ5678", 0.88)
    db.add_plate("ABC1234", 0.92)
    
    # Get recent
    print("\nRecent plates:")
    for record in db.get_recent(5):
        print(f"  {record}")
    
    # Statistics
    print("\nStatistics:")
    stats = db.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
