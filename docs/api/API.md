API.md
API Documentation
Base URL
plain
Copy
Production: https://api.aicreator.app/api/v1
Development: http://localhost:8000/api/v1
Authentication
All API requests require authentication via Bearer token:
plain
Copy
Authorization: Bearer <firebase_id_token>
Endpoints
Authentication
POST /auth/register
Register a new user.
Request:
JSON
Copy
{
  "email": "user@example.com",
  "password": "securepassword",
  "display_name": "John Doe"
}
Response:
JSON
Copy
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "John Doe",
    "subscription_tier": "free",
    "credits": 0
  }
}
POST /auth/login
Login with email and password.
Request:
JSON
Copy
{
  "email": "user@example.com",
  "password": "securepassword"
}
Response: Same as register
POST /auth/social-login
Login with social provider.
Request:
JSON
Copy
{
  "provider": "google",
  "token": "google_id_token",
  "email": "user@example.com",
  "display_name": "John Doe"
}
GET /auth/me
Get current user info.
Response:
JSON
Copy
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "subscription_tier": "pro",
  "credits": 100
}
Users
GET /users/profile
Get user profile.
Response:
JSON
Copy
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "bio": "Content creator",
  "avatar_url": "https://...",
  "subscription_tier": "pro",
  "subscription_expires_at": "2024-12-31T23:59:59Z",
  "credits": 100,
  "created_at": "2024-01-01T00:00:00Z"
}
PUT /users/profile
Update user profile.
Request:
JSON
Copy
{
  "display_name": "Jane Doe",
  "bio": "AI content creator",
  "avatar_url": "https://..."
}
GET /users/settings
Get user settings.
Response:
JSON
Copy
{
  "default_niche": "tech",
  "default_video_type": "narration",
  "default_video_length": 60,
  "default_aspect_ratio": "9:16",
  "character_consistency_enabled": true,
  "captions_enabled": true,
  "caption_style": "modern",
  "background_music_enabled": true,
  "default_style": "cinematic"
}
PUT /users/settings
Update user settings.
Request:
JSON
Copy
{
  "default_niche": "cooking",
  "default_video_length": 45
}
GET /users/usage
Get usage statistics.
Response:
JSON
Copy
{
  "total_videos_generated": 150,
  "videos_this_month": 25,
  "videos_today": 2,
  "storage_used": 1073741824,
  "remaining_daily_videos": 8
}
Videos
POST /videos/generate
Create a new video.
Request:
JSON
Copy
{
  "title": "My Awesome Video",
  "description": "A description of the video",
  "niche": "tech",
  "video_type": "narration",
  "duration": 60,
  "aspect_ratio": "9:16",
  "style": "cinematic",
  "captions_enabled": true,
  "background_music_enabled": true,
  "user_instructions": "Focus on AI technology"
}
Response:
JSON
Copy
{
  "id": "video-uuid",
  "title": "My Awesome Video",
  "status": "pending",
  "progress": 0,
  "created_at": "2024-01-15T10:30:00Z"
}
GET /videos/list
List user's videos.
Query Parameters:
status (optional): Filter by status
page (optional): Page number (default: 1)
limit (optional): Items per page (default: 20)
Response:
JSON
Copy
{
  "videos": [
    {
      "id": "video-uuid",
      "title": "My Video",
      "status": "completed",
      "progress": 100,
      "video_url": "https://...",
      "thumbnail_url": "https://...",
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:35:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "pages": 8
}
GET /videos/{video_id}
Get video details.
Response:
JSON
Copy
{
  "id": "video-uuid",
  "title": "My Video",
  "description": "Description",
  "niche": "tech",
  "video_type": "narration",
  "duration": 60,
  "aspect_ratio": "9:16",
  "style": "cinematic",
  "status": "completed",
  "progress": 100,
  "video_url": "https://...",
  "thumbnail_url": "https://...",
  "script": {
    "title": "...",
    "scenes": [...]
  },
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:35:00Z"
}
GET /videos/{video_id}/scenes
Get video scenes.
Response:
JSON
Copy
{
  "scenes": [
    {
      "id": "scene-uuid",
      "scene_number": 1,
      "description": "Scene description",
      "caption": "Caption text",
      "narration": "Narration text",
      "image_url": "https://...",
      "video_clip_url": "https://...",
      "duration": 3.0,
      "status": "completed"
    }
  ]
}
DELETE /videos/{video_id}
Delete a video.
POST /videos/{video_id}/regenerate
Regenerate a failed video.
Schedules
POST /videos/schedules
Create a video schedule.
Request:
JSON
Copy
{
  "name": "Daily Tech Videos",
  "frequency": "daily",
  "days_of_week": [1, 2, 3, 4, 5],
  "schedule_times": ["09:00", "18:00"],
  "max_videos_per_day": 2,
  "video_config": {
    "niche": "tech",
    "duration": 30,
    "style": "cinematic"
  }
}
GET /videos/schedules/list
List schedules.
PUT /videos/schedules/{schedule_id}
Update schedule.
DELETE /videos/schedules/{schedule_id}
Delete schedule.
AI Services
POST /ai/generate-script
Generate video script.
Request:
JSON
Copy
{
  "niche": "tech",
  "video_type": "narration",
  "duration": 60,
  "style": "cinematic",
  "user_instructions": "Focus on AI"
}
Response:
JSON
Copy
{
  "title": "The Future of AI",
  "description": "Exploring AI technology",
  "scenes": [
    {
      "scene_number": 1,
      "description": "Opening scene",
      "caption": "AI is changing the world",
      "image_prompt": "Futuristic AI visualization"
    }
  ],
  "narration": "Full narration text...",
  "hashtags": ["#AI", "#technology", "#future"]
}
POST /ai/generate-image
Generate image.
Request:
JSON
Copy
{
  "prompt": "Futuristic city with AI robots",
  "style": "cinematic",
  "aspect_ratio": "9:16"
}
Response:
JSON
Copy
{
  "image_url": "https://...",
  "prompt": "Futuristic city with AI robots"
}
POST /ai/preview-video
Generate video preview.
Response:
JSON
Copy
{
  "script": {...},
  "sample_images": [
    {
      "scene_number": 1,
      "image_url": "https://..."
    }
  ]
}
GET /ai/niches
Get available niches.
GET /ai/styles
Get available styles.
GET /ai/caption-styles
Get caption styles.
GET /ai/music-styles
Get music styles.
Payments
GET /payments/plans
Get subscription plans.
Response:
JSON
Copy
{
  "plans": [
    {
      "id": "plan-uuid",
      "name": "Pro",
      "slug": "pro",
      "price_monthly": 29.99,
      "price_yearly": 299.99,
      "daily_video_limit": 20,
      "max_video_length": 120,
      "features": ["Narration", "Custom music", "Priority support"]
    }
  ]
}
GET /payments/credit-packages
Get credit packages.
POST /payments/subscribe
Create subscription.
Request:
JSON
Copy
{
  "plan_id": "plan-uuid",
  "billing_cycle": "monthly"
}
POST /payments/create-payment-intent
Create payment intent for credits.
GET /payments/history
Get payment history.
GET /payments/current
Get current subscription.
POST /payments/cancel-subscription
Cancel subscription.
Error Responses
400 Bad Request
JSON
Copy
{
  "error": "Validation error",
  "code": "VALIDATION_ERROR",
  "details": {
    "field": "email",
    "message": "Invalid email format"
  }
}
401 Unauthorized
JSON
Copy
{
  "error": "Authentication required",
  "code": "AUTHENTICATION_ERROR"
}
403 Forbidden
JSON
Copy
{
  "error": "Not authorized",
  "code": "AUTHORIZATION_ERROR"
}
404 Not Found
JSON
Copy
{
  "error": "Resource not found",
  "code": "NOT_FOUND"
}
429 Rate Limit
JSON
Copy
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
500 Internal Error
JSON
Copy
{
  "error": "Internal server error",
  "code": "INTERNAL_ERROR"
}
Rate Limits
Free tier: 100 requests/hour
Pro tier: 1000 requests/hour
Enterprise: Unlimited
Webhooks
Stripe Webhook
Endpoint: POST /payments/webhook
Events:
payment_intent.succeeded
invoice.payment_failed
subscription.created
subscription.cancelled
SDKs
Python
Python
Copy
from ai_creator import Client

client = Client(api_key="your_api_key")
video = client.videos.create(
    niche="tech",
    duration=60,
    style="cinematic"
)
JavaScript
JavaScript
Copy
import { AICreator } from '@ai-creator/sdk';

const client = new AICreator({ apiKey: 'your_api_key' });
const video = await client.videos.create({
  niche: 'tech',
  duration: 60,
  style: 'cinematic'
});
