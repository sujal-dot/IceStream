# Running IceStream on a Windows Laptop — Step-by-Step Guide

This guide provides end-to-end instructions for setting up, running, and testing the **IceStream** lakehouse streaming and observability platform on a Windows 10 or Windows 11 laptop.

---

## Table of Contents
1. [Prerequisites & System Requirements](#1-prerequisites--system-requirements)
2. [Service Endpoints & Port Map](#2-service-endpoints--port-map)
3. [Method 1: WSL 2 (Recommended & Fastest)](#3-method-1-wsl-2-recommended--fastest)
4. [Method 2: Native Windows (PowerShell + Docker Desktop)](#4-method-2-native-windows-powershell--docker-desktop)
5. [Verifying the Running System](#5-verifying-the-running-system)
6. [Simulating Live Streaming Data & Faults](#6-simulating-live-streaming-data--faults)
7. [Stopping the Services](#7-stopping-the-services)
8. [Troubleshooting Common Windows Issues](#8-troubleshooting-common-windows-issues)

---

## 1. Prerequisites & System Requirements

### Hardware Requirements
- **OS**: Windows 10 (Build 19041+) or Windows 11 (64-bit).
- **RAM**: Minimum **8 GB** (16 GB strongly recommended, as Kafka, Flink, MinIO, Iceberg, Postgres, Prometheus, and Grafana run concurrently).
- **Disk Space**: At least **15 GB** free disk space for Docker images, Kafka logs, and local Lakehouse storage.
- **Virtualization**: Hardware virtualization (VT-x / AMD-V) enabled in your BIOS/UEFI.

### Required Software
1. **Docker Desktop for Windows**:
   - Download & install: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
   - During installation, ensure **"Use WSL 2 instead of Hyper-V"** is checked.
2. **Git for Windows**:
   - Download & install: [https://git-scm.com/download/win](https://git-scm.com/download/win)
3. **Python 3.10 or 3.11**:
   - Download: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - ⚠️ **IMPORTANT**: During installation, check the box **"Add python.exe to PATH"**.
4. **Node.js (LTS version 18.x or 20.x)**:
   - Download & install: [https://nodejs.org/](https://nodejs.org/)

---

## 2. Service Endpoints & Port Map

Once running, IceStream exposes the following services on `localhost`:

| Service | Endpoint URL | Default Credentials | Purpose |
| :--- | :--- | :--- | :--- |
| **React Observability UI** | [http://localhost:5173](http://localhost:5173) | *None* | Interactive lineage, DAG, real-time metrics |
| **FastAPI Backend** | [http://localhost:8000](http://localhost:8000) | Bearer Token | Telemetry API, Circuit Breaker, Incident Management |
| **API Swagger Documentation**| [http://localhost:8000/docs](http://localhost:8000/docs)| *None* | Interactive API docs |
| **Grafana Dashboards** | [http://localhost:3000](http://localhost:3000) | `admin` / `admin` | Telemetry & system metrics |
| **Apache Flink Dashboard** | [http://localhost:8081](http://localhost:8081) | *None* | Streaming jobs status and task slots |
| **MinIO S3 Console** | [http://localhost:9001](http://localhost:9001) | `icestream_minio` / `change-me-minio-secret` | S3 lakehouse bucket browser |
| **Iceberg REST Catalog** | [http://localhost:8181](http://localhost:8181) | *None* | Catalog config & table metadata |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | *None* | Metrics query engine |
| **PostgreSQL Database** | `localhost:5433` | `icestream_user` / `change-me-postgres-secret` | Metadata & incidents store |
| **Apache Kafka Broker** | `localhost:9092` | *None* | Event streaming broker (KRaft mode) |

---

## 3. Method 1: WSL 2 (Recommended & Fastest)

WSL 2 (Windows Subsystem for Linux) provides a native Linux environment directly inside Windows. This allows you to use the repository's automated `./start.sh` script without modifying anything.

### Step 1: Install WSL 2 (Ubuntu)
Open **PowerShell as Administrator** and run:
```powershell
wsl --install -d Ubuntu
```
Restart your computer if prompted. After rebooting, launch **Ubuntu** from the Start Menu, set up your UNIX username and password, and update packages:
```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Enable Docker Desktop WSL 2 Integration
1. Open **Docker Desktop** on Windows.
2. Go to **Settings** (gear icon) > **General** > Ensure **"Use the WSL 2 based engine"** is checked.
3. Go to **Settings** > **Resources** > **WSL integration**.
4. Enable integration with your **Ubuntu** distribution.
5. Click **Apply & restart**.

### Step 3: Install Required Packages in Ubuntu
Open your **Ubuntu terminal** and install Python and Node.js:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl jq

# Install Node.js (v20 LTS) & npm
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verify the tools:
```bash
docker --version
docker compose version
python3 --version
node --version
npm --version
```

### Step 4: Clone the Repository & Setup Environment
In your Ubuntu terminal:
```bash
# Clone the repository
git clone https://github.com/sujal-dot/IceStream.git
cd IceStream

# Prevent Windows CRLF line ending conversions
git config core.autocrlf input

# Create .env from template
cp .env.example .env
```

### Step 5: Install Python & Frontend Dependencies
```bash
# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python backend dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt

# Install React frontend dependencies
cd frontend
npm install
cd ..
```

### Step 6: Start IceStream with One Command
Make `start.sh` executable and run it:
```bash
chmod +x start.sh
./start.sh
```

`start.sh` will automatically:
1. Validate required tools.
2. Spin up all Docker containers (Kafka, MinIO, Iceberg REST, Postgres, Flink, Prometheus, Grafana).
3. Wait for all 7 infrastructure health checks to turn green.
4. Create Kafka topics and MinIO buckets (`warehouse`, `checkpoints`, `schemas`, `logs`).
5. Initialize the Iceberg Catalog and table schemas.
6. Submit the Flink Bronze streaming pipeline.
7. Launch the FastAPI backend on port 8000.
8. Launch the Vite React frontend on port 5173.
9. Launch the background telemetry generator.

### Step 7: Open in Your Windows Browser
Windows 10/11 automatically forwards WSL 2 network ports to your host Windows machine. Open your favorite Windows browser:
- **Dashboard**: [http://localhost:5173](http://localhost:5173)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Grafana**: [http://localhost:3000](http://localhost:3000)

---

## 4. Method 2: Native Windows (PowerShell + Docker Desktop)

If you prefer running directly in Windows PowerShell without WSL:

### Step 1: Open PowerShell and Enable Script Execution
Open **PowerShell as Administrator** once and run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Type `Y` and press Enter.

### Step 2: Clone Repository & Create Environment Configuration
Open a standard **PowerShell** window:
```powershell
# Navigate to your workspace folder
cd C:\Projects   # or your preferred directory

# Clone repository
git clone https://github.com/sujal-dot/IceStream.git
cd IceStream

# Copy .env template
Copy-Item .env.example .env
```

### Step 3: Set Up Python Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install backend dependencies
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Step 4: Install Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

### Step 5: Start Docker Infrastructure
Ensure **Docker Desktop** is running (green whale icon in system tray), then execute:
```powershell
docker compose up -d
```

Verify that all containers are running and healthy:
```powershell
docker compose ps
```

### Step 6: Initialize Kafka Topics & MinIO Buckets

#### 1. Create Kafka Topics:
```powershell
docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic checkout-events --partitions 3 --replication-factor 1
docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic checkout-valid --partitions 3 --replication-factor 1
docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic checkout-invalid --partitions 3 --replication-factor 1
docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic checkout-dlq --partitions 3 --replication-factor 1
docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic pipeline-control --partitions 1 --replication-factor 1
docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic schema-events --partitions 1 --replication-factor 1
```

#### 2. Create MinIO Buckets:
```powershell
docker exec icestream-minio mc alias set local http://localhost:9000 icestream_minio change-me-minio-secret
docker exec icestream-minio mc mb --ignore-existing local/warehouse
docker exec icestream-minio mc mb --ignore-existing local/checkpoints
docker exec icestream-minio mc mb --ignore-existing local/schemas
docker exec icestream-minio mc mb --ignore-existing local/logs
```

#### 3. Initialize Iceberg Catalog & Tables:
```powershell
$env:PYTHONPATH="."
python scripts/iceberg/init_catalog.py
```

#### 4. Submit Flink Streaming Job:
```powershell
python scripts/submit_flink_job.py
```

### Step 7: Launch Application Services

Open **two separate PowerShell terminals** in the `IceStream` directory:

#### Terminal 1 — FastAPI Backend:
```powershell
cd C:\path\to\IceStream
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
*(Leave this terminal running. Backend will be live at http://localhost:8000)*

#### Terminal 2 — React Dashboard:
```powershell
cd C:\path\to\IceStream\frontend
npm run dev -- --host 0.0.0.0 --port 5173
```
*(Leave this terminal running. Dashboard will be live at http://localhost:5173)*

---

## 5. Verifying the Running System

1. **Dashboard UI**:
   Navigate to [http://localhost:5173](http://localhost:5173) in your browser. You should see the real-time Lakehouse pipeline topology (Kafka → Flink → Iceberg / Quarantine / DLQ), error rate charts, and circuit breaker status.
2. **Backend Health**:
   Open PowerShell or terminal and run:
   ```powershell
   curl http://localhost:8000/health
   ```
   Expected response:
   ```json
   {"status":"ok","database":"connected","iceberg_catalog":"ok","kafka":"connected"}
   ```
3. **Flink Streaming Pipeline**:
   Visit [http://localhost:8081](http://localhost:8081). Under **Running Jobs**, you will see `IceStream_Bronze_Ingestion` actively consuming from Kafka and appending to Apache Iceberg.
4. **MinIO Object Browser**:
   Visit [http://localhost:9001](http://localhost:9001) (User: `icestream_minio`, Password: `change-me-minio-secret`). Check that the `warehouse/` bucket contains Iceberg metadata and Parquet data files.

---

## 6. Simulating Live Streaming Data & Faults

To generate synthetic checkout events and observe real-time error detection, open a new terminal:

### Generating Normal Traffic:
```bash
# In WSL:
PYTHONPATH=. .venv/bin/python generator/main.py --rate 100 --null-rate 2.0

# In PowerShell:
$env:PYTHONPATH="."
python generator/main.py --rate 100 --null-rate 2.0
```

### Simulating Fault Injection (Tripping the Circuit Breaker):
Inject bad schemas or corrupted events:
```bash
# In WSL:
PYTHONPATH=. .venv/bin/python generator/main.py --rate 200 --error-rate 0.25

# In PowerShell:
$env:PYTHONPATH="."
python generator/main.py --rate 200 --error-rate 0.25
```
Watch the React dashboard ([http://localhost:5173](http://localhost:5173)):
- The dynamic error rate gauge will spike past 2.0%.
- The automated circuit breaker will transition from **CLOSED** (normal) to **OPEN** (isolated).
- Bad records are redirected to the `quarantine` table in Iceberg and the DLQ.

---

## 7. Stopping the Services

### If Using WSL 2:
```bash
./start.sh --stop
```
*(This gracefully stops backend, frontend, and Docker containers while preserving all data volumes).*

### If Using Native Windows:
1. In the Backend and Frontend PowerShell terminals, press `Ctrl + C` to stop the processes.
2. In PowerShell, stop the containers safely:
   ```powershell
   docker compose stop
   ```
3. To completely tear down containers without losing data:
   ```powershell
   docker compose down
   ```
   *(To wipe volumes and start completely fresh: `docker compose down -v`)*

---

## 8. Troubleshooting Common Windows Issues

### Issue 1: `\r: command not found` or `syntax error near unexpected token`
- **Cause**: Git on Windows automatically converted Linux line endings (`LF`) to Windows carriage returns (`CRLF`).
- **Fix**: In your repo root, run:
  ```bash
  # Inside WSL or Git Bash
  git config core.autocrlf input
  git checkout-index --force --all
  # Or convert start.sh directly:
  sed -i -e 's/\r$//' start.sh
  sed -i -e 's/\r$//' scripts/**/*.sh
  ```

### Issue 2: `Activate.ps1 cannot be loaded because running scripts is disabled`
- **Cause**: PowerShell restricts executing scripts by default.
- **Fix**: Run PowerShell as Administrator and execute:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```

### Issue 3: Docker containers exit or laptop freezes / high memory usage
- **Cause**: WSL 2 / Docker Desktop can consume up to 80% of host RAM if unconstrained.
- **Fix**: Create a `.wslconfig` file in your Windows user home directory (`C:\Users\<YourUsername>\.wslconfig`):
  ```ini
  [wsl2]
  memory=6GB
  processors=4
  swap=2GB
  ```
  Then restart WSL in PowerShell:
  ```powershell
  wsl --shutdown
  ```

### Issue 4: Port 5433 or 8000 already in use
- **Cause**: A local PostgreSQL instance or existing development server is occupying the port.
- **Fix**: Check what process is using the port:
  ```powershell
  netstat -ano | findstr :5433
  ```
  Kill the conflicting PID or adjust the port inside `.env` (e.g. `POSTGRES_PORT=5434`).

### Issue 5: `docker: command not found` inside WSL 2
- **Cause**: Docker Desktop WSL 2 integration is not turned on for your Ubuntu distro.
- **Fix**: Open Docker Desktop > Settings > Resources > WSL Integration > Switch toggle ON for your Ubuntu distribution > Click "Apply & Restart".

---

## 9. Running Tests on Windows

To run the full test suite locally on your Windows machine:

```bash
# In WSL or PowerShell (with .venv active):
pytest tests/ -v
```

To run offline testing mode:
```bash
TESTING=true pytest tests/ -v
```
