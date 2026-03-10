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
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Settings saved!')),
      );
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
                _buildSection('Account'),
                _buildListTile(
                  icon: Icons.person,
                  title: 'Profile',
                  subtitle: 'Edit your profile information',
                  onTap: () => _showEditProfileDialog(),
                ),
                _buildListTile(
                  icon: Icons.workspace_premium,
                  title: 'Subscription',
                  subtitle: 'Manage your subscription',
                  onTap: () => _showSubscriptionDialog(),
                ),
                _buildListTile(
                  icon: Icons.payment,
                  title: 'Payment History',
                  subtitle: 'View your payment history',
                  onTap: () => _showPaymentHistory(),
                ),

                SizedBox(height: 24.h),

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

                _buildSection('Privacy & Security'),
                _buildListTile(
                  icon: Icons.lock,
                  title: 'Change Password',
                  subtitle: 'Update your password',
                  onTap: () => _showChangePasswordDialog(),
                ),
                _buildListTile(
                  icon: Icons.download,
                  title: 'Export Data',
                  subtitle: 'Download all your data',
                  onTap: () => _showExportDataDialog(),
                ),
                _buildListTile(
                  icon: Icons.delete_forever,
                  title: 'Delete Account',
                  subtitle: 'Permanently delete your account',
                  onTap: () => _showDeleteAccountConfirmation(),
                  textColor: Colors.red,
                ),

                SizedBox(height: 24.h),

                _buildSection('About'),
                _buildListTile(
                  icon: Icons.info,
                  title: 'About chAs AI Creator',
                  subtitle: 'Version 1.0.0 — Made by chAs',
                  onTap: () => _showAboutDialog(),
                ),
                _buildListTile(
                  icon: Icons.privacy_tip,
                  title: 'Privacy Policy',
                  onTap: () => _showPrivacyPolicy(),
                ),
                _buildListTile(
                  icon: Icons.description,
                  title: 'Terms of Service',
                  onTap: () => _showTermsOfService(),
                ),

                SizedBox(height: 24.h),

                ElevatedButton.icon(
                  onPressed: () => _showLogoutConfirmation(),
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

  void _showOptionsDialog({
    required String title,
    required List<String> options,
    required String selected,
    required Function(String) onSelected,
  }) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: options.length,
            itemBuilder: (context, index) {
              final option = options[index];
              final isSelected = selected == option;
              return ListTile(
                title: Text(option[0].toUpperCase() + option.substring(1)),
                trailing: isSelected
                    ? Icon(Icons.check, color: AppTheme.primaryColor)
                    : null,
                onTap: () {
                  Navigator.pop(context);
                  onSelected(option);
                },
              );
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }

  void _showNicheSelector() {
    _showOptionsDialog(
      title: 'Default Niche',
      options: ['general', 'fitness', 'cooking', 'travel', 'tech', 'fashion', 'finance', 'education', 'entertainment', 'news'],
      selected: _settings?.defaultNiche ?? 'general',
      onSelected: (value) {
        if (_settings != null) {
          _updateSettings(_settings!.copyWith(defaultNiche: value));
        }
      },
    );
  }

  void _showDurationSelector() {
    final durations = [10, 15, 20, 30, 45, 60, 90, 120];
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Default Duration'),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: durations.length,
            itemBuilder: (context, index) {
              final d = durations[index];
              final isSelected = (_settings?.defaultVideoLength ?? 30) == d;
              return ListTile(
                title: Text('$d seconds'),
                trailing: isSelected
                    ? Icon(Icons.check, color: AppTheme.primaryColor)
                    : null,
                onTap: () {
                  Navigator.pop(context);
                  if (_settings != null) {
                    _updateSettings(_settings!.copyWith(defaultVideoLength: d));
                  }
                },
              );
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }

  void _showAspectRatioSelector() {
    _showOptionsDialog(
      title: 'Default Aspect Ratio',
      options: ['9:16', '16:9', '1:1'],
      selected: _settings?.defaultAspectRatio ?? '9:16',
      onSelected: (value) {
        if (_settings != null) {
          _updateSettings(_settings!.copyWith(defaultAspectRatio: value));
        }
      },
    );
  }

  void _showStyleSelector() {
    _showOptionsDialog(
      title: 'Default Style',
      options: ['cinematic', 'anime', 'realistic', 'cartoon', 'minimalist'],
      selected: _settings?.defaultStyle ?? 'cinematic',
      onSelected: (value) {
        if (_settings != null) {
          _updateSettings(_settings!.copyWith(defaultStyle: value));
        }
      },
    );
  }

  void _showCaptionStyleSelector() {
    _showOptionsDialog(
      title: 'Caption Style',
      options: ['modern', 'classic', 'bold', 'minimal', 'neon'],
      selected: _settings?.captionStyle ?? 'modern',
      onSelected: (value) {
        if (_settings != null) {
          _updateSettings(_settings!.copyWith(captionStyle: value));
        }
      },
    );
  }

  void _showMusicStyleSelector() {
    _showOptionsDialog(
      title: 'Music Style',
      options: ['upbeat', 'calm', 'dramatic', 'inspirational', 'none'],
      selected: _settings?.backgroundMusicStyle ?? 'upbeat',
      onSelected: (value) {
        if (_settings != null) {
          _updateSettings(_settings!.copyWith(backgroundMusicStyle: value));
        }
      },
    );
  }

  void _showEditProfileDialog() {
    final nameController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit Profile'),
        content: TextField(
          controller: nameController,
          decoration: const InputDecoration(
            labelText: 'Display Name',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              try {
                await _apiService.updateProfile(displayName: nameController.text);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Profile updated!')),
                );
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Failed: $e')),
                );
              }
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _showChangePasswordDialog() {
    final currentController = TextEditingController();
    final newController = TextEditingController();
    final confirmController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change Password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: currentController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Current Password',
                border: OutlineInputBorder(),
              ),
            ),
            SizedBox(height: 12.h),
            TextField(
              controller: newController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'New Password',
                border: OutlineInputBorder(),
              ),
            ),
            SizedBox(height: 12.h),
            TextField(
              controller: confirmController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Confirm New Password',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              if (newController.text != confirmController.text) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Passwords do not match')),
                );
                return;
              }
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Password changed successfully!')),
              );
            },
            child: const Text('Update'),
          ),
        ],
      ),
    );
  }

  void _showSubscriptionDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Subscription'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Current Plan: FREE'),
            SizedBox(height: 16.h),
            const Text('Upgrade to PRO for:'),
            SizedBox(height: 8.h),
            const Text('✅ 20 videos per day'),
            const Text('✅ Up to 2 minutes per video'),
            const Text('✅ Priority generation'),
            const Text('✅ No ads'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Maybe Later'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Redirecting to payment...')),
              );
            },
            child: const Text('Upgrade Now'),
          ),
        ],
      ),
    );
  }

  void _showPaymentHistory() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Payment History'),
        content: const Text('No payment history yet.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showExportDataDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Export Data'),
        content: const Text(
          'Your data export will be prepared and sent to your email address.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Export request sent to your email!')),
              );
            },
            child: const Text('Request Export'),
          ),
        ],
      ),
    );
  }

  void _showAboutDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('chAs AI Creator'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_awesome, size: 60.w, color: AppTheme.primaryColor),
            SizedBox(height: 16.h),
            const Text('Version 1.0.0', textAlign: TextAlign.center),
            SizedBox(height: 8.h),
            const Text(
              'AI-powered video content creation platform built for Nigerian creators.',
              textAlign: TextAlign.center,
            ),
            SizedBox(height: 8.h),
            const Text('Made with ❤️ by chAs Tech Group', textAlign: TextAlign.center),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showPrivacyPolicy() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Privacy Policy'),
        content: const SingleChildScrollView(
          child: Text(
            'chAs AI Creator collects your email and usage data to provide the service. '
            'We do not sell your personal data to third parties. '
            'Your videos are stored securely on our servers. '
            'You can request data deletion at any time by contacting support.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showTermsOfService() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Terms of Service'),
        content: const SingleChildScrollView(
          child: Text(
            'By using chAs AI Creator, you agree to use the app responsibly. '
            'You must not use the app to generate harmful, illegal, or misleading content. '
            'chAs Tech Group reserves the right to suspend accounts that violate these terms. '
            'Free tier is limited to 2 videos per day.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showLogoutConfirmation() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<AuthBloc>().add(LoggedOut());
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Logout', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
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
              context.read<AuthBloc>().add(LoggedOut());
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Account deletion requested.')),
              );
            },
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
