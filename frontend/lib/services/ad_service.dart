/*
Ad Service - Unity Ads Implementation (Nigeria Friendly)
Created by: chAs
*/

import 'package:flutter/material.dart';
import 'package:unity_ads_plugin/unity_ads_plugin.dart';
import '../config/theme.dart';

class AdService {
  static final AdService _instance = AdService._internal();
  factory AdService() => _instance;
  AdService._internal();

  bool _isInitialized = false;
  
  // Track ad load states
  final Map<String, bool> _adLoadStates = {};
  
  String get gameId {
    if (AppConfig.isAndroid) {
      return AppConfig.unityGameIdAndroid;
    } else {
      return AppConfig.unityGameIdIOS;
    }
  }

  String get rewardedAdUnitId => AppConfig.unityRewardedPlacementId;
  String get interstitialAdUnitId => AppConfig.unityInterstitialPlacementId;
  String get bannerAdUnitId => AppConfig.unityBannerPlacementId;

  Future<void> initialize() async {
    if (_isInitialized) return;

    try {
      await UnityAds.init(
        gameId: gameId,
        testMode: AppConfig.isDebug,
        onComplete: () {
          debugPrint('✅ Unity Ads initialized');
          _isInitialized = true;
          // Preload ads after initialization
          _loadAds();
        },
        onFailed: (error, message) {
          debugPrint('❌ Unity Ads init failed: $error - $message');
        },
      );
    } catch (e) {
      debugPrint('❌ Ad initialization error: $e');
    }
  }

  /// Preload ads after initialization
  Future<void> _loadAds() async {
    await loadRewardedAd();
    await loadInterstitialAd();
  }

  /// Load rewarded ad (pre-cache)
  Future<void> loadRewardedAd() async {
    if (!_isInitialized) return;
    
    try {
      await UnityAds.load(
        placementId: rewardedAdUnitId,
        onComplete: (placementId) {
          debugPrint('✅ Rewarded ad loaded: $placementId');
          _adLoadStates[placementId] = true;
        },
        onFailed: (placementId, error, message) {
          debugPrint('❌ Rewarded ad load failed: $error');
          _adLoadStates[placementId] = false;
        },
      );
    } catch (e) {
      debugPrint('❌ Error loading rewarded ad: $e');
    }
  }

  /// Load interstitial ad (pre-cache)
  Future<void> loadInterstitialAd() async {
    if (!_isInitialized) return;
    
    try {
      await UnityAds.load(
        placementId: interstitialAdUnitId,
        onComplete: (placementId) {
          debugPrint('✅ Interstitial ad loaded: $placementId');
          _adLoadStates[placementId] = true;
        },
        onFailed: (placementId, error, message) {
          debugPrint('❌ Interstitial ad load failed: $error');
          _adLoadStates[placementId] = false;
        },
      );
    } catch (e) {
      debugPrint('❌ Error loading interstitial ad: $e');
    }
  }

  /// Check if ad is ready (using cached state)
  bool isAdReady(String placementId) {
    return _adLoadStates[placementId] ?? false;
  }

  Future<bool> showRewardedAd({
    required VoidCallback onRewardEarned,
    required VoidCallback onFailed,
  }) async {
    if (!_isInitialized) {
      await initialize();
    }

    try {
      await UnityAds.showVideoAd(
        placementId: rewardedAdUnitId,
        onComplete: (placementId) {
          debugPrint('✅ Rewarded ad completed: $placementId');
          _adLoadStates[placementId] = false; // Mark as used
          onRewardEarned();
          // Reload for next time
          loadRewardedAd();
        },
        onFailed: (placementId, error, message) {
          debugPrint('❌ Rewarded ad failed: $error');
          _adLoadStates[placementId] = false;
          onFailed();
        },
        onStart: (placementId) {
          debugPrint('▶️ Rewarded ad started: $placementId');
        },
        onClick: (placementId) {
          debugPrint('👆 Rewarded ad clicked: $placementId');
        },
        onSkipped: (placementId) {
          debugPrint('⏭️ Rewarded ad skipped: $placementId');
          _adLoadStates[placementId] = false;
          onFailed();
          // Reload for next time
          loadRewardedAd();
        },
      );
      return true;
    } catch (e) {
      debugPrint('❌ Error showing rewarded ad: $e');
      onFailed();
      return false;
    }
  }

  Future<bool> showInterstitialAd() async {
    if (!_isInitialized) {
      await initialize();
    }

    // Check if ad is ready first
    if (!isAdReady(interstitialAdUnitId)) {
      debugPrint('⚠️ Interstitial ad not ready, attempting to load...');
      await loadInterstitialAd();
      // Small delay to allow load attempt
      await Future.delayed(const Duration(milliseconds: 500));
    }

    try {
      await UnityAds.showVideoAd(
        placementId: interstitialAdUnitId,
        onComplete: (placementId) {
          debugPrint('✅ Interstitial ad completed: $placementId');
          _adLoadStates[placementId] = false;
          // Reload for next time
          loadInterstitialAd();
        },
        onFailed: (placementId, error, message) {
          debugPrint('❌ Interstitial ad failed: $error');
          _adLoadStates[placementId] = false;
        },
        onStart: (placementId) {
          debugPrint('▶️ Interstitial ad started: $placementId');
        },
        onClick: (placementId) {
          debugPrint('👆 Interstitial ad clicked: $placementId');
        },
        onSkipped: (placementId) {
          debugPrint('⏭️ Interstitial ad skipped: $placementId');
          _adLoadStates[placementId] = false;
          loadInterstitialAd();
        },
      );
      return true;
    } catch (e) {
      debugPrint('❌ Error showing interstitial ad: $e');
      return false;
    }
  }

  Widget createBannerAd() {
    return UnityBannerAd(
      placementId: bannerAdUnitId,
      onLoad: (placementId) => debugPrint('✅ Banner loaded: $placementId'),
      onClick: (placementId) => debugPrint('👆 Banner clicked: $placementId'),
      onFailed: (placementId, error, message) {
        debugPrint('❌ Banner failed: $error');
      },
      onShown: (placementId) => debugPrint('👁️ Banner shown: $placementId'),
    );
  }
}
