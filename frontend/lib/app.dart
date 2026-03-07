app.dart
/*
 * chAs AI Creator - App Root Widget
 * Created by: chAs
 * Main app entry with routing and auth handling
 */

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'providers/auth_bloc.dart';
import 'screens/auth/login_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/onboarding/onboarding_screen.dart';
import 'screens/splash_screen.dart';

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {
        // Show splash screen while checking auth
        if (state is AuthInitial) {
          return const SplashScreen();
        }
        
        // Show onboarding for new users
        if (state is AuthInitial) {
          return FutureBuilder<bool>(
            future: _checkOnboarding(),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const SplashScreen();
              }
              
              final hasSeenOnboarding = snapshot.data ?? false;
              if (!hasSeenOnboarding) {
                return const OnboardingScreen();
              }
              
              return const LoginScreen();
            },
          );
        }
        
        // User is authenticated
        if (state is Authenticated) {
          return const HomeScreen();
        }
        
        // User is not authenticated
        if (state is Unauthenticated) {
          return FutureBuilder<bool>(
            future: _checkOnboarding(),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const SplashScreen();
              }
              
              final hasSeenOnboarding = snapshot.data ?? false;
              if (!hasSeenOnboarding) {
                return const OnboardingScreen();
              }
              
              return const LoginScreen();
            },
          );
        }
        
        // Default to splash
        return const SplashScreen();
      },
    );
  }

  Future<bool> _checkOnboarding() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('has_seen_onboarding') ?? false;
  }
}
