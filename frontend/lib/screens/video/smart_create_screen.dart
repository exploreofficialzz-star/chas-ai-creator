import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:image_picker/image_picker.dart';

import '../../config/theme.dart';
import '../../models/user.dart';
import '../../providers/auth_bloc.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_button.dart';

// ── Platform targets ──────────────────────────────────────────────────────────
enum TargetPlatform { tiktok, youtube, instagram, facebook, twitter, linkedin }

extension TargetPlatformExt on TargetPlatform {
  String get label => switch (this) {
        TargetPlatform.tiktok     => 'TikTok',
        TargetPlatform.youtube    => 'YouTube',
        TargetPlatform.instagram  => 'Instagram',
        TargetPlatform.facebook   => 'Facebook',
        TargetPlatform.twitter    => 'X / Twitter',
        TargetPlatform.linkedin   => 'LinkedIn',
      };
  String get icon => switch (this) {
        TargetPlatform.tiktok     => '🎵',
        TargetPlatform.youtube    => '▶️',
        TargetPlatform.instagram  => '📸',
        TargetPlatform.facebook   => '👤',
        TargetPlatform.twitter    => '🐦',
        TargetPlatform.linkedin   => '💼',
      };
  String get bestRatio => switch (this) {
        TargetPlatform.tiktok     => '9:16',
        TargetPlatform.youtube    => '16:9',
        TargetPlatform.instagram  => '1:1',
        TargetPlatform.facebook   => '16:9',
        TargetPlatform.twitter    => '16:9',
        TargetPlatform.linkedin   => '16:9',
      };
}

// ── Audio mode ────────────────────────────────────────────────────────────────
enum AudioMode { silent, narration, soundSync }

extension AudioModeExt on AudioMode {
  String get label => switch (this) {
        AudioMode.silent    => 'Silent',
        AudioMode.narration => 'AI Narration',
        AudioMode.soundSync => 'Sound Sync',
      };
  String get description => switch (this) {
        AudioMode.silent    => 'Background music only',
        AudioMode.narration => 'AI voiceover reads your script',
        AudioMode.soundSync => 'Realistic sounds synced to visuals',
      };
  IconData get icon => switch (this) {
        AudioMode.silent    => Icons.volume_off,
        AudioMode.narration => Icons.record_voice_over,
        AudioMode.soundSync => Icons.graphic_eq,
      };
}

class SmartCreateScreen extends StatefulWidget {
  const SmartCreateScreen({super.key});

  @override
  State<SmartCreateScreen> createState() => _SmartCreateScreenState();
}

class _SmartCreateScreenState extends State<SmartCreateScreen>
    with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  final _ideaController = TextEditingController();
  final _imagePicker = ImagePicker();

  // ── State ──────────────────────────────────────────────────────────────────
  bool _isGenerating = false;
  bool _isCreating = false;
  Map<String, dynamic>? _generatedPlan;
  String _currentStep = '';
  int _currentStepIndex = 0;

  // ── Video settings ─────────────────────────────────────────────────────────
  String _aspectRatio = '9:16';
  int _duration = 30;
  String _style = 'cinematic';
  bool _captionsEnabled = true;
  bool _characterConsistencyEnabled = false;
  AudioMode _audioMode = AudioMode.narration;
  String _voiceStyle = 'professional';
  String _musicStyle = 'upbeat';
  Set<TargetPlatform> _targetPlatforms = {TargetPlatform.tiktok};

  // ── Uploaded images ────────────────────────────────────────────────────────
  List<File> _uploadedImages = [];

  // ── Animation ──────────────────────────────────────────────────────────────
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  late TabController _tabController;

  // ── Steps ──────────────────────────────────────────────────────────────────
  final List<String> _steps = [
    '🔍 Analyzing your idea...',
    '📈 Finding trending topics...',
    '🎯 Optimizing for platforms...',
    '✍️ Writing scene scripts...',
    '🏷️ Generating SEO tags...',
    '✅ Plan ready!',
  ];

  @override
  void initState() {
    super.initState();
    _loadUserSettings();
    _tabController = TabController(length: 3, vsync: this);
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.97, end: 1.03).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ideaController.dispose();
    _pulseController.dispose();
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadUserSettings() async {
    try {
      final settings = await _apiService.getUserSettings();
      if (settings != null && mounted) {
        setState(() {
          _aspectRatio = settings.defaultAspectRatio ?? '9:16';
          _duration = settings.defaultVideoLength ?? 30;
          _style = settings.defaultStyle ?? 'cinematic';
          _captionsEnabled = settings.captionsEnabled ?? true;
          _musicStyle = settings.backgroundMusicStyle ?? 'upbeat';
        });
      }
    } catch (_) {}
  }

  // ── Image picker ───────────────────────────────────────────────────────────
  Future<void> _pickImages() async {
    final picked = await _imagePicker.pickMultiImage(imageQuality: 85);
    if (picked.isNotEmpty) {
      setState(() {
        _uploadedImages = [
          ..._uploadedImages,
          ...picked.map((x) => File(x.path)),
        ].take(6).toList(); // max 6 images
      });
    }
  }

  Future<void> _pickFromCamera() async {
    final picked = await _imagePicker.pickImage(
      source: ImageSource.camera,
      imageQuality: 85,
    );
    if (picked != null) {
      setState(() {
        if (_uploadedImages.length < 6) {
          _uploadedImages.add(File(picked.path));
        }
      });
    }
  }

  void _removeImage(int index) {
    setState(() => _uploadedImages.removeAt(index));
  }

  // ── Generate plan ──────────────────────────────────────────────────────────
  Future<void> _generatePlan() async {
    final idea = _ideaController.text.trim();
    if (idea.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✏️ Describe your video idea first!'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    setState(() {
      _isGenerating = true;
      _generatedPlan = null;
      _currentStepIndex = 0;
      _currentStep = _steps[0];
    });

    // Animate through steps
    for (int i = 0; i < _steps.length - 1; i++) {
      await Future.delayed(const Duration(milliseconds: 700));
      if (mounted) {
        setState(() {
          _currentStepIndex = i + 1;
          _currentStep = _steps[i + 1];
        });
      }
    }

    try {
      // Auto-set aspect ratio from primary platform
      if (_targetPlatforms.isNotEmpty) {
        _aspectRatio = _targetPlatforms.first.bestRatio;
      }

      final plan = await _apiService.smartGeneratePlan(
        idea: idea,
        aspectRatio: _aspectRatio,
        duration: _duration,
        style: _style,
        captionsEnabled: _captionsEnabled,
        backgroundMusicEnabled: _audioMode != AudioMode.silent,
        audioMode: _audioMode.name,
        voiceStyle: _voiceStyle,
        targetPlatforms: _targetPlatforms.map((p) => p.name).toList(),
        characterConsistency: _characterConsistencyEnabled,
        uploadedImageCount: _uploadedImages.length,
      );

      setState(() {
        _generatedPlan = plan;
        _isGenerating = false;
        _currentStep = '';
      });
    } catch (e) {
      setState(() {
        _isGenerating = false;
        _currentStep = '';
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('❌ ${_apiService.handleError(e)}'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  // ── Create video ───────────────────────────────────────────────────────────
  Future<void> _createVideo() async {
    if (_generatedPlan == null) return;

    setState(() {
      _isCreating = true;
      _currentStep = '🚀 Queuing video generation...';
    });

    try {
      await _apiService.createVideo(
        niche: _generatedPlan!['niche'] ?? 'general',
        title: _generatedPlan!['title'],
        description: _generatedPlan!['description'],
        videoType: _audioMode == AudioMode.narration ? 'narration' : 'silent',
        duration: _duration,
        aspectRatio: _aspectRatio,
        style: _style,
        captionsEnabled: _captionsEnabled,
        captionStyle: _generatedPlan!['caption_style'] ?? 'modern',
        backgroundMusicEnabled: _audioMode != AudioMode.silent,
        backgroundMusicStyle: _generatedPlan!['music_style'] ?? 'upbeat',
        characterConsistencyEnabled: _characterConsistencyEnabled,
        userInstructions: _ideaController.text.trim(),
      );

      setState(() {
        _isCreating = false;
        _currentStep = '';
        _generatedPlan = null;
        _ideaController.clear();
        _uploadedImages.clear();
      });

      if (mounted) _showSuccessSheet();
    } catch (e) {
      setState(() {
        _isCreating = false;
        _currentStep = '';
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('❌ ${_apiService.handleError(e)}'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD
  // ─────────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Icon(Icons.auto_awesome, size: 20.w, color: AppTheme.primaryColor),
            SizedBox(width: 8.w),
            const Text('Smart Create'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune),
            tooltip: 'Advanced settings',
            onPressed: _showAdvancedSettings,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(16.w),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Idea box ──────────────────────────────────────────────────
            _buildIdeaBox(),
            SizedBox(height: 16.h),

            // ── Platform selector ─────────────────────────────────────────
            _buildPlatformSelector(),
            SizedBox(height: 16.h),

            // ── Audio mode ────────────────────────────────────────────────
            _buildAudioModeSelector(),
            SizedBox(height: 16.h),

            // ── Image upload ──────────────────────────────────────────────
            _buildImageUpload(),
            SizedBox(height: 16.h),

            // ── Settings row ──────────────────────────────────────────────
            _buildSettingsRow(),
            SizedBox(height: 20.h),

            // ── Generate button ───────────────────────────────────────────
            CustomButton(
              text: _isGenerating
                  ? 'Generating plan...'
                  : '✨ Generate Video Plan',
              isLoading: _isGenerating,
              onPressed: _isGenerating ? null : _generatePlan,
            ),

            // ── Step progress ─────────────────────────────────────────────
            if (_currentStep.isNotEmpty) ...[
              SizedBox(height: 16.h),
              _buildStepProgress(),
            ],

            // ── Generated plan ────────────────────────────────────────────
            if (_generatedPlan != null) ...[
              SizedBox(height: 24.h),
              _buildGeneratedPlan(),
            ],

            SizedBox(height: 40.h),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // IDEA BOX
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildIdeaBox() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryColor.withOpacity(0.08),
            AppTheme.accentColor.withOpacity(0.03),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20.r),
        border: Border.all(
          color: AppTheme.primaryColor.withOpacity(0.2),
          width: 1.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(16.w, 16.h, 16.w, 0),
            child: Row(
              children: [
                Container(
                  padding: EdgeInsets.all(8.w),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10.r),
                  ),
                  child: Icon(Icons.lightbulb_outline,
                      size: 18.w, color: AppTheme.primaryColor),
                ),
                SizedBox(width: 10.w),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Describe your video',
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                      Text(
                        'AI finds trends, writes script & optimizes',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Colors.grey,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: EdgeInsets.all(10.w),
            child: TextField(
              controller: _ideaController,
              maxLines: 4,
              minLines: 3,
              decoration: InputDecoration(
                hintText:
                    'e.g. "A cinematic video about the future of electric cars with dramatic music"\n\n'
                    'or "A day in the life of a professional chef in New York"',
                hintStyle: TextStyle(
                  fontSize: 13.sp,
                  color: Colors.grey.shade500,
                  height: 1.5,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14.r),
                  borderSide: BorderSide.none,
                ),
                filled: true,
                fillColor: Theme.of(context).cardColor,
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 14.w, vertical: 12.h),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PLATFORM SELECTOR
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildPlatformSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionLabel('🌍 Target Platforms', 'Auto-sets aspect ratio & hashtags'),
        SizedBox(height: 10.h),
        Wrap(
          spacing: 8.w,
          runSpacing: 8.h,
          children: TargetPlatform.values.map((p) {
            final selected = _targetPlatforms.contains(p);
            return GestureDetector(
              onTap: () => setState(() {
                if (selected) {
                  if (_targetPlatforms.length > 1) {
                    _targetPlatforms.remove(p);
                  }
                } else {
                  _targetPlatforms.add(p);
                }
              }),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding:
                    EdgeInsets.symmetric(horizontal: 12.w, vertical: 8.h),
                decoration: BoxDecoration(
                  color: selected
                      ? AppTheme.primaryColor.withOpacity(0.15)
                      : Theme.of(context).cardColor,
                  borderRadius: BorderRadius.circular(20.r),
                  border: Border.all(
                    color: selected
                        ? AppTheme.primaryColor
                        : Colors.grey.withOpacity(0.3),
                    width: selected ? 1.5 : 1,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(p.icon, style: TextStyle(fontSize: 14.sp)),
                    SizedBox(width: 6.w),
                    Text(
                      p.label,
                      style: TextStyle(
                        fontSize: 12.sp,
                        fontWeight: selected
                            ? FontWeight.w600
                            : FontWeight.normal,
                        color: selected
                            ? AppTheme.primaryColor
                            : Colors.grey,
                      ),
                    ),
                    if (selected) ...[
                      SizedBox(width: 4.w),
                      Icon(Icons.check,
                          size: 12.w, color: AppTheme.primaryColor),
                    ],
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // AUDIO MODE
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildAudioModeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionLabel('🎙️ Audio Mode', 'Choose how your video sounds'),
        SizedBox(height: 10.h),
        Row(
          children: AudioMode.values.map((mode) {
            final selected = _audioMode == mode;
            return Expanded(
              child: GestureDetector(
                onTap: () => setState(() => _audioMode = mode),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: EdgeInsets.only(
                      right: mode != AudioMode.soundSync ? 8.w : 0),
                  padding: EdgeInsets.symmetric(
                      vertical: 12.h, horizontal: 8.w),
                  decoration: BoxDecoration(
                    color: selected
                        ? AppTheme.primaryColor.withOpacity(0.15)
                        : Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(14.r),
                    border: Border.all(
                      color: selected
                          ? AppTheme.primaryColor
                          : Colors.grey.withOpacity(0.2),
                      width: selected ? 1.5 : 1,
                    ),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        mode.icon,
                        size: 22.w,
                        color: selected
                            ? AppTheme.primaryColor
                            : Colors.grey,
                      ),
                      SizedBox(height: 6.h),
                      Text(
                        mode.label,
                        style: TextStyle(
                          fontSize: 11.sp,
                          fontWeight: selected
                              ? FontWeight.w600
                              : FontWeight.normal,
                          color: selected
                              ? AppTheme.primaryColor
                              : Colors.grey,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      SizedBox(height: 3.h),
                      Text(
                        mode.description,
                        style: TextStyle(
                          fontSize: 9.sp,
                          color: Colors.grey.shade500,
                        ),
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ),
            );
          }).toList(),
        ),

        // Voice style picker — only show when narration selected
        if (_audioMode == AudioMode.narration) ...[
          SizedBox(height: 12.h),
          Text(
            'Voice Style',
            style: Theme.of(context)
                .textTheme
                .labelMedium
                ?.copyWith(color: Colors.grey),
          ),
          SizedBox(height: 8.h),
          Wrap(
            spacing: 8.w,
            runSpacing: 6.h,
            children: [
              'professional', 'friendly', 'dramatic',
              'energetic', 'calm', 'authoritative'
            ].map((v) {
              final sel = _voiceStyle == v;
              return GestureDetector(
                onTap: () => setState(() => _voiceStyle = v),
                child: Container(
                  padding: EdgeInsets.symmetric(
                      horizontal: 12.w, vertical: 6.h),
                  decoration: BoxDecoration(
                    color: sel
                        ? AppTheme.accentColor.withOpacity(0.15)
                        : Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(20.r),
                    border: Border.all(
                      color: sel
                          ? AppTheme.accentColor
                          : Colors.grey.withOpacity(0.2),
                    ),
                  ),
                  child: Text(
                    v[0].toUpperCase() + v.substring(1),
                    style: TextStyle(
                      fontSize: 12.sp,
                      color: sel ? AppTheme.accentColor : Colors.grey,
                      fontWeight:
                          sel ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // IMAGE UPLOAD
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildImageUpload() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: _buildSectionLabel(
                '📸 Reference Images (Optional)',
                'Upload up to 6 images for character/scene consistency',
              ),
            ),
            if (_characterConsistencyEnabled)
              Container(
                padding: EdgeInsets.symmetric(
                    horizontal: 8.w, vertical: 4.h),
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8.r),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.lock,
                        size: 10.w, color: AppTheme.primaryColor),
                    SizedBox(width: 4.w),
                    Text(
                      'Consistency ON',
                      style: TextStyle(
                          fontSize: 10.sp, color: AppTheme.primaryColor),
                    ),
                  ],
                ),
              ),
          ],
        ),
        SizedBox(height: 10.h),
        SizedBox(
          height: 90.h,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              // Add buttons
              _buildImageAddButton(Icons.photo_library, 'Gallery', _pickImages),
              SizedBox(width: 8.w),
              _buildImageAddButton(
                  Icons.camera_alt, 'Camera', _pickFromCamera),
              SizedBox(width: 8.w),

              // Uploaded images
              ..._uploadedImages.asMap().entries.map((entry) {
                return Container(
                  width: 80.w,
                  height: 90.h,
                  margin: EdgeInsets.only(right: 8.w),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12.r),
                    image: DecorationImage(
                      image: FileImage(entry.value),
                      fit: BoxFit.cover,
                    ),
                  ),
                  child: Stack(
                    children: [
                      Positioned(
                        top: 4,
                        right: 4,
                        child: GestureDetector(
                          onTap: () => _removeImage(entry.key),
                          child: Container(
                            width: 20.w,
                            height: 20.w,
                            decoration: const BoxDecoration(
                              color: Colors.red,
                              shape: BoxShape.circle,
                            ),
                            child: Icon(Icons.close,
                                size: 12.w, color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ],
          ),
        ),

        if (_uploadedImages.isNotEmpty) ...[
          SizedBox(height: 10.h),
          SwitchListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            title: Text(
              'Character Consistency',
              style: TextStyle(fontSize: 13.sp, fontWeight: FontWeight.w500),
            ),
            subtitle: Text(
              'Keep characters consistent across all scenes',
              style: TextStyle(fontSize: 11.sp, color: Colors.grey),
            ),
            value: _characterConsistencyEnabled,
            onChanged: (v) =>
                setState(() => _characterConsistencyEnabled = v),
            secondary: Icon(Icons.face_retouching_natural,
                color: AppTheme.primaryColor, size: 20.w),
          ),
        ],
      ],
    );
  }

  Widget _buildImageAddButton(
      IconData icon, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 80.w,
        height: 90.h,
        decoration: BoxDecoration(
          color: AppTheme.primaryColor.withOpacity(0.06),
          borderRadius: BorderRadius.circular(12.r),
          border: Border.all(
            color: AppTheme.primaryColor.withOpacity(0.2),
            style: BorderStyle.solid,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 24.w, color: AppTheme.primaryColor),
            SizedBox(height: 6.h),
            Text(
              label,
              style: TextStyle(
                  fontSize: 11.sp, color: AppTheme.primaryColor),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SETTINGS ROW
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildSettingsRow() {
    return Container(
      padding: EdgeInsets.all(12.w),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(14.r),
      ),
      child: Row(
        children: [
          _buildSettingItem(Icons.aspect_ratio, _aspectRatio),
          _buildDivider(),
          _buildSettingItem(Icons.timer, '${_duration}s'),
          _buildDivider(),
          _buildSettingItem(Icons.style, _style),
          _buildDivider(),
          _buildSettingItem(
            Icons.closed_caption,
            _captionsEnabled ? 'CC ON' : 'CC OFF',
            active: _captionsEnabled,
          ),
          const Spacer(),
          GestureDetector(
            onTap: _showAdvancedSettings,
            child: Container(
              padding: EdgeInsets.all(6.w),
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8.r),
              ),
              child: Icon(Icons.tune,
                  size: 16.w, color: AppTheme.primaryColor),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSettingItem(IconData icon, String label,
      {bool active = true}) {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 6.w),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon,
              size: 13.w,
              color: active ? AppTheme.primaryColor : Colors.grey),
          SizedBox(width: 4.w),
          Text(
            label,
            style: TextStyle(
              fontSize: 11.sp,
              color: active ? AppTheme.primaryColor : Colors.grey,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDivider() => Container(
        width: 1,
        height: 14.h,
        color: Colors.grey.withOpacity(0.2),
        margin: EdgeInsets.symmetric(horizontal: 4.w),
      );

  // ─────────────────────────────────────────────────────────────────────────
  // STEP PROGRESS
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStepProgress() {
    return ScaleTransition(
      scale: _pulseAnimation,
      child: Container(
        padding: EdgeInsets.all(16.w),
        decoration: BoxDecoration(
          color: AppTheme.primaryColor.withOpacity(0.07),
          borderRadius: BorderRadius.circular(14.r),
          border: Border.all(
              color: AppTheme.primaryColor.withOpacity(0.15)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                SizedBox(
                  width: 16.w,
                  height: 16.w,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppTheme.primaryColor,
                  ),
                ),
                SizedBox(width: 10.w),
                Text(
                  _currentStep,
                  style: TextStyle(
                    fontSize: 13.sp,
                    color: AppTheme.primaryColor,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
            SizedBox(height: 10.h),
            // Progress dots
            Row(
              children: List.generate(_steps.length, (i) {
                final done = i <= _currentStepIndex;
                return Expanded(
                  child: Container(
                    height: 3.h,
                    margin: EdgeInsets.only(right: i < _steps.length - 1 ? 3.w : 0),
                    decoration: BoxDecoration(
                      color: done
                          ? AppTheme.primaryColor
                          : AppTheme.primaryColor.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(2.r),
                    ),
                  ),
                );
              }),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GENERATED PLAN
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildGeneratedPlan() {
    final plan = _generatedPlan!;
    final scenes = (plan['scenes'] as List?) ?? [];
    final hashtags = (plan['hashtags'] as List?) ?? [];
    final seoTags = (plan['seo_tags'] as List?) ?? [];
    final platformTips =
        (plan['platform_tips'] as Map?) ?? {};

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        Row(
          children: [
            Icon(Icons.auto_awesome,
                size: 18.w, color: AppTheme.primaryColor),
            SizedBox(width: 8.w),
            Text(
              'Your Video Plan',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: _generatePlan,
              icon: Icon(Icons.refresh, size: 14.w),
              label: const Text('Redo'),
              style: TextButton.styleFrom(
                  padding: EdgeInsets.symmetric(
                      horizontal: 8.w, vertical: 4.h)),
            ),
          ],
        ),

        SizedBox(height: 12.h),

        // Tab bar — Scenes / Copy / Platforms
        Container(
          decoration: BoxDecoration(
            color: Theme.of(context).cardColor,
            borderRadius: BorderRadius.circular(12.r),
          ),
          child: TabBar(
            controller: _tabController,
            indicatorSize: TabBarIndicatorSize.tab,
            indicator: BoxDecoration(
              color: AppTheme.primaryColor,
              borderRadius: BorderRadius.circular(10.r),
            ),
            labelColor: Colors.white,
            unselectedLabelColor: Colors.grey,
            labelStyle: TextStyle(
                fontSize: 12.sp, fontWeight: FontWeight.w600),
            tabs: const [
              Tab(text: '🎬 Scenes'),
              Tab(text: '🏷️ Copy'),
              Tab(text: '📱 Platforms'),
            ],
          ),
        ),

        SizedBox(height: 12.h),

        SizedBox(
          height: 380.h,
          child: TabBarView(
            controller: _tabController,
            children: [
              // ── TAB 1: Scenes ────────────────────────────────────────
              _buildScenesTab(plan, scenes),

              // ── TAB 2: Copy / Tags ───────────────────────────────────
              _buildCopyTab(plan, hashtags, seoTags),

              // ── TAB 3: Platform tips ─────────────────────────────────
              _buildPlatformsTab(platformTips),
            ],
          ),
        ),

        SizedBox(height: 20.h),

        // Create button
        CustomButton(
          text: _isCreating ? 'Creating your video...' : '🎬 Create This Video',
          isLoading: _isCreating,
          onPressed: _isCreating ? null : _createVideo,
        ),

        SizedBox(height: 10.h),

        CustomButton(
          text: '✏️ Edit idea',
          isOutlined: true,
          onPressed: () => setState(() => _generatedPlan = null),
        ),
      ],
    );
  }

  Widget _buildScenesTab(Map plan, List scenes) {
    return SingleChildScrollView(
      child: Column(
        children: [
          // Title card
          Container(
            padding: EdgeInsets.all(16.w),
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: BorderRadius.circular(16.r),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  plan['title'] ?? 'Untitled',
                  style: TextStyle(
                    fontSize: 16.sp,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                SizedBox(height: 6.h),
                Text(
                  plan['description'] ?? '',
                  style: TextStyle(
                      fontSize: 12.sp, color: Colors.white70),
                ),
                SizedBox(height: 10.h),
                Wrap(
                  spacing: 6.w,
                  children: [
                    _planBadge(Icons.category, plan['niche'] ?? ''),
                    _planBadge(Icons.music_note, plan['music_style'] ?? ''),
                    _planBadge(Icons.mic, _audioMode.label),
                  ],
                ),
              ],
            ),
          ),

          SizedBox(height: 10.h),

          Text(
            '${scenes.length} Scenes',
            style: Theme.of(context)
                .textTheme
                .labelMedium
                ?.copyWith(color: Colors.grey),
          ),

          SizedBox(height: 8.h),

          ...scenes.asMap().entries.map((e) =>
              _buildSceneCard(e.key + 1, e.value as Map<String, dynamic>)),
        ],
      ),
    );
  }

  Widget _buildCopyTab(Map plan, List hashtags, List seoTags) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _copySection(
            '📝 Trending Title',
            plan['title'] ?? '',
            onCopy: () => _copyToClipboard(plan['title'] ?? ''),
          ),
          SizedBox(height: 12.h),
          _copySection(
            '📄 Caption / Description',
            plan['caption'] ?? plan['description'] ?? '',
            onCopy: () => _copyToClipboard(
                plan['caption'] ?? plan['description'] ?? ''),
          ),
          SizedBox(height: 12.h),

          // Hashtags
          _buildTagsSection('🔥 Hashtags', hashtags,
              color: AppTheme.primaryColor),
          SizedBox(height: 12.h),

          // SEO Tags
          _buildTagsSection('🔍 SEO Tags', seoTags,
              color: AppTheme.accentColor),
        ],
      ),
    );
  }

  Widget _buildPlatformsTab(Map platformTips) {
    if (platformTips.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.info_outline, color: Colors.grey, size: 32.w),
            SizedBox(height: 8.h),
            Text(
              'Select platforms above\nto see optimization tips',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey, fontSize: 13.sp),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: Column(
        children: TargetPlatform.values
            .where((p) => _targetPlatforms.contains(p))
            .map((p) {
          final tips = platformTips[p.name] as Map? ?? {};
          return Container(
            margin: EdgeInsets.only(bottom: 10.h),
            padding: EdgeInsets.all(14.w),
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              borderRadius: BorderRadius.circular(12.r),
              border: Border.all(
                  color: AppTheme.primaryColor.withOpacity(0.1)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(p.icon,
                        style: TextStyle(fontSize: 18.sp)),
                    SizedBox(width: 8.w),
                    Text(
                      p.label,
                      style: TextStyle(
                        fontSize: 14.sp,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Spacer(),
                    Container(
                      padding: EdgeInsets.symmetric(
                          horizontal: 8.w, vertical: 3.h),
                      decoration: BoxDecoration(
                        color: Colors.green.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8.r),
                      ),
                      child: Text(
                        p.bestRatio,
                        style: TextStyle(
                          fontSize: 10.sp,
                          color: Colors.green,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                if (tips['tip'] != null) ...[
                  SizedBox(height: 8.h),
                  Text(
                    tips['tip'].toString(),
                    style: TextStyle(
                        fontSize: 12.sp, color: Colors.grey),
                  ),
                ],
                if (tips['best_time'] != null) ...[
                  SizedBox(height: 6.h),
                  Row(
                    children: [
                      Icon(Icons.schedule,
                          size: 13.w, color: Colors.orange),
                      SizedBox(width: 4.w),
                      Text(
                        'Best time: ${tips['best_time']}',
                        style: TextStyle(
                          fontSize: 11.sp,
                          color: Colors.orange,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _copySection(String title, String content,
      {required VoidCallback onCopy}) {
    return Container(
      padding: EdgeInsets.all(12.w),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(12.r),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(title,
                  style: TextStyle(
                      fontSize: 12.sp,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey)),
              const Spacer(),
              GestureDetector(
                onTap: onCopy,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.copy, size: 14.w, color: AppTheme.primaryColor),
                    SizedBox(width: 4.w),
                    Text('Copy',
                        style: TextStyle(
                            fontSize: 11.sp,
                            color: AppTheme.primaryColor)),
                  ],
                ),
              ),
            ],
          ),
          SizedBox(height: 6.h),
          Text(content, style: TextStyle(fontSize: 13.sp)),
        ],
      ),
    );
  }

  Widget _buildTagsSection(String title, List tags, {required Color color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(title,
                style: TextStyle(
                    fontSize: 12.sp,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey)),
            const Spacer(),
            GestureDetector(
              onTap: () => _copyToClipboard(tags.join(' ')),
              child: Text('Copy all',
                  style: TextStyle(
                      fontSize: 11.sp, color: AppTheme.primaryColor)),
            ),
          ],
        ),
        SizedBox(height: 8.h),
        Wrap(
          spacing: 6.w,
          runSpacing: 6.h,
          children: tags
              .map((tag) => Container(
                    padding: EdgeInsets.symmetric(
                        horizontal: 10.w, vertical: 4.h),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(20.r),
                      border: Border.all(color: color.withOpacity(0.2)),
                    ),
                    child: Text(
                      tag.toString(),
                      style:
                          TextStyle(fontSize: 11.sp, color: color),
                    ),
                  ))
              .toList(),
        ),
      ],
    );
  }

  Widget _buildSceneCard(int number, Map<String, dynamic> scene) {
    return Container(
      margin: EdgeInsets.only(bottom: 8.h),
      padding: EdgeInsets.all(12.w),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(12.r),
        border: Border.all(
            color: AppTheme.primaryColor.withOpacity(0.08)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 26.w,
            height: 26.w,
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                '$number',
                style: TextStyle(
                  fontSize: 11.sp,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryColor,
                ),
              ),
            ),
          ),
          SizedBox(width: 10.w),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  scene['description'] ?? '',
                  style: TextStyle(
                      fontSize: 13.sp, fontWeight: FontWeight.w500),
                ),
                if ((scene['caption'] ?? '').isNotEmpty) ...[
                  SizedBox(height: 4.h),
                  Text(
                    scene['caption'],
                    style: TextStyle(
                      fontSize: 11.sp,
                      color: AppTheme.primaryColor,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
                if (_audioMode == AudioMode.narration &&
                    (scene['narration'] ?? '').isNotEmpty) ...[
                  SizedBox(height: 4.h),
                  Row(
                    children: [
                      Icon(Icons.mic,
                          size: 11.w, color: Colors.orange),
                      SizedBox(width: 4.w),
                      Expanded(
                        child: Text(
                          scene['narration'],
                          style: TextStyle(
                            fontSize: 11.sp,
                            color: Colors.orange.shade300,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _planBadge(IconData icon, String label) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 8.w, vertical: 4.h),
      decoration: BoxDecoration(
        color: Colors.white24,
        borderRadius: BorderRadius.circular(8.r),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11.w, color: Colors.white),
          SizedBox(width: 4.w),
          Text(label,
              style: TextStyle(
                  fontSize: 10.sp,
                  color: Colors.white,
                  fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ADVANCED SETTINGS SHEET
  // ─────────────────────────────────────────────────────────────────────────

  void _showAdvancedSettings() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setSheet) => Container(
          padding: EdgeInsets.all(24.w),
          decoration: BoxDecoration(
            color: Theme.of(context).scaffoldBackgroundColor,
            borderRadius:
                BorderRadius.vertical(top: Radius.circular(24.r)),
          ),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40.w,
                    height: 4.h,
                    decoration: BoxDecoration(
                      color: Colors.grey.shade300,
                      borderRadius: BorderRadius.circular(2.r),
                    ),
                  ),
                ),
                SizedBox(height: 20.h),
                Text('⚙️ Advanced Settings',
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.bold)),
                SizedBox(height: 20.h),

                // Aspect Ratio
                Text('Aspect Ratio',
                    style: Theme.of(context).textTheme.labelLarge),
                SizedBox(height: 8.h),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: '9:16', label: Text('9:16')),
                    ButtonSegment(value: '16:9', label: Text('16:9')),
                    ButtonSegment(value: '1:1', label: Text('1:1')),
                  ],
                  selected: {_aspectRatio},
                  onSelectionChanged: (v) {
                    setSheet(() {});
                    setState(() => _aspectRatio = v.first);
                  },
                ),

                SizedBox(height: 16.h),

                // Duration
                Text('Duration: ${_duration}s',
                    style: Theme.of(context).textTheme.labelLarge),
                Slider(
                  value: _duration.toDouble(),
                  min: 10,
                  max: 120,
                  divisions: 11,
                  label: '${_duration}s',
                  onChanged: (v) {
                    setSheet(() {});
                    setState(() => _duration = v.toInt());
                  },
                ),

                SizedBox(height: 8.h),

                // Visual Style
                Text('Visual Style',
                    style: Theme.of(context).textTheme.labelLarge),
                SizedBox(height: 8.h),
                Wrap(
                  spacing: 8.w,
                  runSpacing: 6.h,
                  children: [
                    'cinematic', 'cartoon', 'realistic',
                    'dramatic', 'minimal', 'funny'
                  ]
                      .map((s) => ChoiceChip(
                            label: Text(s),
                            selected: _style == s,
                            onSelected: (_) {
                              setSheet(() {});
                              setState(() => _style = s);
                            },
                          ))
                      .toList(),
                ),

                SizedBox(height: 8.h),

                // Music Style
                Text('Music Style',
                    style: Theme.of(context).textTheme.labelLarge),
                SizedBox(height: 8.h),
                Wrap(
                  spacing: 8.w,
                  runSpacing: 6.h,
                  children: [
                    'upbeat', 'calm', 'dramatic',
                    'inspirational', 'epic', 'lofi', 'none'
                  ]
                      .map((s) => ChoiceChip(
                            label: Text(s),
                            selected: _musicStyle == s,
                            onSelected: (_) {
                              setSheet(() {});
                              setState(() => _musicStyle = s);
                            },
                          ))
                      .toList(),
                ),

                SizedBox(height: 8.h),

                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Enable Captions'),
                  value: _captionsEnabled,
                  onChanged: (v) {
                    setSheet(() {});
                    setState(() => _captionsEnabled = v);
                  },
                  secondary: const Icon(Icons.closed_caption),
                ),

                SizedBox(height: 16.h),

                CustomButton(
                  text: 'Done',
                  onPressed: () => Navigator.pop(context),
                ),
                SizedBox(height: 16.h),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildSectionLabel(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w600)),
        Text(subtitle,
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: Colors.grey)),
      ],
    );
  }

  void _copyToClipboard(String text) {
    // ignore: deprecated_member_use
    // Use Clipboard.setData in real implementation
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('✅ Copied to clipboard!'),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _showSuccessSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: EdgeInsets.all(32.w),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72.w,
              height: 72.w,
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.check_circle,
                  size: 38.w, color: Colors.green),
            ),
            SizedBox(height: 16.h),
            Text('Video is generating! 🎉',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 8.h),
            Text(
              'Your video is being created.\nCheck My Videos to track progress.',
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: Colors.grey),
            ),
            SizedBox(height: 24.h),
            CustomButton(
              text: 'Got it!',
              onPressed: () => Navigator.pop(context),
            ),
            SizedBox(height: 16.h),
          ],
        ),
      ),
    );
  }
}
