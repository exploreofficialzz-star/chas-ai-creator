import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_text_field.dart';

class CreateVideoScreen extends StatefulWidget {
  const CreateVideoScreen({super.key});

  @override
  State<CreateVideoScreen> createState() => _CreateVideoScreenState();
}

class _CreateVideoScreenState extends State<CreateVideoScreen> {
  final ApiService _apiService = ApiService();
  
  // Form controllers
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _instructionsController = TextEditingController();
  
  // Selected values
  String _selectedNiche = 'general';
  String _selectedVideoType = 'silent';
  String _selectedAspectRatio = '9:16';
  String _selectedStyle = 'cinematic';
  String _selectedCaptionStyle = 'modern';
  String _selectedMusicStyle = 'upbeat';
  
  double _duration = 30;
  bool _captionsEnabled = true;
  bool _backgroundMusicEnabled = true;
  bool _characterConsistencyEnabled = false;
  
  List<dynamic> _niches = [];
  List<dynamic> _styles = [];
  bool _isLoading = false;
  bool _isGenerating = false;
  
  Map<String, dynamic>? _previewScript;

  @override
  void initState() {
    super.initState();
    _loadOptions();
  }

  Future<void> _loadOptions() async {
    setState(() => _isLoading = true);
    
    try {
      final niches = await _apiService.getNiches();
      final styles = await _apiService.getStyles();
      
      setState(() {
        _niches = niches['niches'] ?? [];
        _styles = styles['styles'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _generatePreview() async {
    setState(() => _isGenerating = true);
    
    try {
      final preview = await _apiService.previewVideo(
        niche: _selectedNiche,
        videoType: _selectedVideoType,
        duration: _duration.toInt(),
        style: _selectedStyle,
        userInstructions: _instructionsController.text.isNotEmpty
            ? _instructionsController.text
            : null,
      );
      
      setState(() {
        _previewScript = preview;
        _isGenerating = false;
      });
      
      _showPreviewDialog();
    } catch (e) {
      setState(() => _isGenerating = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to generate preview: $e')),
      );
    }
  }

  Future<void> _createVideo() async {
    setState(() => _isGenerating = true);
    
    try {
      await _apiService.createVideo(
        niche: _selectedNiche,
        title: _titleController.text.isNotEmpty ? _titleController.text : null,
        description: _descriptionController.text.isNotEmpty
            ? _descriptionController.text
            : null,
        videoType: _selectedVideoType,
        duration: _duration.toInt(),
        aspectRatio: _selectedAspectRatio,
        style: _selectedStyle,
        characterConsistencyEnabled: _characterConsistencyEnabled,
        captionsEnabled: _captionsEnabled,
        captionStyle: _selectedCaptionStyle,
        backgroundMusicEnabled: _backgroundMusicEnabled,
        backgroundMusicStyle: _selectedMusicStyle,
        userInstructions: _instructionsController.text.isNotEmpty
            ? _instructionsController.text
            : null,
      );
      
      setState(() => _isGenerating = false);
      
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Video generation started!')),
      );
      
      // Reset form
      _resetForm();
    } catch (e) {
      setState(() => _isGenerating = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to create video: $e')),
      );
    }
  }

  void _resetForm() {
    _titleController.clear();
    _descriptionController.clear();
    _instructionsController.clear();
    setState(() {
      _previewScript = null;
    });
  }

  void _showPreviewDialog() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.9,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        builder: (context, scrollController) {
          return Container(
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              borderRadius: BorderRadius.vertical(top: Radius.circular(20.r)),
            ),
            child: Column(
              children: [
                // Handle
                Container(
                  margin: EdgeInsets.symmetric(vertical: 12.h),
                  width: 40.w,
                  height: 4.h,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(2.r),
                  ),
                ),
                
                // Title
                Padding(
                  padding: EdgeInsets.symmetric(horizontal: 20.w),
                  child: Text(
                    'Preview',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
                
                SizedBox(height: 16.h),
                
                // Content
                Expanded(
                  child: ListView(
                    controller: scrollController,
                    padding: EdgeInsets.symmetric(horizontal: 20.w),
                    children: [
                      if (_previewScript != null) ...[
                        Text(
                          _previewScript!['script']['title'] ?? 'Untitled',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        SizedBox(height: 8.h),
                        Text(
                          _previewScript!['script']['description'] ?? '',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                        SizedBox(height: 24.h),
                        
                        // Scenes
                        Text(
                          'Scenes',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        SizedBox(height: 12.h),
                        ...(_previewScript!['script']['scenes'] as List)
                            .map((scene) => _buildSceneCard(scene)),
                        
                        SizedBox(height: 24.h),
                        
                        // Sample Images
                        if (_previewScript!['sample_images'] != null) ...[
                          Text(
                            'Sample Images',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          SizedBox(height: 12.h),
                          SizedBox(
                            height: 200.h,
                            child: ListView.builder(
                              scrollDirection: Axis.horizontal,
                              itemCount: _previewScript!['sample_images'].length,
                              itemBuilder: (context, index) {
                                final image = _previewScript!['sample_images'][index];
                                return Container(
                                  width: 150.w,
                                  margin: EdgeInsets.only(right: 12.w),
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(12.r),
                                    image: DecorationImage(
                                      image: NetworkImage(image['image_url']),
                                      fit: BoxFit.cover,
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ],
                      ],
                    ],
                  ),
                ),
                
                // Actions
                Padding(
                  padding: EdgeInsets.all(20.w),
                  child: Row(
                    children: [
                      Expanded(
                        child: CustomButton(
                          text: 'Edit',
                          onPressed: () => Navigator.pop(context),
                          isOutlined: true,
                        ),
                      ),
                      SizedBox(width: 12.w),
                      Expanded(
                        child: CustomButton(
                          text: 'Generate Video',
                          onPressed: () {
                            Navigator.pop(context);
                            _createVideo();
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSceneCard(dynamic scene) {
    return Container(
      margin: EdgeInsets.only(bottom: 12.h),
      padding: EdgeInsets.all(16.w),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(12.r),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Scene ${scene['scene_number']}',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              color: AppTheme.primaryColor,
            ),
          ),
          SizedBox(height: 8.h),
          Text(
            scene['description'] ?? '',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          if (scene['caption'] != null && scene['caption'].isNotEmpty) ...[
            SizedBox(height: 8.h),
            Container(
              padding: EdgeInsets.all(12.w),
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8.r),
              ),
              child: Text(
                scene['caption'],
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Video'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: EdgeInsets.all(16.w),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Niche Selection
                  _buildSectionTitle('Content Niche'),
                  SizedBox(height: 12.h),
                  Wrap(
                    spacing: 8.w,
                    runSpacing: 8.h,
                    children: _niches.map((niche) {
                      final isSelected = _selectedNiche == niche['id'];
                      return ChoiceChip(
                        label: Text('${niche['icon']} ${niche['name']}'),
                        selected: isSelected,
                        onSelected: (selected) {
                          if (selected) {
                            setState(() => _selectedNiche = niche['id']);
                          }
                        },
                        selectedColor: AppTheme.primaryColor.withOpacity(0.2),
                        labelStyle: TextStyle(
                          color: isSelected ? AppTheme.primaryColor : null,
                          fontWeight: isSelected ? FontWeight.w600 : null,
                        ),
                      );
                    }).toList(),
                  ),
                  
                  SizedBox(height: 24.h),
                  
                  // Video Type
                  _buildSectionTitle('Video Type'),
                  SizedBox(height: 12.h),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                        value: 'silent',
                        label: Text('Silent'),
                        icon: Icon(Icons.volume_off),
                      ),
                      ButtonSegment(
                        value: 'narration',
                        label: Text('Narration'),
                        icon: Icon(Icons.record_voice_over),
                      ),
                    ],
                    selected: {_selectedVideoType},
                    onSelectionChanged: (value) {
                      setState(() => _selectedVideoType = value.first);
                    },
                  ),
                  
                  SizedBox(height: 24.h),
                  
                  // Duration
                  _buildSectionTitle('Duration'),
                  SizedBox(height: 12.h),
                  Slider(
                    value: _duration,
                    min: 10,
                    max: 120,
                    divisions: 11,
                    label: '${_duration.toInt()}s',
                    onChanged: (value) {
                      setState(() => _duration = value);
                    },
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('10s', style: Theme.of(context).textTheme.bodySmall),
                      Text(
                        '${_duration.toInt()} seconds',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text('120s', style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                  
                  SizedBox(height: 24.h),
                  
                  // Aspect Ratio
                  _buildSectionTitle('Aspect Ratio'),
                  SizedBox(height: 12.h),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                        value: '16:9',
                        label: Text('16:9'),
                      ),
                      ButtonSegment(
                        value: '9:16',
                        label: Text('9:16'),
                      ),
                      ButtonSegment(
                        value: '1:1',
                        label: Text('1:1'),
                      ),
                    ],
                    selected: {_selectedAspectRatio},
                    onSelectionChanged: (value) {
                      setState(() => _selectedAspectRatio = value.first);
                    },
                  ),
                  
                  SizedBox(height: 24.h),
                  
                  // Style
                  _buildSectionTitle('Visual Style'),
                  SizedBox(height: 12.h),
                  Wrap(
                    spacing: 8.w,
                    runSpacing: 8.h,
                    children: _styles.map((style) {
                      final isSelected = _selectedStyle == style['id'];
                      return ChoiceChip(
                        label: Text(style['name']),
                        selected: isSelected,
                        onSelected: (selected) {
                          if (selected) {
                            setState(() => _selectedStyle = style['id']);
                          }
                        },
                        selectedColor: AppTheme.primaryColor.withOpacity(0.2),
                        labelStyle: TextStyle(
                          color: isSelected ? AppTheme.primaryColor : null,
                          fontWeight: isSelected ? FontWeight.w600 : null,
                        ),
                      );
                    }).toList(),
                  ),
                  
                  SizedBox(height: 24.h),
                  
                  // Options
                  _buildSectionTitle('Options'),
                  SizedBox(height: 12.h),
                  
                  // Captions
                  SwitchListTile(
                    title: const Text('Enable Captions'),
                    subtitle: const Text('Add text overlays to your video'),
                    value: _captionsEnabled,
                    onChanged: (value) {
                      setState(() => _captionsEnabled = value);
                    },
                  ),
                  
                  // Background Music
                  SwitchListTile(
                    title: const Text('Background Music'),
                    subtitle: const Text('Add AI-selected background music'),
                    value: _backgroundMusicEnabled,
                    onChanged: (value) {
                      setState(() => _backgroundMusicEnabled = value);
                    },
                  ),
                  
                  // Character Consistency
                  SwitchListTile(
                    title: const Text('Character Consistency'),
                    subtitle: const Text('Maintain consistent characters across scenes'),
                    value: _characterConsistencyEnabled,
                    onChanged: (value) {
                      setState(() => _characterConsistencyEnabled = value);
                    },
                  ),
                  
                  SizedBox(height: 24.h),
                  
                  // Instructions
                  CustomTextField(
                    controller: _instructionsController,
                    label: 'Additional Instructions (Optional)',
                    hint: 'Describe any specific scenes, elements, or style you want...',
                    maxLines: 4,
                  ),
                  
                  SizedBox(height: 32.h),
                  
                  // Actions - FIXED: Wrapped in lambda functions
                  Row(
                    children: [
                      Expanded(
                        child: CustomButton(
                          text: 'Preview',
                          onPressed: _isGenerating ? null : () => _generatePreview(),
                          isLoading: _isGenerating,
                          isOutlined: true,
                        ),
                      ),
                      SizedBox(width: 12.w),
                      Expanded(
                        child: CustomButton(
                          text: 'Create Video',
                          onPressed: _isGenerating ? null : () => _createVideo(),
                          isLoading: _isGenerating,
                        ),
                      ),
                    ],
                  ),
                  
                  SizedBox(height: 32.h),
                ],
              ),
            ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: Theme.of(context).textTheme.titleMedium?.copyWith(
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

