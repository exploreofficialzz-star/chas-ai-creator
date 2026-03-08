/*
Banner Ad Container - Unity Ads Implementation
Created by: chAs
*/

import 'package:flutter/material.dart';
import 'package:unity_ads_plugin/unity_ads_plugin.dart';
import '../services/ad_service.dart';

class BannerAdContainer extends StatefulWidget {
  final bool isLarge;
  
  const BannerAdContainer({
    Key? key,
    this.isLarge = false,
  }) : super(key: key);

  @override
  State<BannerAdContainer> createState() => _BannerAdContainerState();
}

class _BannerAdContainerState extends State<BannerAdContainer> {
  bool _isLoaded = false;
  bool _hasError = false;

  @override
  Widget build(BuildContext context) {
    if (_hasError) {
      return const SizedBox.shrink();
    }

    return Container(
      width: double.infinity,
      height: widget.isLarge ? 250 : 100,
      alignment: Alignment.center,
      child: UnityBannerAd(
        placementId: AdService().bannerAdUnitId,
        onLoad: (placementId) {
          setState(() {
            _isLoaded = true;
          });
        },
        onClick: (placementId) {
          debugPrint('👆 Banner clicked: $placementId');
        },
        onFailed: (placementId, error, message) {
          setState(() {
            _hasError = true;
          });
        },
      ),
    );
  }
}
