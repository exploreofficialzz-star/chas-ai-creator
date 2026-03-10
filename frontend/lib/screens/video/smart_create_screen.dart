import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../models/user.dart';
import '../../providers/auth_bloc.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_button.dart';

class SmartCreateScreen extends StatefulWidget {
  const SmartCreateScreen({super.key});

  @override
  State<SmartCreateScreen> createState() => _SmartCreateScreenState();
}

class _SmartCreateScreenState extends State<SmartCreateScreen>
    with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  final _ideaController = TextEditingController();

  bool _isGenerating = false;
  bool _isCreating = false;
  Map<String, dynamic>? _generatedPlan;
  String _currentStep = '';

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  // These come from the user's saved settings
  String _aspectRatio = '9:16';
  int _duration = 30;
  String _style = 'cinematic';
  bool _captionsEnabled = true;
  bool _backgroundMusicEnabled = true;

  @override
  void initState() {
    super.initState();
    _loadUserSettings();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ideaController.dispose();
    _pulseController.dispose();
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
          _backgroundMusicEnabled = settings.backgroundMusicEnabled ?? true;
        });
      }
    } catch (_) {}
  }

  Future<void> _generatePlan() async {
    final idea = _ideaController.text.trim();
    if (idea.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('✏️ Please describe your video idea first!')),
      );
      return;
    }

    setState(() {
      _isGenerating = true;
      _generatedPlan = null;
      _currentStep = '✍️ Understanding your idea...';
    });

    try {
      await Future.delayed(const Duration(milliseconds: 600));
      setState(() => _currentStep = '🎯 Picking the best niche...');

      await Future.delayed(const Duration(milliseconds: 600));
      setState(() => _currentStep = '🎨 Writing scene prompts...');

      final plan = await _apiService.smartGeneratePlan(
        idea: idea,
        aspectRatio: _aspectRatio,
        duration: _duration,
        style: _style,
        captionsEnabled: _captionsEnabled,
        backgroundMusicEnabled: _backgroundMusicEnabled,
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
          SnackBar(content: Text('❌ Failed to plan video: $e')),
        );
      }
    }
  }

  Future<void> _createVideo() async {
    if (_generatedPlan == null) return;

    setState(() {
      _isCreating = true;
      _currentStep = '🚀 Sending to generation queue...';
    });

    try {
      await _apiService.createVideo(
        niche: _generatedPlan!['niche'] ?? 'general',
        title: _generatedPlan!['title'],
        description: _generatedPlan!['description'],
        videoType: 'silent',
        duration: _duration,
        aspectRatio: _aspectRatio,
        style: _style,
        captionsEnabled: _captionsEnabled,
        captionStyle: _generatedPlan!['caption_style'] ?? 'modern',
        backgroundMusicEnabled: _backgroundMusicEnabled,
        backgroundMusicStyle: _generatedPlan!['music_style'] ?? 'upbeat',
        userInstructions: _ideaController.text.trim(),
      );

      setState(() {
        _isCreating = false;
        _currentStep = '';
        _generatedPlan = null;
        _ideaController.clear();
      });

      if (mounted) {
        _showSuccessSheet();
      }
    } catch (e) {
      setState(() {
        _isCreating = false;
        _currentStep = '';
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('❌ Failed to create video: $e')),
        );
      }
    }
  }

  void _showSuccessSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: EdgeInsets.all(32.w),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72.w,
              height: 72.w,
              decoration: BoxDecoration(
                color: AppTheme.successColor.withOpacity(0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.check_circle,
                  size: 40.w, color: AppTheme.successColor),
            ),
            SizedBox(height: 16.h),
            Text(
              'Video is generating! 🎉',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            SizedBox(height: 8.h),
            Text(
              'Your video is being created based on your idea.\nCheck My Videos to track progress.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey,
                  ),
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

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {
        User? user;
        if (state is Authenticated) user = state.user;

        return Scaffold(
          appBar: AppBar(
            title: Row(
              children: [
                Icon(Icons.auto_awesome,
                    size: 20.w, color: AppTheme.primaryColor),
                SizedBox(width: 8.w),
                const Text('Smart Create'),
              ],
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.tune),
                tooltip: 'Video settings',
                onPressed: _showSettingsSheet,
              ),
            ],
          ),
          body: SingleChildScrollView(
            padding: EdgeInsets.all(20.w),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Hero prompt box ──────────────────────────────────────
                _buildIdeaBox(),

                SizedBox(height: 16.h),

                // ── Settings chips ───────────────────────────────────────
                _buildSettingsChips(),

                SizedBox(height: 20.h),

                // ── Generate button ──────────────────────────────────────
                CustomButton(
                  text: _isGenerating ? 'Planning your video...' : '✨ Generate Video Plan',
                  isLoading: _isGenerating,
                  onPressed: _isGenerating ? null : _generatePlan,
                ),

                // ── Step indicator ───────────────────────────────────────
                if (_currentStep.isNotEmpty) ...[
                  SizedBox(height: 16.h),
                  _buildStepIndicator(),
                ],

                // ── Generated plan card ──────────────────────────────────
                if (_generatedPlan != null) ...[
                  SizedBox(height: 24.h),
                  _buildGeneratedPlan(),
                ],

                SizedBox(height: 32.h),
              ],
            ),
          ),
        );
      },
    );
  }

  // ── IDEA BOX ─────────────────────────────────────────────────────────────

  Widget _buildIdeaBox() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryColor.withOpacity(0.08),
            AppTheme.accentColor.withOpacity(0.04),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20.r),
        border: Border.all(
          color: AppTheme.primaryColor.withOpacity(0.25),
          width: 1.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(20.w, 20.h, 20.w, 0),
            child: Row(
              children: [
                Container(
                  padding: EdgeInsets.all(8.w),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10.r),
                  ),
                  child: Icon(Icons.lightbulb_outline,
                      size: 20.w, color: AppTheme.primaryColor),
                ),
                SizedBox(width: 10.w),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Describe your video idea',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                      Text(
                        'AI will plan and generate it for you',
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
            padding: EdgeInsets.all(12.w),
            child: TextField(
              controller: _ideaController,
              maxLines: 5,
              minLines: 3,
              textInputAction: TextInputAction.newline,
              decoration: InputDecoration(
                hintText:
                    'e.g. "A video showing 5 benefits of drinking water every morning, '
                    'with motivational captions and upbeat music"\n\n'
                    'or "Funny Nigerian street food video showing suya, puff puff, and shawarma"',
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
                    EdgeInsets.symmetric(horizontal: 16.w, vertical: 14.h),
              ),
            ),
          ),
          // Example chips
          Padding(
            padding: EdgeInsets.fromLTRB(12.w, 0, 12.w, 16.h),
            child: Wrap(
              spacing: 8.w,
              runSpacing: 6.h,
              children: [
                _buildExampleChip('💪 Fitness tips'),
                _buildExampleChip('🍲 Nigerian recipes'),
                _buildExampleChip('💰 Money advice'),
                _buildExampleChip('🐾 Cute animals'),
                _buildExampleChip('🚀 Tech trends'),
                _buildExampleChip('✈️ Travel Nigeria'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExampleChip(String label) {
    return GestureDetector(
      onTap: () {
        // Strip emoji for cleaner text, keep label
        final text = label.replaceAll(RegExp(r'[^\w\s]'), '').trim();
        _ideaController.text =
            'Create an engaging short video about $text for a Nigerian audience';
        _ideaController.selection = TextSelection.fromPosition(
          TextPosition(offset: _ideaController.text.length),
        );
      },
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: 10.w, vertical: 6.h),
        decoration: BoxDecoration(
          color: AppTheme.primaryColor.withOpacity(0.1),
          borderRadius: BorderRadius.circular(20.r),
          border: Border.all(
            color: AppTheme.primaryColor.withOpacity(0.2),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12.sp,
            color: AppTheme.primaryColor,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  // ── SETTINGS CHIPS ────────────────────────────────────────────────────────

  Widget _buildSettingsChips() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Video Settings',
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: Colors.grey,
                fontWeight: FontWeight.w600,
              ),
        ),
        SizedBox(height: 8.h),
        Wrap(
          spacing: 8.w,
          runSpacing: 8.h,
          children: [
            _buildChip(Icons.aspect_ratio, _aspectRatio),
            _buildChip(Icons.timer, '${_duration}s'),
            _buildChip(Icons.style, _style),
            _buildChip(
              Icons.closed_caption,
              _captionsEnabled ? 'Captions ON' : 'Captions OFF',
              active: _captionsEnabled,
            ),
            _buildChip(
              Icons.music_note,
              _backgroundMusicEnabled ? 'Music ON' : 'Music OFF',
              active: _backgroundMusicEnabled,
            ),
          ],
        ),
        SizedBox(height: 4.h),
        GestureDetector(
          onTap: _showSettingsSheet,
          child: Text(
            'Tap ⚙️ to change settings',
            style: TextStyle(
              fontSize: 11.sp,
              color: AppTheme.primaryColor,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildChip(IconData icon, String label, {bool active = true}) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 10.w, vertical: 6.h),
      decoration: BoxDecoration(
        color: active
            ? AppTheme.primaryColor.withOpacity(0.1)
            : Colors.grey.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20.r),
        border: Border.all(
          color: active
              ? AppTheme.primaryColor.withOpacity(0.3)
              : Colors.grey.withOpacity(0.2),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon,
              size: 14.w,
              color: active ? AppTheme.primaryColor : Colors.grey),
          SizedBox(width: 4.w),
          Text(
            label,
            style: TextStyle(
              fontSize: 12.sp,
              color: active ? AppTheme.primaryColor : Colors.grey,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  // ── STEP INDICATOR ────────────────────────────────────────────────────────

  Widget _buildStepIndicator() {
    return ScaleTransition(
      scale: _pulseAnimation,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: 20.w, vertical: 14.h),
        decoration: BoxDecoration(
          color: AppTheme.primaryColor.withOpacity(0.08),
          borderRadius: BorderRadius.circular(12.r),
          border: Border.all(color: AppTheme.primaryColor.withOpacity(0.2)),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 18.w,
              height: 18.w,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppTheme.primaryColor,
              ),
            ),
            SizedBox(width: 12.w),
            Text(
              _currentStep,
              style: TextStyle(
                fontSize: 14.sp,
                color: AppTheme.primaryColor,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── GENERATED PLAN ────────────────────────────────────────────────────────

  Widget _buildGeneratedPlan() {
    final plan = _generatedPlan!;
    final scenes = (plan['scenes'] as List?) ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        Row(
          children: [
            Icon(Icons.auto_awesome, size: 18.w, color: AppTheme.primaryColor),
            SizedBox(width: 8.w),
            Text(
              'Your Video Plan',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: _generatePlan,
              icon: Icon(Icons.refresh, size: 16.w),
              label: const Text('Regenerate'),
            ),
          ],
        ),

        SizedBox(height: 12.h),

        // Title & description card
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
                  fontSize: 17.sp,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              SizedBox(height: 6.h),
              Text(
                plan['description'] ?? '',
                style: TextStyle(
                  fontSize: 13.sp,
                  color: Colors.white70,
                ),
              ),
              SizedBox(height: 12.h),
              Wrap(
                spacing: 8.w,
                children: [
                  _buildPlanBadge(
                      Icons.category, plan['niche'] ?? 'general'),
                  _buildPlanBadge(Icons.music_note,
                      plan['music_style'] ?? 'upbeat'),
                  _buildPlanBadge(Icons.closed_caption,
                      plan['caption_style'] ?? 'modern'),
                ],
              ),
            ],
          ),
        ),

        SizedBox(height: 12.h),

        // Scenes preview
        Text(
          '${scenes.length} Scenes',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: Colors.grey,
                fontWeight: FontWeight.w600,
              ),
        ),
        SizedBox(height: 8.h),
        ...scenes.asMap().entries.map((entry) {
          final i = entry.key;
          final scene = entry.value as Map<String, dynamic>;
          return _buildScenePreviewCard(i + 1, scene);
        }),

        // Hashtags
        if (plan['hashtags'] != null) ...[
          SizedBox(height: 12.h),
          Wrap(
            spacing: 6.w,
            runSpacing: 6.h,
            children: ((plan['hashtags'] as List?) ?? [])
                .map((tag) => Container(
                      padding: EdgeInsets.symmetric(
                          horizontal: 10.w, vertical: 4.h),
                      decoration: BoxDecoration(
                        color:
                            AppTheme.accentColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(20.r),
                      ),
                      child: Text(
                        tag.toString(),
                        style: TextStyle(
                          fontSize: 11.sp,
                          color: AppTheme.accentColor,
                        ),
                      ),
                    ))
                .toList(),
          ),
        ],

        SizedBox(height: 20.h),

        // Create button
        CustomButton(
          text: _isCreating ? 'Creating your video...' : '🎬 Create This Video',
          isLoading: _isCreating,
          onPressed: _isCreating ? null : _createVideo,
        ),

        SizedBox(height: 12.h),

        CustomButton(
          text: 'Edit idea',
          isOutlined: true,
          onPressed: () => setState(() => _generatedPlan = null),
        ),
      ],
    );
  }

  Widget _buildScenePreviewCard(int number, Map<String, dynamic> scene) {
    return Container(
      margin: EdgeInsets.only(bottom: 8.h),
      padding: EdgeInsets.all(14.w),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(12.r),
        border: Border.all(
          color: AppTheme.primaryColor.withOpacity(0.1),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 28.w,
            height: 28.w,
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                '$number',
                style: TextStyle(
                  fontSize: 12.sp,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryColor,
                ),
              ),
            ),
          ),
          SizedBox(width: 12.w),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  scene['description'] ?? '',
                  style: TextStyle(
                    fontSize: 13.sp,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                if (scene['caption'] != null &&
                    (scene['caption'] as String).isNotEmpty) ...[
                  SizedBox(height: 4.h),
                  Text(
                    scene['caption'],
                    style: TextStyle(
                      fontSize: 12.sp,
                      color: AppTheme.primaryColor,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPlanBadge(IconData icon, String label) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 8.w, vertical: 4.h),
      decoration: BoxDecoration(
        color: Colors.white24,
        borderRadius: BorderRadius.circular(8.r),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12.w, color: Colors.white),
          SizedBox(width: 4.w),
          Text(
            label,
            style: TextStyle(
              fontSize: 11.sp,
              color: Colors.white,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  // ── SETTINGS SHEET ────────────────────────────────────────────────────────

  void _showSettingsSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => StatefulBuilder(
        builder: (context, setSheetState) => Container(
          padding: EdgeInsets.all(24.w),
          decoration: BoxDecoration(
            color: Theme.of(context).scaffoldBackgroundColor,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24.r)),
          ),
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
              Text(
                '⚙️ Video Settings',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              SizedBox(height: 20.h),

              // Aspect Ratio
              Text('Aspect Ratio',
                  style: Theme.of(context).textTheme.labelLarge),
              SizedBox(height: 8.h),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: '9:16', label: Text('9:16 (TikTok)')),
                  ButtonSegment(value: '16:9', label: Text('16:9 (YouTube)')),
                  ButtonSegment(value: '1:1', label: Text('1:1 (IG)')),
                ],
                selected: {_aspectRatio},
                onSelectionChanged: (v) {
                  setSheetState(() {});
                  setState(() => _aspectRatio = v.first);
                },
              ),

              SizedBox(height: 16.h),

              // Duration
              Text(
                'Duration: ${_duration}s',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              Slider(
                value: _duration.toDouble(),
                min: 10,
                max: 120,
                divisions: 11,
                label: '${_duration}s',
                onChanged: (v) {
                  setSheetState(() {});
                  setState(() => _duration = v.toInt());
                },
              ),

              SizedBox(height: 8.h),

              // Style
              Text('Visual Style',
                  style: Theme.of(context).textTheme.labelLarge),
              SizedBox(height: 8.h),
              Wrap(
                spacing: 8.w,
                runSpacing: 8.h,
                children: ['cinematic', 'cartoon', 'realistic',
                    'dramatic', 'minimal', 'funny']
                    .map((s) => ChoiceChip(
                          label: Text(s),
                          selected: _style == s,
                          onSelected: (_) {
                            setSheetState(() {});
                            setState(() => _style = s);
                          },
                          selectedColor:
                              AppTheme.primaryColor.withOpacity(0.2),
                        ))
                    .toList(),
              ),

              SizedBox(height: 8.h),

              // Toggles
              SwitchListTile(
                title: const Text('Enable Captions'),
                value: _captionsEnabled,
                onChanged: (v) {
                  setSheetState(() {});
                  setState(() => _captionsEnabled = v);
                },
                secondary: const Icon(Icons.closed_caption),
              ),
              SwitchListTile(
                title: const Text('Background Music'),
                value: _backgroundMusicEnabled,
                onChanged: (v) {
                  setSheetState(() {});
                  setState(() => _backgroundMusicEnabled = v);
                },
                secondary: const Icon(Icons.music_note),
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
    );
  }
}
