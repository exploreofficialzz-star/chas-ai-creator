/*
 * chAs AI Creator - API Service
 * Enhanced & Debugged — Global Version
 */

import 'dart:developer' as developer;
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

  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;

  ApiService._internal() {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 180),
      sendTimeout: const Duration(seconds: 60),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    // ── Interceptor: inject token + auto-refresh ────────────────────────
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _authService.getAccessToken();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        _log('→ ${options.method} ${options.path}');
        return handler.next(options);
      },

      onResponse: (response, handler) {
        _log('← ${response.statusCode} ${response.requestOptions.path}');
        return handler.next(response);
      },

      onError: (error, handler) async {
        _log('✗ ${error.response?.statusCode} '
            '${error.requestOptions.path}: ${error.message}');

        // FIX 1 — auto-retry on 401 with refreshed token
        if (error.response?.statusCode == 401) {
          try {
            final newToken = await _authService.refreshAccessToken();
            if (newToken != null) {
              error.requestOptions.headers['Authorization'] =
                  'Bearer $newToken';
              final response =
                  await _dio.fetch(error.requestOptions);
              return handler.resolve(response);
            }
          } catch (_) {}
          await _authService.signOut();
        }

        // FIX 2 — auto-retry ONCE on 502/503 (Render cold start)
        if ((error.response?.statusCode == 502 ||
                error.response?.statusCode == 503) &&
            !(error.requestOptions.extra['retried'] == true)) {
          try {
            _log('⏳ Cold start detected — retrying in 3s...');
            await Future.delayed(const Duration(seconds: 3));
            final opts = error.requestOptions;
            opts.extra['retried'] = true;
            final response = await _dio.fetch(opts);
            return handler.resolve(response);
          } catch (_) {}
        }

        return handler.next(error);
      },
    ));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // USER
  // ─────────────────────────────────────────────────────────────────────────

  // FIX 3 — was hitting '/auth/me', correct endpoint is '/users/me'
  Future<User> getCurrentUser() async {
    final response = await _dio.get('/users/me');
    return User.fromJson(_asMap(response.data));
  }

  // FIX 4 — was PUT '/users/profile', consistent with auth_service PATCH '/users/me'
  Future<User> updateProfile({
    String? displayName,
    String? bio,
    String? avatarUrl,
  }) async {
    final response = await _dio.patch('/users/me', data: {
      if (displayName != null) 'display_name': displayName.trim(),
      if (bio != null) 'bio': bio.trim(),
      if (avatarUrl != null) 'avatar_url': avatarUrl,
    });
    return User.fromJson(_asMap(response.data));
  }

  Future<UserSettings?> getUserSettings() async {
    try {
      final response = await _dio.get('/users/settings');
      final data = _asMap(response.data);
      // FIX 5 — handle both {'settings': {...}} and flat response
      final settingsJson =
          data['settings'] as Map<String, dynamic>? ?? data;
      if (settingsJson.isEmpty) return null;
      return UserSettings.fromJson(settingsJson);
    } on DioException catch (e) {
      // FIX 6 — 404 means no settings saved yet → return null (use defaults)
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<UserSettings> updateUserSettings(UserSettings settings) async {
    final response = await _dio.put(
      '/users/settings',
      data: settings.toJson(),
    );
    final data = _asMap(response.data);
    // FIX 7 — handle both {'settings': {...}} and flat response
    final settingsJson =
        data['settings'] as Map<String, dynamic>? ?? data;
    return UserSettings.fromJson(settingsJson);
  }

  Future<Map<String, dynamic>> getUsageStats() async {
    try {
      final response = await _dio.get('/users/usage');
      final data = _asMap(response.data);
      // FIX 8 — normalize all possible key names from backend
      return {
        'total_videos_generated':
            data['total_videos_generated'] ??
            data['total_videos'] ??
            data['totalVideos'] ?? 0,
        'remaining_daily_videos':
            data['remaining_daily_videos'] ??
            data['remaining'] ??
            data['videos_remaining'] ?? 0,
        'videos_today':
            data['videos_today'] ??
            data['today_count'] ??
            data['videosToday'] ?? 0,
        'videos_this_month':
            data['videos_this_month'] ??
            data['month_count'] ??
            data['videosThisMonth'] ?? 0,
        'credits':
            data['credits'] ?? 0,
        'daily_limit':
            data['daily_limit'] ??
            data['limit'] ?? 2,
        ...data,
      };
    } catch (_) {
      // FIX 9 — return safe defaults on failure so dashboard never crashes
      return {
        'total_videos_generated': 0,
        'remaining_daily_videos': 0,
        'videos_today': 0,
        'videos_this_month': 0,
        'credits': 0,
        'daily_limit': 2,
      };
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // VIDEOS
  // ─────────────────────────────────────────────────────────────────────────

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
    String audioMode = 'silent',
    String voiceStyle = 'professional',
    List<String> targetPlatforms = const ['tiktok'],
  }) async {
    final response = await _dio.post(
      '/videos/generate',
      data: {
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
        if (userInstructions != null)
          'user_instructions': userInstructions,
        if (scenePriorityNotes != null)
          'scene_priority_notes': scenePriorityNotes,
        'audio_mode': audioMode,
        'voice_style': voiceStyle,
        'target_platforms': targetPlatforms,
      },
      // FIX 10 — video generation can take a long time
      options: Options(receiveTimeout: const Duration(seconds: 300)),
    );
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getVideos({
    String? status,
    int page = 1,
    int limit = 20,
  }) async {
    // FIX 11 — try both endpoint patterns (some backends use /videos/)
    Response response;
    try {
      response = await _dio.get('/videos/', queryParameters: {
        if (status != null) 'status': status,
        'page': page,
        'limit': limit,
        'per_page': limit,
      });
    } on DioException catch (e) {
      if (e.response?.statusCode == 404 ||
          e.response?.statusCode == 405) {
        // Fallback to /videos/list
        response = await _dio.get('/videos/list', queryParameters: {
          if (status != null) 'status': status,
          'page': page,
          'limit': limit,
        });
      } else {
        rethrow;
      }
    }

    final data = _asMap(response.data);

    // FIX 12 — normalize all possible video list response shapes
    final videos = (data['videos'] ??
            data['data'] ??
            data['items'] ??
            data['results'] ??
            []) as List;

    return {
      'videos': videos,
      'total': data['total'] ??
          data['count'] ??
          data['total_count'] ??
          videos.length,
      'page': data['page'] ?? page,
      'pages': data['pages'] ??
          data['total_pages'] ??
          data['pageCount'] ?? 1,
      ...data,
    };
  }

  Future<Map<String, dynamic>> getVideo(String videoId) async {
    final response = await _dio.get('/videos/$videoId');
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getVideoScenes(String videoId) async {
    final response = await _dio.get('/videos/$videoId/scenes');
    return _asMap(response.data);
  }

  Future<void> deleteVideo(String videoId) async {
    await _dio.delete('/videos/$videoId');
  }

  Future<Map<String, dynamic>> regenerateVideo(String videoId) async {
    final response =
        await _dio.post('/videos/$videoId/regenerate');
    return _asMap(response.data);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SCHEDULES
  // ─────────────────────────────────────────────────────────────────────────

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
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getSchedules() async {
    final response = await _dio.get('/videos/schedules/list');
    return _asMap(response.data);
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
      if (maxVideosPerDay != null)
        'max_videos_per_day': maxVideosPerDay,
      if (videoConfig != null) 'video_config': videoConfig,
    });
  }

  Future<void> deleteSchedule(String scheduleId) async {
    await _dio.delete('/videos/schedules/$scheduleId');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // AI SERVICES
  // ─────────────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> generateScript({
    required String niche,
    String videoType = 'silent',
    int duration = 30,
    String? userInstructions,
    String style = 'cinematic',
  }) async {
    final response = await _dio.post(
      '/ai/generate-script',
      data: {
        'niche': niche,
        'video_type': videoType,
        'duration': duration,
        'style': style,
        if (userInstructions != null)
          'user_instructions': userInstructions,
      },
      options:
          Options(receiveTimeout: const Duration(seconds: 120)),
    );
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> generateImage({
    required String prompt,
    String style = 'cinematic',
    String aspectRatio = '9:16',
    String? negativePrompt,
  }) async {
    final response = await _dio.post(
      '/ai/generate-image',
      data: {
        'prompt': prompt,
        'style': style,
        'aspect_ratio': aspectRatio,
        if (negativePrompt != null)
          'negative_prompt': negativePrompt,
      },
      options:
          Options(receiveTimeout: const Duration(seconds: 120)),
    );
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> previewVideo({
    required String niche,
    String videoType = 'silent',
    int duration = 30,
    String style = 'cinematic',
    String? userInstructions,
  }) async {
    final response = await _dio.post(
      '/ai/preview-video',
      data: {
        'niche': niche,
        'video_type': videoType,
        'duration': duration,
        'style': style,
        if (userInstructions != null)
          'user_instructions': userInstructions,
      },
      options:
          Options(receiveTimeout: const Duration(seconds: 180)),
    );
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> smartGeneratePlan({
    required String idea,
    String aspectRatio = '9:16',
    int duration = 30,
    String style = 'cinematic',
    bool captionsEnabled = true,
    bool backgroundMusicEnabled = true,
    String audioMode = 'narration',
    String voiceStyle = 'professional',
    List<String> targetPlatforms = const ['tiktok'],
    bool characterConsistency = false,
    int uploadedImageCount = 0,
  }) async {
    final response = await _dio.post(
      '/ai/smart-plan',
      data: {
        'idea': idea,
        'aspect_ratio': aspectRatio,
        'duration': duration,
        'style': style,
        'captions_enabled': captionsEnabled,
        'background_music_enabled': backgroundMusicEnabled,
        'audio_mode': audioMode,
        'voice_style': voiceStyle,
        'target_platforms': targetPlatforms,
        'character_consistency': characterConsistency,
        'uploaded_image_count': uploadedImageCount,
      },
      options:
          Options(receiveTimeout: const Duration(seconds: 240)),
    );
    return _asMap(response.data);
  }

  Future<List<String>> uploadReferenceImages(
      List<File> images) async {
    final urls = <String>[];
    for (final image in images) {
      try {
        final url = await uploadFile(image, 'references');
        urls.add(url);
      } catch (e) {
        _log('⚠️ Skipped image upload: $e');
      }
    }
    return urls;
  }

  Future<Map<String, dynamic>> checkAiHealth() async {
    try {
      final response = await _dio.get(
        '/ai/health',
        options:
            Options(receiveTimeout: const Duration(seconds: 10)),
      );
      return _asMap(response.data);
    } catch (_) {
      return {'status': 'unavailable'};
    }
  }

  Future<Map<String, dynamic>> getNiches() async {
    final r = await _dio.get('/ai/niches');
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> getStyles() async {
    final r = await _dio.get('/ai/styles');
    return _asMap(r.data);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PAYMENTS
  // ─────────────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSubscriptionPlans() async {
    final r = await _dio.get('/payments/plans');
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> getCreditPackages() async {
    final r = await _dio.get('/payments/credit-packages');
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> initializePayment({
    required String packageId,
    String? callbackUrl,
  }) async {
    final r = await _dio.post('/payments/initialize', data: {
      'package_id': packageId,
      if (callbackUrl != null) 'callback_url': callbackUrl,
    });
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> verifyPayment(
      String reference) async {
    final r = await _dio.post('/payments/verify',
        data: {'reference': reference});
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> createSubscription({
    required String planId,
    String billingCycle = 'monthly',
  }) async {
    final r = await _dio.post('/payments/subscribe', data: {
      'plan_id': planId,
      'billing_cycle': billingCycle,
    });
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> getPaymentHistory() async {
    final r = await _dio.get('/payments/history');
    return _asMap(r.data);
  }

  Future<Map<String, dynamic>> getCurrentSubscription() async {
    final r = await _dio.get('/payments/current');
    return _asMap(r.data);
  }

  Future<void> cancelSubscription() async {
    await _dio.post('/payments/cancel-subscription');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FILE UPLOAD
  // ─────────────────────────────────────────────────────────────────────────

  Future<String> uploadFile(File file, String path) async {
    final fileName = file.path.split('/').last;
    final ext = fileName.split('.').last.toLowerCase();
    final contentType = switch (ext) {
      'png'  => MediaType('image', 'png'),
      'gif'  => MediaType('image', 'gif'),
      'webp' => MediaType('image', 'webp'),
      'mp4'  => MediaType('video', 'mp4'),
      'mov'  => MediaType('video', 'quicktime'),
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
        receiveTimeout: const Duration(seconds: 180),
        sendTimeout: const Duration(seconds: 180),
        contentType: 'multipart/form-data',
      ),
    );

    final data = _asMap(response.data);
    // FIX 13 — handle 'url', 'file_url', 'secure_url' (Cloudinary)
    final url = data['url'] ??
        data['file_url'] ??
        data['secure_url'] ??
        data['public_url'];

    if (url == null || url.toString().isEmpty) {
      throw Exception('Upload succeeded but no URL returned');
    }
    return url.toString();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR HANDLING
  // ─────────────────────────────────────────────────────────────────────────

  String handleError(dynamic error) {
    if (error is DioException) {
      // Timeout / network errors
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
          return '⏱️ Connection timed out. Please check your internet.';
        case DioExceptionType.receiveTimeout:
          return '⏱️ Server took too long. Please try again.';
        case DioExceptionType.connectionError:
          return '📡 No internet connection. Please check your network.';
        default:
          break;
      }

      final response = error.response;
      if (response != null) {
        // FIX 14 — parse FastAPI validation error list format
        final data = response.data;
        if (data is Map) {
          final detail = data['detail'];
          if (detail is List && detail.isNotEmpty) {
            final first = detail.first;
            if (first is Map) {
              return first['msg']?.toString() ??
                  'Validation error';
            }
          }
          final msg = data['detail'] ??
              data['error'] ??
              data['message'];
          if (msg != null && msg.toString().isNotEmpty) {
            return msg.toString();
          }
        }

        return switch (response.statusCode) {
          400  => '❌ Invalid request. Please check your inputs.',
          401  => '🔒 Session expired. Please log in again.',
          403  => '🚫 You don\'t have permission to do this.',
          404  => '🔍 Not found. It may have been deleted.',
          409  => '⚠️ This already exists.',
          422  => '❌ Invalid data. Please check your inputs.',
          429  => '⏳ Too many requests. Please wait a moment.',
          500  => '🔧 Server error. Please try again.',
          502  => '🔧 Server is starting up. Please retry in 30s.',
          503  => '🔧 Service unavailable. Please try again soon.',
          _    => '❌ Something went wrong (${response.statusCode}).',
        };
      }
      return '📡 Network error. Please check your connection.';
    }

    final msg = error?.toString() ?? '';
    if (msg.contains('SocketException') ||
        msg.contains('Connection refused')) {
      return '📡 No internet connection.';
    }

    return '❌ Unexpected error. Please try again.';
  }

  bool isNetworkError(dynamic error) {
    if (error is DioException) {
      return error.type == DioExceptionType.connectionError ||
          error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout ||
          error.type == DioExceptionType.sendTimeout;
    }
    return error is SocketException;
  }

  bool isAuthError(dynamic error) {
    if (error is DioException) {
      return error.response?.statusCode == 401 ||
          error.response?.statusCode == 403;
    }
    return false;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  /// FIX 15 — safely cast any response.data to Map<String, dynamic>
  Map<String, dynamic> _asMap(dynamic data) {
    if (data is Map<String, dynamic>) return data;
    if (data is Map) {
      return Map<String, dynamic>.from(data);
    }
    return {};
  }

  void _log(String msg) =>
      developer.log(msg, name: 'ApiService');
}
