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

  /// Register with email and password
  Future<User> registerWithEmail(
    String email,
    String password, {
    String? displayName,
  }) async {
    try {
      developer.log('🔵 REGISTER: Starting...', name: 'AuthService');
      
      final uri = Uri.parse('$baseUrl/auth/register');
      developer.log('🔵 URL: $uri', name: 'AuthService');
      
      final requestBody = {
        'email': email.trim(),
        'password': password,
        'display_name': displayName ?? email.split('@')[0],
      };
      
      final jsonBody = jsonEncode(requestBody);
      developer.log('🔵 Body: $jsonBody', name: 'AuthService');

      // Make request with explicit headers
      final response = await http.post(
        uri,
        headers: {
          'Content-Type': 'application/json; charset=UTF-8',
          'Accept': 'application/json',
          'Origin': 'https://chas-ai-creator-2.onrender.com',
        },
        body: jsonBody,
      ).timeout(const Duration(seconds: 30));

      developer.log('🟢 Status: ${response.statusCode}', name: 'AuthService');
      developer.log('🟢 Body: ${response.body}', name: 'AuthService');
      developer.log('🟢 Headers: ${response.headers}', name: 'AuthService');

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
    } catch (e, stackTrace) {
      developer.log('🔴 ERROR: $e', name: 'AuthService');
      developer.log('🔴 STACK: $stackTrace', name: 'AuthService');
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

  /// Sign out
  Future<void> signOut() async {
    await _clearAuthData();
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
