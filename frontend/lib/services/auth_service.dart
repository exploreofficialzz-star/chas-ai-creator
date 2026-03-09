/*
 * chAs AI Creator - Auth Service
 * Created by: chAs
 * Custom JWT Authentication (Nigeria Friendly)
 * Replaces Firebase Auth which doesn't work in Nigeria
 */

import 'dart:convert';
import 'dart:developer' as developer;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:google_sign_in/google_sign_in.dart';

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

  // Google Sign-In instance
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: ['email', 'profile'],
  );

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
      developer.log('🔵 REGISTER: Starting registration', name: 'AuthService');
      developer.log('🔵 REGISTER: URL: $baseUrl/auth/register', name: 'AuthService');
      developer.log('🔵 REGISTER: Email: $email', name: 'AuthService');
      developer.log('🔵 REGISTER: Password length: ${password.length}', name: 'AuthService');
      
      // Validate password length before sending
      if (password.length < 8) {
        throw Exception('Password must be at least 8 characters');
      }
      
      final requestBody = {
        'email': email,
        'password': password,
        'display_name': displayName,
      };
      
      developer.log('🔵 REGISTER: Request body: ${jsonEncode(requestBody)}', name: 'AuthService');

      final response = await http.post(
        Uri.parse('$baseUrl/auth/register'),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: jsonEncode(requestBody),
      ).timeout(const Duration(seconds: 30));

      developer.log('🟢 REGISTER: Response status: ${response.statusCode}', name: 'AuthService');
      developer.log('🟢 REGISTER: Response body: ${response.body}', name: 'AuthService');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Validate response has required fields
        if (data['access_token'] == null || data['refresh_token'] == null) {
          throw Exception('Invalid server response: missing tokens');
        }
        
        if (data['user'] == null) {
          throw Exception('Invalid server response: missing user data');
        }
        
        // Save tokens
        await _saveTokens(
          data['access_token'],
          data['refresh_token'],
        );
        
        // Create user object
        final user = User(
          id: data['user']['id'] ?? '',
          email: data['user']['email'] ?? email,
          displayName: data['user']['display_name'],
          subscriptionTier: data['user']['subscription_tier'] ?? 'free',
          credits: data['user']['credits'] ?? 0,
        );
        
        await _saveUser(user);
        
        developer.log('✅ REGISTER: Success! User: ${user.email}', name: 'AuthService');
        
        return user;
      } else if (response.statusCode == 400) {
        // Bad request - validation error
        final error = jsonDecode(response.body);
        final errorMsg = error['error'] ?? error['detail'] ?? error['message'] ?? 'Invalid request';
        developer.log('🔴 REGISTER: 400 Error: $errorMsg', name: 'AuthService');
        throw Exception(errorMsg);
      } else if (response.statusCode == 409) {
        // Conflict - email already exists
        developer.log('🔴 REGISTER: 409 - Email already exists', name: 'AuthService');
        throw Exception('Email already registered. Please sign in instead.');
      } else if (response.statusCode == 422) {
        // Validation error
        final error = jsonDecode(response.body);
        final errorMsg = error['error'] ?? error['detail'] ?? 'Validation failed';
        developer.log('🔴 REGISTER: 422 Error: $errorMsg', name: 'AuthService');
        throw Exception(errorMsg);
      } else if (response.statusCode >= 500) {
        // Server error
        developer.log('🔴 REGISTER: Server error ${response.statusCode}', name: 'AuthService');
        throw Exception('Server error. Please try again later.');
      } else {
        // Other errors
        final error = jsonDecode(response.body);
        final errorMsg = error['error'] ?? error['detail'] ?? 'Registration failed (Code: ${response.statusCode})';
        developer.log('🔴 REGISTER: Error ${response.statusCode}: $errorMsg', name: 'AuthService');
        throw Exception(errorMsg);
      }
    } on FormatException catch (e) {
      developer.log('🔴 REGISTER: JSON parsing error: $e', name: 'AuthService');
      throw Exception('Invalid server response. Please try again.');
    } on http.ClientException catch (e) {
      developer.log('🔴 REGISTER: Network error: $e', name: 'AuthService');
      throw Exception('Network error. Check your internet connection.');
    } catch (e) {
      developer.log('🔴 REGISTER: Unexpected error: $e', name: 'AuthService');
      throw Exception('Registration failed: $e');
    }
  }

  /// Sign in with email and password
  Future<User> signInWithEmail(String email, String password) async {
    try {
      developer.log('🔵 LOGIN: Starting login', name: 'AuthService');
      developer.log('🔵 LOGIN: URL: $baseUrl/auth/login', name: 'AuthService');

      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      ).timeout(const Duration(seconds: 30));

      developer.log('🟢 LOGIN: Response status: ${response.statusCode}', name: 'AuthService');

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
        
        developer.log('✅ LOGIN: Success!', name: 'AuthService');
        
        return user;
      } else if (response.statusCode == 401) {
        throw Exception('Invalid email or password');
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? error['detail'] ?? 'Login failed');
      }
    } catch (e) {
      developer.log('🔴 LOGIN: Error: $e', name: 'AuthService');
      throw Exception('Login failed: $e');
    }
  }

  /// Sign in with Google - WORKING IMPLEMENTATION
  Future<User> signInWithGoogle() async {
    try {
      developer.log('🔵 GOOGLE: Starting Google Sign-In', name: 'AuthService');
      
      // Trigger Google Sign-In flow
      final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
      
      if (googleUser == null) {
        developer.log('🟡 GOOGLE: User cancelled', name: 'AuthService');
        throw Exception('Google Sign-In cancelled by user');
      }

      developer.log('🔵 GOOGLE: Got user: ${googleUser.email}', name: 'AuthService');

      // Get authentication details
      final GoogleSignInAuthentication googleAuth = await googleUser.authentication;
      
      // Get ID token (this is what we send to backend)
      final String? idToken = googleAuth.idToken;
      final String? accessToken = googleAuth.accessToken;
      
      if (idToken == null) {
        developer.log('🔴 GOOGLE: No ID token received', name: 'AuthService');
        throw Exception('Failed to get Google ID token');
      }

      developer.log('🔵 GOOGLE: Sending to backend...', name: 'AuthService');

      // Send to your backend for verification and JWT token generation
      final response = await http.post(
        Uri.parse('$baseUrl/auth/social-login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'provider': 'google',
          'token': idToken,
          'email': googleUser.email,
          'display_name': googleUser.displayName,
        }),
      ).timeout(const Duration(seconds: 30));

      developer.log('🟢 GOOGLE: Response status: ${response.statusCode}', name: 'AuthService');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Save tokens from your backend
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
        
        developer.log('✅ GOOGLE: Success!', name: 'AuthService');
        
        return user;
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? error['detail'] ?? 'Google login failed');
      }
    } catch (e) {
      developer.log('🔴 GOOGLE: Error: $e', name: 'AuthService');
      // Sign out from Google if backend auth fails
      await _googleSignIn.signOut();
      throw Exception('Google Sign-In failed: $e');
    }
  }

  /// Sign in with Apple - PLACEHOLDER (requires iOS setup)
  Future<User> signInWithApple() async {
    throw Exception('Apple Sign-In coming soon. Please use Google or Email login.');
  }

  /// Social login (generic - used by Google/Apple)
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
        throw Exception(error['error'] ?? error['detail'] ?? 'Social login failed');
      }
    } catch (e) {
      throw Exception('Social login failed: $e');
    }
  }

  /// Sign out
  Future<void> signOut() async {
    // Sign out from Google
    try {
      await _googleSignIn.signOut();
    } catch (e) {
      // Ignore errors
    }
    
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
        throw Exception(error['error'] ?? error['detail'] ?? 'Password reset failed');
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
        throw Exception(error['error'] ?? error['detail'] ?? 'Password change failed');
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
        throw Exception(error['error'] ?? error['detail'] ?? 'Profile update failed');
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
