/*
 * chAs AI Creator - App Root Widget
 * FILE: lib/app.dart
 *
 * FIXES APPLIED:
 * 1. buildWhen skips AuthLoading + AuthError during active login
 *    so LoginScreen is never unmounted mid-login (frozen splash fix)
 * 2. OnboardingScreen receives onComplete callback — no Navigator
 *    call from onboarding that leaves LoginScreen on the stack
 */

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'providers/auth_bloc.dart';
import 'screens/auth/login_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/onboarding/onboarding_screen.dart';
import 'screens/splash_screen.dart';

class App extends StatefulWidget {
  const App({super.key});

  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  bool? _hasSeenOnboarding;

  @override
  void initState() {
    super.initState();
    _initApp();
  }

  Future<void> _initApp() async {
    final prefs = await SharedPreferences.getInstance();
    final seen = prefs.getBool('has_seen_onboarding') ?? false;
    if (!mounted) return;
    setState(() => _hasSeenOnboarding = seen);
    context.read<AuthBloc>().add(AppStarted());
  }

  @override
  Widget build(BuildContext context) {
    if (_hasSeenOnboarding == null) {
      return const SplashScreen();
    }

    return BlocBuilder<AuthBloc, AuthState>(
      // ── THE LOGIN FIX ────────────────────────────────────────────
      // Skip AuthLoading rebuilds (except from AuthInitial) so
      // LoginScreen stays mounted during the entire login attempt.
      // Skip AuthError rebuilds so LoginScreen's BlocListener can
      // show the error snackbar without being unmounted first.
      buildWhen: (previous, current) {
        if (current is AuthLoading && previous is! AuthInitial) {
          return false;
        }
        if (current is AuthError) return false;
        return true;
      },
      builder: (context, state) {
        if (state is AuthInitial || state is AuthLoading) {
          return const SplashScreen();
        }

        if (state is Authenticated) {
          return const HomeScreen();
        }

        // Unauthenticated / PasswordResetSent
        if (!_hasSeenOnboarding!) {
          // FIX — pass onComplete callback so OnboardingScreen
          // never calls Navigator itself. When onboarding is done,
          // we update _hasSeenOnboarding here and BlocBuilder
          // re-renders LoginScreen cleanly as the home widget.
          return OnboardingScreen(
            onComplete: () {
              setState(() => _hasSeenOnboarding = true);
            },
          );
        }

        return const LoginScreen();
      },
    );
  }
}
