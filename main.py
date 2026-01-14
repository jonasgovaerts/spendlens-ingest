#!/usr/bin/env python3
"""
Spendlens Ingest Application - Monitors MinIO bucket for CSV files and ingests into PostgreSQL
"""

import os
import pandas as pd
from time import sleep
from datetime import datetime
from dotenv import load_dotenv
import logging
import hashlib

# Load environment variables
load_dotenv()

# Configure logging
# Get log level from environment variable or default to INFO
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

# Setup logging to stdout only
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from src.minio_client import MinIOClient
from src.database import DatabaseClient

def calculate_file_checksum(content):
    """Calculate SHA256 checksum of file content"""
    try:
        # Calculate SHA256 hash
        checksum = hashlib.sha256(content).hexdigest()
        return checksum
    except Exception as e:
        logger.error(f"Failed to calculate checksum: {e}")
        return None

def validate_env_vars():
    """Check that all required environment variables are set"""
    required_vars = [
        'MINIO_ACCESS_KEY',
        'MINIO_SECRET_KEY',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    logger.info("All required environment variables are set")

def process_csv_data(csv_content):
    """Process CSV data and extract records"""
    try:
        # Read CSV content - handle semicolon-separated files with proper quoting
        # Using a more robust approach for handling complex CSVs with embedded semicolons in quoted fields
        df = pd.read_csv(
            pd.io.common.BytesIO(csv_content),
            encoding='utf-8',
            skipinitialspace=True,
            sep=';',
            quotechar='"',
            quoting=1,  # csv.QUOTE_MINIMAL
            skip_blank_lines=True,
            on_bad_lines='skip'
        )
        
        # Rename columns to match our database schema
        column_mapping = {
            'Uittreksel': 'record_id_bank',
            'Datum': 'transaction_date',
            'Valuta datum': 'currency_date',
            'Rekening': 'account',
            'Beschrijving': 'description',
            'Bedrag': 'amount',
            'Valuta': 'currency'
        }
        
        # Map columns to database schema
        df = df.rename(columns=column_mapping)
        
        # Convert amount to numeric (remove any currency symbols, plus signs and handle thousand separators)
        df['amount'] = df['amount'].astype(str)
        # Remove plus signs and currency symbols
        df['amount'] = df['amount'].str.replace('+', '').str.replace('€', '').str.replace(' ', '')
        # Handle European number format (1.234,56 -> 1234.56)
        df['amount'] = df['amount'].str.replace('.', '', regex=False).str.replace(',', '.').str.strip()
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Convert date formats if needed
        df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='%d/%m/%Y', errors='coerce')
        df['currency_date'] = pd.to_datetime(df['currency_date'], format='%d/%m/%Y', errors='coerce')
        
        # Prepare records for database insertion with explicit type conversion
        records = []
        for _, row in df.iterrows():
            # Debug logging to see raw data
            logger.debug(f"Raw row data: {row.to_dict()}")
            
            # Handle each field with explicit type conversion
            record = (
                str(row['record_id_bank']) if pd.notna(row['record_id_bank']) and row['record_id_bank'] != '' else None,
                row['transaction_date'].strftime('%Y-%m-%d') if pd.notna(row['transaction_date']) else None,
                row['currency_date'].strftime('%Y-%m-%d') if pd.notna(row['currency_date']) else None,
                str(row['account']) if pd.notna(row['account']) and row['account'] != '' else None,
                str(row['description']) if pd.notna(row['description']) and row['description'] != '' else None,
                float(row['amount']) if pd.notna(row['amount']) and row['amount'] != '' and row['amount'] is not None else 0.0,
                str(row['currency']) if pd.notna(row['currency']) and row['currency'] != '' else None
            )
            records.append(record)
        
        # Log the first few records for debugging
        if len(records) > 0:
            logger.debug(f"First 3 records from CSV:")
            for i, record in enumerate(records[:3]):
                logger.debug(f"  Record {i+1}: {record}")
            
            if len(records) > 3:
                logger.debug(f"  ... and {len(records) - 3} more records")
        else:
            logger.debug("No records found in CSV")
        
        logger.info(f"Successfully processed {len(records)} records from CSV")
        return records
        
    except Exception as e:
        logger.error(f"Failed to process CSV data: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return []

def main():
    """Main ingestion function"""
    try:
        # Validate environment variables
        validate_env_vars()
        
        # Initialize MinIO client
        minio_client = MinIOClient()
        minio_client.connect()
        
        # Get bucket name from environment or use default
        bucket_name = os.getenv('MINIO_BUCKET', 'spendlens')
        
        # Check if bucket exists
        if not minio_client.bucket_exists(bucket_name):
            return
        
        # Get all CSV files
        csv_files = minio_client.list_csv_files(bucket_name)
        
        if not csv_files:
            logger.info("No CSV files found in bucket")
            return
        
        # Initialize database client
        db_client = DatabaseClient()
        db_client.connect()
        db_client.create_tables()
        
        # Process each CSV file
        for file_key in csv_files:
            logger.info(f"Processing file: {file_key}")
            
            # Download CSV
            csv_content = minio_client.download_csv(bucket_name, file_key)
            if not csv_content:
                continue
            
            # Calculate file checksum
            checksum = calculate_file_checksum(csv_content)
            if not checksum:
                logger.warning(f"Failed to calculate checksum for file {file_key}")
                continue
            
            # Check if file has already been processed
            if db_client.check_file_processed(file_key, checksum):
                continue
            
            # Process data
            records = process_csv_data(csv_content)
            
            # Insert into database
            if records:
                db_client.insert_records(records)
                
                # Mark file as processed
                db_client.mark_file_as_processed(file_key, checksum)
        
        logger.info("CSV processing completed successfully")
        
    except Exception as e:
        logger.error(f"Error in CSV processing: {e}")
        raise
    finally:
        # Close database connection if it exists
        try:
            db_client.close()
        except:
            pass

if __name__ == "__main__":
    while True:
        try:
            main()
            print("\nWaiting 1 minute before next processing cycle...")
            sleep(60)
        except KeyboardInterrupt:
            print("\nProcessing stopped by user.")
            break
        except Exception as e:
            print(f"\nError in main loop: {e}")
            print("Continuing after 1 minute...")
            sleep(60)