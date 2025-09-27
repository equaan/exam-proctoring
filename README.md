# 🎓 Proctoring System - Modern Exam Management Platform

A comprehensive, real-time exam management and monitoring system built with FastAPI, WebSocket technology, and modern web interfaces. This system provides automated proctoring, cheating detection, and detailed marking capabilities for online examinations.

## ✨ Key Features

### 🎯 **Core Functionality**
- **Real-time Student Monitoring** - Track all students during exams with live status updates
- **Automated Marking System** - 20 marks per question (5 MCQ questions = 100 total marks)
- **Cheating Detection & Penalties** - Flag system with automatic penalty application
- **Virtual Student Management** - Handle students whether they're connected or not
- **WebSocket Communication** - Real-time updates across all interfaces

### 🎨 **Modern User Interface**
- **Centralized Dashboard Hub** - Beautiful landing page with role-based navigation
- **Glass Morphism Design** - Modern UI with smooth animations and hover effects
- **Responsive Layout** - Works perfectly on desktop, tablet, and mobile devices
- **Clean Architecture** - Organized file structure following best practices

### 📊 **Advanced Features**
- **Detailed Marksheet** - View simple or detailed results with answer breakdown
- **Auto-save Functionality** - Student answers saved every 5 seconds
- **Exam Timer** - Countdown timer visible to all participants
- **System Reset** - Quick reset functionality for multiple exam sessions
- **Legacy URL Support** - Backward compatibility maintained

## 🚀 Quick Start

### **Prerequisites**
- Python 3.8 or higher
- Virtual environment (recommended)

### **Installation & Setup**

1. **Navigate to the project directory:**
   ```bash
   cd "proctoring"
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```
   
3. **Activate virtual environment:**
   ```bash
   .\.venv\Scripts\Activate.ps1
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the system:**
   ```bash
   python run.py
   ```

6. **Open your browser:**
   - The system will start on `http://localhost:8001`
   - Your browser should automatically open to the centralized dashboard

## 🌐 System Access Points

### **Main Dashboard Hub**
- **URL**: `http://localhost:8001/`
- **Description**: Beautiful centralized landing page with role selection cards
- **Features**: System status monitoring, quick actions, modern animations

### **Role-Based Interfaces**

#### 👨‍🏫 **Teacher Dashboard**
- **URL**: `http://localhost:8001/teacher`
- **Purpose**: Monitor students and manage exam results
- **Features**:
  - Real-time student status monitoring
  - Cheating alerts and flag management
  - Detailed marksheet with answer breakdown
  - Penalty application system
  - Export and override capabilities

#### ⚙️ **Processor Control Panel**
- **URL**: `http://localhost:8001/processor`
- **Purpose**: Control exam flow and system state
- **Features**:
  - Start/stop exams with custom duration
  - System state management
  - Real-time exam monitoring
  - Emergency controls

#### 👨‍🎓 **Student Portal**
- **URL**: `http://localhost:8001/student`
- **Purpose**: Take exams and submit answers
- **Features**:
  - Student selection and login
  - MCQ examination interface
  - Real-time countdown timer
  - Auto-save functionality
  - Back button for switching students

## 📋 How to Use the System

### **For Exam Administrators:**

1. **Start the System**
   ```bash
   python run.py
   ```

2. **Open Dashboard**
   - Navigate to `http://localhost:8001`
   - See the beautiful centralized hub

3. **Set Up Exam**
   - Click "Processor Control" card
   - Configure exam duration (e.g., 60 minutes)
   - Click "Start Exam"

4. **Monitor Students**
   - Click "Teacher Dashboard" card
   - Watch real-time student status
   - Monitor cheating alerts
   - View live submissions

### **For Students:**

1. **Join Exam**
   - Navigate to `http://localhost:8001`
   - Click "Student Portal" card
   - Select your student ID from dropdown
   - Click "Join"

2. **Take Exam**
   - Answer 5 MCQ questions (20 marks each)
   - Watch countdown timer
   - Answers auto-save every 5 seconds
   - Submit when complete

3. **Navigation**
   - Use "Back to Selection" to switch students
   - Timer shows remaining time
   - Submit button available during exam

## 📊 Exam Questions & Marking

### **Sample Questions (Distributed Systems Theme):**
1. **Which property is ensured by consensus?** (Answer: Agreement)
2. **CAP: when partitions happen, you must choose** (Answer: C or A)
3. **Raft uses** (Answer: Leader election + logs)
4. **Eventual consistency means** (Answer: convergence over time)
5. **Load balancing needs** (Answer: sticky sessions for WebSockets)

### **Marking System:**
- **20 marks per correct answer**
- **Total possible: 100 marks**
- **Penalty system**:
  - 0 flags: Full marks
  - 1 flag: 50% penalty
  - 2+ flags: 0 marks (complete penalty)

## 🏗️ Project Structure

```
proctoring/
├── 🚀 run.py                    # Main entry point - START HERE
├── 📋 requirements.txt          # Python dependencies
├── 📄 README.md                 # This documentation
├── 📄 PROJECT_STRUCTURE.md      # Detailed structure info
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
│   ├── proctoring.db          # SQLite database (auto-created)
│   ├── students.json          # Student information
│   ├── submissions.json       # Exam submissions
│   └── flags.jsonl           # Cheating detection logs
│
├── 📚 docs/                   # Additional documentation
└── 🔧 .venv/                 # Python virtual environment
```

## 🎯 What You'll See

### **1. Landing Dashboard Hub**
- Beautiful gradient background with floating animations
- Three role selection cards with hover effects
- System status panel showing server health
- Quick actions for common tasks
- Modern glass morphism design

### **2. Teacher Dashboard**
- Real-time student list with status indicators
- Cheating alerts panel with flag counts
- Comprehensive marksheet with detailed results
- "View Detailed Results" button for answer breakdown
- Override and penalty management tools

### **3. Student Interface**
- Clean exam interface with countdown timer
- 5 multiple-choice questions
- Auto-save indicator
- Submit button and back navigation
- Responsive design for all devices

### **4. Processor Control**
- Exam start/stop controls
- Duration configuration
- System state monitoring
- Emergency reset capabilities
- Real-time status updates

## 🔧 Technical Details

### **Backend Technology:**
- **FastAPI** - Modern Python web framework
- **WebSocket** - Real-time bidirectional communication
- **SQLite** - Lightweight database for student data
- **Asyncio** - Asynchronous programming for performance

### **Frontend Technology:**
- **Modern HTML5/CSS3/JavaScript**
- **Tailwind CSS** - Utility-first CSS framework
- **WebSocket Client** - Real-time UI updates
- **Responsive Design** - Mobile-friendly interface

### **Key Features:**
- **Real-time Communication** - WebSocket connections for live updates
- **Automated Marking** - Server-side answer validation
- **Penalty System** - Cheating detection with automatic penalties
- **Virtual Students** - Handle disconnected students gracefully
- **Clean Architecture** - Organized, maintainable codebase

## 🚨 Troubleshooting

### **Common Issues:**

1. **Server won't start:**
   ```bash
   # Kill existing processes
   taskkill /f /im python.exe
   # Restart
   python run.py
   ```

2. **Port already in use:**
   - The system uses port 8001
   - Check if another application is using this port
   - Modify port in `run.py` if needed

3. **Students can't join:**
   - Ensure exam is started from Processor UI
   - Check WebSocket connections in browser console
   - Verify student IDs exist in database

4. **UI not loading:**
   - Check all files are in correct folders
   - Verify templates/ folder contains all HTML files
   - Restart server after file changes

## 🎉 Success Indicators

When everything is working correctly, you should see:

✅ **Server starts** with "🎓 Starting Proctoring System..." message
✅ **Landing page loads** at `http://localhost:8001` with beautiful design
✅ **All role cards** are clickable and navigate correctly
✅ **System status** shows green indicators
✅ **Students can join** and see exam interface
✅ **Real-time updates** work across all interfaces
✅ **Marking system** calculates scores correctly
✅ **Timer countdown** displays properly

## 📞 Support

If you encounter any issues:
1. Check the console output for error messages
2. Verify all dependencies are installed
3. Ensure virtual environment is activated
4. Check browser console for JavaScript errors
5. Restart the system with `python run.py`

## 👤 Author
- [Mohammad Equaan Kacchi](https://www.linkedin.com/in/mohammad-equaan-kacchi-4a8a49290/)

## 🤝 Contributors
- Sajiya Shaikh
- Tamanna Shaikh
- Shruti Tambade

## 🙏 Acknowledgment
Special thanks to **Amit Nerulkar (Mentor)** for his valuable guidance and support.

---

