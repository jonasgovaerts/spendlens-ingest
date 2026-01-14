# Spendlens Ingest Application

This application monitors a MinIO bucket for CSV files and ingests their data into a PostgreSQL database.

## Project Structure

```
.
├── main.py                 # Main application entry point
├── src/
│   ├── __init__.py         # Package initialization
│   ├── minio_client.py     # MinIO client implementation
│   └── database.py         # Database client implementation
├── requirements.txt        # Python dependencies
└── .env                    # Environment variables
```

## Features

- Monitors MinIO bucket for CSV files
- Processes CSV files using pandas
- Stores data in PostgreSQL database
- Tracks processed files to avoid duplicates
- Handles errors gracefully with logging

## Setup

1. Create a `.env` file with the following variables:
   ```
   MINIO_ENDPOINT=https://minio.homelab.jonasg.be
   MINIO_ACCESS_KEY=your_minio_access_key
   MINIO_SECRET_KEY=your_minio_secret_key
   MINIO_BUCKET=spendlens
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=spendlens_db
   DB_USER=spendlens_user
   DB_PASSWORD=spendlens_password
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

## Components

### MinIO Client (`src/minio_client.py`)
Handles connections to MinIO and file operations.

### Database Client (`src/database.py`)
Manages PostgreSQL database connections and data operations.