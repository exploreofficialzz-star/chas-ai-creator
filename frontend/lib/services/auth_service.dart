/*
 * chAs AI Creator - Auth Service
 * Created by: chAs
 * Custom JWT Authentication (Nigeria Friendly)
 */

import 'dart:convert';
import 'dart:developer' as developer;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/user.dart';

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  // API Base URL - Production (Render)
  static const String baseUrl = 'https://chas-ai-creator-2.onrender.com/api/v1';
  
  // Token storage keys
  static const String _accessTokenKey = 'access_token';
  static const String _refreshTokenKey = 'refresh_token';
  static const String _userKey = 'user_data';

  User? _currentUser;

  /// Get stored access token
  Future<String?> getAccessToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_accessTokenKey);
  }

  /// Get stored refresh token
  Future<String?> getRefreshToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_refreshTokenKey);
  }

  /// Save tokens to storage
  Future<void> _saveTokens(String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessTokenKey, accessToken);
    await prefs.setString(_refreshTokenKey, refreshToken);
  }

  /// Save user to storage
  Future<void> _saveUser(User user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_userKey, jsonEncode(user.toJson()));
    _currentUser = user;
  }

  /// Clear all auth data
  Future<void> _clearAuthData() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessTokenKey);
    await prefs.remove(_refreshTokenKey);
    await prefs.remove(_userKey);
    _currentUser = null;
  }

  /// Check if user is signed in
  Future<bool> isSignedIn() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  /// Get current user
  Future<User?> getCurrentUser() async {
    if (_currentUser != null) return _currentUser;
    
    final prefs = await SharedPreferences.getInstance();
    final userData = prefs.getString(_userKey);
    
    if (userData != null) {
      _currentUser = User.fromJson(jsonDecode(userData));
      return _currentUser;
    }
    
    return null;
  }

  /// Register with email and password
  Future<User> registerWithEmail(
    String email,
    String password, {
    String? displayName,
  }) async {
    try {
      developer.log('🔵 REGISTER: Starting...', name: 'AuthService');
      
      final uri = Uri.parse('$baseUrl/auth/register');
      
      final requestBody = {
        'email': email.trim(),
        'password': password,
        'display_name': displayName ?? email.split('@')[0],
      };
      
      final jsonBody = jsonEncode(requestBody);
      developer.log('🔵 Body: $jsonBody', name: 'AuthService');

      final response = await http.post(
        uri,
        headers: {
          'Content-Type': 'application/json; charset=UTF-8',
          'Accept': 'application/json',
        },
        body: jsonBody,
      ).timeout(const Duration(seconds: 30));

      developer.log('🟢 Status: ${response.statusCode}', name: 'AuthService');
      developer.log('🟢 Body: ${response.body}', name: 'AuthService');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        await _saveTokens(
          data['access_token'],
          data['refresh_token'],
        );
        
        final user = User(
          id: data['user']['id'],
          email: data['user']['email'],
          displayName: data['user']['display_name'],
          subscriptionTier: data['user']['subscription_tier'],
          credits: data['user']['credits'],
        );
        
        await _saveUser(user);
        
        return user;
      } else {
        String errorMsg;
        try {
          final error = jsonDecode(response.body);
          errorMsg = error['error'] ?? error['detail'] ?? error['message'] ?? 'Unknown error';
        } catch (e) {
          errorMsg = 'Server error (Code: ${response.statusCode})';
        }
        throw Exception(errorMsg);
      }
    } catch (e) {
      developer.log('🔴 ERROR: $e', name: 'AuthService');
      throw Exception('Registration failed: $e');
    }
  }

  /// Sign in with email and password
  Future<User> signInWithEmail(String email, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {
          'Content-Type': 'application/json; charset=UTF-8',
          'Accept': 'application/json',
        },
        body: jsonEncode({
          'email': email.trim(),
          'password': password,
        }),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        await _saveTokens(
          data['access_token'],
          data['refresh_token'],
        );
        
        final user = User(
          id: data['user']['id'],
          email: data['user']['email'],
          displayName: data['user']['display_name'],
          subscriptionTier: data['user']['subscription_tier'],
          credits: data['user']['credits'],
        );
        
        await _saveUser(user);
        
        return user;
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? error['detail'] ?? 'Login failed');
      }
    } catch (e) {
      throw Exception('Login failed: $e');
    }
  }

  /// Sign in with Google - PLACEHOLDER
  Future<User> signInWithGoogle() async {
    throw Exception('Google Sign-In not configured. Please use email/password.');
  }

  /// Sign in with Apple - PLACEHOLDER
  Future<User> signInWithApple() async {
    throw Exception('Apple Sign-In not configured. Please use email/password.');
  }

  /// Refresh access token
  Future<String?> refreshAccessToken() async {
    try {
      final refreshToken = await getRefreshToken();
      
      if (refreshToken == null) return null;

      final response = await http.post(
        Uri.parse('$baseUrl/auth/refresh'),
        headers: {
          'Content-Type': 'application/json; charset=UTF-8',
          'Accept': 'application/json',
        },
        body: jsonEncode({'refresh_token': refreshToken}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final newAccessToken = data['access_token'];
        
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_accessTokenKey, newAccessToken);
        
        return newAccessToken;
      }
    } catch (e) {
      await _clearAuthData();
    }
    
    return null;
  }

  /// Sign out
  Future<void> signOut() async {
    await _clearAuthData();
  }

  /// Reset password
  Future<void> resetPassword(String email) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/forgot-password'),
        headers: {
          'Content-Type': 'application/json; charset=UTF-8',
          'Accept': 'application/json',
        },
        body: jsonEncode({'email': email.trim()}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode != 200) {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? error['detail'] ?? 'Password reset failed');
      }
    } catch (e) {
      throw Exception('Password reset failed: $e');
    }
  }

  /// Get auth headers for API requests
  Future<Map<String, String>> getAuthHeaders() async {
    final token = await getAccessToken();
    
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }
}
