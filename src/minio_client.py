"""
MinIO Client for Spendlens Ingest Application
"""

import os
import boto3
import logging

logger = logging.getLogger(__name__)

class MinIOClient:
    """Handles MinIO connection and operations"""
    
    def __init__(self):
        """Initialize MinIO client with environment variables"""
        self.endpoint_url = os.getenv('MINIO_ENDPOINT', 'https://minio.homelab.jonasg.be')
        self.access_key = os.getenv('MINIO_ACCESS_KEY')
        self.secret_key = os.getenv('MINIO_SECRET_KEY')
        self.client = None
        
    def connect(self):
        """Establish connection to MinIO"""
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='us-east-1'
            )
            
            # Test connectivity by listing buckets
            self.client.list_buckets()
            logger.info("Successfully connected to MinIO")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MinIO: {e}")
            raise
    
    def list_csv_files(self, bucket_name):
        """Get all CSV files from the bucket"""
        try:
            response = self.client.list_objects_v2(Bucket=bucket_name)
            csv_files = []
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.csv'):
                        csv_files.append(obj['Key'])
            
            logger.info(f"Found {len(csv_files)} CSV files in bucket")
            return csv_files
        except Exception as e:
            logger.error(f"Failed to list CSV files: {e}")
            return []
    
    def download_csv(self, bucket_name, file_key):
        """Download CSV file from MinIO"""
        try:
            response = self.client.get_object(Bucket=bucket_name, Key=file_key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to download CSV file {file_key}: {e}")
            return None
    
    def bucket_exists(self, bucket_name):
        """Check if bucket exists"""
        try:
            self.client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' exists")
            return True
        except Exception as e:
            logger.error(f"Bucket '{bucket_name}' does not exist or is inaccessible: {e}")
            return False