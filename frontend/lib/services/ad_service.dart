/*
 * chAs AI Creator - Ad Service (Unity Ads)
 * FILE: lib/services/ad_service.dart
 *
 * FIXES:
 * 1. AppConfig is defined in lib/config/theme.dart — just needed
 *    the correct import. All AppConfig.x references now work.
 *    Previous fix replaced them with inline constants unnecessarily.
 *
 * 2. showInterstitialAd() fully wrapped in try/catch — no exception
 *    can escape and disturb the post-login flow.
 */

import 'package:flutter/material.dart';
import 'package:unity_ads_plugin/unity_ads_plugin.dart';

import '../config/theme.dart';  // ← AppConfig lives here

class AdService {
  static final AdService _instance = AdService._internal();
  factory AdService() => _instance;
  AdService._internal();

  bool _isInitialized = false;
  final Map<String, bool> _adLoadStates = {};

  // ── IDs (from AppConfig in theme.dart) ───────────────────────────────────

  String get _gameId => AppConfig.isAndroid
      ? AppConfig.unityGameIdAndroid
      : AppConfig.unityGameIdIOS;

  String get rewardedAdUnitId     => AppConfig.unityRewardedPlacementId;
  String get interstitialAdUnitId => AppConfig.unityInterstitialPlacementId;
  String get bannerAdUnitId       => AppConfig.unityBannerPlacementId;

  // ── Init ─────────────────────────────────────────────────────────────────

  Future<void> initialize() async {
    if (_isInitialized) return;
    try {
      await UnityAds.init(
        gameId: _gameId,
        testMode: AppConfig.isDebug,
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
    // FIX 2 — fully wrapped so nothing escapes and disturbs
    // the post-login flow in dashboard_screen.dart
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
