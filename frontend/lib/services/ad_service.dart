/*
 * chAs AI Creator - Ad Service
 * Created by: chAs
 * Google AdMob Integration for Monetization
 */

import 'dart:io';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:flutter/foundation.dart';

/// Ad Service for managing Google AdMob ads
/// Created by: chAs
class AdService {
  static final AdService _instance = AdService._internal();
  factory AdService() => _instance;
  AdService._internal();

  // Ad Unit IDs - Replace with your actual AdMob IDs
  // Test IDs for development
  static const String _testBannerAdUnitId = 'ca-app-pub-3940256099942544/6300978111';
  static const String _testInterstitialAdUnitId = 'ca-app-pub-3940256099942544/1033173712';
  static const String _testRewardedAdUnitId = 'ca-app-pub-3940256099942544/5224354917';
  static const String _testNativeAdUnitId = 'ca-app-pub-3940256099942544/2247696110';

  // Production IDs - Replace these with your actual AdMob IDs
  static const String _androidBannerAdUnitId = 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX';
  static const String _androidInterstitialAdUnitId = 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX';
  static const String _androidRewardedAdUnitId = 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX';
  
  static const String _iosBannerAdUnitId = 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX';
  static const String _iosInterstitialAdUnitId = 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX';
  static const String _iosRewardedAdUnitId = 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX';

  bool _isInitialized = false;
  
  // Ad counters for frequency capping
  int _videoCreationCount = 0;
  int _screenViewCount = 0;
  
  // Cached ads
  InterstitialAd? _interstitialAd;
  RewardedAd? _rewardedAd;
  bool _isInterstitialAdLoading = false;
  bool _isRewardedAdLoading = false;

  /// Initialize the ad service
  Future<void> initialize() async {
    if (_isInitialized) return;
    
    await MobileAds.instance.initialize();
    _isInitialized = true;
    
    if (kDebugMode) {
      print('🎯 chAs AI Creator: Ad Service initialized');
    }
    
    // Preload ads
    _loadInterstitialAd();
    _loadRewardedAd();
  }

  /// Get banner ad unit ID
  String get bannerAdUnitId {
    if (kDebugMode) return _testBannerAdUnitId;
    return Platform.isAndroid ? _androidBannerAdUnitId : _iosBannerAdUnitId;
  }

  /// Get interstitial ad unit ID
  String get interstitialAdUnitId {
    if (kDebugMode) return _testInterstitialAdUnitId;
    return Platform.isAndroid ? _androidInterstitialAdUnitId : _iosInterstitialAdUnitId;
  }

  /// Get rewarded ad unit ID
  String get rewardedAdUnitId {
    if (kDebugMode) return _testRewardedAdUnitId;
    return Platform.isAndroid ? _androidRewardedAdUnitId : _iosRewardedAdUnitId;
  }

  /// Create a banner ad
  BannerAd createBannerAd() {
    return BannerAd(
      adUnitId: bannerAdUnitId,
      size: AdSize.banner,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (ad) {
          if (kDebugMode) print('🎯 Banner ad loaded');
        },
        onAdFailedToLoad: (ad, error) {
          if (kDebugMode) print('🎯 Banner ad failed to load: $error');
          ad.dispose();
        },
      ),
    );
  }

  /// Create a medium rectangle banner ad
  BannerAd createMediumBannerAd() {
    return BannerAd(
      adUnitId: bannerAdUnitId,
      size: AdSize.mediumRectangle,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (ad) {
          if (kDebugMode) print('🎯 Medium banner ad loaded');
        },
        onAdFailedToLoad: (ad, error) {
          if (kDebugMode) print('🎯 Medium banner ad failed to load: $error');
          ad.dispose();
        },
      ),
    );
  }

  /// Load interstitial ad
  void _loadInterstitialAd() {
    if (_isInterstitialAdLoading) return;
    
    _isInterstitialAdLoading = true;
    
    InterstitialAd.load(
      adUnitId: interstitialAdUnitId,
      request: const AdRequest(),
      adLoadCallback: InterstitialAdLoadCallback(
        onAdLoaded: (ad) {
          _interstitialAd = ad;
          _isInterstitialAdLoading = false;
          if (kDebugMode) print('🎯 Interstitial ad loaded');
        },
        onAdFailedToLoad: (error) {
          _isInterstitialAdLoading = false;
          if (kDebugMode) print('🎯 Interstitial ad failed to load: $error');
        },
      ),
    );
  }

  /// Show interstitial ad if ready
  Future<bool> showInterstitialAd() async {
    if (_interstitialAd != null) {
      await _interstitialAd!.show();
      _interstitialAd = null;
      _loadInterstitialAd(); // Preload next ad
      return true;
    } else {
      _loadInterstitialAd();
      return false;
    }
  }

  /// Load rewarded ad
  void _loadRewardedAd() {
    if (_isRewardedAdLoading) return;
    
    _isRewardedAdLoading = true;
    
    RewardedAd.load(
      adUnitId: rewardedAdUnitId,
      request: const AdRequest(),
      rewardedAdLoadCallback: RewardedAdLoadCallback(
        onAdLoaded: (ad) {
          _rewardedAd = ad;
          _isRewardedAdLoading = false;
          if (kDebugMode) print('🎯 Rewarded ad loaded');
        },
        onAdFailedToLoad: (error) {
          _isRewardedAdLoading = false;
          if (kDebugMode) print('🎯 Rewarded ad failed to load: $error');
        },
      ),
    );
  }

  /// Show rewarded ad
  Future<bool> showRewardedAd({
    required Function(AdWithoutView, RewardItem) onUserEarnedReward,
  }) async {
    if (_rewardedAd != null) {
      _rewardedAd!.fullScreenContentCallback = FullScreenContentCallback(
        onAdDismissedFullScreenContent: (ad) {
          ad.dispose();
          _rewardedAd = null;
          _loadRewardedAd();
        },
        onAdFailedToShowFullScreenContent: (ad, error) {
          ad.dispose();
          _rewardedAd = null;
          _loadRewardedAd();
        },
      );
      
      await _rewardedAd!.show(onUserEarnedReward: onUserEarnedReward);
      return true;
    } else {
      _loadRewardedAd();
      return false;
    }
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
      onUserEarnedReward: (ad, reward) {
        // User earned reward - give credits
        onCreditsEarned(5); // Give 5 credits for watching ad
      },
    );
  }

  /// Dispose all ads
  void dispose() {
    _interstitialAd?.dispose();
    _rewardedAd?.dispose();
  }
}

/// Widget for displaying banner ads
class BannerAdWidget extends StatefulWidget {
  final AdSize size;
  
  const BannerAdWidget({
    super.key,
    this.size = AdSize.banner,
  });

  @override
  State<BannerAdWidget> createState() => _BannerAdWidgetState();
}

class _BannerAdWidgetState extends State<BannerAdWidget> {
  BannerAd? _bannerAd;
  bool _isLoaded = false;

  @override
  void initState() {
    super.initState();
    _loadAd();
  }

  void _loadAd() {
    _bannerAd = BannerAd(
      adUnitId: AdService().bannerAdUnitId,
      size: widget.size,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (ad) {
          setState(() {
            _isLoaded = true;
          });
        },
        onAdFailedToLoad: (ad, error) {
          ad.dispose();
        },
      ),
    )..load();
  }

  @override
  void dispose() {
    _bannerAd?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_isLoaded || _bannerAd == null) {
      return const SizedBox.shrink();
    }
    
    return Container(
      alignment: Alignment.center,
      width: _bannerAd!.size.width.toDouble(),
      height: _bannerAd!.size.height.toDouble(),
      child: AdWidget(ad: _bannerAd!),
    );
  }
}
