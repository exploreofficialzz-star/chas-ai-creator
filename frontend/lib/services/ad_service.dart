/*
 * chAs AI Creator - Ad Service
 * Created by: chAs
 * Unity Ads Integration for Monetization (Nigeria Friendly)
 * Replaces Google AdMob which doesn't work in Nigeria
 */

import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:unity_ads_plugin/unity_ads_plugin.dart';

/// Ad Service for managing Unity Ads
/// Created by: chAs
/// Unity Ads works in Nigeria unlike Google AdMob
class AdService {
  static final AdService _instance = AdService._internal();
  factory AdService() => _instance;
  AdService._internal();

  // Unity Ads Game IDs - Replace with your actual Unity Ads IDs
  // Get these from https://dashboard.unity3d.com
  static const String _androidGameId = 'YOUR_UNITY_ANDROID_GAME_ID';
  static const String _iosGameId = 'YOUR_UNITY_IOS_GAME_ID';
  
  // Test Mode - Set to false for production
  static const bool _testMode = true;

  // Ad Placement IDs
  static const String _bannerPlacementId = 'Banner_Android';
  static const String _interstitialPlacementId = 'Interstitial_Android';
  static const String _rewardedPlacementId = 'Rewarded_Android';

  bool _isInitialized = false;
  bool _isBannerLoaded = false;
  
  // Ad counters for frequency capping
  int _videoCreationCount = 0;
  int _screenViewCount = 0;

  /// Initialize the ad service
  Future<void> initialize() async {
    if (_isInitialized) return;
    
    final gameId = Platform.isAndroid ? _androidGameId : _iosGameId;
    
    await UnityAds.init(
      gameId: gameId,
      testMode: _testMode,
      onComplete: () {
        _isInitialized = true;
        if (kDebugMode) {
          print('🎯 chAs AI Creator: Unity Ads initialized');
        }
        _loadInterstitialAd();
        _loadRewardedAd();
      },
      onFailed: (error, message) {
        if (kDebugMode) {
          print('🎯 Unity Ads initialization failed: $error - $message');
        }
      },
    );
  }

  /// Get current game ID
  String get gameId => Platform.isAndroid ? _androidGameId : _iosGameId;

  /// Load interstitial ad
  void _loadInterstitialAd() {
    UnityAds.load(
      placementId: _interstitialPlacementId,
      onComplete: (placementId) {
        if (kDebugMode) print('🎯 Interstitial ad loaded: $placementId');
      },
      onFailed: (placementId, error, message) {
        if (kDebugMode) print('🎯 Interstitial ad failed to load: $error');
      },
    );
  }

  /// Show interstitial ad if ready
  Future<bool> showInterstitialAd() async {
    if (!_isInitialized) {
      if (kDebugMode) print('🎯 Unity Ads not initialized');
      return false;
    }

    bool adShown = false;
    
    await UnityAds.showVideoAd(
      placementId: _interstitialPlacementId,
      onComplete: (placementId) {
        if (kDebugMode) print('🎯 Interstitial ad completed: $placementId');
        adShown = true;
        _loadInterstitialAd(); // Preload next ad
      },
      onFailed: (placementId, error, message) {
        if (kDebugMode) print('🎯 Interstitial ad failed: $error');
        _loadInterstitialAd();
      },
      onStart: (placementId) {
        if (kDebugMode) print('🎯 Interstitial ad started: $placementId');
      },
      onClick: (placementId) {
        if (kDebugMode) print('🎯 Interstitial ad clicked: $placementId');
      },
      onSkipped: (placementId) {
        if (kDebugMode) print('🎯 Interstitial ad skipped: $placementId');
        adShown = true;
        _loadInterstitialAd();
      },
    );
    
    return adShown;
  }

  /// Load rewarded ad
  void _loadRewardedAd() {
    UnityAds.load(
      placementId: _rewardedPlacementId,
      onComplete: (placementId) {
        if (kDebugMode) print('🎯 Rewarded ad loaded: $placementId');
      },
      onFailed: (placementId, error, message) {
        if (kDebugMode) print('🎯 Rewarded ad failed to load: $error');
      },
    );
  }

  /// Show rewarded ad
  Future<bool> showRewardedAd({
    required Function onUserEarnedReward,
  }) async {
    if (!_isInitialized) {
      if (kDebugMode) print('🎯 Unity Ads not initialized');
      return false;
    }

    bool rewardEarned = false;
    
    await UnityAds.showVideoAd(
      placementId: _rewardedPlacementId,
      onComplete: (placementId) {
        if (kDebugMode) print('🎯 Rewarded ad completed: $placementId');
        rewardEarned = true;
        onUserEarnedReward();
        _loadRewardedAd(); // Preload next ad
      },
      onFailed: (placementId, error, message) {
        if (kDebugMode) print('🎯 Rewarded ad failed: $error');
        _loadRewardedAd();
      },
      onStart: (placementId) {
        if (kDebugMode) print('🎯 Rewarded ad started: $placementId');
      },
      onClick: (placementId) {
        if (kDebugMode) print('🎯 Rewarded ad clicked: $placementId');
      },
      onSkipped: (placementId) {
        if (kDebugMode) print('🎯 Rewarded ad skipped: $placementId');
        _loadRewardedAd();
      },
    );
    
    return rewardEarned;
  }

  /// Show banner ad
  Widget createBannerAd() {
    return UnityBannerAd(
      placementId: _bannerPlacementId,
      onLoad: (placementId) {
        if (kDebugMode) print('🎯 Banner ad loaded: $placementId');
        _isBannerLoaded = true;
      },
      onClick: (placementId) {
        if (kDebugMode) print('🎯 Banner ad clicked: $placementId');
      },
      onFailed: (placementId, error, message) {
        if (kDebugMode) print('🎯 Banner ad failed: $error');
        _isBannerLoaded = false;
      },
    );
  }

  /// Track video creation and show ad if needed
  /// Returns true if ad was shown
  Future<bool> trackVideoCreationAndShowAd() async {
    _videoCreationCount++;
    
    // Show interstitial ad every 2 video creations
    if (_videoCreationCount % 2 == 0) {
      return await showInterstitialAd();
    }
    return false;
  }

  /// Track screen view and show ad if needed
  /// Returns true if ad was shown
  Future<bool> trackScreenViewAndShowAd() async {
    _screenViewCount++;
    
    // Show interstitial ad every 5 screen views
    if (_screenViewCount % 5 == 0) {
      return await showInterstitialAd();
    }
    return false;
  }

  /// Show rewarded ad to earn credits
  Future<bool> showRewardedAdForCredits({
    required Function(int credits) onCreditsEarned,
  }) async {
    return await showRewardedAd(
      onUserEarnedReward: () {
        // User earned reward - give credits
        onCreditsEarned(5); // Give 5 credits for watching ad
      },
    );
  }

  /// Check if ads are initialized
  bool get isInitialized => _isInitialized;

  /// Dispose ads
  void dispose() {
    // Unity Ads doesn't require explicit disposal
  }
}

// Re-export UnityBannerAd for convenience
export 'package:unity_ads_plugin/unity_ads_plugin.dart' show UnityBannerAd;
