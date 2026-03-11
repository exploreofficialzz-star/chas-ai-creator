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
  // FIX 1 — cache the future so FutureBuilder doesn't re-fire on every
  // BlocBuilder rebuild. Without this, every auth state change (e.g. going
  // from AuthLoading → Unauthenticated) recreates the future and flickers
  // back to SplashScreen before settling on LoginScreen.
  late final Future<bool> _onboardingFuture = _checkOnboarding();

  @override
  void initState() {
    super.initState();
    // FIX 2 — added mounted guard so AppStarted is never dispatched
    // after the widget is removed from the tree
    Future.microtask(() {
      if (mounted) context.read<AuthBloc>().add(AppStarted());
    });
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {
        // ── Initialising / loading ───────────────────────────────────
        if (state is AuthInitial || state is AuthLoading) {
          return const SplashScreen();
        }

        // ── Authenticated ────────────────────────────────────────────
        // FIX 3 — THIS is the only navigation that should happen after
        // login/register. LoginScreen must NOT call
        // Navigator.pushReplacementNamed('/home') — that named route
        // doesn't exist and will crash or push a blank screen.
        // When AuthBloc emits Authenticated, this BlocBuilder fires and
        // replaces the entire widget tree with HomeScreen automatically.
        if (state is Authenticated) {
          return const HomeScreen();
        }

        // ── Unauthenticated / error ──────────────────────────────────
        if (state is Unauthenticated || state is AuthError) {
          return FutureBuilder<bool>(
            future: _onboardingFuture, // FIX 1 — reuse cached future
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

        // ── Fallback ─────────────────────────────────────────────────
        return const SplashScreen();
      },
    );
  }

  Future<bool> _checkOnboarding() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('has_seen_onboarding') ?? false;
  }
}
