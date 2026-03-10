/*
 * chAs AI Creator - Auth Service
 * Enhanced & Debugged
 */

import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/user.dart';

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  static const String baseUrl =
      'https://chas-ai-creator-2.onrender.com/api/v1';

  static const String _accessTokenKey  = 'access_token';
  static const String _refreshTokenKey = 'refresh_token';
  static const String _userKey         = 'user_data';

  // FIX 1 — in-memory cache so we don't hit SharedPreferences every call
  User? _currentUser;
  String? _cachedAccessToken;
  bool _isRefreshing = false;

  // ─────────────────────────────────────────────────────────────────────────
  // TOKEN MANAGEMENT
  // ─────────────────────────────────────────────────────────────────────────

  Future<String?> getAccessToken() async {
    // FIX 2 — return cached token first to avoid slow SharedPreferences reads
    if (_cachedAccessToken != null) return _cachedAccessToken;
    final prefs = await SharedPreferences.getInstance();
    _cachedAccessToken = prefs.getString(_accessTokenKey);
    return _cachedAccessToken;
  }

  Future<String?> getRefreshToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_refreshTokenKey);
  }

  Future<void> _saveTokens(String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_accessTokenKey, accessToken),
      prefs.setString(_refreshTokenKey, refreshToken),
    ]);
    _cachedAccessToken = accessToken; // FIX 2 - keep cache in sync
  }

  Future<void> _saveUser(User user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_userKey, jsonEncode(user.toJson()));
    _currentUser = user;
  }

  Future<void> _clearAuthData() async {
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.remove(_accessTokenKey),
      prefs.remove(_refreshTokenKey),
      prefs.remove(_userKey),
    ]);
    _currentUser = null;
    _cachedAccessToken = null; // FIX 2 - clear cache too
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SESSION CHECKS
  // ─────────────────────────────────────────────────────────────────────────

  Future<bool> isSignedIn() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  /// FIX 3 — try local cache first, then SharedPrefs, then hit the API
  /// so user data is always fresh after app restart
  Future<User?> getCurrentUser() async {
    if (_currentUser != null) return _currentUser;

    final prefs = await SharedPreferences.getInstance();
    final userData = prefs.getString(_userKey);

    if (userData != null) {
      try {
        _currentUser = User.fromJson(jsonDecode(userData));
      } catch (_) {
        // corrupt local data — fetch fresh from API below
      }
    }

    // Always refresh from API in background if we have a token
    final token = await getAccessToken();
    if (token != null) {
      try {
        final freshUser = await _fetchUserFromApi(token);
        if (freshUser != null) {
          await _saveUser(freshUser);
          return freshUser;
        }
      } catch (_) {
        // network unavailable — return cached user
      }
    }

    return _currentUser;
  }

  Future<User?> _fetchUserFromApi(String token) async {
    final response = await http.get(
      Uri.parse('$baseUrl/users/me'),
      headers: _headers(token: token),
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return User.fromJson(jsonDecode(response.body));
    }
    if (response.statusCode == 401) {
      // Token expired — try refresh
      final newToken = await refreshAccessToken();
      if (newToken != null) {
        final retry = await http.get(
          Uri.parse('$baseUrl/users/me'),
          headers: _headers(token: newToken),
        ).timeout(const Duration(seconds: 15));
        if (retry.statusCode == 200) {
          return User.fromJson(jsonDecode(retry.body));
        }
      }
      await _clearAuthData();
    }
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // REGISTER
  // ─────────────────────────────────────────────────────────────────────────

  Future<User> registerWithEmail(
    String email,
    String password, {
    String? displayName,
  }) async {
    _log('REGISTER: $email');

    final response = await _post(
      '/auth/register',
      {
        'email': email.trim().toLowerCase(),
        'password': password,
        'display_name': displayName?.trim() ??
            email.split('@')[0],
      },
      requiresAuth: false,
    );

    return _handleAuthResponse(response, 'Registration failed');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOGIN
  // ─────────────────────────────────────────────────────────────────────────

  Future<User> signInWithEmail(String email, String password) async {
    _log('LOGIN: $email');

    final response = await _post(
      '/auth/login',
      {
        'email': email.trim().toLowerCase(),
        'password': password,
      },
      requiresAuth: false,
    );

    return _handleAuthResponse(response, 'Login failed');
  }

  /// FIX 4 — shared handler for register + login responses
  Future<User> _handleAuthResponse(
      http.Response response, String errorPrefix) async {
    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;

      // FIX 5 — handle both 'access_token' and 'token' keys from backend
      final accessToken = data['access_token'] ??
          data['token'] ??
          data['accessToken'] ?? '';
      final refreshToken = data['refresh_token'] ??
          data['refreshToken'] ?? '';

      if (accessToken.isEmpty) {
        throw Exception('$errorPrefix: No token in response');
      }

      await _saveTokens(accessToken, refreshToken);

      // FIX 6 — backend might return user inside 'user' key or at root
      final userJson = (data['user'] as Map<String, dynamic>?) ?? data;
      final user = User.fromJson(userJson);
      await _saveUser(user);

      _log('SUCCESS: ${user.email} (${user.subscriptionTier})');
      return user;
    }

    throw Exception(_parseError(response, errorPrefix));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GOOGLE SIGN IN
  // ─────────────────────────────────────────────────────────────────────────

  Future<User> signInWithGoogle() async {
    // App uses custom JWT — Google OAuth not configured
    throw Exception(
        'Google Sign-In is not available. Please use email and password.');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TOKEN REFRESH
  // ─────────────────────────────────────────────────────────────────────────

  /// FIX 7 — guard against multiple simultaneous refresh calls
  Future<String?> refreshAccessToken() async {
    if (_isRefreshing) {
      // Wait for ongoing refresh to complete
      await Future.delayed(const Duration(milliseconds: 500));
      return _cachedAccessToken;
    }

    _isRefreshing = true;

    try {
      final refreshToken = await getRefreshToken();
      if (refreshToken == null || refreshToken.isEmpty) {
        await _clearAuthData();
        return null;
      }

      final response = await http.post(
        Uri.parse('$baseUrl/auth/refresh'),
        headers: _headers(),
        body: jsonEncode({'refresh_token': refreshToken}),
      ).timeout(const Duration(seconds: 20));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final newToken = data['access_token'] ?? data['token'] ?? '';
        final newRefresh = data['refresh_token'] ?? refreshToken;

        if (newToken.isNotEmpty) {
          await _saveTokens(newToken, newRefresh);
          _log('TOKEN REFRESHED');
          return newToken;
        }
      }

      // FIX 8 — refresh failed → clear data → force re-login
      _log('REFRESH FAILED (${response.statusCode}) → clearing session');
      await _clearAuthData();
      return null;
    } catch (e) {
      _log('REFRESH ERROR: $e');
      await _clearAuthData();
      return null;
    } finally {
      _isRefreshing = false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RESET PASSWORD
  // ─────────────────────────────────────────────────────────────────────────

  Future<void> resetPassword(String email) async {
    _log('RESET PASSWORD: $email');

    final response = await _post(
      '/auth/forgot-password',
      {'email': email.trim().toLowerCase()},
      requiresAuth: false,
    );

    // FIX 9 — treat 404 as success to prevent email enumeration
    if (response.statusCode == 404) return;

    if (response.statusCode != 200 && response.statusCode != 202) {
      throw Exception(
          _parseError(response, 'Password reset failed'));
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // UPDATE PROFILE
  // ─────────────────────────────────────────────────────────────────────────

  Future<User> updateProfile({
    String? displayName,
    String? bio,
    String? avatarUrl,
  }) async {
    final response = await _patch(
      '/users/me',
      {
        if (displayName != null) 'display_name': displayName.trim(),
        if (bio != null) 'bio': bio.trim(),
        if (avatarUrl != null) 'avatar_url': avatarUrl,
      },
    );

    if (response.statusCode == 200) {
      final user = User.fromJson(jsonDecode(response.body));
      await _saveUser(user);
      return user;
    }

    throw Exception(_parseError(response, 'Profile update failed'));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SIGN OUT
  // ─────────────────────────────────────────────────────────────────────────

  Future<void> signOut() async {
    try {
      // Best-effort server-side logout — don't block on failure
      final token = await getAccessToken();
      if (token != null) {
        await http.post(
          Uri.parse('$baseUrl/auth/logout'),
          headers: _headers(token: token),
        ).timeout(const Duration(seconds: 5));
      }
    } catch (_) {
      // Ignore — always clear local data
    } finally {
      await _clearAuthData();
      _log('SIGNED OUT');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // AUTH HEADERS
  // ─────────────────────────────────────────────────────────────────────────

  Future<Map<String, String>> getAuthHeaders() async {
    final token = await getAccessToken();
    return _headers(token: token);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PRIVATE HTTP HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  Map<String, String> _headers({String? token}) => {
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept': 'application/json',
        if (token != null && token.isNotEmpty)
          'Authorization': 'Bearer $token',
      };

  Future<http.Response> _post(
    String path,
    Map<String, dynamic> body, {
    bool requiresAuth = true,
  }) async {
    try {
      String? token;
      if (requiresAuth) token = await getAccessToken();

      final response = await http.post(
        Uri.parse('$baseUrl$path'),
        headers: _headers(token: token),
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 30));

      // FIX 10 — auto-retry with refreshed token on 401
      if (response.statusCode == 401 && requiresAuth) {
        final newToken = await refreshAccessToken();
        if (newToken != null) {
          return http.post(
            Uri.parse('$baseUrl$path'),
            headers: _headers(token: newToken),
            body: jsonEncode(body),
          ).timeout(const Duration(seconds: 30));
        }
      }

      return response;
    } on SocketException {
      throw Exception(
          'No internet connection. Please check your network.');
    } on HttpException {
      throw Exception('Network error. Please try again.');
    } on FormatException {
      throw Exception('Server returned invalid data.');
    }
  }

  Future<http.Response> _patch(
    String path,
    Map<String, dynamic> body,
  ) async {
    try {
      var token = await getAccessToken();

      final response = await http.patch(
        Uri.parse('$baseUrl$path'),
        headers: _headers(token: token),
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 401) {
        token = await refreshAccessToken();
        if (token != null) {
          return http.patch(
            Uri.parse('$baseUrl$path'),
            headers: _headers(token: token),
            body: jsonEncode(body),
          ).timeout(const Duration(seconds: 30));
        }
      }

      return response;
    } on SocketException {
      throw Exception('No internet connection.');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR PARSING
  // ─────────────────────────────────────────────────────────────────────────

  String _parseError(http.Response response, String prefix) {
    try {
      final body = jsonDecode(response.body);
      // FIX 11 — handle FastAPI validation error format
      if (body['detail'] is List) {
        final details = body['detail'] as List;
        return details.isNotEmpty
            ? details.first['msg'] ?? prefix
            : prefix;
      }
      return body['error'] ??
          body['detail'] ??
          body['message'] ??
          '$prefix (${response.statusCode})';
    } catch (_) {
      return '$prefix (${response.statusCode})';
    }
  }

  void _log(String msg) =>
      developer.log('🔐 AUTH: $msg', name: 'AuthService');
}
