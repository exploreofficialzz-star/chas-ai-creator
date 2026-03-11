/*
 * chAs AI Creator - Reward Ad Button
 * FILE: lib/widgets/reward_ad_button.dart
 *
 * FIXES:
 * 1. Converted to StatefulWidget so it has BuildContext for showing
 *    a snackbar when the ad fails or is skipped. Previously the user
 *    got zero feedback on ad failure — they just tapped and nothing
 *    happened with no explanation.
 *
 * 2. Added flutter_screenutil sizing to match the rest of the app.
 *
 * 3. Added _isLoading internal state so the button shows a spinner
 *    while the ad is loading/showing without requiring the parent
 *    to manage loading state.
 */

import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../services/ad_service.dart';

class RewardAdButton extends StatefulWidget {
  final VoidCallback onRewardEarned;
  final String label;

  const RewardAdButton({
    super.key,
    required this.onRewardEarned,
    this.label = '🎬 Watch Ad for 5 Credits',
  });

  @override
  State<RewardAdButton> createState() => _RewardAdButtonState();
}

class _RewardAdButtonState extends State<RewardAdButton> {
  bool _isLoading = false;

  Future<void> _showRewardedAd() async {
    if (_isLoading) return;
    setState(() => _isLoading = true);

    await AdService().showRewardedAd(
      onRewardEarned: () {
        if (mounted) {
          setState(() => _isLoading = false);
          widget.onRewardEarned();
        }
      },
      onFailed: () {
        if (mounted) {
          setState(() => _isLoading = false);
          // FIX 1 — show snackbar so user knows why nothing happened
          ScaffoldMessenger.of(context)
            ..clearSnackBars()
            ..showSnackBar(
              SnackBar(
                content: const Text(
                    '⚠️ Ad not available right now. Try again later.'),
                backgroundColor: Colors.orange.shade700,
                behavior: SnackBarBehavior.floating,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10.r)),
                margin: EdgeInsets.all(12.w),
                duration: const Duration(seconds: 3),
              ),
            );
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: _isLoading ? null : _showRewardedAd,
        icon: _isLoading
            ? SizedBox(
                width: 18.w,
                height: 18.w,
                child: const CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : Icon(Icons.play_circle_outline, size: 22.w),
        label: Text(
          _isLoading ? 'Loading ad...' : widget.label,
          style: TextStyle(
            fontSize: 14.sp,
            fontWeight: FontWeight.w600,
          ),
        ),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.green.shade600,
          foregroundColor: Colors.white,
          disabledBackgroundColor:
              Colors.green.shade600.withOpacity(0.5),
          padding: EdgeInsets.symmetric(
              horizontal: 24.w, vertical: 14.h),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14.r),
          ),
          elevation: 0,
        ),
      ),
    );
  }
}
