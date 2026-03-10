/*
 * chAs AI Creator - API Service
 * Created by: chAs
 * Nigeria Friendly Version - Uses Custom JWT Auth
 */

import 'dart:io';

import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';

import '../models/user.dart';
import 'auth_service.dart';

class ApiService {
  late Dio _dio;
  final AuthService _authService = AuthService();

  static const String baseUrl =
      'https://chas-ai-creator-2.onrender.com/api/v1';

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 120), // FIX 1 - AI calls need longer timeout
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _authService.getAccessToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (error, handler) async {
        // FIX 2 - only attempt refresh on 401, not on all errors
        if (error.response?.statusCode == 401) {
          try {
            final newToken = await _authService.refreshAccessToken();
            if (newToken != null) {
              error.requestOptions.headers['Authorization'] =
                  'Bearer $newToken';
              final response = await _dio.fetch(error.requestOptions);
              return handler.resolve(response);
            } else {
              await _authService.signOut();
            }
          } catch (_) {
            await _authService.signOut();
          }
        }
        return handler.next(error);
      },
    ));
  }

  // ─── USER ──────────────────────────────────────────────────────────────────

  Future<User> getCurrentUser() async {
    final response = await _dio.get('/auth/me');
    return User.fromJson(response.data);
  }

  Future<User> updateProfile({
    String? displayName,
    String? bio,
    String? avatarUrl,
  }) async {
    final response = await _dio.put('/users/profile', data: {
      if (displayName != null) 'display_name': displayName,
      if (bio != null) 'bio': bio,
      if (avatarUrl != null) 'avatar_url': avatarUrl,
    });
    return User.fromJson(response.data);
  }

  Future<UserSettings?> getUserSettings() async {
    // FIX 3 - return null instead of crashing when settings not found
    try {
      final response = await _dio.get('/users/settings');
      final data = response.data;
      if (data == null || data['settings'] == null) return null;
      return UserSettings.fromJson(data['settings']);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<UserSettings> updateUserSettings(UserSettings settings) async {
    final response =
        await _dio.put('/users/settings', data: settings.toJson());
    return UserSettings.fromJson(response.data['settings']);
  }

  Future<Map<String, dynamic>> getUsageStats() async {
    final response = await _dio.get('/users/usage');
    // FIX 4 - safe defaults so dashboard never crashes on missing fields
    final data = response.data as Map<String, dynamic>? ?? {};
    return {
      'total_videos_generated': 0,
      'remaining_daily_videos': 0,
      'videos_today': 0,
      'videos_this_month': 0,
      'credits': 0,
      ...data,
    };
  }

  // ─── VIDEOS ────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> createVideo({
    required String niche,
    String? title,
    String? description,
    String videoType = 'silent',
    int duration = 30,
    String aspectRatio = '9:16',
    String style = 'cinematic',
    bool characterConsistencyEnabled = false,
    String? characterDescription,
    bool captionsEnabled = true,
    String captionStyle = 'modern',
    String captionColor = 'white',
    bool captionEmojiEnabled = true,
    bool backgroundMusicEnabled = true,
    String backgroundMusicStyle = 'upbeat',
    String? userInstructions,
    String? scenePriorityNotes,
  }) async {
    final response = await _dio.post('/videos/generate', data: {
      'niche': niche,
      if (title != null) 'title': title,
      if (description != null) 'description': description,
      'video_type': videoType,
      'duration': duration,
      'aspect_ratio': aspectRatio,
      'style': style,
      'character_consistency_enabled': characterConsistencyEnabled,
      if (characterDescription != null)
        'character_description': characterDescription,
      'captions_enabled': captionsEnabled,
      'caption_style': captionStyle,
      'caption_color': captionColor,
      'caption_emoji_enabled': captionEmojiEnabled,
      'background_music_enabled': backgroundMusicEnabled,
      'background_music_style': backgroundMusicStyle,
      if (userInstructions != null) 'user_instructions': userInstructions,
      if (scenePriorityNotes != null) 'scene_priority_notes': scenePriorityNotes,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> getVideos({
    String? status,
    int page = 1,
    int limit = 20,
  }) async {
    final response = await _dio.get('/videos/list', queryParameters: {
      if (status != null) 'status': status,
      'page': page,
      'limit': limit,
    });
    // FIX 5 - safe defaults so videos screen never crashes
    final data = response.data as Map<String, dynamic>? ?? {};
    return {
      'videos': [],
      'total': 0,
      'page': page,
      'pages': 1,
      ...data,
    };
  }

  Future<Map<String, dynamic>> getVideo(String videoId) async {
    final response = await _dio.get('/videos/$videoId');
    return response.data;
  }

  Future<Map<String, dynamic>> getVideoScenes(String videoId) async {
    final response = await _dio.get('/videos/$videoId/scenes');
    return response.data;
  }

  Future<void> deleteVideo(String videoId) async {
    await _dio.delete('/videos/$videoId');
  }

  Future<void> regenerateVideo(String videoId) async {
    await _dio.post('/videos/$videoId/regenerate');
  }

  // ─── SCHEDULES ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> createSchedule({
    String? name,
    String frequency = 'daily',
    List<int>? daysOfWeek,
    required List<String> scheduleTimes,
    int maxVideosPerDay = 1,
    Map<String, dynamic>? videoConfig,
  }) async {
    final response = await _dio.post('/videos/schedules', data: {
      if (name != null) 'name': name,
      'frequency': frequency,
      if (daysOfWeek != null) 'days_of_week': daysOfWeek,
      'schedule_times': scheduleTimes,
      'max_videos_per_day': maxVideosPerDay,
      if (videoConfig != null) 'video_config': videoConfig,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> getSchedules() async {
    final response = await _dio.get('/videos/schedules/list');
    return response.data;
  }

  Future<void> updateSchedule(
    String scheduleId, {
    String? name,
    String? frequency,
    List<int>? daysOfWeek,
    List<String>? scheduleTimes,
    int? maxVideosPerDay,
    Map<String, dynamic>? videoConfig,
  }) async {
    await _dio.put('/videos/schedules/$scheduleId', data: {
      if (name != null) 'name': name,
      if (frequency != null) 'frequency': frequency,
      if (daysOfWeek != null) 'days_of_week': daysOfWeek,
      if (scheduleTimes != null) 'schedule_times': scheduleTimes,
      if (maxVideosPerDay != null) 'max_videos_per_day': maxVideosPerDay,
      if (videoConfig != null) 'video_config': videoConfig,
    });
  }

  Future<void> deleteSchedule(String scheduleId) async {
    await _dio.delete('/videos/schedules/$scheduleId');
  }

  // ─── AI SERVICES ───────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> generateScript({
    required String niche,
    String videoType = 'silent',
    int duration = 30,
    String? userInstructions,
    String style = 'cinematic',
  }) async {
    final response = await _dio.post('/ai/generate-script', data: {
      'niche': niche,
      'video_type': videoType,
      'duration': duration,
      if (userInstructions != null) 'user_instructions': userInstructions,
      'style': style,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> generateImage({
    required String prompt,
    String style = 'cinematic',
    String aspectRatio = '9:16',
    String? negativePrompt,
  }) async {
    final response = await _dio.post('/ai/generate-image', data: {
      'prompt': prompt,
      'style': style,
      'aspect_ratio': aspectRatio,
      if (negativePrompt != null) 'negative_prompt': negativePrompt,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> previewVideo({
    required String niche,
    String videoType = 'silent',
    int duration = 30,
    String style = 'cinematic',
    String? userInstructions,
  }) async {
    final response = await _dio.post('/ai/preview-video', data: {
      'niche': niche,
      'video_type': videoType,
      'duration': duration,
      'style': style,
      if (userInstructions != null) 'user_instructions': userInstructions,
    });
    return response.data;
  }

  // FIX 6 - added missing smartGeneratePlan used by SmartCreateScreen
  Future<Map<String, dynamic>> smartGeneratePlan({
    required String idea,
    String aspectRatio = '9:16',
    int duration = 30,
    String style = 'cinematic',
    bool captionsEnabled = true,
    bool backgroundMusicEnabled = true,
  }) async {
    final response = await _dio.post('/ai/smart-plan', data: {
      'idea': idea,
      'aspect_ratio': aspectRatio,
      'duration': duration,
      'style': style,
      'captions_enabled': captionsEnabled,
      'background_music_enabled': backgroundMusicEnabled,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> getNiches() async {
    final response = await _dio.get('/ai/niches');
    return response.data;
  }

  Future<Map<String, dynamic>> getStyles() async {
    final response = await _dio.get('/ai/styles');
    return response.data;
  }

  Future<Map<String, dynamic>> getCaptionStyles() async {
    final response = await _dio.get('/ai/caption-styles');
    return response.data;
  }

  Future<Map<String, dynamic>> getMusicStyles() async {
    final response = await _dio.get('/ai/music-styles');
    return response.data;
  }

  // ─── PAYMENTS ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSubscriptionPlans() async {
    final response = await _dio.get('/payments/plans');
    return response.data;
  }

  Future<Map<String, dynamic>> getCreditPackages() async {
    final response = await _dio.get('/payments/credit-packages');
    return response.data;
  }

  Future<Map<String, dynamic>> initializePayment({
    required String packageId,
    String? callbackUrl,
  }) async {
    final response = await _dio.post('/payments/initialize', data: {
      'package_id': packageId,
      if (callbackUrl != null) 'callback_url': callbackUrl,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> verifyPayment(String reference) async {
    final response = await _dio.post('/payments/verify', data: {
      'reference': reference,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> createSubscription({
    required String planId,
    String billingCycle = 'monthly',
  }) async {
    final response = await _dio.post('/payments/subscribe', data: {
      'plan_id': planId,
      'billing_cycle': billingCycle,
    });
    return response.data;
  }

  Future<Map<String, dynamic>> getPaymentHistory() async {
    final response = await _dio.get('/payments/history');
    return response.data;
  }

  Future<Map<String, dynamic>> getCurrentSubscription() async {
    final response = await _dio.get('/payments/current');
    return response.data;
  }

  Future<void> cancelSubscription() async {
    await _dio.post('/payments/cancel-subscription');
  }

  // ─── FILE UPLOAD ───────────────────────────────────────────────────────────

  Future<String> uploadFile(File file, String path) async {
    final fileName = file.path.split('/').last;

    // FIX 7 - detect correct content type from extension
    final ext = fileName.split('.').last.toLowerCase();
    final contentType = switch (ext) {
      'png'  => MediaType('image', 'png'),
      'gif'  => MediaType('image', 'gif'),
      'webp' => MediaType('image', 'webp'),
      _      => MediaType('image', 'jpeg'),
    };

    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: fileName,
        contentType: contentType,
      ),
    });

    final response = await _dio.post(
      '/upload/$path',
      data: formData,
      options: Options(
        // FIX 8 - longer timeout for file uploads on slow Nigerian networks
        receiveTimeout: const Duration(seconds: 180),
        sendTimeout: const Duration(seconds: 180),
      ),
    );
    return response.data['url'];
  }

  // ─── ERROR HANDLING ────────────────────────────────────────────────────────

  // FIX 9 - extract clean user-friendly error messages from backend responses
  String handleError(dynamic error) {
    if (error is DioException) {
      // No internet
      if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout ||
          error.type == DioExceptionType.sendTimeout) {
        return '⏱️ Connection timed out. Please check your internet and try again.';
      }
      if (error.type == DioExceptionType.connectionError) {
        return '📡 No internet connection. Please check your network.';
      }

      final response = error.response;
      if (response != null) {
        final data = response.data;

        // Backend sends structured error with 'detail' or 'error' field
        if (data is Map) {
          final msg = data['detail'] ?? data['error'] ?? data['message'];
          if (msg != null && msg.toString().isNotEmpty) {
            return msg.toString();
          }
        }

        // HTTP status fallbacks
        return switch (response.statusCode) {
          400 => '❌ Invalid request. Please check your inputs.',
          401 => '🔒 Session expired. Please log in again.',
          403 => '🚫 You don\'t have permission to do this.',
          404 => '🔍 Not found. It may have been deleted.',
          429 => '⏳ Too many requests. Please wait a moment.',
          500 => '🔧 Server error. Please try again shortly.',
          503 => '🔧 Service temporarily unavailable. Try again soon.',
          _   => '❌ Something went wrong (${response.statusCode}).',
        };
      }

      return '📡 Network error. Please check your connection.';
    }

    return '❌ Unexpected error: ${error.toString()}';
  }
}
