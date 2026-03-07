🚀 chAs AI Creator - Complete Deployment Guide
Created by: chAs
Version: 1.0.0
Last Updated: 2024
📋 Table of Contents
Prerequisites
Project Structure Overview
Backend Deployment
Frontend (Flutter) Deployment
Google Play Store Deployment
Apple App Store Deployment
Web Deployment
Post-Deployment Checklist
Troubleshooting
✅ Prerequisites
Before starting deployment, ensure you have:
Required Accounts
[ ] Google Play Console ($25 one-time fee)
[ ] Apple Developer Account ($99/year)
[ ] Firebase Account (Free tier available)
[ ] Google Cloud Platform (Free tier available)
[ ] Stripe Account (For payments)
[ ] Google AdMob Account (For ads)
[ ] Domain Name (For web deployment)
Required Software
[ ] Flutter SDK (Latest stable version)
[ ] Android Studio (For Android builds)
[ ] Xcode (For iOS builds - Mac only)
[ ] Docker (For backend deployment)
[ ] Git (For version control)
[ ] VS Code or preferred IDE
System Requirements
Windows/Mac/Linux for Flutter development
Mac with macOS for iOS builds (required)
8GB+ RAM recommended
50GB+ free disk space
📁 Project Structure Overview
plain
Copy
chas-ai-creator/
├── 📁 backend/                 # Python FastAPI Backend
│   ├── 📁 app/
│   │   ├── 📁 api/v1/         # API Routes
│   │   ├── 📁 core/           # Security, Logging
│   │   ├── 📁 models/         # Database Models
│   │   ├── 📁 services/       # Business Logic
│   │   │   └── 📁 ai/         # AI Services
│   │   └── main.py            # Entry Point
│   ├── Dockerfile             # Container Config
│   ├── docker-compose.yml     # Local Dev Stack
│   └── requirements.txt       # Python Dependencies
│
├── 📁 frontend/               # Flutter Application
│   ├── 📁 android/            # Android Config
│   ├── 📁 ios/                # iOS Config
│   ├── 📁 lib/                # Dart Source Code
│   ├── 📁 web/                # Web Config
│   └── pubspec.yaml           # Flutter Dependencies
│
└── 📁 docs/                   # Documentation
🔧 Step 1: Backend Deployment
1.1 Configure Environment Variables
Create a .env file in the backend/ directory:
bash
Copy
cd backend
cp .env.example .env
Edit .env with your production values:
env
Copy
# App Config
APP_NAME="chAs AI Creator"
APP_VERSION=1.0.0
DEBUG=false
ENVIRONMENT=production

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@your-db-host:5432/aicreator

# Redis
REDIS_URL=redis://your-redis-host:6379/0

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com

# AWS S3
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET=chas-ai-creator-videos

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Google AdMob
ADMOB_APP_ID_ANDROID=ca-app-pub-XXXXXXXXXXXXXXXX~XXXXXXXXXX
ADMOB_APP_ID_IOS=ca-app-pub-XXXXXXXXXXXXXXXX~XXXXXXXXXX

# AI Services
HUGGINGFACE_API_KEY=hf_...
OPENAI_API_KEY=sk-...

# Security
SECRET_KEY=your-super-secret-key-min-32-chars
1.2 Deploy to Google Cloud Run (Recommended)
bash
Copy
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/chas-ai-creator-backend

gcloud run deploy chas-ai-creator-backend \
  --image gcr.io/YOUR_PROJECT_ID/chas-ai-creator-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=postgresql://..." \
  --set-env-vars "REDIS_URL=redis://..."
1.3 Deploy to AWS (Alternative)
bash
Copy
# Build Docker image
docker build -t chas-ai-creator-backend .

# Tag for ECR
docker tag chas-ai-creator-backend:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/chas-ai-creator-backend:latest

# Push to ECR
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/chas-ai-creator-backend:latest

# Deploy to ECS/Fargate via AWS Console or CLI
1.4 Verify Backend Deployment
bash
Copy
# Test health endpoint
curl https://your-backend-url/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "app": "chAs AI Creator",
  "creator": "chAs"
}
📱 Step 2: Frontend (Flutter) Configuration
2.1 Update API Configuration
Edit frontend/lib/services/api_service.dart:
dart
Copy
// Change this to your production backend URL
static const String baseUrl = 'https://your-backend-url/api/v1';
2.2 Configure Firebase
bash
Copy
cd frontend

# Install Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Initialize Firebase
firebase init

# Configure Firebase in your app
# Download google-services.json (Android) and GoogleService-Info.plist (iOS)
# from Firebase Console and place in respective directories
2.3 Configure Google AdMob
Android - Edit android/app/src/main/AndroidManifest.xml:
xml
Copy
<manifest>
    <application>
        <!-- Add this meta-data tag -->
        <meta-data
            android:name="com.google.android.gms.ads.APPLICATION_ID"
            android:value="ca-app-pub-XXXXXXXXXXXXXXXX~XXXXXXXXXX"/>
    </application>
</manifest>
iOS - Edit ios/Runner/Info.plist:
xml
Copy
<dict>
    <!-- Add this key -->
    <key>GADApplicationIdentifier</key>
    <string>ca-app-pub-XXXXXXXXXXXXXXXX~XXXXXXXXXX</string>
</dict>
🤖 Step 3: Google Play Store Deployment
3.1 Prepare Your App
bash
Copy
cd frontend

# Update version in pubspec.yaml
version: 1.0.0+1  # format: versionName+versionCode

# Get dependencies
flutter pub get

# Clean build
flutter clean

# Build APK (for testing)
flutter build apk --release

# Build App Bundle (for Play Store)
flutter build appbundle --release
3.2 Create Keystore (First Time Only)
bash
Copy
# Generate keystore
keytool -genkey -v -keystore ~/upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias upload

# Create key.properties file
cat > android/key.properties << EOF
storePassword=YOUR_STORE_PASSWORD
keyPassword=YOUR_KEY_PASSWORD
keyAlias=upload
storeFile=/Users/YOUR_USERNAME/upload-keystore.jks
EOF
3.3 Configure Signing
Edit android/app/build.gradle:
gradle
Copy
android {
    // ...
    
    signingConfigs {
        release {
            keyAlias keystoreProperties['keyAlias']
            keyPassword keystoreProperties['keyPassword']
            storeFile keystoreProperties['storeFile'] ? file(keystoreProperties['storeFile']) : null
            storePassword keystoreProperties['storePassword']
        }
    }
    
    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }
    }
}
3.4 Build Release AAB
bash
Copy
flutter build appbundle --release

# Output: build/app/outputs/bundle/release/app-release.aab
3.5 Create Play Store Listing
Go to Google Play Console
Click "Create app"
Fill in app details:
App name: chAs AI Creator
Default language: English
App or game: App
Free or paid: Free (with in-app purchases)
3.6 Upload Your App
Navigate to Production > Create new release
Upload your app-release.aab file
Fill in release notes:
plain
Copy
🎉 Initial Release of chAs AI Creator!

✨ Features:
• AI-powered video script generation
• Automatic image and video creation
• Multiple video styles and formats
• Schedule videos for automatic creation
• Earn credits by watching ads
• Upgrade to Pro for unlimited videos

Made with ❤️ by chAs
3.7 Complete Store Listing
Required Assets:
[ ] App Icon: 512x512 PNG
[ ] Feature Graphic: 1024x500 PNG
[ ] Screenshots:
Phone: 16:9 or 9:16 (min 2, max 8)
Tablet: 16:9 or 9:16 (min 2, max 8)
[ ] Short Description: 80 characters max
[ ] Full Description: 4000 characters max
Example Description:
plain
Copy
🎬 chAs AI Creator - Create Viral Videos with AI!

Transform your ideas into stunning videos in minutes with the power of AI!

✨ What You Can Do:
• Generate AI-written scripts for any topic
• Create beautiful visuals automatically
• Choose from multiple video styles (Cinematic, Cartoon, Realistic)
• Export in any format (16:9, 9:16, 1:1)
• Schedule videos to be created automatically
• Add captions, music, and voiceovers

🆓 FREE to Use:
• 2 videos per day on FREE tier
• Earn credits by watching ads
• Upgrade anytime for unlimited videos

💎 PRO Features:
• Unlimited video creation
• Longer videos (up to 5 minutes)
• Priority processing
• No ads
• Advanced AI models

Perfect for:
✓ Content Creators
✓ Social Media Managers
✓ Small Businesses
✓ Influencers
✓ Anyone who wants to create videos!

📱 Available on Android, iOS, and Web

Made with ❤️ by chAs

Download now and start creating amazing videos!
3.8 Set Up Content Rating
Go to Store presence > Content rating
Fill out the questionnaire
Expected rating: PEGI 3 or ESRB Everyone
3.9 Set Up Pricing & Distribution
Go to Monetize > Products
Create in-app products:
Pro Monthly: $9.99
Pro Yearly: $79.99 (save 33%)
Credits Pack: $4.99 for 50 credits
3.10 Submit for Review
Review all sections (green checkmarks)
Click Submit for review
Wait 1-3 days for approval
🍎 Step 4: Apple App Store Deployment
4.1 Prepare Your App (Mac Required)
bash
Copy
cd frontend

# Update version in pubspec.yaml
version: 1.0.0+1

# Get dependencies
flutter pub get

# Clean build
flutter clean

# Install CocoaPods dependencies
cd ios
pod install
cd ..

# Build iOS
flutter build ios --release
4.2 Configure Xcode
Open ios/Runner.xcworkspace in Xcode
Select Runner in the project navigator
Configure:
Bundle Identifier: com.chas.aicreator
Version: 1.0.0
Build: 1
Team: Your Apple Developer account
Signing: Automatically manage signing
4.3 Add Required Permissions
Edit ios/Runner/Info.plist:
xml
Copy
<dict>
    <!-- Photos -->
    <key>NSPhotoLibraryUsageDescription</key>
    <string>This app needs access to photos to save your created videos.</string>
    
    <!-- Camera (if needed) -->
    <key>NSCameraUsageDescription</key>
    <string>This app needs access to camera for video creation.</string>
    
    <!-- Microphone (if needed) -->
    <key>NSMicrophoneUsageDescription</key>
    <string>This app needs access to microphone for voice features.</string>
    
    <!-- App Tracking Transparency (for ads) -->
    <key>NSUserTrackingUsageDescription</key>
    <string>This identifier will be used to deliver personalized ads to you.</string>
</dict>
4.4 Build and Archive
In Xcode, select Product > Scheme > Runner
Select Any iOS Device (arm64)
Click Product > Archive
Wait for archive to complete
Click Distribute App
Select App Store Connect > Upload
4.5 Create App Store Listing
Go to App Store Connect
Click My Apps > + > New App
Fill in details:
Platform: iOS
Name: chAs AI Creator
Primary Language: English
Bundle ID: com.chas.aicreator
SKU: chas-aicreator-001
User Access: Full Access
4.6 Complete App Information
Required Information:
[ ] Subtitle: 30 characters max
[ ] Category: Photo & Video
[ ] Content Rights: No
[ ] Age Rating: 4+
Screenshots Required:
iPhone 6.7" Display: 1290x2796 (portrait)
iPhone 6.5" Display: 1284x2778 (portrait)
iPhone 5.5" Display: 1242x2208 (portrait)
iPad Pro 6th Gen: 2048x2732 (portrait)
4.7 Upload Screenshots
Use Simulator to take screenshots:
bash
Copy
# Open Simulator
open -a Simulator

# Take screenshot: Cmd + S
# Screenshots saved to Desktop
4.8 Set Up In-App Purchases
Go to Features > In-App Purchases
Click + to add products:
Pro Monthly: Auto-Renewable Subscription, $9.99
Pro Yearly: Auto-Renewable Subscription, $79.99
Credits Pack: Consumable, $4.99
4.9 Submit for Review
Go to App Store tab
Select 1.0 Prepare for Submission
Upload build (select from dropdown)
Fill in export compliance
Click Submit for Review
Wait 1-2 days for approval
🌐 Step 5: Web Deployment
5.1 Build for Web
bash
Copy
cd frontend

# Enable web support
flutter config --enable-web

# Build for production
flutter build web --release

# Output: build/web/
5.2 Deploy to Firebase Hosting (Recommended)
bash
Copy
# Install Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Initialize
firebase init hosting

# Select your project
# Set public directory: build/web
# Configure as single-page app: Yes

# Deploy
firebase deploy --only hosting

# Your app will be live at: https://your-project.web.app
5.3 Deploy to Netlify (Alternative)
bash
Copy
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
netlify deploy --prod --dir=build/web

# Or drag and drop build/web folder to Netlify dashboard
5.4 Deploy to Vercel (Alternative)
bash
Copy
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod
5.5 Configure Custom Domain
Purchase domain (e.g., Namecheap, GoDaddy)
Add custom domain in Firebase/Netlify/Vercel
Update DNS records:
A Record: @ → 151.101.1.195
CNAME: www → your-site.netlify.app
✅ Post-Deployment Checklist
Backend Verification
[ ] Health endpoint returns 200
[ ] Database connections working
[ ] Firebase Auth integrated
[ ] Stripe webhooks configured
[ ] AI services responding
[ ] Celery workers running
Mobile Apps Verification
[ ] App launches without crashes
[ ] Login/Signup works
[ ] Video creation flow works
[ ] Ads display correctly
[ ] In-app purchases work
[ ] Push notifications work
[ ] Videos save to gallery
Web Verification
[ ] Site loads correctly
[ ] Responsive on mobile/desktop
[ ] All features functional
[ ] SEO meta tags set
[ ] Analytics tracking
Marketing Setup
[ ] App Store Optimization (ASO)
[ ] Screenshots optimized
[ ] Keywords researched
[ ] Social media accounts created
[ ] Website landing page live
🔧 Troubleshooting
Common Issues
Issue: Build fails with "Keystore file not found"
bash
Copy
# Solution: Create keystore
keytool -genkey -v -keystore ~/upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
Issue: "Firebase App not initialized"
bash
Copy
# Solution: Re-download config files
# Android: google-services.json → android/app/
# iOS: GoogleService-Info.plist → ios/Runner/
Issue: Ads not showing
bash
Copy
# Solution: Use test IDs in development
# Check AdMob app ID is correct
# Verify app is published in AdMob
Issue: Backend connection refused
bash
Copy
# Solution: Check CORS settings
# Verify API URL is correct
# Check firewall rules
Getting Help
Flutter Issues: flutter.dev/docs
Firebase Help: firebase.google.com/support
Play Store Help: support.google.com/googleplay
App Store Help: developer.apple.com/support
📞 Support
Created by chAs
For support, contact:
📧 Email: support@chasaicreator.com
🌐 Website: https://chasaicreator.com
💬 Discord: Join our community
📄 License
Copyright (c) 2024 chAs. All rights reserved.
This project is licensed under the MIT License.
🎉 Congratulations! Your chAs AI Creator app is now live!
Share your success and keep creating amazing videos! 🚀
