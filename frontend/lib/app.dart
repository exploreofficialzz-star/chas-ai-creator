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

class App extends StatefulWidget {
  const App({super.key});

  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  // FIX 1 — onboarding stored as a plain bool, NOT a FutureBuilder.
  // null = still loading (show splash), true/false = ready.
  // This completely eliminates the FutureBuilder that was blocking
  // BlocBuilder from reacting to Authenticated on first login.
  bool? _hasSeenOnboarding;

  @override
  void initState() {
    super.initState();
    _initApp();
  }

  // FIX 2 — load onboarding status FIRST, then dispatch AppStarted.
  // Old code dispatched AppStarted immediately in initState while
  // FutureBuilder was still running — creating a race where
  // Authenticated could arrive before FutureBuilder finished,
  // and the nested SplashScreen swallowed the navigation.
  Future<void> _initApp() async {
    final prefs = await SharedPreferences.getInstance();
    final seen = prefs.getBool('has_seen_onboarding') ?? false;

    if (!mounted) return;

    setState(() => _hasSeenOnboarding = seen);

    // FIX 3 — AppStarted is only dispatched AFTER onboarding is
    // known. This guarantees the BlocBuilder always has a
    // _hasSeenOnboarding value ready when any auth state arrives.
    context.read<AuthBloc>().add(AppStarted());
  }

  @override
  Widget build(BuildContext context) {
    // FIX 4 — while onboarding status is loading, show splash
    // outside BlocBuilder so there is zero FutureBuilder nesting.
    if (_hasSeenOnboarding == null) {
      return const SplashScreen();
    }

    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {

        // ── Loading / initialising ───────────────────────────────
        if (state is AuthInitial || state is AuthLoading) {
          return const SplashScreen();
        }

        // ── Authenticated ────────────────────────────────────────
        // This now fires INSTANTLY with nothing blocking it.
        // No FutureBuilder, no nested async, no race condition.
        if (state is Authenticated) {
          return const HomeScreen();
        }

        // ── Unauthenticated / error / password reset sent ────────
        // FIX 5 — PasswordResetSent extends Unauthenticated so it
        // falls through here correctly and keeps LoginScreen visible.
        // FIX 6 — Plain bool check, zero async inside BlocBuilder.
        if (!_hasSeenOnboarding!) {
          return const OnboardingScreen();
        }
        return const LoginScreen();
      },
    );
  }
}
