/*
 * chAs AI Creator - Banner Ad Container
 * FILE: lib/widgets/banner_ad_container.dart
 *
 * FIX — _isLoaded was set but never used. Now shows a subtle
 * placeholder while the banner is loading so the layout doesn't
 * jump when the ad appears. Collapses to SizedBox.shrink() on error
 * so it takes zero space and never shows a blank gap.
 */

import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:unity_ads_plugin/unity_ads_plugin.dart';

import '../config/theme.dart';

class BannerAdContainer extends StatefulWidget {
  final bool isLarge;

  const BannerAdContainer({
    super.key,
    this.isLarge = false,
  });

  @override
  State<BannerAdContainer> createState() =>
      _BannerAdContainerState();
}

class _BannerAdContainerState extends State<BannerAdContainer> {
  bool _isLoaded = false;
  bool _hasError = false;

  double get _height => widget.isLarge ? 250.h : 60.h;

  @override
  Widget build(BuildContext context) {
    // Collapse completely on error — no blank gap in the layout
    if (_hasError) return const SizedBox.shrink();

    return SizedBox(
      width: double.infinity,
      height: _height,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Placeholder shown while ad is loading
          if (!_isLoaded)
            Container(
              width: double.infinity,
              height: _height,
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withOpacity(0.04),
                borderRadius: BorderRadius.circular(8.r),
                border: Border.all(
                  color: AppTheme.primaryColor.withOpacity(0.08),
                ),
              ),
              child: Center(
                child: Text(
                  'Advertisement',
                  style: TextStyle(
                    fontSize: 11.sp,
                    color: Colors.grey.shade400,
                    letterSpacing: 1,
                  ),
                ),
              ),
            ),

          // Unity banner — always in tree so it can load
          UnityBannerAd(
            placementId: AppConfig.unityBannerPlacementId,
            onLoad: (placementId) {
              if (mounted) setState(() => _isLoaded = true);
              debugPrint('✅ Banner loaded: $placementId');
            },
            onClick: (placementId) =>
                debugPrint('👆 Banner clicked: $placementId'),
            onFailed: (placementId, error, message) {
              if (mounted) setState(() => _hasError = true);
              debugPrint('❌ Banner failed: $error');
            },
            onShown: (placementId) =>
                debugPrint('👁️ Banner shown: $placementId'),
          ),
        ],
      ),
    );
  }
}
