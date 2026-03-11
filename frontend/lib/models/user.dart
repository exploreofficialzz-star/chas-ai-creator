/*
 * chAs AI Creator - User Model
 * FILE: lib/models/user.dart
 */

import 'package:equatable/equatable.dart';

// ─────────────────────────────────────────────────────────────────────────────
// USER
// ─────────────────────────────────────────────────────────────────────────────

class User extends Equatable {
  final String id;
  final String email;
  final String? displayName;
  final String? avatarUrl;
  final String? bio;
  final String subscriptionTier;
  final int credits;
  final bool isActive;
  final bool isVerified;
  final DateTime? subscriptionExpiresAt;
  final DateTime? lastLoginAt;
  final DateTime? createdAt;

  const User({
    required this.id,
    required this.email,
    this.displayName,
    this.avatarUrl,
    this.bio,
    this.subscriptionTier = 'free',
    this.credits = 0,
    this.isActive = true,
    this.isVerified = false,
    this.subscriptionExpiresAt,
    this.lastLoginAt,
    this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    // FIX — num-safe credits: backend can return int, double, or String
    int parseCredits(dynamic v) {
      if (v == null) return 0;
      if (v is int) return v;
      if (v is double) return v.toInt();
      if (v is String) return int.tryParse(v) ?? 0;
      return 0;
    }

    return User(
      // FIX — id: handle int ids from some backends
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      displayName: json['display_name']?.toString(),
      avatarUrl: json['avatar_url']?.toString(),
      bio: json['bio']?.toString(),
      subscriptionTier:
          json['subscription_tier']?.toString() ?? 'free',
      credits: parseCredits(json['credits']),
      isActive: json['is_active'] as bool? ?? true,
      isVerified: json['is_verified'] as bool? ?? false,
      subscriptionExpiresAt:
          json['subscription_expires_at'] != null
              ? DateTime.tryParse(
                  json['subscription_expires_at'].toString())
              : null,
      lastLoginAt: json['last_login_at'] != null
          ? DateTime.tryParse(
              json['last_login_at'].toString())
          : null,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'display_name': displayName,
        'avatar_url': avatarUrl,
        'bio': bio,
        'subscription_tier': subscriptionTier,
        'credits': credits,
        'is_active': isActive,
        'is_verified': isVerified,
        'subscription_expires_at':
            subscriptionExpiresAt?.toIso8601String(),
        'last_login_at': lastLoginAt?.toIso8601String(),
        'created_at': createdAt?.toIso8601String(),
      };

  // ── Convenience getters ───────────────────────────────────────────────────
  bool get isPro =>
      subscriptionTier == 'pro' ||
      subscriptionTier == 'enterprise';
  bool get isBasic => subscriptionTier == 'basic';
  bool get isFree => subscriptionTier == 'free';
  bool get isEnterprise => subscriptionTier == 'enterprise';

  String get tierEmoji =>
      switch (subscriptionTier.toLowerCase()) {
        'pro'        => '⭐',
        'basic'      => '🔵',
        'enterprise' => '💎',
        _            => '🆓',
      };

  String get displayNameOrEmail =>
      displayName?.isNotEmpty == true
          ? displayName!
          : email.split('@').first;

  String get initial =>
      (displayName?.isNotEmpty == true
              ? displayName!
              : email)
          .isNotEmpty
          ? (displayName?.isNotEmpty == true
                  ? displayName!
                  : email)[0]
              .toUpperCase()
          : 'C';

  int get dailyVideoLimit =>
      switch (subscriptionTier.toLowerCase()) {
        'pro'        => 50,
        'basic'      => 10,
        'enterprise' => 999,
        _            => 2,
      };

  User copyWith({
    String? id,
    String? email,
    String? displayName,
    String? avatarUrl,
    String? bio,
    String? subscriptionTier,
    int? credits,
    bool? isActive,
    bool? isVerified,
    DateTime? subscriptionExpiresAt,
    DateTime? lastLoginAt,
    DateTime? createdAt,
  }) =>
      User(
        id: id ?? this.id,
        email: email ?? this.email,
        displayName: displayName ?? this.displayName,
        avatarUrl: avatarUrl ?? this.avatarUrl,
        bio: bio ?? this.bio,
        subscriptionTier:
            subscriptionTier ?? this.subscriptionTier,
        credits: credits ?? this.credits,
        isActive: isActive ?? this.isActive,
        isVerified: isVerified ?? this.isVerified,
        subscriptionExpiresAt:
            subscriptionExpiresAt ?? this.subscriptionExpiresAt,
        lastLoginAt: lastLoginAt ?? this.lastLoginAt,
        createdAt: createdAt ?? this.createdAt,
      );

  @override
  List<Object?> get props => [
        id,
        email,
        displayName,
        avatarUrl,
        bio,
        subscriptionTier,
        credits,
        isActive,
        isVerified,
        subscriptionExpiresAt,
        lastLoginAt,
        createdAt,
      ];
}

// ─────────────────────────────────────────────────────────────────────────────
// USER SETTINGS
// ─────────────────────────────────────────────────────────────────────────────

class UserSettings extends Equatable {
  final String defaultNiche;
  final String defaultVideoType;
  final int defaultVideoLength;
  final String defaultAspectRatio;
  final String defaultStyle;
  final String defaultAudioMode;
  final String defaultVoiceStyle;
  final List<String> defaultTargetPlatforms;
  final bool characterConsistencyEnabled;
  final String? characterDescription;
  final List<String> characterImages;
  final bool captionsEnabled;
  final String captionStyle;
  final String captionColor;
  final bool captionEmojiEnabled;
  final bool backgroundMusicEnabled;
  final String backgroundMusicStyle;
  final int defaultDailyVideoCount;
  final List<String> defaultScheduleTimes;
  final bool emailNotificationsEnabled;
  final bool pushNotificationsEnabled;
  final bool notifyOnVideoComplete;
  final bool notifyOnSchedule;
  final int? autoDeleteVideosDays;

  const UserSettings({
    this.defaultNiche = 'general',
    this.defaultVideoType = 'silent',
    this.defaultVideoLength = 30,
    this.defaultAspectRatio = '9:16',
    this.defaultStyle = 'cinematic',
    this.defaultAudioMode = 'narration',
    this.defaultVoiceStyle = 'professional',
    this.defaultTargetPlatforms = const ['tiktok'],
    this.characterConsistencyEnabled = false,
    this.characterDescription,
    this.characterImages = const [],
    this.captionsEnabled = true,
    this.captionStyle = 'modern',
    this.captionColor = 'white',
    this.captionEmojiEnabled = true,
    this.backgroundMusicEnabled = true,
    this.backgroundMusicStyle = 'upbeat',
    this.defaultDailyVideoCount = 1,
    this.defaultScheduleTimes = const ['09:00'],
    this.emailNotificationsEnabled = true,
    this.pushNotificationsEnabled = true,
    this.notifyOnVideoComplete = true,
    this.notifyOnSchedule = true,
    this.autoDeleteVideosDays,
  });

  factory UserSettings.fromJson(Map<String, dynamic> json) {
    return UserSettings(
      defaultNiche: json['default_niche'] ?? 'general',
      defaultVideoType:
          json['default_video_type'] ?? 'silent',
      defaultVideoLength:
          json['default_video_length'] ?? 30,
      defaultAspectRatio:
          json['default_aspect_ratio'] ?? '9:16',
      defaultStyle: json['default_style'] ?? 'cinematic',
      defaultAudioMode:
          json['default_audio_mode'] ?? 'narration',
      defaultVoiceStyle:
          json['default_voice_style'] ?? 'professional',
      defaultTargetPlatforms:
          json['default_target_platforms'] != null
              ? List<String>.from(
                  json['default_target_platforms'])
              : const ['tiktok'],
      characterConsistencyEnabled:
          json['character_consistency_enabled'] ?? false,
      characterDescription:
          json['character_description']?.toString(),
      characterImages: List<String>.from(
          json['character_images'] ?? []),
      captionsEnabled:
          json['captions_enabled'] ?? true,
      captionStyle:
          json['caption_style'] ?? 'modern',
      captionColor:
          json['caption_color'] ?? 'white',
      captionEmojiEnabled:
          json['caption_emoji_enabled'] ?? true,
      backgroundMusicEnabled:
          json['background_music_enabled'] ?? true,
      backgroundMusicStyle:
          json['background_music_style'] ?? 'upbeat',
      defaultDailyVideoCount:
          json['default_daily_video_count'] ?? 1,
      defaultScheduleTimes: List<String>.from(
          json['default_schedule_times'] ?? ['09:00']),
      emailNotificationsEnabled:
          json['email_notifications_enabled'] ?? true,
      pushNotificationsEnabled:
          json['push_notifications_enabled'] ?? true,
      notifyOnVideoComplete:
          json['notify_on_video_complete'] ?? true,
      notifyOnSchedule:
          json['notify_on_schedule'] ?? true,
      autoDeleteVideosDays:
          json['auto_delete_videos_days'],
    );
  }

  Map<String, dynamic> toJson() => {
        'default_niche': defaultNiche,
        'default_video_type': defaultVideoType,
        'default_video_length': defaultVideoLength,
        'default_aspect_ratio': defaultAspectRatio,
        'default_style': defaultStyle,
        'default_audio_mode': defaultAudioMode,
        'default_voice_style': defaultVoiceStyle,
        'default_target_platforms': defaultTargetPlatforms,
        'character_consistency_enabled':
            characterConsistencyEnabled,
        'character_description': characterDescription,
        'character_images': characterImages,
        'captions_enabled': captionsEnabled,
        'caption_style': captionStyle,
        'caption_color': captionColor,
        'caption_emoji_enabled': captionEmojiEnabled,
        'background_music_enabled': backgroundMusicEnabled,
        'background_music_style': backgroundMusicStyle,
        'default_daily_video_count': defaultDailyVideoCount,
        'default_schedule_times': defaultScheduleTimes,
        'email_notifications_enabled':
            emailNotificationsEnabled,
        'push_notifications_enabled':
            pushNotificationsEnabled,
        'notify_on_video_complete': notifyOnVideoComplete,
        'notify_on_schedule': notifyOnSchedule,
        'auto_delete_videos_days': autoDeleteVideosDays,
      };

  UserSettings copyWith({
    String? defaultNiche,
    String? defaultVideoType,
    int? defaultVideoLength,
    String? defaultAspectRatio,
    String? defaultStyle,
    String? defaultAudioMode,
    String? defaultVoiceStyle,
    List<String>? defaultTargetPlatforms,
    bool? characterConsistencyEnabled,
    String? characterDescription,
    List<String>? characterImages,
    bool? captionsEnabled,
    String? captionStyle,
    String? captionColor,
    bool? captionEmojiEnabled,
    bool? backgroundMusicEnabled,
    String? backgroundMusicStyle,
    int? defaultDailyVideoCount,
    List<String>? defaultScheduleTimes,
    bool? emailNotificationsEnabled,
    bool? pushNotificationsEnabled,
    bool? notifyOnVideoComplete,
    bool? notifyOnSchedule,
    int? autoDeleteVideosDays,
  }) =>
      UserSettings(
        defaultNiche: defaultNiche ?? this.defaultNiche,
        defaultVideoType:
            defaultVideoType ?? this.defaultVideoType,
        defaultVideoLength:
            defaultVideoLength ?? this.defaultVideoLength,
        defaultAspectRatio:
            defaultAspectRatio ?? this.defaultAspectRatio,
        defaultStyle: defaultStyle ?? this.defaultStyle,
        defaultAudioMode:
            defaultAudioMode ?? this.defaultAudioMode,
        defaultVoiceStyle:
            defaultVoiceStyle ?? this.defaultVoiceStyle,
        defaultTargetPlatforms:
            defaultTargetPlatforms ??
                this.defaultTargetPlatforms,
        characterConsistencyEnabled:
            characterConsistencyEnabled ??
                this.characterConsistencyEnabled,
        characterDescription:
            characterDescription ?? this.characterDescription,
        characterImages:
            characterImages ?? this.characterImages,
        captionsEnabled:
            captionsEnabled ?? this.captionsEnabled,
        captionStyle: captionStyle ?? this.captionStyle,
        captionColor: captionColor ?? this.captionColor,
        captionEmojiEnabled:
            captionEmojiEnabled ?? this.captionEmojiEnabled,
        backgroundMusicEnabled:
            backgroundMusicEnabled ??
                this.backgroundMusicEnabled,
        backgroundMusicStyle:
            backgroundMusicStyle ?? this.backgroundMusicStyle,
        defaultDailyVideoCount:
            defaultDailyVideoCount ??
                this.defaultDailyVideoCount,
        defaultScheduleTimes:
            defaultScheduleTimes ?? this.defaultScheduleTimes,
        emailNotificationsEnabled:
            emailNotificationsEnabled ??
                this.emailNotificationsEnabled,
        pushNotificationsEnabled:
            pushNotificationsEnabled ??
                this.pushNotificationsEnabled,
        notifyOnVideoComplete:
            notifyOnVideoComplete ?? this.notifyOnVideoComplete,
        notifyOnSchedule:
            notifyOnSchedule ?? this.notifyOnSchedule,
        autoDeleteVideosDays:
            autoDeleteVideosDays ?? this.autoDeleteVideosDays,
      );

  @override
  List<Object?> get props => [
        defaultNiche,
        defaultVideoType,
        defaultVideoLength,
        defaultAspectRatio,
        defaultStyle,
        defaultAudioMode,
        defaultVoiceStyle,
        defaultTargetPlatforms,
        characterConsistencyEnabled,
        characterDescription,
        characterImages,
        captionsEnabled,
        captionStyle,
        captionColor,
        captionEmojiEnabled,
        backgroundMusicEnabled,
        backgroundMusicStyle,
        defaultDailyVideoCount,
        defaultScheduleTimes,
        emailNotificationsEnabled,
        pushNotificationsEnabled,
        notifyOnVideoComplete,
        notifyOnSchedule,
        autoDeleteVideosDays,
      ];
}
