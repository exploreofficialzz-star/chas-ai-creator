/*
 * chAs AI Creator - App Configuration & Theme
 * FILE: lib/config/theme.dart
 *
 * FIX — removed surfaceContainerHighest (added in Flutter 3.22+,
 * not available in Flutter 3.19.0). Back to background/onBackground
 * which are deprecated but fully functional in Flutter 3.19.
 */

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ─────────────────────────────────────────────────────────────────────────────
// APP CONFIG
// ─────────────────────────────────────────────────────────────────────────────

class AppConfig {
  static const bool isDebug = kDebugMode;
  static bool get isAndroid =>
      defaultTargetPlatform == TargetPlatform.android;
  static bool get isIOS =>
      defaultTargetPlatform == TargetPlatform.iOS;

  static const String baseUrl =
      'https://chas-ai-creator-2.onrender.com/api/v1';

  // Unity Ads — Nigeria Friendly
  static const String unityGameIdAndroid           = '6060848';
  static const String unityGameIdIOS               = '6060849';
  static const String unityRewardedPlacementId     = 'rewardedVideo';
  static const String unityInterstitialPlacementId = 'interstitialVideo';
  static const String unityBannerPlacementId       = 'banner';

  // Paystack
  static const String paystackPublicKey = 'pk_test_your_key_here';

  // App Info
  static const String appName    = 'chAs AI Creator';
  static const String appVersion = '1.0.0';
}

// ─────────────────────────────────────────────────────────────────────────────
// APP THEME
// ─────────────────────────────────────────────────────────────────────────────

class AppTheme {
  static const Color primaryColor   = Color(0xFF6C63FF);
  static const Color secondaryColor = Color(0xFF00BFA6);
  static const Color accentColor    = Color(0xFFFF6584);
  static const Color darkColor      = Color(0xFF2D2D3A);
  static const Color lightColor     = Color(0xFFF8F9FA);

  static const Color successColor = Color(0xFF4CAF50);
  static const Color errorColor   = Color(0xFFE53935);
  static const Color warningColor = Color(0xFFFFB300);
  static const Color infoColor    = Color(0xFF2196F3);

  static const Color textPrimaryLight   = Color(0xFF2D2D3A);
  static const Color textSecondaryLight = Color(0xFF6B7280);
  static const Color textPrimaryDark    = Color(0xFFFFFFFF);
  static const Color textSecondaryDark  = Color(0xFFB0B0B0);

  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryColor, Color(0xFF8B5CF6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // ── Dark Theme ────────────────────────────────────────────────────────────

  // ignore: deprecated_member_use
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      primaryColor: primaryColor,
      scaffoldBackgroundColor: darkColor,
      cardColor: const Color(0xFF3D3D4A),
      colorScheme: const ColorScheme.dark(
        primary: primaryColor,
        secondary: secondaryColor,
        surface: Color(0xFF3D3D4A),
        // ignore: deprecated_member_use
        background: darkColor,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: Colors.white,
        // ignore: deprecated_member_use
        onBackground: Colors.white,
      ),
      textTheme:
          GoogleFonts.interTextTheme(ThemeData.dark().textTheme),
      appBarTheme: AppBarTheme(
        elevation: 0,
        centerTitle: true,
        backgroundColor: darkColor,
        titleTextStyle: GoogleFonts.inter(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
              horizontal: 24, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF3D3D4A),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: primaryColor, width: 2),
        ),
      ),
    );
  }

  // ── Light Theme ───────────────────────────────────────────────────────────

  // ignore: deprecated_member_use
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      primaryColor: primaryColor,
      scaffoldBackgroundColor: lightColor,
      cardColor: Colors.white,
      colorScheme: const ColorScheme.light(
        primary: primaryColor,
        secondary: secondaryColor,
        surface: Colors.white,
        // ignore: deprecated_member_use
        background: lightColor,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: darkColor,
        // ignore: deprecated_member_use
        onBackground: darkColor,
      ),
      textTheme:
          GoogleFonts.interTextTheme(ThemeData.light().textTheme),
      appBarTheme: AppBarTheme(
        elevation: 0,
        centerTitle: true,
        backgroundColor: Colors.white,
        titleTextStyle: GoogleFonts.inter(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: darkColor,
        ),
        iconTheme: const IconThemeData(color: darkColor),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
              horizontal: 24, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: Color(0xFFE0E0E0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: Color(0xFFE0E0E0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: primaryColor, width: 2),
        ),
      ),
    );
  }
}
