/*
 * chAs AI Creator - Main Application Entry
 * Created by: chAs
 * Copyright (c) 2024 chAs. All rights reserved.
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
  
  // NOTE: Firebase initialization removed - Nigeria Friendly Version
  // Using Custom JWT Authentication instead of Firebase Auth
  
  // Initialize error handling (without Firebase Crashlytics)
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
  
  // Initialize Unity Ads (Nigeria Friendly - replaces Google AdMob)
  try {
    await AdService().initialize();
  } catch (e) {
    if (kDebugMode) {
      print('Ad Service Init Error: $e');
    }
  }
  
  // Set preferred orientations
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  
  // Set system UI overlay style
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: Colors.white,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );
  
  runApp(const ChAsAICreatorApp());
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
              // FIX 1 - Removed ..add(AppStarted()) from here
              // app.dart already fires AppStarted() in initState
              // firing it twice caused double auth check and loading flicker
              create: (context) => AuthBloc(authService: AuthService()),
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
