import 'package:firebase_auth/firebase_auth.dart' as firebase_auth;
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import '../models/user.dart';
import 'api_service.dart';

class AuthService {
  final firebase_auth.FirebaseAuth _firebaseAuth = firebase_auth.FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn();
  final ApiService _apiService = ApiService();

  // Current user stream
  Stream<User?> get userStream {
    return _firebaseAuth.authStateChanges().asyncMap((firebaseUser) async {
      if (firebaseUser == null) return null;
      return _getUserFromFirebase(firebaseUser);
    });
  }

  // Check if user is signed in
  Future<bool> isSignedIn() async {
    return _firebaseAuth.currentUser != null;
  }

  // Get current user
  Future<User?> getCurrentUser() async {
    final firebaseUser = _firebaseAuth.currentUser;
    if (firebaseUser == null) return null;
    return _getUserFromFirebase(firebaseUser);
  }

  // Sign in with email and password
  Future<User> signInWithEmail(String email, String password) async {
    try {
      final credential = await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      
      final firebaseUser = credential.user;
      if (firebaseUser == null) {
        throw Exception('Sign in failed');
      }
      
      return _getUserFromFirebase(firebaseUser);
    } on firebase_auth.FirebaseAuthException catch (e) {
      throw _handleFirebaseAuthError(e);
    }
  }

  // Register with email and password
  Future<User> registerWithEmail(
    String email,
    String password, {
    String? displayName,
  }) async {
    try {
      final credential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      
      final firebaseUser = credential.user;
      if (firebaseUser == null) {
        throw Exception('Registration failed');
      }
      
      // Update display name
      if (displayName != null) {
        await firebaseUser.updateDisplayName(displayName);
      }
      
      return _getUserFromFirebase(firebaseUser);
    } on firebase_auth.FirebaseAuthException catch (e) {
      throw _handleFirebaseAuthError(e);
    }
  }

  // Sign in with Google
  Future<User> signInWithGoogle() async {
    try {
      final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
      
      if (googleUser == null) {
        throw Exception('Google sign in cancelled');
      }
      
      final GoogleSignInAuthentication googleAuth = await googleUser.authentication;
      
      final credential = firebase_auth.GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );
      
      final userCredential = await _firebaseAuth.signInWithCredential(credential);
      final firebaseUser = userCredential.user;
      
      if (firebaseUser == null) {
        throw Exception('Google sign in failed');
      }
      
      return _getUserFromFirebase(firebaseUser);
    } on firebase_auth.FirebaseAuthException catch (e) {
      throw _handleFirebaseAuthError(e);
    }
  }

  // Sign in with Apple
  Future<User> signInWithApple() async {
    try {
      final credential = await SignInWithApple.getAppleIDCredential(
        scopes: [
          AppleIDAuthorizationScopes.email,
          AppleIDAuthorizationScopes.fullName,
        ],
      );
      
      final oauthCredential = firebase_auth.OAuthProvider('apple.com').credential(
        idToken: credential.identityToken,
        accessToken: credential.authorizationCode,
      );
      
      final userCredential = await _firebaseAuth.signInWithCredential(oauthCredential);
      final firebaseUser = userCredential.user;
      
      if (firebaseUser == null) {
        throw Exception('Apple sign in failed');
      }
      
      return _getUserFromFirebase(firebaseUser);
    } on SignInWithAppleAuthorizationException catch (e) {
      throw Exception('Apple sign in failed: ${e.message}');
    } on firebase_auth.FirebaseAuthException catch (e) {
      throw _handleFirebaseAuthError(e);
    }
  }

  // Sign out
  Future<void> signOut() async {
    await _googleSignIn.signOut();
    await _firebaseAuth.signOut();
  }

  // Reset password
  Future<void> resetPassword(String email) async {
    try {
      await _firebaseAuth.sendPasswordResetEmail(email: email);
    } on firebase_auth.FirebaseAuthException catch (e) {
      throw _handleFirebaseAuthError(e);
    }
  }

  // Update profile
  Future<User> updateProfile({String? displayName, String? photoURL}) async {
    final firebaseUser = _firebaseAuth.currentUser;
    
    if (firebaseUser == null) {
      throw Exception('Not authenticated');
    }
    
    if (displayName != null) {
      await firebaseUser.updateDisplayName(displayName);
    }
    
    if (photoURL != null) {
      await firebaseUser.updatePhotoURL(photoURL);
    }
    
    await firebaseUser.reload();
    return _getUserFromFirebase(_firebaseAuth.currentUser!);
  }

  // Get ID token
  Future<String?> getIdToken() async {
    final firebaseUser = _firebaseAuth.currentUser;
    return firebaseUser?.getIdToken();
  }

  // Convert Firebase user to app User
  Future<User> _getUserFromFirebase(firebase_auth.User firebaseUser) async {
    // Get additional user data from backend
    try {
      final backendUser = await _apiService.getCurrentUser();
      return backendUser;
    } catch (e) {
      // Fallback to Firebase user data
      return User(
        id: firebaseUser.uid,
        email: firebaseUser.email ?? '',
        displayName: firebaseUser.displayName,
        avatarUrl: firebaseUser.photoURL,
      );
    }
  }

  // Handle Firebase Auth errors
  Exception _handleFirebaseAuthError(firebase_auth.FirebaseAuthException e) {
    switch (e.code) {
      case 'user-not-found':
        return Exception('No user found with this email');
      case 'wrong-password':
        return Exception('Incorrect password');
      case 'email-already-in-use':
        return Exception('Email is already registered');
      case 'invalid-email':
        return Exception('Invalid email address');
      case 'weak-password':
        return Exception('Password is too weak');
      case 'user-disabled':
        return Exception('This account has been disabled');
      case 'too-many-requests':
        return Exception('Too many attempts. Please try again later');
      case 'operation-not-allowed':
        return Exception('This operation is not allowed');
      case 'account-exists-with-different-credential':
        return Exception('An account already exists with this email');
      case 'invalid-credential':
        return Exception('Invalid credentials');
      default:
        return Exception(e.message ?? 'Authentication failed');
    }
  }
}
