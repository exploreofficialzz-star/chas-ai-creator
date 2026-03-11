/*
 * chAs AI Creator - Ad Service (Unity Ads)
 * FILE: lib/services/ad_service.dart
 *
 * FIXES:
 * 1. AppConfig was referenced throughout but never imported or defined
 *    anywhere — caused a build-breaking "Undefined name 'AppConfig'" error.
 *    Fixed by replacing all AppConfig.x references with inline constants
 *    and dart:io Platform checks.
 *
 * 2. Removed unused '../config/theme.dart' import (AppTheme never used here).
 *
 * 3. showInterstitialAd() is now fully silent — no exception can escape.
 *    Dashboard calls this fire-and-forget; any throw was crashing silently
 *    and interfering with the post-login flow.
 *
 * ── HOW TO CONFIGURE ─────────────────────────────────────────────────────
 * Replace the placeholder IDs below with your real Unity Dashboard values:
 *   _kAndroidGameId      → Unity Dashboard → Project → Android Game ID
 *   _kIosGameId          → Unity Dashboard → Project → iOS Game ID
 *   _kRewardedPlacement  → Placement ID you named "Rewarded_Android" etc.
 *   _kInterstitialPlacement
 *   _kBannerPlacement
 * ─────────────────────────────────────────────────────────────────────────
 */

import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:unity_ads_plugin/unity_ads_plugin.dart';

class AdService {
  static final AdService _instance = AdService._internal();
  factory AdService() => _instance;
  AdService._internal();

  // ── Unity Ads configuration ──────────────────────────────────────────────
  // FIX 1 — replaced AppConfig.x with inline constants.
  // AppConfig was never defined or imported — build error on every compile.
  static const String _kAndroidGameId     = '6060848'; // ← your real ID
  static const String _kIosGameId         = '6060849'; // ← your real ID
  static const String _kRewardedPlacement = 'Rewarded_Android';
  static const String _kInterstitialPlacement = 'Interstitial_Android';
  static const String _kBannerPlacement   = 'Banner_Android';

  bool _isInitialized = false;
  final Map<String, bool> _adLoadStates = {};

  // ── IDs ──────────────────────────────────────────────────────────────────

  String get _gameId =>
      Platform.isAndroid ? _kAndroidGameId : _kIosGameId;

  String get rewardedAdUnitId     => _kRewardedPlacement;
  String get interstitialAdUnitId => _kInterstitialPlacement;
  String get bannerAdUnitId       => _kBannerPlacement;

  // ── Init ─────────────────────────────────────────────────────────────────

  Future<void> initialize() async {
    if (_isInitialized) return;
    try {
      await UnityAds.init(
        gameId: _gameId,
        // FIX 1 — was AppConfig.isDebug (undefined). Use kDebugMode.
        testMode: kDebugMode,
        onComplete: () {
          debugPrint('✅ Unity Ads initialized');
          _isInitialized = true;
          _loadAds();
        },
        onFailed: (error, message) {
          debugPrint('❌ Unity Ads init failed: $error - $message');
        },
      );
    } catch (e) {
      debugPrint('❌ Ad init error: $e');
    }
  }

  Future<void> _loadAds() async {
    await loadRewardedAd();
    await loadInterstitialAd();
  }

  // ── Load ─────────────────────────────────────────────────────────────────

  Future<void> loadRewardedAd() async {
    if (!_isInitialized) return;
    try {
      await UnityAds.load(
        placementId: rewardedAdUnitId,
        onComplete: (id) {
          debugPrint('✅ Rewarded loaded: $id');
          _adLoadStates[id] = true;
        },
        onFailed: (id, error, message) {
          debugPrint('❌ Rewarded load failed: $error');
          _adLoadStates[id] = false;
        },
      );
    } catch (e) {
      debugPrint('❌ loadRewardedAd error: $e');
    }
  }

  Future<void> loadInterstitialAd() async {
    if (!_isInitialized) return;
    try {
      await UnityAds.load(
        placementId: interstitialAdUnitId,
        onComplete: (id) {
          debugPrint('✅ Interstitial loaded: $id');
          _adLoadStates[id] = true;
        },
        onFailed: (id, error, message) {
          debugPrint('❌ Interstitial load failed: $error');
          _adLoadStates[id] = false;
        },
      );
    } catch (e) {
      debugPrint('❌ loadInterstitialAd error: $e');
    }
  }

  bool isAdReady(String placementId) =>
      _adLoadStates[placementId] ?? false;

  // ── Show Rewarded ─────────────────────────────────────────────────────────

  Future<bool> showRewardedAd({
    required VoidCallback onRewardEarned,
    required VoidCallback onFailed,
  }) async {
    if (!_isInitialized) await initialize();
    try {
      await UnityAds.showVideoAd(
        placementId: rewardedAdUnitId,
        onComplete: (id) {
          debugPrint('✅ Rewarded completed: $id');
          _adLoadStates[id] = false;
          onRewardEarned();
          loadRewardedAd();
        },
        onFailed: (id, error, message) {
          debugPrint('❌ Rewarded failed: $error');
          _adLoadStates[id] = false;
          onFailed();
        },
        onStart:   (id) => debugPrint('▶️ Rewarded started: $id'),
        onClick:   (id) => debugPrint('👆 Rewarded clicked: $id'),
        onSkipped: (id) {
          debugPrint('⏭️ Rewarded skipped: $id');
          _adLoadStates[id] = false;
          onFailed();
          loadRewardedAd();
        },
      );
      return true;
    } catch (e) {
      debugPrint('❌ showRewardedAd error: $e');
      onFailed();
      return false;
    }
  }

  // ── Show Interstitial ─────────────────────────────────────────────────────

  Future<bool> showInterstitialAd() async {
    // FIX 3 — entire method is wrapped in try/catch so nothing
    // can escape and disturb the post-login flow. Dashboard calls
    // this fire-and-forget inside a Future.delayed — any uncaught
    // exception here was killing the isolate silently.
    try {
      if (!_isInitialized) await initialize();

      if (!isAdReady(interstitialAdUnitId)) {
        debugPrint('⚠️ Interstitial not ready — loading...');
        await loadInterstitialAd();
        await Future.delayed(const Duration(milliseconds: 500));
      }

      await UnityAds.showVideoAd(
        placementId: interstitialAdUnitId,
        onComplete: (id) {
          debugPrint('✅ Interstitial completed: $id');
          _adLoadStates[id] = false;
          loadInterstitialAd();
        },
        onFailed: (id, error, message) {
          debugPrint('❌ Interstitial failed: $error');
          _adLoadStates[id] = false;
        },
        onStart:   (id) => debugPrint('▶️ Interstitial started: $id'),
        onClick:   (id) => debugPrint('👆 Interstitial clicked: $id'),
        onSkipped: (id) {
          debugPrint('⏭️ Interstitial skipped: $id');
          _adLoadStates[id] = false;
          loadInterstitialAd();
        },
      );
      return true;
    } catch (e) {
      debugPrint('❌ showInterstitialAd error: $e');
      return false;
    }
  }

  // ── Banner ────────────────────────────────────────────────────────────────

  Widget createBannerAd() {
    return UnityBannerAd(
      placementId: bannerAdUnitId,
      onLoad:   (id) => debugPrint('✅ Banner loaded: $id'),
      onClick:  (id) => debugPrint('👆 Banner clicked: $id'),
      onFailed: (id, error, message) =>
          debugPrint('❌ Banner failed: $error'),
      onShown:  (id) => debugPrint('👁️ Banner shown: $id'),
    );
  }
}
