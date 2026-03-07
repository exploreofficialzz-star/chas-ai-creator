/*
 * chAs AI Creator - Onboarding Screen
 * Created by: chAs
 * User-friendly introduction to the app
 */

import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:introduction_screen/introduction_screen.dart';
import 'package:lottie/lottie.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../config/theme.dart';
import '../auth/login_screen.dart';

class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  Future<void> _onDone(BuildContext context) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('has_seen_onboarding', true);
    
    if (context.mounted) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return IntroductionScreen(
      pages: [
        // Page 1: Welcome
        PageViewModel(
          title: "Welcome to chAs AI Creator",
          body: "Create stunning AI-powered videos in minutes. No editing skills required!",
          image: _buildImage('assets/animations/welcome.json'),
          decoration: _getPageDecoration(),
        ),
        
        // Page 2: AI Script Generation
        PageViewModel(
          title: "AI Script Writing",
          body: "Our AI writes engaging scripts for your videos. Just choose a topic and let the magic happen!",
          image: _buildImage('assets/animations/ai_writing.json'),
          decoration: _getPageDecoration(),
        ),
        
        // Page 3: Visual Generation
        PageViewModel(
          title: "Stunning Visuals",
          body: "AI generates beautiful images and animations that match your script perfectly.",
          image: _buildImage('assets/animations/visuals.json'),
          decoration: _getPageDecoration(),
        ),
        
        // Page 4: Auto Publishing
        PageViewModel(
          title: "Schedule & Publish",
          body: "Schedule videos to be created automatically and publish directly to your social media!",
          image: _buildImage('assets/animations/publish.json'),
          decoration: _getPageDecoration(),
        ),
        
        // Page 5: Free to Use
        PageViewModel(
          title: "Start Creating FREE",
          body: "Get started with 2 free videos daily. Upgrade anytime for unlimited creations!",
          image: _buildImage('assets/animations/free.json'),
          decoration: _getPageDecoration(),
        ),
      ],
      onDone: () => _onDone(context),
      onSkip: () => _onDone(context),
      showSkipButton: true,
      skip: const Text('Skip'),
      next: const Icon(Icons.arrow_forward),
      done: const Text('Get Started', style: TextStyle(fontWeight: FontWeight.w600)),
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

  Widget _buildImage(String assetPath) {
    return Container(
      padding: EdgeInsets.all(40.w),
      child: Lottie.asset(
        assetPath,
        height: 250.h,
        fit: BoxFit.contain,
      ),
    );
  }

  PageDecoration _getPageDecoration() {
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

/// Simple onboarding page widget
class OnboardingPage extends StatelessWidget {
  final String title;
  final String description;
  final String animationAsset;
  final Color backgroundColor;

  const OnboardingPage({
    super.key,
    required this.title,
    required this.description,
    required this.animationAsset,
    this.backgroundColor = Colors.white,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: backgroundColor,
      padding: EdgeInsets.all(24.w),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Lottie.asset(
            animationAsset,
            height: 250.h,
            fit: BoxFit.contain,
          ),
          SizedBox(height: 40.h),
          Text(
            title,
            style: TextStyle(
              fontSize: 28.sp,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimaryLight,
            ),
            textAlign: TextAlign.center,
          ),
          SizedBox(height: 16.h),
          Text(
            description,
            style: TextStyle(
              fontSize: 16.sp,
              color: AppTheme.textSecondaryLight,
              height: 1.5,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
