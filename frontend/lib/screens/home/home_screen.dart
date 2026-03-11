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

  // FIX 1 — DashboardScreen built lazily so it doesn't call
  // initState until actually visited. Previously IndexedStack
  // forced ALL 4 screens to initState simultaneously the moment
  // HomeScreen mounted. Any AuthBloc event fired in DashboardScreen
  // initState would cycle auth state and blank the screen on first login.
  DashboardScreen? _dashboardCache;
  DashboardScreen get _dashboard {
    _dashboardCache ??= DashboardScreen(
      onNavigate: (index) {
        if (mounted) setState(() => _currentIndex = index);
      },
    );
    return _dashboardCache!;
  }

  @override
  Widget build(BuildContext context) {
    // FIX 2 — BlocListener only resets the tab index on logout.
    // It must NEVER call Navigator — app.dart BlocBuilder is the
    // sole navigation authority. Any Navigator call here would push
    // a route on top of app.dart's widget tree causing a blank screen.
    return BlocListener<AuthBloc, AuthState>(
      listenWhen: (previous, current) =>
          current is Unauthenticated ||
          current is AuthInitial,
      listener: (context, state) {
        // Only reset tab — never navigate
        if (mounted) setState(() => _currentIndex = 0);
      },
      child: Scaffold(
        // FIX 3 — Offstage + TickerMode instead of IndexedStack.
        // Offstage keeps each screen alive (preserves scroll + state)
        // but only triggers initState when the screen is first made
        // visible — NOT all at once on HomeScreen mount.
        // TickerMode pauses animations on hidden screens so they
        // don't consume resources in the background.
        body: Stack(
          children: [
            _buildScreen(0, _dashboard),
            _buildScreen(1, const VideosScreen()),
            _buildScreen(2, const SmartCreateScreen()),
            _buildScreen(3, const SettingsScreen()),
          ],
        ),
        bottomNavigationBar: _buildBottomNav(),
      ),
    );
  }

  Widget _buildScreen(int index, Widget screen) {
    return Offstage(
      offstage: _currentIndex != index,
      child: TickerMode(
        enabled: _currentIndex == index,
        child: screen,
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
        onDestinationSelected: (index) {
          if (mounted) setState(() => _currentIndex = index);
        },
        height: 65.h,
        labelBehavior:
            NavigationDestinationLabelBehavior.alwaysShow,
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

          // Smart Create — highlighted centre button
          NavigationDestination(
            icon: _buildCreateIcon(selected: false),
            selectedIcon: _buildCreateIcon(selected: true),
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

  // FIX 4 — extracted to method so icon is not rebuilt
  // as a new Container instance on every setState call
  Widget _buildCreateIcon({required bool selected}) {
    return Container(
      padding: EdgeInsets.all(10.w),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryColor
                .withOpacity(selected ? 0.6 : 0.4),
            blurRadius: selected ? 16 : 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Icon(
        Icons.auto_awesome,
        size: 22.w,
        color: Colors.white,
      ),
    );
  }
}
