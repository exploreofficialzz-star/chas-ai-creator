/*
 * chAs AI Creator - Auth Service
 * Enhanced & Debugged
 */

import 'dart:async';
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

  User?   _currentUser;
  String? _cachedAccessToken;
  bool    _isRefreshing = false;

  // ─────────────────────────────────────────────────────────────────────────
  // TOKEN MANAGEMENT
  // ─────────────────────────────────────────────────────────────────────────

  Future<String?> getAccessToken() async {
    if (_cachedAccessToken != null) return _cachedAccessToken;
    final prefs = await SharedPreferences.getInstance();
    _cachedAccessToken = prefs.getString(_accessTokenKey);
    return _cachedAccessToken;
  }

  Future<String?> getRefreshToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_refreshTokenKey);
  }

  Future<void> _saveTokens(
      String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_accessTokenKey, accessToken),
      if (refreshToken.isNotEmpty)
        prefs.setString(_refreshTokenKey, refreshToken),
    ]);
    _cachedAccessToken = accessToken;
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
    _currentUser        = null;
    _cachedAccessToken  = null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SESSION CHECKS
  // ─────────────────────────────────────────────────────────────────────────

  Future<bool> isSignedIn() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  Future<User?> getCurrentUser() async {
    if (_currentUser != null) return _currentUser;

    // Try local cache first
    final prefs = await SharedPreferences.getInstance();
    final userData = prefs.getString(_userKey);
    if (userData != null) {
      try {
        _currentUser =
            User.fromJson(jsonDecode(userData) as Map<String, dynamic>);
      } catch (_) {
        // Corrupt data — will refresh from API
      }
    }

    // Refresh from API if we have a token
    final token = await getAccessToken();
    if (token != null) {
      try {
        final freshUser = await _fetchUserFromApi(token);
        if (freshUser != null) {
          await _saveUser(freshUser);
          return freshUser;
        }
      } catch (_) {
        // Network unavailable — return cached user
      }
    }

    return _currentUser;
  }

  Future<User?> _fetchUserFromApi(String token) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/users/me'),
        headers: _headers(token: token),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final body = jsonDecode(response.body);
        // FIX 1 — backend sometimes wraps user in a 'data' or 'user' key
        final userJson = _extractUserJson(body);
        return User.fromJson(userJson);
      }

      if (response.statusCode == 401) {
        final newToken = await refreshAccessToken();
        if (newToken != null) {
          final retry = await http.get(
            Uri.parse('$baseUrl/users/me'),
            headers: _headers(token: newToken),
          ).timeout(const Duration(seconds: 15));
          if (retry.statusCode == 200) {
            final body = jsonDecode(retry.body);
            return User.fromJson(_extractUserJson(body));
          }
        }
        await _clearAuthData();
      }
    } on TimeoutException {
      _log('FETCH USER TIMEOUT');
    } on SocketException {
      _log('FETCH USER — no internet');
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
        'email':        email.trim().toLowerCase(),
        'password':     password,
        'display_name': displayName?.trim() ?? email.split('@')[0],
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

    // FIX 2 — some FastAPI backends expect form data not JSON for /auth/login
    // Try JSON first, fall back to form-encoded if we get 422
    final response = await _post(
      '/auth/login',
      {
        'email':    email.trim().toLowerCase(),
        'password': password,
      },
      requiresAuth: false,
    );

    // FIX 3 — 422 usually means backend wants form-encoded login
    if (response.statusCode == 422) {
      _log('LOGIN: JSON failed with 422, retrying as form data');
      final formResponse = await _postForm(
        '/auth/login',
        {
          'username': email.trim().toLowerCase(), // OAuth2 uses 'username'
          'password': password,
        },
      );
      return _handleAuthResponse(formResponse, 'Login failed');
    }

    return _handleAuthResponse(response, 'Login failed');
  }

  // FIX 4 — shared auth response handler with robust key detection
  Future<User> _handleAuthResponse(
      http.Response response, String errorPrefix) async {
    _log('AUTH RESPONSE: ${response.statusCode}');

    if (response.statusCode == 200 || response.statusCode == 201) {
      Map<String, dynamic> data;
      try {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      } catch (_) {
        throw Exception('$errorPrefix: Invalid server response');
      }

      // FIX 5 — handle all possible token key names
      final accessToken = _extractString(data, [
        'access_token', 'token', 'accessToken', 'jwt'
      ]);
      final refreshToken = _extractString(data, [
        'refresh_token', 'refreshToken', 'refresh'
      ]) ?? '';

      if (accessToken == null || accessToken.isEmpty) {
        _log('NO TOKEN IN RESPONSE: ${response.body}');
        throw Exception('$errorPrefix: Server did not return a token');
      }

      await _saveTokens(accessToken, refreshToken);

      // FIX 6 — extract user JSON safely without contaminating it
      // with token fields when user is at the root level
      final userJson = _extractUserJson(data);
      
      User user;
      try {
        user = User.fromJson(userJson);
      } catch (e) {
        _log('USER PARSE ERROR: $e — raw: $userJson');
        throw Exception('$errorPrefix: Could not parse user data');
      }

      await _saveUser(user);
      _log('SUCCESS: ${user.email} (${user.subscriptionTier})');
      return user;
    }

    // FIX 7 — log the actual response body for debugging
    _log('AUTH FAILED ${response.statusCode}: ${response.body}');
    throw Exception(_parseError(response, errorPrefix));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GOOGLE SIGN IN
  // ─────────────────────────────────────────────────────────────────────────

  Future<User> signInWithGoogle() async {
    throw Exception(
        'Google Sign-In is not available. Please use email and password.');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TOKEN REFRESH
  // ─────────────────────────────────────────────────────────────────────────

  Future<String?> refreshAccessToken() async {
    if (_isRefreshing) {
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
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final newToken = _extractString(data,
            ['access_token', 'token', 'accessToken']) ?? '';
        final newRefresh = _extractString(data,
            ['refresh_token', 'refreshToken']) ?? refreshToken;

        if (newToken.isNotEmpty) {
          await _saveTokens(newToken, newRefresh);
          _log('TOKEN REFRESHED');
          return newToken;
        }
      }

      _log('REFRESH FAILED (${response.statusCode}) — clearing session');
      await _clearAuthData();
      return null;
    } on TimeoutException {
      _log('REFRESH TIMEOUT');
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

    // Treat 404 as success — prevent email enumeration
    if (response.statusCode == 404) return;

    if (response.statusCode != 200 && response.statusCode != 202) {
      throw Exception(_parseError(response, 'Password reset failed'));
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
        if (bio != null)         'bio': bio.trim(),
        if (avatarUrl != null)   'avatar_url': avatarUrl,
      },
    );

    if (response.statusCode == 200) {
      final body = jsonDecode(response.body);
      final user = User.fromJson(_extractUserJson(body));
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
      final token = await getAccessToken();
      if (token != null) {
        await http.post(
          Uri.parse('$baseUrl/auth/logout'),
          headers: _headers(token: token),
        ).timeout(const Duration(seconds: 5));
      }
    } catch (_) {
      // Best-effort — always clear local data regardless
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
        'Accept':       'application/json',
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

      // FIX 8 — increased timeout to handle Render cold starts (can take 50s+)
      final response = await http.post(
        Uri.parse('$baseUrl$path'),
        headers: _headers(token: token),
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 60));

      if (response.statusCode == 401 && requiresAuth) {
        final newToken = await refreshAccessToken();
        if (newToken != null) {
          return http.post(
            Uri.parse('$baseUrl$path'),
            headers: _headers(token: newToken),
            body: jsonEncode(body),
          ).timeout(const Duration(seconds: 60));
        }
      }

      return response;
    } on TimeoutException {
      // FIX 9 — was missing TimeoutException handler — caused unhandled
      // exception that crashed the login silently instead of showing error
      throw Exception(
          'Connection timed out. The server may be starting up — please try again.');
    } on SocketException {
      throw Exception(
          'No internet connection. Please check your network.');
    } on HttpException {
      throw Exception('Network error. Please try again.');
    } on FormatException {
      throw Exception('Server returned invalid data.');
    }
  }

  // FIX 3 — form-encoded POST for OAuth2-style login endpoints
  Future<http.Response> _postForm(
    String path,
    Map<String, String> body,
  ) async {
    try {
      return await http.post(
        Uri.parse('$baseUrl$path'),
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept':       'application/json',
        },
        body: body,
      ).timeout(const Duration(seconds: 60));
    } on TimeoutException {
      throw Exception(
          'Connection timed out. Please try again.');
    } on SocketException {
      throw Exception('No internet connection.');
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
    } on TimeoutException {
      throw Exception('Request timed out. Please try again.');
    } on SocketException {
      throw Exception('No internet connection.');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PRIVATE HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  // FIX 5 — safely extract a string value trying multiple key names
  String? _extractString(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final val = data[key];
      if (val != null && val.toString().isNotEmpty) {
        return val.toString();
      }
    }
    return null;
  }

  // FIX 6 — extract user JSON from response without token field contamination
  Map<String, dynamic> _extractUserJson(dynamic body) {
    if (body is! Map<String, dynamic>) return {};

    // If backend wraps user in a key — use that directly
    if (body['user'] is Map<String, dynamic>) {
      return body['user'] as Map<String, dynamic>;
    }
    if (body['data'] is Map<String, dynamic>) {
      final data = body['data'] as Map<String, dynamic>;
      // Make sure data isn't just another wrapper
      if (data.containsKey('email') || data.containsKey('id')) {
        return data;
      }
    }

    // User fields are at root — strip token fields to avoid parse errors
    final tokenKeys = {
      'access_token', 'token', 'accessToken', 'jwt',
      'refresh_token', 'refreshToken', 'refresh',
      'token_type', 'expires_in', 'expires_at',
    };
    return Map<String, dynamic>.fromEntries(
      body.entries.where((e) => !tokenKeys.contains(e.key)),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR PARSING
  // ─────────────────────────────────────────────────────────────────────────

  String _parseError(http.Response response, String prefix) {
    try {
      final body = jsonDecode(response.body);
      if (body is Map) {
        // FastAPI validation error list
        if (body['detail'] is List) {
          final details = body['detail'] as List;
          return details.isNotEmpty
              ? (details.first['msg'] ?? prefix).toString()
              : prefix;
        }
        final msg = body['detail'] ??
            body['error'] ??
            body['message'] ??
            body['msg'];
        if (msg != null && msg.toString().isNotEmpty) {
          return msg.toString();
        }
      }
    } catch (_) {}
    return '$prefix (${response.statusCode})';
  }

  void _log(String msg) =>
      developer.log('🔐 AUTH: $msg', name: 'AuthService');
}
