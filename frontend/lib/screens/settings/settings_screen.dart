import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../models/user.dart';
import '../../providers/auth_bloc.dart';
import '../../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final ApiService _apiService = ApiService();
  UserSettings? _settings;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final settings = await _apiService.getUserSettings();
      setState(() {
        _settings = settings;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _updateSettings(UserSettings newSettings) async {
    try {
      await _apiService.updateUserSettings(newSettings);
      setState(() => _settings = newSettings);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update settings: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: EdgeInsets.all(16.w),
              children: [
                // Account Section
                _buildSection('Account'),
                _buildListTile(
                  icon: Icons.person,
                  title: 'Profile',
                  subtitle: 'Edit your profile information',
                  onTap: () {
                    // Navigate to profile
                  },
                ),
                _buildListTile(
                  icon: Icons.workspace_premium,
                  title: 'Subscription',
                  subtitle: 'Manage your subscription',
                  onTap: () {
                    // Navigate to subscription
                  },
                ),
                _buildListTile(
                  icon: Icons.payment,
                  title: 'Payment History',
                  subtitle: 'View your payment history',
                  onTap: () {
                    // Navigate to payment history
                  },
                ),
                
                SizedBox(height: 24.h),
                
                // Default Settings Section
                _buildSection('Default Video Settings'),
                _buildListTile(
                  icon: Icons.category,
                  title: 'Default Niche',
                  subtitle: _settings?.defaultNiche ?? 'General',
                  onTap: () => _showNicheSelector(),
                ),
                _buildListTile(
                  icon: Icons.timer,
                  title: 'Default Duration',
                  subtitle: '${_settings?.defaultVideoLength ?? 30} seconds',
                  onTap: () => _showDurationSelector(),
                ),
                _buildListTile(
                  icon: Icons.aspect_ratio,
                  title: 'Default Aspect Ratio',
                  subtitle: _settings?.defaultAspectRatio ?? '9:16',
                  onTap: () => _showAspectRatioSelector(),
                ),
                _buildListTile(
                  icon: Icons.style,
                  title: 'Default Style',
                  subtitle: _settings?.defaultStyle ?? 'Cinematic',
                  onTap: () => _showStyleSelector(),
                ),
                
                SizedBox(height: 24.h),
                
                // Caption Settings
                _buildSection('Caption Settings'),
                SwitchListTile(
                  secondary: const Icon(Icons.closed_caption),
                  title: const Text('Enable Captions'),
                  subtitle: const Text('Show captions by default'),
                  value: _settings?.captionsEnabled ?? true,
                  onChanged: (value) {
                    if (_settings != null) {
                      _updateSettings(_settings!.copyWith(captionsEnabled: value));
                    }
                  },
                ),
                _buildListTile(
                  icon: Icons.text_fields,
                  title: 'Caption Style',
                  subtitle: _settings?.captionStyle ?? 'Modern',
                  onTap: () => _showCaptionStyleSelector(),
                ),
                SwitchListTile(
                  secondary: const Icon(Icons.emoji_emotions),
                  title: const Text('Emoji in Captions'),
                  subtitle: const Text('Include emojis in captions'),
                  value: _settings?.captionEmojiEnabled ?? true,
                  onChanged: (value) {
                    if (_settings != null) {
                      _updateSettings(_settings!.copyWith(captionEmojiEnabled: value));
                    }
                  },
                ),
                
                SizedBox(height: 24.h),
                
                // Music Settings
                _buildSection('Music Settings'),
                SwitchListTile(
                  secondary: const Icon(Icons.music_note),
                  title: const Text('Background Music'),
                  subtitle: const Text('Add music to videos by default'),
                  value: _settings?.backgroundMusicEnabled ?? true,
                  onChanged: (value) {
                    if (_settings != null) {
                      _updateSettings(_settings!.copyWith(backgroundMusicEnabled: value));
                    }
                  },
                ),
                _buildListTile(
                  icon: Icons.audiotrack,
                  title: 'Music Style',
                  subtitle: _settings?.backgroundMusicStyle ?? 'Upbeat',
                  onTap: () => _showMusicStyleSelector(),
                ),
                
                SizedBox(height: 24.h),
                
                // Notifications
                _buildSection('Notifications'),
                SwitchListTile(
                  secondary: const Icon(Icons.email),
                  title: const Text('Email Notifications'),
                  value: _settings?.emailNotificationsEnabled ?? true,
                  onChanged: (value) {
                    if (_settings != null) {
                      _updateSettings(_settings!.copyWith(emailNotificationsEnabled: value));
                    }
                  },
                ),
                SwitchListTile(
                  secondary: const Icon(Icons.notifications),
                  title: const Text('Push Notifications'),
                  value: _settings?.pushNotificationsEnabled ?? true,
                  onChanged: (value) {
                    if (_settings != null) {
                      _updateSettings(_settings!.copyWith(pushNotificationsEnabled: value));
                    }
                  },
                ),
                SwitchListTile(
                  secondary: const Icon(Icons.check_circle),
                  title: const Text('Video Complete'),
                  subtitle: const Text('Notify when video generation completes'),
                  value: _settings?.notifyOnVideoComplete ?? true,
                  onChanged: (value) {
                    if (_settings != null) {
                      _updateSettings(_settings!.copyWith(notifyOnVideoComplete: value));
                    }
                  },
                ),
                
                SizedBox(height: 24.h),
                
                // Privacy & Security
                _buildSection('Privacy & Security'),
                _buildListTile(
                  icon: Icons.download,
                  title: 'Export Data',
                  subtitle: 'Download all your data',
                  onTap: () {
                    // Export data
                  },
                ),
                _buildListTile(
                  icon: Icons.delete_forever,
                  title: 'Delete Account',
                  subtitle: 'Permanently delete your account',
                  onTap: () => _showDeleteAccountConfirmation(),
                  textColor: Colors.red,
                ),
                
                SizedBox(height: 24.h),
                
                // About
                _buildSection('About'),
                _buildListTile(
                  icon: Icons.info,
                  title: 'About AI Creator',
                  subtitle: 'Version 1.0.0',
                  onTap: () {
                    // Show about dialog
                  },
                ),
                _buildListTile(
                  icon: Icons.privacy_tip,
                  title: 'Privacy Policy',
                  onTap: () {
                    // Open privacy policy
                  },
                ),
                _buildListTile(
                  icon: Icons.description,
                  title: 'Terms of Service',
                  onTap: () {
                    // Open terms
                  },
                ),
                
                SizedBox(height: 24.h),
                
                // Logout
                ElevatedButton.icon(
                  onPressed: () {
                    context.read<AuthBloc>().add(LoggedOut());
                  },
                  icon: const Icon(Icons.logout),
                  label: const Text('Logout'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                    foregroundColor: Colors.white,
                    padding: EdgeInsets.symmetric(vertical: 16.h),
                  ),
                ),
                
                SizedBox(height: 32.h),
              ],
            ),
    );
  }

  Widget _buildSection(String title) {
    return Padding(
      padding: EdgeInsets.only(left: 16.w, bottom: 8.h),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
          color: AppTheme.primaryColor,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildListTile({
    required IconData icon,
    required String title,
    String? subtitle,
    required VoidCallback onTap,
    Color? textColor,
  }) {
    return ListTile(
      leading: Icon(icon),
      title: Text(
        title,
        style: textColor != null ? TextStyle(color: textColor) : null,
      ),
      subtitle: subtitle != null ? Text(subtitle) : null,
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }

  void _showNicheSelector() {
    // Show niche selector dialog
  }

  void _showDurationSelector() {
    // Show duration selector dialog
  }

  void _showAspectRatioSelector() {
    // Show aspect ratio selector dialog
  }

  void _showStyleSelector() {
    // Show style selector dialog
  }

  void _showCaptionStyleSelector() {
    // Show caption style selector dialog
  }

  void _showMusicStyleSelector() {
    // Show music style selector dialog
  }

  void _showDeleteAccountConfirmation() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Account'),
        content: const Text(
          'Are you sure you want to delete your account? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              // Delete account
            },
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
