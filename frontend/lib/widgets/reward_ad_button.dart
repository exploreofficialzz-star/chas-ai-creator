/*
Reward Ad Button - Unity Ads Implementation
Created by: chAs
*/

import 'package:flutter/material.dart';
import '../services/ad_service.dart';

class RewardAdButton extends StatelessWidget {
  final VoidCallback onRewardEarned;
  final String label;
  final bool isLoading;

  const RewardAdButton({
    Key? key,
    required this.onRewardEarned,
    this.label = 'Watch Ad for Reward',
    this.isLoading = false,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: isLoading ? null : _showRewardedAd,
      icon: isLoading 
        ? const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : const Icon(Icons.play_circle_outline),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        backgroundColor: Colors.green,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      ),
    );
  }

  Future<void> _showRewardedAd() async {
    final adService = AdService();
    
    await adService.showRewardedAd(
      onRewardEarned: onRewardEarned,
      onFailed: () {
        debugPrint('Ad failed or was skipped');
      },
    );
  }
}
