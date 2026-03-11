/*
 * chAs AI Creator - Main Application Entry
 * FILE: lib/main.dart
 *
 * AI-powered video content automation platform
 * Nigeria Friendly Version - No Firebase, Uses Custom JWT & Unity Ads
 */

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import 'app.dart';
import 'config/theme.dart';
import 'providers/auth_bloc.dart';
import 'services/ad_service.dart';
import 'services/auth_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Error handling (no Firebase Crashlytics — Nigeria friendly)
  FlutterError.onError = (errorDetails) {
    if (kDebugMode) {
      print('Flutter Error: ${errorDetails.exception}');
    }
  };

  PlatformDispatcher.instance.onError = (error, stack) {
    if (kDebugMode) {
      print('Platform Error: $error');
    }
    return true;
  };

  // Lock to portrait
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // FIX 1 — use light status bar icons so they are visible on the
  // dark splash/login backgrounds. Was Brightness.dark which made
  // the status bar icons invisible on dark screens.
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  // FIX 2 — Ad init moved AFTER runApp so it never delays app startup.
  // Previously it awaited AdService.initialize() before runApp, meaning
  // the user saw a blank screen for however long Unity Ads took to init.
  // Now the app renders immediately and ads init in the background.
  runApp(const ChAsAICreatorApp());

  // Init ads after first frame — non-blocking
  try {
    await AdService().initialize();
  } catch (e) {
    if (kDebugMode) {
      print('Ad Service Init Error: $e');
    }
  }
}

class ChAsAICreatorApp extends StatelessWidget {
  const ChAsAICreatorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ScreenUtilInit(
      designSize: const Size(375, 812),
      minTextAdapt: true,
      splitScreenMode: true,
      builder: (context, child) {
        return MultiBlocProvider(
          providers: [
            BlocProvider(
              // AppStarted() is dispatched from app.dart initState
              // AFTER onboarding prefs are loaded — not here.
              // Dispatching here AND in app.dart caused a double auth
              // check and an AuthLoading flicker on every cold start.
              create: (context) =>
                  AuthBloc(authService: AuthService()),
            ),
          ],
          child: MaterialApp(
            title: 'chAs AI Creator',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.lightTheme,
            darkTheme: AppTheme.darkTheme,
            themeMode: ThemeMode.system,
            home: const App(),
          ),
        );
      },
    );
  }
}
