# 🏗️ Proctoring System - Project Structure

## 📁 Clean & Organized Structure

```
proctoring/
├── 🚀 run.py                    # Main entry point - START HERE
├── 📋 requirements.txt          # Python dependencies
├── 📄 PROJECT_STRUCTURE.md      # This file
│
├── 📱 app/                      # Application core
│   ├── __init__.py             # Package marker
│   └── server.py               # FastAPI server with all routes
│
├── 🎨 templates/               # All HTML templates
│   ├── landing_hub.html        # Modern centralized dashboard
│   ├── teacher_ui.html         # Teacher monitoring interface
│   ├── student_ui.html         # Student exam interface
│   └── processor_ui.html       # Exam control interface
│
├── 💾 data/                    # Database and data files
│   ├── proctoring.db          # SQLite database
│   ├── students.json          # Student information
│   ├── submissions.json       # Exam submissions
│   └── flags.jsonl           # Cheating detection logs
│
├── 📚 docs/                   # Documentation
│   └── README.md             # Project documentation
│
└── 🔧 .venv/                 # Python virtual environment
```

## 🚀 How to Run

### Quick Start:
```bash
python run.py
```

### Manual Start:
```bash
cd app
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```

## 🌐 Access Points

- **Main Dashboard**: http://localhost:8001/
- **Teacher UI**: http://localhost:8001/teacher
- **Student UI**: http://localhost:8001/student  
- **Processor UI**: http://localhost:8001/processor

## 🎯 Key Features

✅ **Centralized Dashboard Hub** - Modern landing page with role selection
✅ **Real-time Monitoring** - WebSocket-based student tracking
✅ **Automated Marking** - 20 marks per question (5 questions = 100 total)
✅ **Cheating Detection** - Flag system with penalties
✅ **Clean Architecture** - Organized file structure
✅ **Modern UI** - Glass morphism design with smooth animations

## 🔧 Development

- **Backend**: FastAPI with WebSocket support
- **Frontend**: Modern HTML/CSS/JS with Tailwind CSS
- **Database**: SQLite for simplicity
- **Real-time**: WebSocket connections for live updates

## 📝 Notes

- All HTML files are now in `templates/` folder
- Database files are in `data/` folder  
- Main server code is in `app/server.py`
- Use `run.py` as the single entry point
- Legacy URLs still work for backward compatibility
