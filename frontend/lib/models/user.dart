import 'package:equatable/equatable.dart';

class User extends Equatable {
  final String id;
  final String email;
  final String? displayName;
  final String? avatarUrl;
  final String subscriptionTier;
  final int credits;
  final DateTime? subscriptionExpiresAt;

  const User({
    required this.id,
    required this.email,
    this.displayName,
    this.avatarUrl,
    this.subscriptionTier = 'free',
    this.credits = 0,
    this.subscriptionExpiresAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? '',
      email: json['email'] ?? '',
      displayName: json['display_name'],
      avatarUrl: json['avatar_url'],
      subscriptionTier: json['subscription_tier'] ?? 'free',
      credits: json['credits'] ?? 0,
      subscriptionExpiresAt: json['subscription_expires_at'] != null
          ? DateTime.parse(json['subscription_expires_at'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'display_name': displayName,
      'avatar_url': avatarUrl,
      'subscription_tier': subscriptionTier,
      'credits': credits,
      'subscription_expires_at': subscriptionExpiresAt?.toIso8601String(),
    };
  }

  bool get isPro => subscriptionTier == 'pro' || subscriptionTier == 'enterprise';
  bool get isEnterprise => subscriptionTier == 'enterprise';

  User copyWith({
    String? id,
    String? email,
    String? displayName,
    String? avatarUrl,
    String? subscriptionTier,
    int? credits,
    DateTime? subscriptionExpiresAt,
  }) {
    return User(
      id: id ?? this.id,
      email: email ?? this.email,
      displayName: displayName ?? this.displayName,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      subscriptionTier: subscriptionTier ?? this.subscriptionTier,
      credits: credits ?? this.credits,
      subscriptionExpiresAt: subscriptionExpiresAt ?? this.subscriptionExpiresAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        email,
        displayName,
        avatarUrl,
        subscriptionTier,
        credits,
        subscriptionExpiresAt,
      ];
}

class UserSettings extends Equatable {
  final String defaultNiche;
  final String defaultVideoType;
  final int defaultVideoLength;
  final String defaultAspectRatio;
  final bool characterConsistencyEnabled;
  final String? characterDescription;
  final List<String> characterImages;
  final bool captionsEnabled;
  final String captionStyle;
  final String captionColor;
  final bool captionEmojiEnabled;
  final bool backgroundMusicEnabled;
  final String backgroundMusicStyle;
  final String defaultStyle;
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
    this.characterConsistencyEnabled = false,
    this.characterDescription,
    this.characterImages = const [],
    this.captionsEnabled = true,
    this.captionStyle = 'modern',
    this.captionColor = 'white',
    this.captionEmojiEnabled = true,
    this.backgroundMusicEnabled = true,
    this.backgroundMusicStyle = 'upbeat',
    this.defaultStyle = 'cinematic',
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
      defaultVideoType: json['default_video_type'] ?? 'silent',
      defaultVideoLength: json['default_video_length'] ?? 30,
      defaultAspectRatio: json['default_aspect_ratio'] ?? '9:16',
      characterConsistencyEnabled: json['character_consistency_enabled'] ?? false,
      characterDescription: json['character_description'],
      characterImages: List<String>.from(json['character_images'] ?? []),
      captionsEnabled: json['captions_enabled'] ?? true,
      captionStyle: json['caption_style'] ?? 'modern',
      captionColor: json['caption_color'] ?? 'white',
      captionEmojiEnabled: json['caption_emoji_enabled'] ?? true,
      backgroundMusicEnabled: json['background_music_enabled'] ?? true,
      backgroundMusicStyle: json['background_music_style'] ?? 'upbeat',
      defaultStyle: json['default_style'] ?? 'cinematic',
      defaultDailyVideoCount: json['default_daily_video_count'] ?? 1,
      defaultScheduleTimes: List<String>.from(json['default_schedule_times'] ?? ['09:00']),
      emailNotificationsEnabled: json['email_notifications_enabled'] ?? true,
      pushNotificationsEnabled: json['push_notifications_enabled'] ?? true,
      notifyOnVideoComplete: json['notify_on_video_complete'] ?? true,
      notifyOnSchedule: json['notify_on_schedule'] ?? true,
      autoDeleteVideosDays: json['auto_delete_videos_days'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'default_niche': defaultNiche,
      'default_video_type': defaultVideoType,
      'default_video_length': defaultVideoLength,
      'default_aspect_ratio': defaultAspectRatio,
      'character_consistency_enabled': characterConsistencyEnabled,
      'character_description': characterDescription,
      'character_images': characterImages,
      'captions_enabled': captionsEnabled,
      'caption_style': captionStyle,
      'caption_color': captionColor,
      'caption_emoji_enabled': captionEmojiEnabled,
      'background_music_enabled': backgroundMusicEnabled,
      'background_music_style': backgroundMusicStyle,
      'default_style': defaultStyle,
      'default_daily_video_count': defaultDailyVideoCount,
      'default_schedule_times': defaultScheduleTimes,
      'email_notifications_enabled': emailNotificationsEnabled,
      'push_notifications_enabled': pushNotificationsEnabled,
      'notify_on_video_complete': notifyOnVideoComplete,
      'notify_on_schedule': notifyOnSchedule,
      'auto_delete_videos_days': autoDeleteVideosDays,
    };
  }

  UserSettings copyWith({
    String? defaultNiche,
    String? defaultVideoType,
    int? defaultVideoLength,
    String? defaultAspectRatio,
    bool? characterConsistencyEnabled,
    String? characterDescription,
    List<String>? characterImages,
    bool? captionsEnabled,
    String? captionStyle,
    String? captionColor,
    bool? captionEmojiEnabled,
    bool? backgroundMusicEnabled,
    String? backgroundMusicStyle,
    String? defaultStyle,
    int? defaultDailyVideoCount,
    List<String>? defaultScheduleTimes,
    bool? emailNotificationsEnabled,
    bool? pushNotificationsEnabled,
    bool? notifyOnVideoComplete,
    bool? notifyOnSchedule,
    int? autoDeleteVideosDays,
  }) {
    return UserSettings(
      defaultNiche: defaultNiche ?? this.defaultNiche,
      defaultVideoType: defaultVideoType ?? this.defaultVideoType,
      defaultVideoLength: defaultVideoLength ?? this.defaultVideoLength,
      defaultAspectRatio: defaultAspectRatio ?? this.defaultAspectRatio,
      characterConsistencyEnabled: characterConsistencyEnabled ?? this.characterConsistencyEnabled,
      characterDescription: characterDescription ?? this.characterDescription,
      characterImages: characterImages ?? this.characterImages,
      captionsEnabled: captionsEnabled ?? this.captionsEnabled,
      captionStyle: captionStyle ?? this.captionStyle,
      captionColor: captionColor ?? this.captionColor,
      captionEmojiEnabled: captionEmojiEnabled ?? this.captionEmojiEnabled,
      backgroundMusicEnabled: backgroundMusicEnabled ?? this.backgroundMusicEnabled,
      backgroundMusicStyle: backgroundMusicStyle ?? this.backgroundMusicStyle,
      defaultStyle: defaultStyle ?? this.defaultStyle,
      defaultDailyVideoCount: defaultDailyVideoCount ?? this.defaultDailyVideoCount,
      defaultScheduleTimes: defaultScheduleTimes ?? this.defaultScheduleTimes,
      emailNotificationsEnabled: emailNotificationsEnabled ?? this.emailNotificationsEnabled,
      pushNotificationsEnabled: pushNotificationsEnabled ?? this.pushNotificationsEnabled,
      notifyOnVideoComplete: notifyOnVideoComplete ?? this.notifyOnVideoComplete,
      notifyOnSchedule: notifyOnSchedule ?? this.notifyOnSchedule,
      autoDeleteVideosDays: autoDeleteVideosDays ?? this.autoDeleteVideosDays,
    );
  }

  @override
  List<Object?> get props => [
        defaultNiche,
        defaultVideoType,
        defaultVideoLength,
        defaultAspectRatio,
        characterConsistencyEnabled,
        characterDescription,
        characterImages,
        captionsEnabled,
        captionStyle,
        captionColor,
        captionEmojiEnabled,
        backgroundMusicEnabled,
        backgroundMusicStyle,
        defaultStyle,
        defaultDailyVideoCount,
        defaultScheduleTimes,
        emailNotificationsEnabled,
        pushNotificationsEnabled,
        notifyOnVideoComplete,
        notifyOnSchedule,
        autoDeleteVideosDays,
      ];
}
