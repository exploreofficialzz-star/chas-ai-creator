import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../services/api_service.dart';
import '../../widgets/video_card.dart';

class VideosScreen extends StatefulWidget {
  const VideosScreen({super.key});

  @override
  State<VideosScreen> createState() => _VideosScreenState();
}

class _VideosScreenState extends State<VideosScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> _videos = [];
  bool _isLoading = true;
  // FIX 1 - added _isLoadingMore to prevent multiple simultaneous loads
  bool _isLoadingMore = false;
  int _page = 1;
  bool _hasMore = true;
  String? _selectedStatus;

  @override
  void initState() {
    super.initState();
    _loadVideos();
  }

  Future<void> _loadVideos({bool refresh = false}) async {
    if (refresh) {
      setState(() {
        _page = 1;
        _videos = [];
        _hasMore = true;
        _isLoading = true;
      });
    }

    try {
      final response = await _apiService.getVideos(
        status: _selectedStatus,
        page: _page,
        limit: 20,
      );

      // FIX 2 - null safety on response['videos']
      final newVideos = response['videos'] ?? [];
      final total = response['total'] ?? 0;

      setState(() {
        _videos.addAll(newVideos);
        _hasMore = _videos.length < total;
        _isLoading = false;
        _isLoadingMore = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _isLoadingMore = false;
      });
    }
  }

  Future<void> _refresh() async {
    await _loadVideos(refresh: true);
  }

  void _loadMore() {
    // FIX 3 - check _isLoadingMore to prevent multiple simultaneous calls
    if (_hasMore && !_isLoading && !_isLoadingMore) {
      setState(() {
        _page++;
        _isLoadingMore = true;
      });
      _loadVideos();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Videos'),
        actions: [
          // Filter
          PopupMenuButton<String?>(
            icon: const Icon(Icons.filter_list),
            onSelected: (status) {
              setState(() => _selectedStatus = status);
              _loadVideos(refresh: true);
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: null,
                child: Text('All'),
              ),
              const PopupMenuItem(
                value: 'completed',
                child: Text('Completed'),
              ),
              const PopupMenuItem(
                value: 'pending',
                child: Text('Pending'),
              ),
              const PopupMenuItem(
                value: 'failed',
                child: Text('Failed'),
              ),
            ],
          ),
        ],
      ),
      body: _isLoading && _videos.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              child: _videos.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.video_library_outlined,
                            size: 80.w,
                            color: Colors.grey,
                          ),
                          SizedBox(height: 16.h),
                          Text(
                            'No videos yet',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          SizedBox(height: 8.h),
                          Text(
                            'Create your first video!',
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Colors.grey,
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: EdgeInsets.all(16.w),
                      itemCount: _videos.length + (_hasMore ? 1 : 0),
                      itemBuilder: (context, index) {
                        if (index == _videos.length) {
                          _loadMore();
                          return Center(
                            child: Padding(
                              padding: EdgeInsets.all(16.w),
                              child: const CircularProgressIndicator(),
                            ),
                          );
                        }

                        final video = _videos[index];
                        return VideoCard(
                          title: video['title'] ?? 'Untitled',
                          thumbnailUrl: video['thumbnail_url'],
                          status: video['status'],
                          duration: video['duration'],
                          createdAt: video['created_at'],
                          onTap: () {
                            // Navigate to video details
                          },
                          onMoreTap: () {
                            _showVideoOptions(video);
                          },
                        );
                      },
                    ),
            ),
    );
  }

  void _showVideoOptions(dynamic video) {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.play_arrow),
              title: const Text('Play'),
              onTap: () {
                Navigator.pop(context);
                // Play video
              },
            ),
            ListTile(
              leading: const Icon(Icons.download),
              title: const Text('Download'),
              onTap: () {
                Navigator.pop(context);
                // Download video
              },
            ),
            ListTile(
              leading: const Icon(Icons.share),
              title: const Text('Share'),
              onTap: () {
                Navigator.pop(context);
                // Share video
              },
            ),
            if (video['status'] == 'failed')
              ListTile(
                leading: const Icon(Icons.refresh),
                title: const Text('Regenerate'),
                onTap: () {
                  Navigator.pop(context);
                  _apiService.regenerateVideo(video['id']);
                },
              ),
            ListTile(
              leading: const Icon(Icons.delete, color: Colors.red),
              title: const Text('Delete', style: TextStyle(color: Colors.red)),
              onTap: () {
                Navigator.pop(context);
                _showDeleteConfirmation(video);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showDeleteConfirmation(dynamic video) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Video'),
        content: const Text('Are you sure you want to delete this video?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _apiService.deleteVideo(video['id']);
              _loadVideos(refresh: true);
            },
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
