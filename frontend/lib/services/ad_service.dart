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
        },
        onFailed: (error, message) {
          debugPrint('❌ Unity Ads init failed: $error - $message');
        },
      );
    } catch (e) {
      debugPrint('❌ Ad initialization error: $e');
    }
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
          onRewardEarned();
        },
        onFailed: (placementId, error, message) {
          debugPrint('❌ Rewarded ad failed: $error');
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
          onFailed();
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

    try {
      await UnityAds.showVideoAd(
        placementId: interstitialAdUnitId,
        onComplete: (placementId) {
          debugPrint('✅ Interstitial ad completed: $placementId');
        },
        onFailed: (placementId, error, message) {
          debugPrint('❌ Interstitial ad failed: $error');
        },
        onStart: (placementId) {
          debugPrint('▶️ Interstitial ad started: $placementId');
        },
      );
      return true;
    } catch (e) {
      debugPrint('❌ Error showing interstitial ad: $e');
      return false;
    }
  }

  Future<bool> isAdReady(String placementId) async {
    return await UnityAds.isReady(placementId: placementId);
  }

  Widget createBannerAd() {
    return UnityBannerAd(
      placementId: bannerAdUnitId,
      onLoad: (placementId) => debugPrint('✅ Banner loaded: $placementId'),
      onClick: (placementId) => debugPrint('👆 Banner clicked: $placementId'),
      onFailed: (placementId, error, message) {
        debugPrint('❌ Banner failed: $error');
      },
    );
  }
}
