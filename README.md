🎬 chAs AI Creator
AI-Powered Video Content Automation Platform
Created with ❤️ by chAs
https://flutter.dev
https://python.org
LICENSE
https://github.com/yourusername/chas-ai-creator
✨ What is chAs AI Creator?
chAs AI Creator is a revolutionary cross-platform application that uses artificial intelligence to automatically generate stunning videos from simple text descriptions. Perfect for content creators, social media managers, and anyone who wants to create professional videos without any editing skills!
🎯 Key Features
🤖 AI Script Generation - Automatically writes engaging video scripts
🎨 AI Image Generation - Creates beautiful visuals for each scene
🎬 AI Video Composition - Automatically combines everything into a polished video
🗣️ Voice Narration - Optional AI-generated voiceovers
📅 Auto Scheduling - Schedule videos to be created automatically
💰 Earn Free Credits - Watch ads to earn credits for more videos
📱 Cross-Platform - Available on Android, iOS, and Web
📱 Screenshots
<div align="center">
  <img src="docs/screenshots/home.png" width="200" alt="Home Screen"/>
  <img src="docs/screenshots/create.png" width="200" alt="Create Video"/>
  <img src="docs/screenshots/videos.png" width="200" alt="My Videos"/>
  <img src="docs/screenshots/settings.png" width="200" alt="Settings"/>
</div>
🚀 Quick Start
Prerequisites
Flutter SDK 3.0+
Python 3.10+
Docker & Docker Compose
Firebase Account
(Optional) Google Cloud / AWS Account
1. Clone the Repository
bash
Copy
git clone https://github.com/chAs/chas-ai-creator.git
cd chas-ai-creator
2. Backend Setup
bash
Copy
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run with Docker (Recommended)
docker-compose up -d

# Or run locally
uvicorn app.main:app --reload
Backend will be running at: http://localhost:8000
3. Frontend Setup
bash
Copy
cd frontend

# Install dependencies
flutter pub get

# Run on your device
flutter run

# Or build for specific platform
flutter build apk          # Android
flutter build ios          # iOS (Mac only)
flutter build web          # Web
📁 Project Structure
plain
Copy
chas-ai-creator/
├── 📁 backend/                    # Python FastAPI Backend
│   ├── 📁 app/
│   │   ├── 📁 api/v1/            # REST API Routes
│   │   │   ├── auth.py           # Authentication endpoints
│   │   │   ├── users.py          # User management
│   │   │   ├── videos.py         # Video generation
│   │   │   ├── ai_services.py    # AI service endpoints
│   │   │   └── payments.py       # Stripe payments
│   │   ├── 📁 core/              # Core utilities
│   │   ├── 📁 models/            # Database models
│   │   ├── 📁 services/          # Business logic
│   │   │   └── 📁 ai/            # AI integrations
│   │   ├── 📁 tasks/             # Celery background tasks
│   │   ├── config.py             # App configuration
│   │   └── main.py               # Entry point
│   ├── Dockerfile                # Container config
│   ├── docker-compose.yml        # Local development
│   └── requirements.txt          # Python dependencies
│
├── 📁 frontend/                   # Flutter Application
│   ├── 📁 android/               # Android-specific config
│   ├── 📁 ios/                   # iOS-specific config
│   ├── 📁 lib/
│   │   ├── 📁 config/            # Theme & configuration
│   │   ├── 📁 models/            # Data models
│   │   ├── 📁 providers/         # State management (BLoC)
│   │   ├── 📁 screens/           # UI screens
│   │   │   ├── 📁 auth/          # Login/Register
│   │   │   ├── 📁 dashboard/     # Home dashboard
│   │   │   ├── 📁 video/         # Video creation/list
│   │   │   ├── 📁 settings/      # App settings
│   │   │   └── 📁 onboarding/    # First-time tutorial
│   │   ├── 📁 services/          # API clients
│   │   ├── 📁 widgets/           # Reusable components
│   │   ├── app.dart              # App root
│   │   └── main.dart             # Entry point
│   ├── 📁 web/                   # Web-specific config
│   └── pubspec.yaml              # Flutter dependencies
│
├── 📁 docs/                       # Documentation
│   ├── DEPLOYMENT_GUIDE.md       # Complete deployment guide
│   └── api/                      # API documentation
│
└── README.md                      # This file
🛠️ Tech Stack
Backend
Table
Technology	Purpose
FastAPI	Python web framework
PostgreSQL	Primary database
Redis	Caching & task queue
Celery	Background task processing
Firebase Auth	User authentication
Stripe	Payment processing
AWS S3	File storage
Docker	Containerization
AI Services
Table
Technology	Purpose
Hugging Face	AI model inference
Stable Diffusion	Image generation
AnimateDiff	Video generation
Piper TTS	Voice synthesis
FFmpeg	Video processing
Frontend
Table
Technology	Purpose
Flutter	Cross-platform UI
BLoC Pattern	State management
Google AdMob	In-app advertising
Firebase	Analytics & crash reporting
📖 Usage Guide
Creating Your First Video
Open the app and sign up/login
Tap "Create Video" on the dashboard
Select a niche (Tech, Cooking, Motivation, etc.)
Choose video settings:
Type: Silent or Narration
Duration: 10s to 5 minutes
Aspect Ratio: 16:9, 9:16, or 1:1
Style: Cinematic, Cartoon, Realistic
Add instructions (optional) - describe what you want
Tap "Preview" to see AI-generated script
Tap "Create Video" to start generation
Wait for processing (usually 2-5 minutes)
Download and share your video!
Earning Free Credits
Go to Dashboard
Tap "Watch Ad & Earn Credits"
Watch a short advertisement
Get 5 FREE credits instantly!
Scheduling Videos
Go to Schedule tab
Set frequency (Daily, Weekly)
Choose times for auto-creation
Configure video settings
Videos will be created automatically!
💰 Monetization
Free Tier
✅ 2 videos per day
✅ Basic AI models
✅ Standard quality
✅ Watch ads for credits
Pro Tier ($9.99/month)
✅ Unlimited videos
✅ Up to 5-minute videos
✅ Premium AI models
✅ Priority processing
✅ No ads
✅ Advanced features
Credits System
Watch ads → Earn 5 credits
Buy credits → $4.99 for 50 credits
Use credits → 1 credit = 1 video
🚀 Deployment
📱 Mobile Apps
See our comprehensive Deployment Guide for:
✅ Google Play Store deployment
✅ Apple App Store deployment
✅ Backend deployment (Cloud Run/AWS)
✅ Web deployment (Firebase/Netlify)
Quick Deploy
bash
Copy
# Backend to Google Cloud Run
gcloud run deploy chas-ai-creator-backend --source backend/

# Web to Firebase
firebase deploy --only hosting
🔧 Configuration
Environment Variables
Create .env file in backend/:
env
Copy
# Required
DATABASE_URL=postgresql://...
FIREBASE_PROJECT_ID=...
STRIPE_SECRET_KEY=sk_...

# AI Services
HUGGINGFACE_API_KEY=hf_...
OPENAI_API_KEY=sk-...

# Ads
ADMOB_APP_ID_ANDROID=ca-app-pub-...
ADMOB_APP_ID_IOS=ca-app-pub-...
🧪 Testing
Backend Tests
bash
Copy
cd backend
pytest
Frontend Tests
bash
Copy
cd frontend
flutter test
🤝 Contributing
We welcome contributions! Please follow these steps:
Fork the repository
Create a feature branch: git checkout -b feature/amazing-feature
Commit your changes: git commit -m 'Add amazing feature'
Push to the branch: git push origin feature/amazing-feature
Open a Pull Request
Code Style
Python: Follow PEP 8
Dart: Follow Effective Dart
Write tests for new features
Update documentation
📝 API Documentation
Authentication
http
Copy
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
Videos
http
Copy
POST /api/v1/videos/generate
GET  /api/v1/videos/list
GET  /api/v1/videos/{id}
AI Services
http
Copy
POST /api/v1/ai/generate-script
POST /api/v1/ai/generate-image
POST /api/v1/ai/preview-video
Full API docs available at /docs when running backend locally.
🐛 Troubleshooting
Common Issues
App won't build
bash
Copy
flutter clean
flutter pub get
flutter run
Backend connection error
Check .env configuration
Verify backend is running
Check firewall settings
Ads not showing
Use test IDs in development
Verify AdMob account is approved
Check app-ads.txt configuration
📞 Support
Need help? We're here for you!
📧 Email: support@chasaicreator.com
🌐 Website: https://chasaicreator.com
💬 Discord: Join Community
🐦 Twitter: @chAsAICreator
🗺️ Roadmap
Phase 1 (Current)
✅ Core video generation
✅ Basic AI models
✅ User authentication
✅ Payment integration
✅ Ad monetization
Phase 2 (Q2 2024)
🔄 Advanced AI models
🔄 Team collaboration
🔄 API for developers
🔄 More video templates
🔄 Analytics dashboard
Phase 3 (Q3 2024)
📋 Direct social media posting
📋 White-label solution
📋 Enterprise features
📋 Multi-language support
📋 Mobile app enhancements
📄 License
plain
Copy
MIT License

Copyright (c) 2024 chAs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
🙏 Acknowledgments
Special thanks to:
Flutter Team for the amazing framework
Hugging Face for AI model hosting
Firebase for backend services
All contributors who helped build this project
<div align="center">
Made with ❤️ by chAs
🌐 Website • 📧 Contact • 💬 Discord
⭐ Star this repo if you find it helpful! ⭐
</div>
