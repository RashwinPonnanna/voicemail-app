# VoiceMail – Email + Real-Time Voice Communication

A cloud-based web application combining email services with real-time WebRTC voice calling, built with Flask and Socket.IO.

## Features

- **User Authentication** – Register, login, and secure session management
- **Email System** – Compose, send, receive, view, and delete emails
- **Real-Time Voice Calls** – WebRTC peer-to-peer audio calls via Socket.IO signaling
- **Online Presence** – See which users are currently online
- **Responsive UI** – Works on desktop and mobile

## Tech Stack

| Layer      | Technology              |
|------------|-------------------------|
| Frontend   | HTML, CSS, JavaScript   |
| Backend    | Python (Flask)          |
| Real-time  | Socket.IO + WebRTC      |
| Database   | SQLite (dev) / PostgreSQL (prod) |
| Deploy     | Render                  |

---

## Local Development

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd voicemail-app
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## Deploy on Render

### Step 1 – Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/voicemail-app.git
git push -u origin main
```

### Step 2 – Create a new Web Service on Render
1. Go to [https://render.com](https://render.com) and log in
2. Click **New → Web Service**
3. Connect your GitHub account and select the `voicemail-app` repository
4. Render auto-detects `render.yaml` — fill in the settings:

| Setting        | Value                                                              |
|----------------|--------------------------------------------------------------------|
| Name           | voicemail-app                                                      |
| Environment    | Python                                                             |
| Build Command  | `pip install -r requirements.txt`                                  |
| Start Command  | `gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:$PORT` |
| Instance Type  | Free                                                               |

### Step 3 – Set Environment Variables
In Render → Environment → Add:

| Key        | Value                            |
|------------|----------------------------------|
| SECRET_KEY | (generate a long random string)  |

### Step 4 – Deploy
Click **Create Web Service**. Render will build and deploy automatically.

### Step 5 – Use the app
Open your Render URL (e.g. `https://voicemail-app.onrender.com`) and register two accounts in different browsers to test voice calls.

---

## Environment Variables

| Variable     | Description                    | Default                   |
|--------------|--------------------------------|---------------------------|
| SECRET_KEY   | Flask session secret           | dev-secret (change this!) |
| DATABASE_URL | Database connection string     | `sqlite:///voicemail.db`  |
| PORT         | Port to listen on              | 5000 (set by Render)      |

---

## Project Structure

```
voicemail-app/
├── app.py                  # Flask app + routes + Socket.IO events
├── requirements.txt        # Python dependencies
├── Procfile                # Render/Heroku start command
├── render.yaml             # Render deployment config
├── templates/
│   ├── base.html           # Layout + navbar + call panel
│   ├── login.html
│   ├── register.html
│   ├── inbox.html
│   ├── sent.html
│   ├── compose.html
│   └── view_email.html
└── static/
    ├── css/style.css       # Full stylesheet
    └── js/
        ├── webrtc.js       # WebRTC + Socket.IO voice calling
        └── main.js         # Misc UI helpers
```

---

## How Voice Calling Works

1. Caller clicks a user → gets microphone permission → creates WebRTC offer
2. Offer is sent to receiver via Socket.IO signaling server
3. Receiver sees incoming call modal → accepts → creates answer
4. ICE candidates are exchanged
5. Peer-to-peer audio stream is established directly between browsers
6. Either party can end the call

---

## Notes

- SQLite is used by default (file stored in `instance/voicemail.db`)
- For production, set `DATABASE_URL` to a PostgreSQL URL (Render provides free Postgres)
- WebRTC requires HTTPS for microphone access — Render provides SSL automatically
- Only 1 gunicorn worker is used (required for Socket.IO with eventlet)
