import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../services/api_service.dart';

class VideosScreen extends StatefulWidget {
  const VideosScreen({super.key});

  @override
  State<VideosScreen> createState() => _VideosScreenState();
}

class _VideosScreenState extends State<VideosScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  final ScrollController _scrollController = ScrollController();

  List<dynamic> _videos = [];
  bool _isLoading = true;
  bool _isLoadingMore = false;
  bool _isRefreshing = false;
  int _page = 1;
  bool _hasMore = true;
  String? _selectedStatus; // null = All
  String _sortBy = 'newest'; // newest | oldest | longest

  // Stats
  int _totalVideos = 0;
  int _completedCount = 0;
  int _processingCount = 0;

  late TabController _tabController;

  final List<_StatusTab> _tabs = const [
    _StatusTab(null,        '⭐ All'),
    _StatusTab('processing','⏳ Processing'),
    _StatusTab('completed', '✅ Done'),
    _StatusTab('failed',    '❌ Failed'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() => _selectedStatus = _tabs[_tabController.index].status);
        _loadVideos(refresh: true);
      }
    });
    _scrollController.addListener(_onScroll);
    _loadVideos();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      _loadMore();
    }
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

      // FIX 1 - handle both 'videos' and 'data' response keys
      final newVideos = (response['videos'] ??
              response['data'] ??
              response['items'] ??
              []) as List;
      final total = (response['total'] ?? response['count'] ?? 0) as int;

      if (mounted) {
        setState(() {
          if (refresh || _page == 1) {
            _videos = newVideos;
          } else {
            _videos.addAll(newVideos);
          }
          _totalVideos = total;
          _hasMore = _videos.length < total;
          _isLoading = false;
          _isLoadingMore = false;
          _isRefreshing = false;

          // Compute stat counts from loaded videos
          _completedCount =
              _videos.where((v) => v['status'] == 'completed').length;
          _processingCount = _videos
              .where((v) =>
                  v['status'] == 'processing' || v['status'] == 'pending')
              .length;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _isLoadingMore = false;
          _isRefreshing = false;
        });
        _showToast('❌ ${_apiService.handleError(e)}', error: true);
      }
    }
  }

  Future<void> _refresh() async {
    setState(() => _isRefreshing = true);
    await _loadVideos(refresh: true);
  }

  void _loadMore() {
    if (_hasMore && !_isLoading && !_isLoadingMore) {
      setState(() {
        _page++;
        _isLoadingMore = true;
      });
      _loadVideos();
    }
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
        duration: const Duration(seconds: 3),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD
  // ─────────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      body: NestedScrollView(
        controller: _scrollController,
        headerSliverBuilder: (context, innerBoxIsScrolled) => [
          // ── Sliver app bar ───────────────────────────────────────────
          SliverAppBar(
            expandedHeight: 160.h,
            floating: true,
            pinned: true,
            snap: false,
            title: const Text('My Videos'),
            actions: [
              IconButton(
                icon: const Icon(Icons.sort),
                tooltip: 'Sort',
                onPressed: _showSortSheet,
              ),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: _isRefreshing ? null : _refresh,
              ),
            ],
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      AppTheme.primaryColor.withOpacity(0.15),
                      Colors.transparent,
                    ],
                  ),
                ),
                child: SafeArea(
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(
                        16.w, 56.h, 16.w, 0),
                    child: _buildStatsRow(),
                  ),
                ),
              ),
            ),
            bottom: PreferredSize(
              preferredSize: Size.fromHeight(44.h),
              child: _buildTabBar(),
            ),
          ),
        ],
        body: _buildBody(),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // STATS ROW
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStatsRow() {
    return Row(
      children: [
        _buildStatChip('📹', '$_totalVideos', 'Total'),
        SizedBox(width: 10.w),
        _buildStatChip('✅', '$_completedCount', 'Done'),
        SizedBox(width: 10.w),
        _buildStatChip('⏳', '$_processingCount', 'Processing'),
      ],
    );
  }

  Widget _buildStatChip(String emoji, String count, String label) {
    return Expanded(
      child: Container(
        padding: EdgeInsets.symmetric(vertical: 10.h, horizontal: 10.w),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(12.r),
          border: Border.all(
              color: AppTheme.primaryColor.withOpacity(0.1)),
        ),
        child: Column(
          children: [
            Text(emoji, style: TextStyle(fontSize: 16.sp)),
            SizedBox(height: 2.h),
            Text(
              count,
              style: TextStyle(
                fontSize: 18.sp,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryColor,
              ),
            ),
            Text(
              label,
              style: TextStyle(fontSize: 10.sp, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TAB BAR
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildTabBar() {
    return Container(
      color: Theme.of(context).scaffoldBackgroundColor,
      child: TabBar(
        controller: _tabController,
        isScrollable: true,
        indicatorSize: TabBarIndicatorSize.label,
        indicator: BoxDecoration(
          color: AppTheme.primaryColor,
          borderRadius: BorderRadius.circular(20.r),
        ),
        labelColor: Colors.white,
        unselectedLabelColor: Colors.grey,
        labelStyle:
            TextStyle(fontSize: 12.sp, fontWeight: FontWeight.w600),
        padding: EdgeInsets.symmetric(horizontal: 12.w, vertical: 6.h),
        tabs: _tabs
            .map((t) => Tab(
                  child: Container(
                    padding: EdgeInsets.symmetric(
                        horizontal: 12.w, vertical: 4.h),
                    child: Text(t.label),
                  ),
                ))
            .toList(),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BODY
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildBody() {
    if (_isLoading && _videos.isEmpty) {
      return _buildSkeletonLoader();
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      color: AppTheme.primaryColor,
      child: _videos.isEmpty
          ? _buildEmptyState()
          : ListView.builder(
              padding: EdgeInsets.fromLTRB(16.w, 12.h, 16.w, 100.h),
              itemCount: _videos.length + (_hasMore ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _videos.length) {
                  return Padding(
                    padding: EdgeInsets.all(16.w),
                    child: const Center(
                        child: CircularProgressIndicator()),
                  );
                }
                return _buildVideoCard(_videos[index], index);
              },
            ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // VIDEO CARD
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildVideoCard(dynamic video, int index) {
    final status = video['status'] as String? ?? 'pending';
    final title = video['title'] as String? ?? 'Untitled Video';
    final thumbnail = video['thumbnail_url'] as String?;
    final duration = video['duration'] as int? ?? 0;
    final createdAt = video['created_at'] as String?;
    final niche = video['niche'] as String? ?? '';
    final style = video['style'] as String? ?? '';
    final progress = (video['progress'] as num?)?.toDouble() ?? 0.0;

    return Container(
      margin: EdgeInsets.only(bottom: 14.h),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(18.r),
        border: Border.all(
          color: _statusColor(status).withOpacity(0.15),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.06),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(18.r),
        onTap: () => _openVideo(video),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Thumbnail / status area ─────────────────────────
            ClipRRect(
              borderRadius:
                  BorderRadius.vertical(top: Radius.circular(18.r)),
              child: SizedBox(
                height: 160.h,
                width: double.infinity,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    // Thumbnail
                    thumbnail != null && thumbnail.isNotEmpty
                        ? Image.network(
                            thumbnail,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) =>
                                _buildThumbnailPlaceholder(niche),
                          )
                        : _buildThumbnailPlaceholder(niche),

                    // Dark overlay
                    Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            Colors.transparent,
                            Colors.black.withOpacity(0.6),
                          ],
                        ),
                      ),
                    ),

                    // Status badge top-left
                    Positioned(
                      top: 10,
                      left: 10,
                      child: _buildStatusBadge(status),
                    ),

                    // Duration badge top-right
                    if (duration > 0)
                      Positioned(
                        top: 10,
                        right: 10,
                        child: Container(
                          padding: EdgeInsets.symmetric(
                              horizontal: 8.w, vertical: 4.h),
                          decoration: BoxDecoration(
                            color: Colors.black54,
                            borderRadius: BorderRadius.circular(8.r),
                          ),
                          child: Text(
                            _formatDuration(duration),
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 11.sp,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),

                    // Play button center (only for completed)
                    if (status == 'completed')
                      Center(
                        child: Container(
                          width: 48.w,
                          height: 48.w,
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            shape: BoxShape.circle,
                            border: Border.all(
                                color: Colors.white54, width: 2),
                          ),
                          child: Icon(Icons.play_arrow,
                              color: Colors.white, size: 28.w),
                        ),
                      ),

                    // Progress bar for processing
                    if (status == 'processing' || status == 'pending')
                      Positioned(
                        bottom: 0,
                        left: 0,
                        right: 0,
                        child: Column(
                          children: [
                            Padding(
                              padding: EdgeInsets.symmetric(
                                  horizontal: 12.w),
                              child: Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Generating...',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 11.sp,
                                    ),
                                  ),
                                  Text(
                                    '${(progress * 100).toInt()}%',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 11.sp,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            SizedBox(height: 4.h),
                            LinearProgressIndicator(
                              value: progress > 0 ? progress : null,
                              backgroundColor:
                                  Colors.white.withOpacity(0.2),
                              color: AppTheme.primaryColor,
                              minHeight: 4,
                            ),
                          ],
                        ),
                      ),

                    // Failed overlay
                    if (status == 'failed')
                      Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.error_outline,
                                color: Colors.red.shade300,
                                size: 32.w),
                            SizedBox(height: 4.h),
                            Text(
                              'Generation failed',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 12.sp,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),

            // ── Info area ───────────────────────────────────────
            Padding(
              padding: EdgeInsets.all(14.w),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: TextStyle(
                            fontSize: 14.sp,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      SizedBox(width: 8.w),
                      GestureDetector(
                        onTap: () => _showVideoOptions(video),
                        child: Container(
                          padding: EdgeInsets.all(6.w),
                          decoration: BoxDecoration(
                            color: Colors.grey.withOpacity(0.1),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(Icons.more_vert,
                              size: 18.w, color: Colors.grey),
                        ),
                      ),
                    ],
                  ),

                  SizedBox(height: 8.h),

                  // Meta chips
                  Wrap(
                    spacing: 6.w,
                    runSpacing: 4.h,
                    children: [
                      if (niche.isNotEmpty)
                        _buildMetaChip(
                            _nicheEmoji(niche), _capitalize(niche)),
                      if (style.isNotEmpty)
                        _buildMetaChip('🎨', _capitalize(style)),
                      if (createdAt != null)
                        _buildMetaChip(
                            '🕒', _formatDate(createdAt)),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // THUMBNAIL PLACEHOLDER
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildThumbnailPlaceholder(String niche) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppTheme.primaryColor.withOpacity(0.3),
            AppTheme.accentColor.withOpacity(0.2),
          ],
        ),
      ),
      child: Center(
        child: Text(
          _nicheEmoji(niche),
          style: TextStyle(fontSize: 48.sp),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // STATUS BADGE
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStatusBadge(String status) {
    final color = _statusColor(status);
    final label = _statusLabel(status);
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 8.w, vertical: 4.h),
      decoration: BoxDecoration(
        color: color.withOpacity(0.85),
        borderRadius: BorderRadius.circular(8.r),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: Colors.white,
          fontSize: 10.sp,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // META CHIP
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildMetaChip(String emoji, String label) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 8.w, vertical: 3.h),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withOpacity(0.07),
        borderRadius: BorderRadius.circular(20.r),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: TextStyle(fontSize: 11.sp)),
          SizedBox(width: 4.w),
          Text(
            label,
            style: TextStyle(
              fontSize: 11.sp,
              color: AppTheme.primaryColor,
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // EMPTY STATE
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildEmptyState() {
    final isFiltered = _selectedStatus != null;
    return ListView(
      children: [
        SizedBox(height: 80.h),
        Center(
          child: Column(
            children: [
              Container(
                width: 100.w,
                height: 100.w,
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withOpacity(0.08),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isFiltered
                      ? Icons.filter_list
                      : Icons.video_library_outlined,
                  size: 48.w,
                  color: AppTheme.primaryColor.withOpacity(0.5),
                ),
              ),
              SizedBox(height: 20.h),
              Text(
                isFiltered
                    ? 'No ${_statusLabel(_selectedStatus!)} videos'
                    : 'No videos yet',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              SizedBox(height: 8.h),
              Text(
                isFiltered
                    ? 'Try selecting a different filter'
                    : 'Tap Create to generate your first video!',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.grey,
                    ),
                textAlign: TextAlign.center,
              ),
              if (isFiltered) ...[
                SizedBox(height: 20.h),
                TextButton.icon(
                  onPressed: () {
                    _tabController.animateTo(0);
                  },
                  icon: const Icon(Icons.clear),
                  label: const Text('Clear Filter'),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SKELETON LOADER
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildSkeletonLoader() {
    return ListView.builder(
      padding: EdgeInsets.all(16.w),
      itemCount: 4,
      itemBuilder: (_, __) => Container(
        margin: EdgeInsets.only(bottom: 14.h),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(18.r),
        ),
        child: Column(
          children: [
            _shimmer(double.infinity, 160.h,
                topLeft: 18.r, topRight: 18.r),
            Padding(
              padding: EdgeInsets.all(14.w),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _shimmer(200.w, 16.h),
                  SizedBox(height: 8.h),
                  _shimmer(140.w, 12.h),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _shimmer(double width, double height,
      {double topLeft = 8,
      double topRight = 8,
      double bottomLeft = 8,
      double bottomRight = 8}) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Colors.grey.withOpacity(0.15),
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(topLeft),
          topRight: Radius.circular(topRight),
          bottomLeft: Radius.circular(bottomLeft),
          bottomRight: Radius.circular(bottomRight),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // VIDEO OPTIONS SHEET
  // ─────────────────────────────────────────────────────────────────────────

  void _showVideoOptions(dynamic video) {
    final status = video['status'] as String? ?? '';
    final title = video['title'] as String? ?? 'Untitled';

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: EdgeInsets.symmetric(vertical: 12.h),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle
            Container(
              width: 36.w,
              height: 4.h,
              margin: EdgeInsets.only(bottom: 16.h),
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2.r),
              ),
            ),

            // Title
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 20.w),
              child: Text(
                title,
                style: TextStyle(
                  fontSize: 15.sp,
                  fontWeight: FontWeight.bold,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),

            SizedBox(height: 8.h),

            if (status == 'completed') ...[
              _optionTile(Icons.play_circle_outline, 'Play Video',
                  Colors.green, () => _openVideo(video)),
              _optionTile(Icons.download_outlined, 'Download',
                  AppTheme.primaryColor, () => _downloadVideo(video)),
              _optionTile(Icons.share_outlined, 'Share',
                  Colors.blue, () => _shareVideo(video)),
              _optionTile(Icons.copy_outlined, 'Copy Video Link',
                  Colors.orange, () => _copyVideoLink(video)),
            ],
            if (status == 'failed')
              _optionTile(Icons.refresh, 'Regenerate',
                  Colors.orange, () => _regenerateVideo(video)),
            if (status == 'processing' || status == 'pending')
              _optionTile(Icons.info_outline, 'View Progress',
                  AppTheme.primaryColor, () => _showProgress(video)),

            Divider(height: 1, color: Colors.grey.withOpacity(0.1)),

            _optionTile(
              Icons.delete_outline,
              'Delete Video',
              Colors.red,
              () => _showDeleteDialog(video),
            ),

            SizedBox(height: 8.h),
          ],
        ),
      ),
    );
  }

  Widget _optionTile(
      IconData icon, String label, Color color, VoidCallback onTap) {
    return ListTile(
      leading: Container(
        width: 36.w,
        height: 36.w,
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(10.r),
        ),
        child: Icon(icon, size: 18.w, color: color),
      ),
      title: Text(label,
          style: TextStyle(fontSize: 14.sp, color: color)),
      onTap: () {
        Navigator.pop(context);
        onTap();
      },
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SORT SHEET
  // ─────────────────────────────────────────────────────────────────────────

  void _showSortSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: EdgeInsets.all(20.w),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Sort By',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    )),
            SizedBox(height: 12.h),
            ...[
              ('newest', '🆕 Newest First'),
              ('oldest', '📅 Oldest First'),
              ('longest', '⏱️ Longest Duration'),
            ].map((s) => ListTile(
                  title: Text(s.$2),
                  trailing: _sortBy == s.$1
                      ? Icon(Icons.check,
                          color: AppTheme.primaryColor)
                      : null,
                  onTap: () {
                    Navigator.pop(context);
                    setState(() {
                      _sortBy = s.$1;
                      _sortVideos();
                    });
                  },
                )),
            SizedBox(height: 8.h),
          ],
        ),
      ),
    );
  }

  void _sortVideos() {
    setState(() {
      switch (_sortBy) {
        case 'oldest':
          _videos.sort((a, b) =>
              (a['created_at'] ?? '').compareTo(b['created_at'] ?? ''));
        case 'longest':
          _videos.sort((a, b) =>
              (b['duration'] ?? 0).compareTo(a['duration'] ?? 0));
        default:
          _videos.sort((a, b) =>
              (b['created_at'] ?? '').compareTo(a['created_at'] ?? ''));
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ACTIONS
  // ─────────────────────────────────────────────────────────────────────────

  void _openVideo(dynamic video) {
    final url = video['video_url'] as String?;
    if (url == null || url.isEmpty) {
      _showToast('⏳ Video is not ready yet', error: true);
      return;
    }
    // TODO: push to video player screen
    _showToast('▶️ Opening video player...');
  }

  void _downloadVideo(dynamic video) {
    final url = video['video_url'] as String?;
    if (url == null || url.isEmpty) {
      _showToast('❌ Video not available for download', error: true);
      return;
    }
    _showToast('⬇️ Download started!');
  }

  void _shareVideo(dynamic video) {
    final url = video['video_url'] as String?;
    if (url == null || url.isEmpty) {
      _showToast('❌ Video not ready to share', error: true);
      return;
    }
    _showToast('📤 Opening share sheet...');
  }

  void _copyVideoLink(dynamic video) {
    final url = video['video_url'] as String?;
    if (url == null) return;
    Clipboard.setData(ClipboardData(text: url));
    _showToast('✅ Link copied to clipboard!');
  }

  Future<void> _regenerateVideo(dynamic video) async {
    try {
      await _apiService.regenerateVideo(video['id'].toString());
      _showToast('🔄 Regeneration started!');
      await _loadVideos(refresh: true);
    } catch (e) {
      _showToast(_apiService.handleError(e), error: true);
    }
  }

  void _showProgress(dynamic video) {
    final progress =
        ((video['progress'] as num?)?.toDouble() ?? 0.0) * 100;
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Generation Progress'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(
              value: progress > 0 ? progress / 100 : null,
              color: AppTheme.primaryColor,
            ),
            SizedBox(height: 16.h),
            Text('${progress.toInt()}% complete'),
            SizedBox(height: 8.h),
            Text(
              'This may take a few minutes',
              style: TextStyle(color: Colors.grey, fontSize: 12.sp),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showDeleteDialog(dynamic video) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Delete Video'),
        content: const Text(
            'Are you sure? This will permanently delete the video and cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              try {
                await _apiService.deleteVideo(video['id'].toString());
                _showToast('🗑️ Video deleted');
                await _loadVideos(refresh: true);
              } catch (e) {
                _showToast(_apiService.handleError(e), error: true);
              }
            },
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red),
            child: const Text('Delete',
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  Color _statusColor(String status) => switch (status) {
        'completed'  => Colors.green,
        'processing' => Colors.orange,
        'pending'    => Colors.blue,
        'failed'     => Colors.red,
        _            => Colors.grey,
      };

  String _statusLabel(String status) => switch (status) {
        'completed'  => '✅ Done',
        'processing' => '⏳ Processing',
        'pending'    => '🔵 Pending',
        'failed'     => '❌ Failed',
        _            => status,
      };

  String _nicheEmoji(String niche) => switch (niche.toLowerCase()) {
        'fitness'    => '💪',
        'cooking'    => '🍳',
        'tech'       => '💻',
        'travel'     => '✈️',
        'animals'    => '🐾',
        'fashion'    => '👗',
        'finance'    => '💰',
        'education'  => '📚',
        'motivation' => '🚀',
        'gaming'     => '🎮',
        'music'      => '🎵',
        'comedy'     => '😂',
        'nature'     => '🌿',
        'business'   => '💼',
        _            => '🎬',
      };

  String _formatDuration(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return m > 0
        ? '$m:${s.toString().padLeft(2, '0')}'
        : '${s}s';
  }

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final now = DateTime.now();
      final diff = now.difference(dt);
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return '';
    }
  }

  String _capitalize(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
}

// Simple data class for tabs
class _StatusTab {
  final String? status;
  final String label;
  const _StatusTab(this.status, this.label);
}
