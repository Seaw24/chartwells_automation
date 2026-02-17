"""
Database Manager for Autofill Transaction Tracking
Handles all SQLite operations for logging and querying autofill transactions.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import traceback

class TendersDBManager:
    def __init__(self, db_path):
        self.db_path = db_path  
        self._initalize_database()
    
    def _initialize_database(self): 
        try: 
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency

                #Create table 
                conn.execute(''' ''')
        except: