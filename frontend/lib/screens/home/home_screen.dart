import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../providers/auth_bloc.dart';
import '../dashboard/dashboard_screen.dart';
import '../settings/settings_screen.dart';
import '../video/create_video_screen.dart';
import '../video/videos_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  // FIX - changed to late so setState can be used inside the callback
  late final List<Widget> _screens = [
    DashboardScreen(onNavigate: (index) {
      setState(() => _currentIndex = index);
    }),
    const VideosScreen(),
    const CreateVideoScreen(),
    const SettingsScreen(),
  ];

  final List<String> _titles = [
    'Dashboard',
    'My Videos',
    'Create',
    'Settings',
  ];

  final List<IconData> _icons = [
    Icons.dashboard_outlined,
    Icons.video_library_outlined,
    Icons.add_circle_outline,
    Icons.settings_outlined,
  ];

  final List<IconData> _selectedIcons = [
    Icons.dashboard,
    Icons.video_library,
    Icons.add_circle,
    Icons.settings,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() => _currentIndex = index);
        },
        destinations: [
          NavigationDestination(
            icon: Icon(_icons[0]),
            selectedIcon: Icon(_selectedIcons[0]),
            label: _titles[0],
          ),
          NavigationDestination(
            icon: Icon(_icons[1]),
            selectedIcon: Icon(_selectedIcons[1]),
            label: _titles[1],
          ),
          NavigationDestination(
            icon: Icon(_icons[2]),
            selectedIcon: Icon(_selectedIcons[2]),
            label: _titles[2],
          ),
          NavigationDestination(
            icon: Icon(_icons[3]),
            selectedIcon: Icon(_selectedIcons[3]),
            label: _titles[3],
          ),
        ],
      ),
    );
  }
}
