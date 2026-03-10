import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../providers/auth_bloc.dart';
import '../dashboard/dashboard_screen.dart';
import '../settings/settings_screen.dart';
import '../video/smart_create_screen.dart';
import '../video/videos_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  late final List<Widget> _screens = [
    DashboardScreen(
      onNavigate: (index) => setState(() => _currentIndex = index),
    ),
    const VideosScreen(),
    const SmartCreateScreen(),
    const SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return BlocListener<AuthBloc, AuthState>(
      listener: (context, state) {
        // If user gets logged out from anywhere, reset tab to dashboard
        if (state is AuthInitial || state is Unauthenticated) {
          setState(() => _currentIndex = 0);
        }
      },
      child: Scaffold(
        body: IndexedStack(
          index: _currentIndex,
          children: _screens,
        ),
        bottomNavigationBar: _buildBottomNav(),
      ),
    );
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: BoxDecoration(
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 20,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) =>
            setState(() => _currentIndex = index),
        height: 65.h,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [
          // Dashboard
          NavigationDestination(
            icon: const Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(
              Icons.dashboard,
              color: AppTheme.primaryColor,
            ),
            label: 'Dashboard',
          ),

          // My Videos
          NavigationDestination(
            icon: const Icon(Icons.video_library_outlined),
            selectedIcon: Icon(
              Icons.video_library,
              color: AppTheme.primaryColor,
            ),
            label: 'My Videos',
          ),

          // Smart Create — highlighted center button
          NavigationDestination(
            icon: Container(
              padding: EdgeInsets.all(10.w),
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withOpacity(0.4),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Icon(
                Icons.auto_awesome,
                size: 22.w,
                color: Colors.white,
              ),
            ),
            selectedIcon: Container(
              padding: EdgeInsets.all(10.w),
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withOpacity(0.6),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Icon(
                Icons.auto_awesome,
                size: 22.w,
                color: Colors.white,
              ),
            ),
            label: 'Create',
          ),

          // Settings
          NavigationDestination(
            icon: const Icon(Icons.settings_outlined),
            selectedIcon: Icon(
              Icons.settings,
              color: AppTheme.primaryColor,
            ),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
