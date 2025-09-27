#!/usr/bin/env python3
"""
Proctoring System - Entry Point
===============================

A comprehensive exam management and monitoring platform with:
- Real-time student monitoring
- Cheating detection and penalty system
- Automated marking with 20 marks per question
- Modern centralized dashboard hub
- WebSocket-based real-time communication

Usage:
    python run.py

The server will start on http://localhost:8001
Open your browser to see the beautiful centralized dashboard!
"""

import uvicorn
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def main():
    """Start the proctoring system server"""
    print("🎓 Starting Proctoring System...")
    print("📊 Dashboard will be available at: http://localhost:8001")
    print("🚀 Loading centralized hub with modern UI...")
    
    try:
        uvicorn.run(
            "app.server:app",
            host="127.0.0.1",
            port=8001,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Proctoring System stopped gracefully")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
