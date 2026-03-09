/*
 * chAs AI Creator - Auth Service
 * Created by: chAs
 * Custom JWT Authentication (Nigeria Friendly)
 * Replaces Firebase Auth which doesn't work in Nigeria
 */

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/user.dart';

/// Auth Service for managing custom JWT authentication
/// Created by: chAs
/// Uses custom JWT instead of Firebase (works in Nigeria)
class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  // API Base URL - Production (Render)
  // Your deployed backend URL
  static const String baseUrl = 'https://chas-ai-creator-2.onrender.com/api/v1';
  // For local development: 'http://localhost:8000/api/v1'
  
  // Token storage keys
  static const String _accessTokenKey = 'access_token';
  static const String _refreshTokenKey = 'refresh_token';
  static const String _userKey = 'user_data';

  // Current user
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
      final response = await http.post(
        Uri.parse('$baseUrl/auth/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
          'display_name': displayName,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Save tokens
        await _saveTokens(
          data['access_token'],
          data['refresh_token'],
        );
        
        // Create user object
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
        throw Exception(error['detail'] ?? 'Registration failed');
      }
    } catch (e) {
      throw Exception('Registration failed: $e');
    }
  }

  /// Sign in with email and password
  Future<User> signInWithEmail(String email, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Save tokens
        await _saveTokens(
          data['access_token'],
          data['refresh_token'],
        );
        
        // Create user object
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
        throw Exception(error['detail'] ?? 'Login failed');
      }
    } catch (e) {
      throw Exception('Login failed: $e');
    }
  }

  /// Social login (Google/Apple) - Simplified for Nigeria
  /// In production, implement proper OAuth flow
  Future<User> socialLogin({
    required String provider,
    required String token,
    String? email,
    String? displayName,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/social-login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'provider': provider,
          'token': token,
          'email': email,
          'display_name': displayName,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Save tokens
        await _saveTokens(
          data['access_token'],
          data['refresh_token'],
        );
        
        // Create user object
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
        throw Exception(error['detail'] ?? 'Social login failed');
      }
    } catch (e) {
      throw Exception('Social login failed: $e');
    }
  }

  /// Sign in with Google (simplified)
  Future<User> signInWithGoogle() async {
    // For Nigeria version, you can use google_sign_in package
    // and send the ID token to your backend
    // For now, this is a placeholder
    throw Exception('Google Sign-In not implemented. Use email/password login.');
  }

  /// Sign in with Apple (simplified)
  Future<User> signInWithApple() async {
    // For iOS version, implement Apple Sign-In
    // and send the identity token to your backend
    throw Exception('Apple Sign-In not implemented. Use email/password login.');
  }

  /// Sign out
  Future<void> signOut() async {
    await _clearAuthData();
  }

  /// Reset password - Request reset email
  Future<void> resetPassword(String email) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/forgot-password'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email}),
      );

      if (response.statusCode != 200) {
        final error = jsonDecode(response.body);
        throw Exception(error['detail'] ?? 'Password reset failed');
      }
    } catch (e) {
      throw Exception('Password reset failed: $e');
    }
  }

  /// Change password
  Future<void> changePassword(String currentPassword, String newPassword) async {
    try {
      final token = await getAccessToken();
      
      final response = await http.post(
        Uri.parse('$baseUrl/auth/change-password'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'current_password': currentPassword,
          'new_password': newPassword,
        }),
      );

      if (response.statusCode != 200) {
        final error = jsonDecode(response.body);
        throw Exception(error['detail'] ?? 'Password change failed');
      }
    } catch (e) {
      throw Exception('Password change failed: $e');
    }
  }

  /// Update profile
  Future<User> updateProfile({String? displayName, String? photoURL}) async {
    try {
      final token = await getAccessToken();
      
      final response = await http.put(
        Uri.parse('$baseUrl/users/profile'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          if (displayName != null) 'display_name': displayName,
          if (photoURL != null) 'avatar_url': photoURL,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Update current user
        final user = User.fromJson(data);
        await _saveUser(user);
        
        return user;
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['detail'] ?? 'Profile update failed');
      }
    } catch (e) {
      throw Exception('Profile update failed: $e');
    }
  }

  /// Refresh access token
  Future<String?> refreshAccessToken() async {
    try {
      final refreshToken = await getRefreshToken();
      
      if (refreshToken == null) return null;

      final response = await http.post(
        Uri.parse('$baseUrl/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': refreshToken}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final newAccessToken = data['access_token'];
        
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_accessTokenKey, newAccessToken);
        
        return newAccessToken;
      }
    } catch (e) {
      // Token refresh failed, user needs to login again
      await _clearAuthData();
    }
    
    return null;
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

