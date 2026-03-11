/*
 * chAs AI Creator - Onboarding Screen
 * FILE: lib/screens/onboarding/onboarding_screen.dart
 *
 * ROOT CAUSE FIX:
 * _onDone() was calling Navigator.pushReplacement(LoginScreen()).
 * This pushed LoginScreen onto the Navigator stack inside MaterialApp.
 * When login succeeded and app.dart rebuilt with HomeScreen as its
 * home, MaterialApp only replaced the HOME widget — it did NOT pop
 * the Navigator stack. The Navigator-pushed LoginScreen stayed on
 * top, so the user always saw the login screen after onboarding even
 * after a successful login.
 *
 * THE FIX: No Navigator calls here at all. OnboardingScreen accepts
 * an onComplete VoidCallback from app.dart. When onboarding is done,
 * we save the pref and call onComplete(), which does:
 *   setState(() => _hasSeenOnboarding = true)
 * in app.dart. This causes app.dart's BlocBuilder to re-evaluate and
 * show LoginScreen directly as the home widget — clean, no stack leak.
 */

import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:introduction_screen/introduction_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../config/theme.dart';

// FIX — removed unused lottie import (Lottie assets not bundled).
// Replaced Lottie.asset() with icon-based placeholder images that
// work without any asset files. Re-add lottie when you have the
// animation files ready.

class OnboardingScreen extends StatelessWidget {
  /// Called after the user taps Done or Skip.
  /// app.dart passes: () => setState(() => _hasSeenOnboarding = true)
  final VoidCallback onComplete;

  const OnboardingScreen({
    super.key,
    required this.onComplete,
  });

  Future<void> _onDone(BuildContext context) async {
    // Save the flag so AppStarted finds it on next cold start
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('has_seen_onboarding', true);

    // FIX — NO Navigator call here.
    // Calling onComplete() triggers setState in app.dart which
    // sets _hasSeenOnboarding = true and causes BlocBuilder to
    // re-render LoginScreen as the home widget.
    // Any Navigator call from here would push LoginScreen onto
    // the stack and leave it there even after login succeeds.
    onComplete();
  }

  @override
  Widget build(BuildContext context) {
    return IntroductionScreen(
      pages: [
        PageViewModel(
          title: "Welcome to chAs AI Creator",
          body:
              "Create stunning AI-powered videos in minutes. "
              "No editing skills required!",
          image: _buildIcon(Icons.auto_awesome, Colors.purple),
          decoration: _pageDecoration(),
        ),
        PageViewModel(
          title: "AI Script Writing",
          body:
              "Our AI writes engaging scripts for your videos. "
              "Just choose a topic and let the magic happen!",
          image: _buildIcon(Icons.edit_note_rounded, Colors.blue),
          decoration: _pageDecoration(),
        ),
        PageViewModel(
          title: "Stunning Visuals",
          body:
              "AI generates beautiful images and animations "
              "that match your script perfectly.",
          image: _buildIcon(Icons.image_rounded, Colors.teal),
          decoration: _pageDecoration(),
        ),
        PageViewModel(
          title: "Schedule & Publish",
          body:
              "Schedule videos to be created automatically and "
              "publish directly to your social media!",
          image: _buildIcon(Icons.schedule_rounded, Colors.orange),
          decoration: _pageDecoration(),
        ),
        PageViewModel(
          title: "Start Creating FREE",
          body:
              "Get started with 2 free videos daily. "
              "Upgrade anytime for unlimited creations!",
          image: _buildIcon(Icons.rocket_launch_rounded, Colors.green),
          decoration: _pageDecoration(),
        ),
      ],
      onDone: () => _onDone(context),
      onSkip: () => _onDone(context),
      showSkipButton: true,
      skip: const Text('Skip'),
      next: const Icon(Icons.arrow_forward),
      done: Text(
        'Get Started',
        style: TextStyle(fontWeight: FontWeight.w600),
      ),
      dotsDecorator: DotsDecorator(
        size: Size(10.w, 10.w),
        color: Colors.grey,
        activeSize: Size(22.w, 10.w),
        activeColor: AppTheme.primaryColor,
        activeShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(5.r),
        ),
      ),
    );
  }

  Widget _buildIcon(IconData icon, Color color) {
    return Container(
      padding: EdgeInsets.all(40.w),
      child: Container(
        width: 180.w,
        height: 180.w,
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 90.w, color: color),
      ),
    );
  }

  PageDecoration _pageDecoration() {
    return PageDecoration(
      titleTextStyle: TextStyle(
        fontSize: 24.sp,
        fontWeight: FontWeight.bold,
        color: AppTheme.textPrimaryLight,
      ),
      bodyTextStyle: TextStyle(
        fontSize: 16.sp,
        color: AppTheme.textSecondaryLight,
      ),
      imagePadding: EdgeInsets.only(top: 40.h),
      pageColor: Colors.white,
    );
  }
}
