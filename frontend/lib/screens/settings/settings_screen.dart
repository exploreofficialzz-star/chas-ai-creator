import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../models/user.dart';
import '../../providers/auth_bloc.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final ApiService  _apiService  = ApiService();
  final AuthService _authService = AuthService();

  UserSettings? _settings;
  bool _isLoading = true;
  bool _isSaving  = false;
  Timer? _saveDebounce;

  // FIX 1 — _user is NEVER stored locally in this screen.
  // We always read it from AuthBloc so the entire app stays in sync.
  User? get _user {
    final state = context.read<AuthBloc>().state;
    return state is Authenticated ? state.user : null;
  }

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  @override
  void dispose() {
    _saveDebounce?.cancel();
    super.dispose();
  }

  // FIX 2 — only load settings here; user comes from AuthBloc
  Future<void> _loadSettings() async {
    try {
      final settings = await _apiService.getUserSettings();
      if (mounted) {
        setState(() {
          _settings = settings ?? _defaultSettings();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _settings = _defaultSettings();
          _isLoading = false;
        });
      }
    }
  }

  UserSettings _defaultSettings() => UserSettings(
        defaultNiche: 'general',
        defaultVideoLength: 30,
        defaultAspectRatio: '9:16',
        defaultStyle: 'cinematic',
        captionsEnabled: true,
        captionStyle: 'modern',
        captionEmojiEnabled: true,
        backgroundMusicEnabled: true,
        backgroundMusicStyle: 'upbeat',
        emailNotificationsEnabled: true,
        pushNotificationsEnabled: true,
        notifyOnVideoComplete: true,
        defaultAudioMode: 'narration',
        defaultVoiceStyle: 'professional',
        characterConsistencyEnabled: false,
        defaultTargetPlatforms: ['tiktok'],
      );

  void _updateSettings(UserSettings newSettings) {
    setState(() => _settings = newSettings);
    _saveDebounce?.cancel();
    _saveDebounce =
        Timer(const Duration(milliseconds: 800), () async {
      if (!mounted) return;
      setState(() => _isSaving = true);
      try {
        await _apiService.updateUserSettings(newSettings);
        if (mounted) setState(() => _isSaving = false);
      } catch (e) {
        if (mounted) {
          setState(() => _isSaving = false);
          _showToast('❌ ${_apiService.handleError(e)}',
              error: true);
        }
      }
    });
  }

  void _showToast(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor:
            error ? Colors.red.shade700 : Colors.green.shade700,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10.r)),
        margin: EdgeInsets.all(12.w),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD
  // ─────────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    // FIX 3 — BlocBuilder wraps the whole screen so every widget that
    // reads _user automatically rebuilds when AuthBloc emits UpdateUser.
    // This is what makes the profile card + dashboard stay in sync.
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, authState) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('Settings'),
            actions: [
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                child: _isSaving
                    ? Padding(
                        key: const ValueKey('saving'),
                        padding: EdgeInsets.only(right: 16.w),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            SizedBox(
                              width: 14.w,
                              height: 14.w,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppTheme.primaryColor,
                              ),
                            ),
                            SizedBox(width: 6.w),
                            Text('Saving…',
                                style: TextStyle(
                                    fontSize: 12.sp,
                                    color: Colors.grey)),
                          ],
                        ),
                      )
                    : const SizedBox.shrink(
                        key: ValueKey('idle')),
              ),
            ],
          ),
          body: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _loadSettings,
                  child: ListView(
                    padding: EdgeInsets.symmetric(
                        horizontal: 16.w, vertical: 8.h),
                    children: [
                      _buildProfileCard(),
                      SizedBox(height: 24.h),

                      _buildSectionHeader('🔐 Account'),
                      _buildCard([
                        _buildTile(
                          icon: Icons.person_outline,
                          title: 'Edit Profile',
                          subtitle: _user?.displayName ??
                              _user?.email ??
                              '',
                          onTap: _showEditProfileDialog,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.workspace_premium_outlined,
                          title: 'Subscription',
                          subtitle: _subscriptionLabel(),
                          trailingWidget: _buildTierBadge(),
                          onTap: _showSubscriptionDialog,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.receipt_long_outlined,
                          title: 'Payment History',
                          onTap: _showPaymentHistory,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.lock_outline,
                          title: 'Change Password',
                          onTap: _showChangePasswordDialog,
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader(
                          '🎬 Default Video Settings'),
                      _buildCard([
                        _buildTile(
                          icon: Icons.aspect_ratio,
                          title: 'Aspect Ratio',
                          subtitle: _settings?.defaultAspectRatio ??
                              '9:16',
                          onTap: () => _showOptionsSheet(
                            title: 'Default Aspect Ratio',
                            options: const [
                              '9:16', '16:9', '1:1'
                            ],
                            selected:
                                _settings?.defaultAspectRatio ??
                                    '9:16',
                            onSelected: (v) => _updateSettings(
                                _settings!.copyWith(
                                    defaultAspectRatio: v)),
                          ),
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.timer_outlined,
                          title: 'Default Duration',
                          subtitle:
                              '${_settings?.defaultVideoLength ?? 30} seconds',
                          onTap: _showDurationSelector,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.style_outlined,
                          title: 'Visual Style',
                          subtitle: _capitalize(
                              _settings?.defaultStyle ??
                                  'cinematic'),
                          onTap: () => _showOptionsSheet(
                            title: 'Default Visual Style',
                            options: const [
                              'cinematic', 'realistic', 'cartoon',
                              'dramatic', 'minimal', 'funny',
                            ],
                            selected:
                                _settings?.defaultStyle ??
                                    'cinematic',
                            onSelected: (v) => _updateSettings(
                                _settings!
                                    .copyWith(defaultStyle: v)),
                          ),
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.category_outlined,
                          title: 'Default Niche',
                          subtitle: _capitalize(
                              _settings?.defaultNiche ?? 'general'),
                          onTap: () => _showOptionsSheet(
                            title: 'Default Niche',
                            options: const [
                              'general', 'fitness', 'cooking',
                              'travel', 'tech', 'fashion',
                              'finance', 'education', 'motivation',
                              'gaming', 'music', 'business',
                              'science', 'nature', 'comedy',
                            ],
                            selected:
                                _settings?.defaultNiche ??
                                    'general',
                            onSelected: (v) => _updateSettings(
                                _settings!
                                    .copyWith(defaultNiche: v)),
                          ),
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('🎙️ Audio & Voice'),
                      _buildCard([
                        _buildTile(
                          icon: Icons.record_voice_over_outlined,
                          title: 'Default Audio Mode',
                          subtitle: _capitalize(
                              _settings?.defaultAudioMode ??
                                  'narration'),
                          onTap: () => _showOptionsSheet(
                            title: 'Default Audio Mode',
                            options: const [
                              'silent', 'narration', 'soundSync'
                            ],
                            labels: const [
                              'Silent (Music only)',
                              'AI Narration (Voiceover)',
                              'Sound Sync (Realistic sounds)',
                            ],
                            selected:
                                _settings?.defaultAudioMode ??
                                    'narration',
                            onSelected: (v) => _updateSettings(
                                _settings!.copyWith(
                                    defaultAudioMode: v)),
                          ),
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.mic_outlined,
                          title: 'Voice Style',
                          subtitle: _capitalize(
                              _settings?.defaultVoiceStyle ??
                                  'professional'),
                          onTap: () => _showOptionsSheet(
                            title: 'Voice Style',
                            options: const [
                              'professional', 'friendly',
                              'dramatic', 'energetic', 'calm',
                              'authoritative',
                            ],
                            selected:
                                _settings?.defaultVoiceStyle ??
                                    'professional',
                            onSelected: (v) => _updateSettings(
                                _settings!.copyWith(
                                    defaultVoiceStyle: v)),
                          ),
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.music_note_outlined,
                          title: 'Music Style',
                          subtitle: _capitalize(
                              _settings?.backgroundMusicStyle ??
                                  'upbeat'),
                          onTap: () => _showOptionsSheet(
                            title: 'Background Music Style',
                            options: const [
                              'upbeat', 'calm', 'dramatic',
                              'inspirational', 'epic', 'lofi',
                              'none',
                            ],
                            selected:
                                _settings?.backgroundMusicStyle ??
                                    'upbeat',
                            onSelected: (v) => _updateSettings(
                                _settings!.copyWith(
                                    backgroundMusicStyle: v)),
                          ),
                        ),
                        _buildDivider(),
                        _buildSwitch(
                          icon: Icons.music_note,
                          title: 'Background Music',
                          subtitle:
                              'Add music to all videos by default',
                          value: _settings
                                  ?.backgroundMusicEnabled ??
                              true,
                          onChanged: (v) => _updateSettings(
                              _settings!.copyWith(
                                  backgroundMusicEnabled: v)),
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('💬 Captions'),
                      _buildCard([
                        _buildSwitch(
                          icon: Icons.closed_caption_outlined,
                          title: 'Enable Captions',
                          subtitle:
                              'Show captions on all videos by default',
                          value: _settings?.captionsEnabled ?? true,
                          onChanged: (v) => _updateSettings(
                              _settings!
                                  .copyWith(captionsEnabled: v)),
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.text_fields,
                          title: 'Caption Style',
                          subtitle: _capitalize(
                              _settings?.captionStyle ?? 'modern'),
                          onTap: () => _showOptionsSheet(
                            title: 'Caption Style',
                            options: const [
                              'modern', 'classic', 'bold',
                              'minimal', 'fun'
                            ],
                            selected:
                                _settings?.captionStyle ?? 'modern',
                            onSelected: (v) => _updateSettings(
                                _settings!
                                    .copyWith(captionStyle: v)),
                          ),
                        ),
                        _buildDivider(),
                        _buildSwitch(
                          icon: Icons.emoji_emotions_outlined,
                          title: 'Emoji in Captions',
                          subtitle:
                              'Include emojis in caption text',
                          value:
                              _settings?.captionEmojiEnabled ?? true,
                          onChanged: (v) => _updateSettings(
                              _settings!.copyWith(
                                  captionEmojiEnabled: v)),
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('📱 Default Platforms'),
                      _buildCard([_buildPlatformSelector()]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('🎭 AI Generation'),
                      _buildCard([
                        _buildSwitch(
                          icon: Icons.face_retouching_natural,
                          title: 'Character Consistency',
                          subtitle:
                              'Keep characters the same across all scenes',
                          value: _settings
                                  ?.characterConsistencyEnabled ??
                              false,
                          onChanged: (v) => _updateSettings(
                              _settings!.copyWith(
                                  characterConsistencyEnabled: v)),
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('🔔 Notifications'),
                      _buildCard([
                        _buildSwitch(
                          icon: Icons.notifications_outlined,
                          title: 'Push Notifications',
                          value: _settings
                                  ?.pushNotificationsEnabled ??
                              true,
                          onChanged: (v) => _updateSettings(
                              _settings!.copyWith(
                                  pushNotificationsEnabled: v)),
                        ),
                        _buildDivider(),
                        _buildSwitch(
                          icon: Icons.email_outlined,
                          title: 'Email Notifications',
                          value: _settings
                                  ?.emailNotificationsEnabled ??
                              true,
                          onChanged: (v) => _updateSettings(
                              _settings!.copyWith(
                                  emailNotificationsEnabled: v)),
                        ),
                        _buildDivider(),
                        _buildSwitch(
                          icon: Icons.check_circle_outline,
                          title: 'Video Complete Alert',
                          subtitle:
                              'Notify when a video finishes generating',
                          value:
                              _settings?.notifyOnVideoComplete ??
                                  true,
                          onChanged: (v) => _updateSettings(
                              _settings!.copyWith(
                                  notifyOnVideoComplete: v)),
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('🔒 Privacy & Security'),
                      _buildCard([
                        _buildTile(
                          icon: Icons.download_outlined,
                          title: 'Export My Data',
                          subtitle:
                              'Download all your videos and data',
                          onTap: _showExportDataDialog,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.delete_forever_outlined,
                          title: 'Delete Account',
                          subtitle:
                              'Permanently delete your account',
                          textColor: Colors.red,
                          onTap: _showDeleteAccountDialog,
                        ),
                      ]),

                      SizedBox(height: 24.h),

                      _buildSectionHeader('ℹ️ About'),
                      _buildCard([
                        _buildTile(
                          icon: Icons.info_outline,
                          title: 'About chAs AI Creator',
                          subtitle: 'Version 1.0.0',
                          onTap: _showAboutDialog,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.privacy_tip_outlined,
                          title: 'Privacy Policy',
                          onTap: _showPrivacyPolicy,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.description_outlined,
                          title: 'Terms of Service',
                          onTap: _showTermsOfService,
                        ),
                        _buildDivider(),
                        _buildTile(
                          icon: Icons.support_agent_outlined,
                          title: 'Contact Support',
                          onTap: _showContactSupport,
                        ),
                      ]),

                      SizedBox(height: 24.h),
                      _buildLogoutButton(),
                      SizedBox(height: 40.h),
                    ],
                  ),
                ),
        );
      },
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PROFILE CARD
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildProfileCard() {
    return GestureDetector(
      onTap: _showEditProfileDialog,
      child: Container(
        padding: EdgeInsets.all(20.w),
        decoration: BoxDecoration(
          gradient: AppTheme.primaryGradient,
          borderRadius: BorderRadius.circular(20.r),
        ),
        child: Row(
          children: [
            Container(
              width: 60.w,
              height: 60.w,
              decoration: BoxDecoration(
                color: Colors.white24,
                shape: BoxShape.circle,
                border: Border.all(
                    color: Colors.white38, width: 2),
              ),
              child: _user?.avatarUrl != null
                  ? ClipOval(
                      child: Image.network(
                        _user!.avatarUrl!,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            _buildAvatarFallback(),
                      ),
                    )
                  : _buildAvatarFallback(),
            ),
            SizedBox(width: 16.w),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // FIX 3 — reads from AuthBloc via _user getter,
                  // so this updates instantly app-wide after profile edit
                  Text(
                    _user?.displayName ?? 'Creator',
                    style: TextStyle(
                      fontSize: 17.sp,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  SizedBox(height: 3.h),
                  Text(
                    _user?.email ?? '',
                    style: TextStyle(
                        fontSize: 12.sp,
                        color: Colors.white70),
                  ),
                  SizedBox(height: 8.h),
                  _buildTierBadge(light: true),
                ],
              ),
            ),
            Icon(Icons.edit_outlined,
                color: Colors.white70, size: 18.w),
          ],
        ),
      ),
    );
  }

  Widget _buildAvatarFallback() {
    final name = _user?.displayName ?? _user?.email ?? 'C';
    return Center(
      child: Text(
        name[0].toUpperCase(),
        style: TextStyle(
          fontSize: 24.sp,
          fontWeight: FontWeight.bold,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildTierBadge({bool light = false}) {
    final tier = _user?.subscriptionTier ?? 'free';
    final color = switch (tier.toLowerCase()) {
      'pro'   => Colors.amber,
      'basic' => Colors.blue,
      _       => light ? Colors.white54 : Colors.grey,
    };
    final label = switch (tier.toLowerCase()) {
      'pro'   => '⭐ PRO',
      'basic' => '🔵 BASIC',
      _       => '🆓 FREE',
    };
    return Container(
      padding: EdgeInsets.symmetric(
          horizontal: 10.w, vertical: 4.h),
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(20.r),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11.sp,
          color: light ? Colors.white : color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  String _subscriptionLabel() {
    final tier = _user?.subscriptionTier ?? 'free';
    return switch (tier.toLowerCase()) {
      'pro'   => 'Pro Plan — all features unlocked',
      'basic' => 'Basic Plan — 10 videos/day',
      _       => 'Free Plan — 2 videos/day',
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PLATFORM SELECTOR
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildPlatformSelector() {
    final platforms = {
      'tiktok':    ('🎵', 'TikTok'),
      'youtube':   ('▶️', 'YouTube'),
      'instagram': ('📸', 'Instagram'),
      'facebook':  ('👤', 'Facebook'),
      'twitter':   ('🐦', 'X / Twitter'),
      'linkedin':  ('💼', 'LinkedIn'),
    };

    final selected = Set<String>.from(
        _settings?.defaultTargetPlatforms ?? ['tiktok']);

    return Padding(
      padding: EdgeInsets.all(16.w),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Default platforms for hashtag & format optimization',
            style:
                TextStyle(fontSize: 12.sp, color: Colors.grey),
          ),
          SizedBox(height: 12.h),
          Wrap(
            spacing: 8.w,
            runSpacing: 8.h,
            children: platforms.entries.map((e) {
              final isSelected = selected.contains(e.key);
              return GestureDetector(
                onTap: () {
                  final updated = Set<String>.from(selected);
                  if (isSelected) {
                    if (updated.length > 1) {
                      updated.remove(e.key);
                    }
                  } else {
                    updated.add(e.key);
                  }
                  _updateSettings(_settings!.copyWith(
                      defaultTargetPlatforms:
                          updated.toList()));
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: EdgeInsets.symmetric(
                      horizontal: 12.w, vertical: 8.h),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppTheme.primaryColor
                            .withOpacity(0.12)
                        : Colors.transparent,
                    borderRadius:
                        BorderRadius.circular(20.r),
                    border: Border.all(
                      color: isSelected
                          ? AppTheme.primaryColor
                          : Colors.grey.withOpacity(0.3),
                      width: isSelected ? 1.5 : 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(e.value.$1,
                          style:
                              TextStyle(fontSize: 14.sp)),
                      SizedBox(width: 6.w),
                      Text(
                        e.value.$2,
                        style: TextStyle(
                          fontSize: 12.sp,
                          color: isSelected
                              ? AppTheme.primaryColor
                              : Colors.grey,
                          fontWeight: isSelected
                              ? FontWeight.w600
                              : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUILDING BLOCKS
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: EdgeInsets.only(left: 4.w, bottom: 10.h),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13.sp,
          fontWeight: FontWeight.w700,
          color: AppTheme.primaryColor,
          letterSpacing: 0.3,
        ),
      ),
    );
  }

  Widget _buildCard(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(16.r),
        border: Border.all(
            color: Colors.grey.withOpacity(0.1)),
      ),
      child: Column(children: children),
    );
  }

  Widget _buildTile({
    required IconData icon,
    required String title,
    String? subtitle,
    Widget? trailingWidget,
    required VoidCallback onTap,
    Color? textColor,
  }) {
    return ListTile(
      contentPadding:
          EdgeInsets.symmetric(horizontal: 16.w, vertical: 2.h),
      leading: Container(
        width: 36.w,
        height: 36.w,
        decoration: BoxDecoration(
          color: (textColor ?? AppTheme.primaryColor)
              .withOpacity(0.1),
          borderRadius: BorderRadius.circular(10.r),
        ),
        child: Icon(icon,
            size: 18.w,
            color: textColor ?? AppTheme.primaryColor),
      ),
      title: Text(
        title,
        style: TextStyle(
          fontSize: 14.sp,
          fontWeight: FontWeight.w500,
          color: textColor,
        ),
      ),
      subtitle: subtitle != null
          ? Text(subtitle,
              style: TextStyle(
                  fontSize: 12.sp, color: Colors.grey))
          : null,
      trailing: trailingWidget ??
          Icon(Icons.chevron_right,
              size: 18.w, color: Colors.grey),
      onTap: onTap,
    );
  }

  Widget _buildSwitch({
    required IconData icon,
    required String title,
    String? subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return SwitchListTile(
      contentPadding:
          EdgeInsets.symmetric(horizontal: 16.w, vertical: 2.h),
      secondary: Container(
        width: 36.w,
        height: 36.w,
        decoration: BoxDecoration(
          color: AppTheme.primaryColor.withOpacity(0.1),
          borderRadius: BorderRadius.circular(10.r),
        ),
        child: Icon(icon,
            size: 18.w, color: AppTheme.primaryColor),
      ),
      title: Text(title,
          style: TextStyle(
              fontSize: 14.sp, fontWeight: FontWeight.w500)),
      subtitle: subtitle != null
          ? Text(subtitle,
              style: TextStyle(
                  fontSize: 12.sp, color: Colors.grey))
          : null,
      activeColor: Colors.white,
      activeTrackColor: AppTheme.primaryColor,
      value: value,
      onChanged: onChanged,
    );
  }

  Widget _buildDivider() => Divider(
        height: 1,
        indent: 68.w,
        color: Colors.grey.withOpacity(0.1),
      );

  Widget _buildLogoutButton() {
    return GestureDetector(
      onTap: _showLogoutDialog,
      child: Container(
        padding: EdgeInsets.symmetric(vertical: 16.h),
        decoration: BoxDecoration(
          color: Colors.red.withOpacity(0.08),
          borderRadius: BorderRadius.circular(16.r),
          border:
              Border.all(color: Colors.red.withOpacity(0.2)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.logout, color: Colors.red, size: 20.w),
            SizedBox(width: 10.w),
            Text(
              'Log Out',
              style: TextStyle(
                fontSize: 15.sp,
                color: Colors.red,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // OPTIONS SHEET
  // ─────────────────────────────────────────────────────────────────────────

  void _showOptionsSheet({
    required String title,
    required List<String> options,
    List<String>? labels,
    required String selected,
    required Function(String) onSelected,
  }) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.5,
        minChildSize: 0.3,
        maxChildSize: 0.85,
        expand: false,
        builder: (_, scrollCtrl) => Container(
          decoration: BoxDecoration(
            color: Theme.of(context).scaffoldBackgroundColor,
            borderRadius: BorderRadius.vertical(
                top: Radius.circular(20.r)),
          ),
          child: Column(
            children: [
              Padding(
                padding:
                    EdgeInsets.fromLTRB(20.w, 12.h, 20.w, 0),
                child: Column(
                  children: [
                    Center(
                      child: Container(
                        width: 36.w,
                        height: 4.h,
                        decoration: BoxDecoration(
                          color: Colors.grey.shade300,
                          borderRadius:
                              BorderRadius.circular(2.r),
                        ),
                      ),
                    ),
                    SizedBox(height: 14.h),
                    Text(title,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(
                                fontWeight:
                                    FontWeight.bold)),
                    SizedBox(height: 8.h),
                    Divider(
                        color: Colors.grey.withOpacity(0.1)),
                  ],
                ),
              ),
              Expanded(
                child: ListView.builder(
                  controller: scrollCtrl,
                  padding: EdgeInsets.symmetric(
                      horizontal: 12.w, vertical: 4.h),
                  itemCount: options.length,
                  itemBuilder: (_, i) {
                    final opt = options[i];
                    final label =
                        labels?[i] ?? _capitalize(opt);
                    final isSelected = opt == selected;
                    return ListTile(
                      contentPadding:
                          EdgeInsets.symmetric(
                              horizontal: 8.w),
                      title: Text(
                        label,
                        style: TextStyle(
                          fontSize: 14.sp,
                          color: isSelected
                              ? AppTheme.primaryColor
                              : null,
                          fontWeight: isSelected
                              ? FontWeight.w600
                              : FontWeight.normal,
                        ),
                      ),
                      trailing: isSelected
                          ? Container(
                              width: 28.w,
                              height: 28.w,
                              decoration: BoxDecoration(
                                color: AppTheme.primaryColor,
                                shape: BoxShape.circle,
                              ),
                              child: Icon(Icons.check,
                                  color: Colors.white,
                                  size: 14.w),
                            )
                          : null,
                      onTap: () {
                        Navigator.pop(context);
                        onSelected(opt);
                      },
                    );
                  },
                ),
              ),
              SizedBox(height: 16.h),
            ],
          ),
        ),
      ),
    );
  }

  void _showDurationSelector() {
    final durations = [10, 15, 20, 30, 45, 60, 90, 120];
    _showOptionsSheet(
      title: 'Default Duration',
      options: durations.map((d) => '$d').toList(),
      labels: durations.map((d) => '$d seconds').toList(),
      selected: '${_settings?.defaultVideoLength ?? 30}',
      onSelected: (v) => _updateSettings(_settings!
          .copyWith(defaultVideoLength: int.parse(v))),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // EDIT PROFILE — THE MAIN FIX
  // ─────────────────────────────────────────────────────────────────────────

  void _showEditProfileDialog() {
    // FIX 4 — pre-fill from AuthBloc user, not local _user variable
    final nameCtrl = TextEditingController(
        text: _user?.displayName ?? '');
    final bioCtrl =
        TextEditingController(text: _user?.bio ?? '');
    bool isSavingProfile = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) => StatefulBuilder(
        // FIX 5 — StatefulBuilder so the save button can show loading
        // without rebuilding the whole screen
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.only(
              bottom:
                  MediaQuery.of(context).viewInsets.bottom),
          child: Container(
            padding: EdgeInsets.all(24.w),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              borderRadius: BorderRadius.vertical(
                  top: Radius.circular(24.r)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Edit Profile',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(
                                fontWeight: FontWeight.bold)),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () =>
                          Navigator.pop(sheetCtx),
                    ),
                  ],
                ),
                SizedBox(height: 20.h),
                TextField(
                  controller: nameCtrl,
                  textCapitalization:
                      TextCapitalization.words,
                  decoration: InputDecoration(
                    labelText: 'Display Name',
                    border: OutlineInputBorder(
                        borderRadius:
                            BorderRadius.circular(12.r)),
                    prefixIcon:
                        const Icon(Icons.person_outline),
                  ),
                ),
                SizedBox(height: 14.h),
                TextField(
                  controller: bioCtrl,
                  maxLines: 3,
                  maxLength: 160,
                  decoration: InputDecoration(
                    labelText: 'Bio (optional)',
                    border: OutlineInputBorder(
                        borderRadius:
                            BorderRadius.circular(12.r)),
                    prefixIcon:
                        const Icon(Icons.info_outline),
                  ),
                ),
                SizedBox(height: 20.h),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: isSavingProfile
                        ? null
                        : () async {
                            final name =
                                nameCtrl.text.trim();
                            if (name.isEmpty) {
                              _showToast(
                                  '❌ Display name cannot be empty',
                                  error: true);
                              return;
                            }

                            setSheetState(() =>
                                isSavingProfile = true);

                            try {
                              // FIX 6 — call AuthService.updateProfile
                              // so the token is guaranteed to be attached
                              final updated =
                                  await _authService
                                      .updateProfile(
                                displayName: name,
                                bio: bioCtrl.text.trim(),
                              );

                              // FIX 7 — THE KEY FIX: dispatch UpdateUser
                              // to AuthBloc so EVERY screen in the app
                              // (dashboard, home, settings profile card)
                              // rebuilds with the new name/bio instantly.
                              if (mounted) {
                                context.read<AuthBloc>().add(
                                    UpdateUser(user: updated));
                              }

                              if (mounted) {
                                Navigator.pop(sheetCtx);
                                _showToast(
                                    '✅ Profile updated!');
                              }
                            } catch (e) {
                              setSheetState(() =>
                                  isSavingProfile = false);
                              _showToast(
                                  '❌ ${_apiService.handleError(e)}',
                                  error: true);
                            }
                          },
                    style: ElevatedButton.styleFrom(
                      padding: EdgeInsets.symmetric(
                          vertical: 14.h),
                      shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(12.r)),
                    ),
                    child: isSavingProfile
                        ? SizedBox(
                            height: 18.h,
                            width: 18.h,
                            child:
                                const CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Save Changes'),
                  ),
                ),
                SizedBox(height: 8.h),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CHANGE PASSWORD
  // ─────────────────────────────────────────────────────────────────────────

  void _showChangePasswordDialog() {
    final currentCtrl  = TextEditingController();
    final newCtrl      = TextEditingController();
    final confirmCtrl  = TextEditingController();
    bool isSaving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.only(
              bottom:
                  MediaQuery.of(context).viewInsets.bottom),
          child: Container(
            padding: EdgeInsets.all(24.w),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              borderRadius: BorderRadius.vertical(
                  top: Radius.circular(24.r)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Change Password',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(
                                fontWeight: FontWeight.bold)),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () =>
                          Navigator.pop(sheetCtx),
                    ),
                  ],
                ),
                SizedBox(height: 20.h),
                _buildPasswordField(
                    currentCtrl, 'Current Password'),
                SizedBox(height: 12.h),
                _buildPasswordField(
                    newCtrl, 'New Password'),
                SizedBox(height: 12.h),
                _buildPasswordField(
                    confirmCtrl, 'Confirm New Password'),
                SizedBox(height: 20.h),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: isSaving
                        ? null
                        : () async {
                            if (currentCtrl.text.isEmpty) {
                              _showToast(
                                  '❌ Enter your current password',
                                  error: true);
                              return;
                            }
                            if (newCtrl.text !=
                                confirmCtrl.text) {
                              _showToast(
                                  '❌ Passwords do not match',
                                  error: true);
                              return;
                            }
                            if (newCtrl.text.length < 8) {
                              _showToast(
                                  '❌ Password must be at least 8 characters',
                                  error: true);
                              return;
                            }

                            setSheetState(
                                () => isSaving = true);
                            try {
                              await _apiService
                                  .changePassword(
                                currentPassword:
                                    currentCtrl.text,
                                newPassword: newCtrl.text,
                              );
                              if (mounted) {
                                Navigator.pop(sheetCtx);
                                _showToast(
                                    '✅ Password changed!');
                              }
                            } catch (e) {
                              setSheetState(
                                  () => isSaving = false);
                              _showToast(
                                  '❌ ${_apiService.handleError(e)}',
                                  error: true);
                            }
                          },
                    style: ElevatedButton.styleFrom(
                      padding: EdgeInsets.symmetric(
                          vertical: 14.h),
                      shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(12.r)),
                    ),
                    child: isSaving
                        ? SizedBox(
                            height: 18.h,
                            width: 18.h,
                            child:
                                const CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Update Password'),
                  ),
                ),
                SizedBox(height: 8.h),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPasswordField(
      TextEditingController ctrl, String label) {
    return TextField(
      controller: ctrl,
      obscureText: true,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12.r)),
        prefixIcon: const Icon(Icons.lock_outline),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SUBSCRIPTION
  // ─────────────────────────────────────────────────────────────────────────

  void _showSubscriptionDialog() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => Container(
        padding: EdgeInsets.all(24.w),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: BorderRadius.vertical(
              top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Subscription Plans',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 20.h),
            _buildPlanCard('🆓 Free',
                ['2 videos/day', '30s max', 'Basic quality'],
                false),
            SizedBox(height: 10.h),
            _buildPlanCard('🔵 Basic', [
              '10 videos/day', '60s max',
              'HD quality', 'No watermark'
            ], false),
            SizedBox(height: 10.h),
            _buildPlanCard('⭐ Pro', [
              '50 videos/day', '5 min max',
              '4K quality', 'Priority generation',
              'All AI features'
            ], true),
            SizedBox(height: 20.h),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  _showToast('🚀 Redirecting to upgrade...');
                },
                style: ElevatedButton.styleFrom(
                  padding:
                      EdgeInsets.symmetric(vertical: 14.h),
                  shape: RoundedRectangleBorder(
                      borderRadius:
                          BorderRadius.circular(12.r)),
                ),
                child: const Text('Upgrade Now'),
              ),
            ),
            SizedBox(height: 8.h),
          ],
        ),
      ),
    );
  }

  Widget _buildPlanCard(
      String name, List<String> features, bool highlighted) {
    return Container(
      padding: EdgeInsets.all(14.w),
      decoration: BoxDecoration(
        color: highlighted
            ? AppTheme.primaryColor.withOpacity(0.1)
            : Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(14.r),
        border: Border.all(
          color: highlighted
              ? AppTheme.primaryColor
              : Colors.grey.withOpacity(0.2),
          width: highlighted ? 1.5 : 1,
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: TextStyle(
                      fontSize: 15.sp,
                      fontWeight: FontWeight.bold,
                      color: highlighted
                          ? AppTheme.primaryColor
                          : null,
                    )),
                SizedBox(height: 6.h),
                ...features.map((f) => Padding(
                      padding: EdgeInsets.only(top: 2.h),
                      child: Text('✓ $f',
                          style: TextStyle(
                              fontSize: 12.sp,
                              color: Colors.grey)),
                    )),
              ],
            ),
          ),
          if (highlighted)
            Container(
              padding: EdgeInsets.symmetric(
                  horizontal: 8.w, vertical: 4.h),
              decoration: BoxDecoration(
                color: AppTheme.primaryColor,
                borderRadius: BorderRadius.circular(8.r),
              ),
              child: Text('Best',
                  style: TextStyle(
                      fontSize: 11.sp,
                      color: Colors.white,
                      fontWeight: FontWeight.bold)),
            ),
        ],
      ),
    );
  }

  void _showPaymentHistory() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: EdgeInsets.all(24.w),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: BorderRadius.vertical(
              top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Payment History',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 40.h),
            Icon(Icons.receipt_long_outlined,
                size: 48.w, color: Colors.grey),
            SizedBox(height: 12.h),
            Text('No payments yet',
                style: TextStyle(
                    fontSize: 14.sp, color: Colors.grey)),
            SizedBox(height: 40.h),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PRIVACY / LEGAL / ABOUT
  // ─────────────────────────────────────────────────────────────────────────

  void _showExportDataDialog() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Export My Data'),
        content: const Text(
          'We will prepare a complete export of all your videos, '
          'settings, and account data and send it to your email '
          'within 24 hours.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              _showToast(
                  '✅ Export requested! Check your email soon.');
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
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('chAs AI Creator'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72.w,
              height: 72.w,
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                borderRadius: BorderRadius.circular(20.r),
              ),
              child: Icon(Icons.auto_fix_high_rounded,
                  size: 36.w, color: Colors.white),
            ),
            SizedBox(height: 16.h),
            Text('Version 1.0.0',
                style: TextStyle(
                    fontSize: 13.sp, color: Colors.grey)),
            SizedBox(height: 8.h),
            Text(
              'AI-powered video content creation platform for global creators.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13.sp),
            ),
            SizedBox(height: 8.h),
            Text('Made with ❤️ by chAs Tech Group',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: 12.sp, color: Colors.grey)),
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
    _showTextDialog(
      'Privacy Policy',
      'chAs AI Creator collects your email and usage data solely '
          'to provide the service. We do not sell your personal data '
          'to third parties. Your videos are stored securely and only '
          'accessible by you. You may request complete data deletion at '
          'any time by contacting support. We use industry-standard '
          'encryption to protect all your data.',
    );
  }

  void _showTermsOfService() {
    _showTextDialog(
      'Terms of Service',
      'By using chAs AI Creator, you agree to use the app responsibly. '
          'You must not use the app to generate harmful, illegal, '
          'misleading, or hateful content. All generated content remains '
          'your intellectual property. chAs Tech Group reserves the right '
          'to suspend accounts that violate these terms. Free tier is '
          'limited to 2 videos per day.',
    );
  }

  void _showContactSupport() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Contact Support'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: Container(
                padding: EdgeInsets.all(8.w),
                decoration: BoxDecoration(
                  color:
                      AppTheme.primaryColor.withOpacity(0.1),
                  borderRadius:
                      BorderRadius.circular(10.r),
                ),
                child: Icon(Icons.email_outlined,
                    color: AppTheme.primaryColor,
                    size: 20.w),
              ),
              title: const Text('Email Support'),
              subtitle:
                  const Text('chasofficiallz@gmail.com'),
              onTap: () {
                Navigator.pop(context);
                Clipboard.setData(const ClipboardData(
                    text: 'chasofficiallz@gmail.com'));
                _showToast('✅ Email copied to clipboard!');
              },
            ),
            ListTile(
              leading: Container(
                padding: EdgeInsets.all(8.w),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.1),
                  borderRadius:
                      BorderRadius.circular(10.r),
                ),
                child: Icon(Icons.chat_outlined,
                    color: Colors.green, size: 20.w),
              ),
              title: const Text('Live Chat'),
              subtitle:
                  const Text('Mon–Fri, 9am–6pm WAT'),
              onTap: () => Navigator.pop(context),
            ),
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

  void _showTextDialog(String title, String content) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: Text(title),
        content: SingleChildScrollView(child: Text(content)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Log Out'),
        content:
            const Text('Are you sure you want to log out?'),
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
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red),
            child: const Text('Log Out',
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showDeleteAccountDialog() {
    final confirmCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Delete Account'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '⚠️ This will permanently delete all your videos, '
              'settings, and account data. This cannot be undone.',
              style: TextStyle(fontSize: 13.sp),
            ),
            SizedBox(height: 16.h),
            Text('Type DELETE to confirm:',
                style: TextStyle(
                    fontSize: 12.sp,
                    fontWeight: FontWeight.w600)),
            SizedBox(height: 8.h),
            TextField(
              controller: confirmCtrl,
              decoration: InputDecoration(
                hintText: 'DELETE',
                border: OutlineInputBorder(
                    borderRadius:
                        BorderRadius.circular(10.r)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              if (confirmCtrl.text != 'DELETE') {
                _showToast(
                    '❌ Please type DELETE to confirm',
                    error: true);
                return;
              }
              Navigator.pop(context);
              context.read<AuthBloc>().add(LoggedOut());
            },
            child: const Text('Delete',
                style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  String _capitalize(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
}
