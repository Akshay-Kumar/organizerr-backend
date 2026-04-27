# Organizerr Backend (FastAPI)

A FastAPI-based backend service for managing and processing media organization workflows.
It provides APIs consumed by the frontend and media organizer engine.

---

## 🚀 Features

* ⚡ FastAPI backend
* 🗄 SQLite database (lightweight, file-based)
* 🔗 Integration with qBittorrent
* 🎬 TMDB API integration for metadata
* 📁 File operations management
* 🔌 REST API for frontend + media organizer

---

## 🧱 Tech Stack

* Python 3.11
* FastAPI
* SQLite
* Uvicorn

---

## 📂 Project Structure

```
organizerr-backend/
├── app/
│   ├── main.py
│   ├── routers/
│   ├── services/
│   └── models/
├── requirements.txt
├── backend.env
└── Dockerfile
```

---

## ⚙️ Environment Variables

Create a `backend.env` file:

```
DATABASE_URL=sqlite:///./data/torrents.db
UPLOAD_DIR=/app/uploads

QBT_HOST=http://<qbittorrent-ip>:8080
QBT_USER=your_username
QBT_PASS=your_password

TMDB_API_KEY=your_tmdb_key

FILE_OPERATIONS_PATH=/config/file_operations.json
```

---

## 🐳 Docker Setup

### Build & Run

```bash
docker compose up -d --build backend
```

---

### Ports

```
Backend: http://localhost:8005
```

---

## 💾 Database

* SQLite database stored at:

```
./backend_data/torrents.db
```

* Persistent via Docker volume

---

## 🔗 API Endpoints

Example:

```
GET /api/worldnews
GET /api/torrents
POST /api/process
```

Swagger docs:

```
http://localhost:8005/docs
```

---

## 🔄 Integration

### Frontend

```
REACT_APP_API_URL=http://localhost:8005
```

---

### Media Organizer

The media organizer calls backend APIs to:

* fetch metadata
* retrieve processing rules
* update job status

---

## ▶️ Run Locally (without Docker)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8005
```

---

## 🧪 Development Tips

* Use `.env` for local overrides
* Keep SQLite file outside container
* Use `/docs` for API testing

---

## 🔐 Security Notes

* Do not commit `backend.env`
* Protect qBittorrent credentials
* Use HTTPS in production

---

## 📌 Future Improvements

* Job queue system (Celery / RQ)
* Authentication layer
* Background workers

---

## 👨‍💻 Author

Akshay Kumar
