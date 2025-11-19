# Deployment Guide for #4CK P07470 CTF Lab

This guide covers local deployment and free hosting platforms for your Flask CTF lab.

## Local Deployment (Recommended for Development)

**Best for:** Testing, development, and small class deployments on local network.

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)

### Steps:

1. **Navigate to server directory:**
   ```bash
   cd server
   ```

2. **Create virtual environment:**
   ```bash
   # Windows
   python -m venv .venv
   
   # Linux/Mac
   python3 -m venv .venv
   ```

3. **Activate virtual environment:**
   ```bash
   # Windows (PowerShell)
   .\.venv\Scripts\activate
   
   # Windows (CMD)
   .venv\Scripts\activate.bat
   
   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize database:**
   ```bash
   # First time setup (creates DB and seeds data)
   python init_db.py --csv data/students_sample.csv
   
   # Reset existing database (WARNING: deletes all progress)
   python init_db.py --csv data/students_sample.csv --reset
   ```

6. **Run the application:**
   ```bash
   flask --app app run --debug
   ```
   
   Or with custom host/port:
   ```bash
   flask --app app run --host=0.0.0.0 --port=5000
   ```

7. **Access the application:**
   - Open browser: `http://localhost:5000`
   - For network access: `http://YOUR_IP:5000` (replace YOUR_IP with your machine's IP)

### Default Credentials

- **Student Login:** Use roll numbers from `data/students_sample.csv` (user: `SEC23001`, default password: `compass123`)

### Troubleshooting Local Deployment

**Port already in use:**
```bash
# Use a different port
flask --app app run --port=5001
```

**Database errors:**
```bash
# Reset the database
python init_db.py --csv data/students_sample.csv --reset
```

**Module not found errors:**
```bash
# Make sure virtual environment is activated
# Reinstall dependencies
pip install -r requirements.txt
```



