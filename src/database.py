"""
Database Client for Spendlens Ingest Application
"""

import os
import psycopg2
from psycopg2.extras import execute_batch
import logging

logger = logging.getLogger(__name__)

class DatabaseClient:
    """Handles PostgreSQL database connection and operations"""
    
    def __init__(self):
        """Initialize database client with environment variables"""
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5432')
        self.database = os.getenv('DB_NAME')
        self.user = os.getenv('DB_USER')
        self.password = os.getenv('DB_PASSWORD')
        self.connection = None
    
    def connect(self):
        """Establish connection to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            
            # Test connectivity by executing a simple query
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            logger.info("Successfully connected to PostgreSQL database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL database: {e}")
            raise
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.connection.cursor()
            
            # Create unprocessed_records table if it doesn't exist
            create_table_query = """
                CREATE TABLE IF NOT EXISTS unprocessed_records (
                    id SERIAL PRIMARY KEY,
                    record_id_bank VARCHAR(255) UNIQUE,
                    transaction_date DATE,
                    currency_date DATE,
                    account VARCHAR(255),
                    description TEXT,
                    amount DECIMAL(15,2),
                    currency VARCHAR(10)
                )
            """
            
            cursor.execute(create_table_query)
            
            # Create processed_records table if it doesn't exist
            create_processed_table_query = """
                CREATE TABLE IF NOT EXISTS processed_records (
                    id SERIAL PRIMARY KEY,
                    record_id_bank VARCHAR(255) UNIQUE,
                    transaction_date DATE,
                    currency_date DATE,
                    account VARCHAR(255),
                    description TEXT,
                    amount DECIMAL(15,2),
                    currency VARCHAR(10),
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            cursor.execute(create_processed_table_query)
            
            # Create processed_files table if it doesn't exist
            create_processed_files_table_query = """
                CREATE TABLE IF NOT EXISTS processed_files (
                    id SERIAL PRIMARY KEY,
                    file_key VARCHAR(255) UNIQUE,
                    checksum VARCHAR(64),
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            cursor.execute(create_processed_files_table_query)
            
            self.connection.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def insert_records(self, records):
        """Insert records into unprocessed_records table"""
        if not records:
            logger.info("No records to insert")
            return
        
        try:
            cursor = self.connection.cursor()
            
            # Insert records only if they don't already exist in processed_records
            insert_query = """
                INSERT INTO unprocessed_records (
                    record_id_bank, transaction_date, currency_date, account, description, amount, currency
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id_bank) DO NOTHING
            """
            
            # Check if records already exist in processed_records and filter them out
            filtered_records = []
            for record in records:
                record_id = record[0]  # record_id_bank is at index 0
                check_query = "SELECT COUNT(*) FROM processed_records WHERE record_id_bank = %s"
                cursor.execute(check_query, (record_id,))
                count = cursor.fetchone()[0]
                
                if count == 0:
                    filtered_records.append(record)
                else:
                    logger.debug(f"Record with ID {record_id} already exists in processed_records, skipping")
            
            if filtered_records:
                execute_batch(cursor, insert_query, filtered_records, page_size=100)
                self.connection.commit()
                
                logger.info(f"Successfully inserted {len(filtered_records)} records into database")
            else:
                logger.info("All records already exist in processed_records, nothing to insert")
            
        except Exception as e:
            logger.error(f"Failed to insert records into database: {e}")
            logger.error(f"Records that failed: {records[:3] if records else 'No records'}")
            self.connection.rollback()
            raise
        finally:
            cursor.close()
    
    def check_file_processed(self, file_key, checksum):
        """Check if a file with the same checksum has already been processed"""
        try:
            cursor = self.connection.cursor()
            
            # Check if file with this checksum has already been processed
            check_query = """
                SELECT file_key FROM processed_files WHERE checksum = %s
            """
            
            cursor.execute(check_query, (checksum,))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"File {file_key} with checksum {checksum[:10]}... already processed")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to check if file was processed: {e}")
            return False
        finally:
            cursor.close()
    
    def mark_file_as_processed(self, file_key, checksum):
        """Mark a file as processed and store its checksum in database"""
        try:
            cursor = self.connection.cursor()
            
            # Insert file info into processed_files table
            insert_query = """
                INSERT INTO processed_files (file_key, checksum) VALUES (%s, %s)
                ON CONFLICT (file_key) DO UPDATE SET checksum = EXCLUDED.checksum
            """
            
            cursor.execute(insert_query, (file_key, checksum))
            self.connection.commit()
            
            logger.info(f"Marked file {file_key} as processed with checksum {checksum[:10]}...")
            
        except Exception as e:
            logger.error(f"Failed to mark file as processed: {e}")
            self.connection.rollback()
            raise
        finally:
            cursor.close()
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()