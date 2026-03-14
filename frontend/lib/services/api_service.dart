/*
 * chAs AI Creator - API Service
 * FILE: lib/services/api_service.dart
 *
 * BUGS FIXED:
 *
 * 1. CRITICAL — createSchedule() signature mismatch.
 *    videos_screen.dart and dashboard_screen.dart call:
 *      _apiService.createSchedule({ 'name': ..., 'frequency': ..., ... })
 *    But the old signature was named parameters:
 *      createSchedule({String? name, String frequency = 'daily', ...})
 *    This causes a compile error. Fixed: accepts Map<String, dynamic>
 *    so all callers work without change.
 *
 * 2. CRITICAL — updateSchedule() signature mismatch.
 *    videos_screen.dart calls:
 *      _apiService.updateSchedule(scheduleId, {'is_active': val})
 *    But the old signature was:
 *      updateSchedule(String id, {String? name, String? frequency, ...})
 *    The positional Map argument was rejected. Fixed: accepts
 *    (String scheduleId, Map<String, dynamic> data) positionally.
 *
 * 3. CRITICAL — smartGeneratePlan() missing referenceImages param.
 *    smart_create_screen passes reference image URLs but the old
 *    signature only had uploadedImageCount (an int). The backend
 *    expects 'reference_images' as a List<String>. Fixed: added
 *    List<String>? referenceImages parameter.
 *
 * ROOT CAUSE OF LOGIN BUG (already fixed, preserved here):
 * The Dio 401 interceptor was calling _authService.signOut() which
 * wiped the token on Render cold-start 401s. Removed signOut() call —
 * callers handle errors silently, auth state is never affected.
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
      connectTimeout: const Duration(seconds: 60),
      receiveTimeout: const Duration(seconds: 180),
      sendTimeout: const Duration(seconds: 60),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

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
        _log('← ${response.statusCode} '
            '${response.requestOptions.path}');
        return handler.next(response);
      },

      onError: (error, handler) async {
        _log('✗ ${error.response?.statusCode} '
            '${error.requestOptions.path}: ${error.message}');

        // ── 401 handler ───────────────────────────────────────────
        if (error.response?.statusCode == 401) {
          final refreshToken =
              await _authService.getRefreshToken();

          if (refreshToken != null && refreshToken.isNotEmpty) {
            try {
              final newToken =
                  await _authService.refreshAccessToken();
              if (newToken != null) {
                error.requestOptions.headers['Authorization'] =
                    'Bearer $newToken';
                final retried =
                    await _dio.fetch(error.requestOptions);
                return handler.resolve(retried);
              }
            } catch (_) {
              // Refresh threw — fall through to handler.next
            }
          }

          // DO NOT call signOut() here — see file header.
          _log('⚠️ 401 on ${error.requestOptions.path} — '
              'passing to caller, NOT clearing token');
          return handler.next(error);
        }

        // ── 502 / 503 — Render cold start, retry once ─────────
        if ((error.response?.statusCode == 502 ||
                error.response?.statusCode == 503) &&
            error.requestOptions.extra['retried'] != true) {
          try {
            _log('⏳ Cold start (${error.response?.statusCode}) '
                '— retrying in 3s…');
            await Future.delayed(const Duration(seconds: 3));
            final opts = error.requestOptions
              ..extra['retried'] = true;
            final retried = await _dio.fetch(opts);
            return handler.resolve(retried);
          } catch (_) {
            // Retry also failed — fall through
          }
        }

        return handler.next(error);
      },
    ));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // USER
  // ─────────────────────────────────────────────────────────────────────────

  Future<User> getCurrentUser() async {
    final response = await _dio.get('/users/me');
    return User.fromJson(_asMap(response.data));
  }

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

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _dio.patch('/users/me/password', data: {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
  }

  Future<UserSettings?> getUserSettings() async {
    try {
      final response = await _dio.get('/users/settings');
      final data = _asMap(response.data);
      final settingsJson =
          data['settings'] as Map<String, dynamic>? ?? data;
      if (settingsJson.isEmpty) return null;
      return UserSettings.fromJson(settingsJson);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<UserSettings> updateUserSettings(
      UserSettings settings) async {
    final response = await _dio.put(
      '/users/settings',
      data: settings.toJson(),
    );
    final data = _asMap(response.data);
    final settingsJson =
        data['settings'] as Map<String, dynamic>? ?? data;
    return UserSettings.fromJson(settingsJson);
  }

  Future<Map<String, dynamic>> getUsageStats() async {
    try {
      final response = await _dio.get('/users/usage');
      final data = _asMap(response.data);
      return {
        'total_videos_generated':
            data['total_videos_generated'] ??
                data['total_videos'] ??
                data['totalVideos'] ??
                0,
        'remaining_daily_videos':
            data['remaining_daily_videos'] ??
                data['remaining'] ??
                data['videos_remaining'] ??
                0,
        'videos_today': data['videos_today'] ??
            data['today_count'] ??
            data['videosToday'] ??
            0,
        'videos_this_month': data['videos_this_month'] ??
            data['month_count'] ??
            data['videosThisMonth'] ??
            0,
        'credits': data['credits'] ?? 0,
        'daily_limit':
            data['daily_limit'] ?? data['limit'] ?? 2,
        ...data,
      };
    } catch (_) {
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
      options:
          Options(receiveTimeout: const Duration(seconds: 300)),
    );
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getVideos({
    String? status,
    int page = 1,
    int limit = 20,
  }) async {
    try {
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
          response =
              await _dio.get('/videos/list', queryParameters: {
            if (status != null) 'status': status,
            'page': page,
            'limit': limit,
          });
        } else {
          rethrow;
        }
      }

      final data = _asMap(response.data);
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
            data['pageCount'] ??
            1,
        ...data,
      };
    } catch (_) {
      return {'videos': [], 'total': 0, 'page': 1, 'pages': 1};
    }
  }

  Future<Map<String, dynamic>> getVideo(String videoId) async {
    final response = await _dio.get('/videos/$videoId');
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getVideoScenes(
      String videoId) async {
    final response = await _dio.get('/videos/$videoId/scenes');
    return _asMap(response.data);
  }

  Future<void> deleteVideo(String videoId) async {
    await _dio.delete('/videos/$videoId');
  }

  Future<Map<String, dynamic>> regenerateVideo(
      String videoId) async {
    final response =
        await _dio.post('/videos/$videoId/regenerate');
    return _asMap(response.data);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SCHEDULES
  // ─────────────────────────────────────────────────────────────────────────

  /// FIX 1 — was named params, callers pass a Map.
  /// videos_screen.dart calls: _apiService.createSchedule({ 'name': ... })
  /// dashboard_screen.dart calls: _apiService.createSchedule({ ... })
  Future<Map<String, dynamic>> createSchedule(
      Map<String, dynamic> data) async {
    final response =
        await _dio.post('/videos/schedules', data: data);
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getSchedules() async {
    final response = await _dio.get('/videos/schedules/list');
    return _asMap(response.data);
  }

  /// FIX 2 — was named params, callers pass a positional Map.
  /// videos_screen.dart calls:
  ///   _apiService.updateSchedule(scheduleId, {'is_active': val})
  Future<void> updateSchedule(
      String scheduleId, Map<String, dynamic> data) async {
    await _dio.put('/videos/schedules/$scheduleId', data: data);
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

  /// FIX 3 — added referenceImages param.
  /// smart_create_screen passes uploaded image URLs to the backend
  /// as 'reference_images'. Old signature only had uploadedImageCount
  /// which is an int — the backend never received the actual URLs.
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
    List<String>? referenceImages,           // FIX 3 — was missing
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
        // FIX 3 — send actual URLs, fall back to empty list
        'reference_images': referenceImages ?? [],
        'uploaded_image_count':
            referenceImages?.length ?? uploadedImageCount,
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
      'png' => MediaType('image', 'png'),
      'gif' => MediaType('image', 'gif'),
      'webp' => MediaType('image', 'webp'),
      'mp4' => MediaType('video', 'mp4'),
      'mov' => MediaType('video', 'quicktime'),
      _ => MediaType('image', 'jpeg'),
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
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
          return '⏱️ Server is warming up — please wait '
              'a moment and try again.';
        case DioExceptionType.receiveTimeout:
          return '⏱️ Server took too long. Please try again.';
        case DioExceptionType.connectionError:
          return '📡 No internet connection. '
              'Please check your network.';
        default:
          break;
      }

      final response = error.response;
      if (response != null) {
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
          400 => '❌ Invalid request. Please check your inputs.',
          401 => '🔒 Session expired. Please log in again.',
          403 =>
            '🚫 You don\'t have permission to do this.',
          404 =>
            '🔍 Not found. It may have been deleted.',
          409 => '⚠️ This already exists.',
          422 =>
            '❌ Invalid data. Please check your inputs.',
          429 =>
            '⏳ Too many requests. Please wait a moment.',
          500 => '🔧 Server error. Please try again.',
          502 =>
            '🔧 Server is starting up. Please retry in 30s.',
          503 =>
            '🔧 Service unavailable. Please try again soon.',
          _ =>
            '❌ Something went wrong (${response.statusCode}).',
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

  Map<String, dynamic> _asMap(dynamic data) {
    if (data is Map<String, dynamic>) return data;
    if (data is Map) return Map<String, dynamic>.from(data);
    return {};
  }

  void _log(String msg) =>
      developer.log(msg, name: 'ApiService');
}
