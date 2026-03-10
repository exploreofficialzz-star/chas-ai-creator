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
  String? _selectedStatus;
  String _sortBy = 'newest';

  int _totalVideos = 0;
  int _completedCount = 0;
  int _processingCount = 0;

  late TabController _tabController;

  final List<_StatusTab> _tabs = const [
    _StatusTab(null,         '⭐ All'),
    _StatusTab('processing', '⏳ Processing'),
    _StatusTab('completed',  '✅ Done'),
    _StatusTab('failed',     '❌ Failed'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController =
        TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(
            () => _selectedStatus = _tabs[_tabController.index].status);
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

      final newVideos = (response['videos'] ??
              response['data'] ??
              response['items'] ??
              []) as List;
      final total =
          (response['total'] ?? response['count'] ?? 0) as int;

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
          _completedCount = _videos
              .where((v) => v['status'] == 'completed')
              .length;
          _processingCount = _videos
              .where((v) =>
                  v['status'] == 'processing' ||
                  v['status'] == 'pending' ||
                  (v['status'] as String? ?? '')
                      .contains('generating'))
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

      // FIX 1 — plain AppBar + separate tab bar underneath the stats
      // Removed NestedScrollView + SliverAppBar which was cutting off stats
      appBar: _buildAppBar(),

      body: Column(
        children: [
          // FIX 2 — stats row sits outside scroll, never gets clipped
          _buildStatsRow(),

          // FIX 3 — tab bar sits below stats with proper breathing room
          _buildTabBar(),

          // scrollable content
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // APP BAR
  // ─────────────────────────────────────────────────────────────────────────

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      title: const Text('My Videos'),
      centerTitle: true,
      actions: [
        IconButton(
          icon: const Icon(Icons.sort_rounded),
          tooltip: 'Sort',
          onPressed: _showSortSheet,
        ),
        IconButton(
          icon: _isRefreshing
              ? SizedBox(
                  width: 18.w,
                  height: 18.w,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppTheme.primaryColor,
                  ),
                )
              : const Icon(Icons.refresh_rounded),
          onPressed: _isRefreshing ? null : _refresh,
        ),
        SizedBox(width: 4.w),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // STATS ROW — FIX 2: proper padding, never clipped
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStatsRow() {
    return Container(
      // FIX 4 — gradient background for visual polish
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppTheme.primaryColor.withOpacity(0.08),
            Colors.transparent,
          ],
        ),
      ),
      padding: EdgeInsets.fromLTRB(16.w, 14.h, 16.w, 14.h),
      child: Row(
        children: [
          _buildStatChip('📹', '$_totalVideos', 'Total'),
          SizedBox(width: 10.w),
          _buildStatChip('✅', '$_completedCount', 'Done'),
          SizedBox(width: 10.w),
          _buildStatChip('⏳', '$_processingCount', 'Processing'),
        ],
      ),
    );
  }

  Widget _buildStatChip(
      String emoji, String count, String label) {
    return Expanded(
      child: Container(
        // FIX 5 — consistent fixed height, never squeezed
        padding:
            EdgeInsets.symmetric(vertical: 10.h, horizontal: 8.w),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(14.r),
          border: Border.all(
              color: AppTheme.primaryColor.withOpacity(0.12)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(emoji, style: TextStyle(fontSize: 18.sp)),
            SizedBox(height: 4.h),
            Text(
              count,
              style: TextStyle(
                fontSize: 20.sp,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryColor,
              ),
            ),
            SizedBox(height: 2.h),
            Text(
              label,
              style:
                  TextStyle(fontSize: 10.sp, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TAB BAR — FIX 3: tabs no longer squished, all 4 visible
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildTabBar() {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: Border(
          bottom: BorderSide(
            color: Colors.grey.withOpacity(0.12),
            width: 1,
          ),
        ),
      ),
      // FIX 6 — consistent height for the tab bar container
      height: 52.h,
      child: TabBar(
        controller: _tabController,
        isScrollable: true,
        // FIX 7 — tabAlignment ensures tabs start from left
        tabAlignment: TabAlignment.start,
        indicatorSize: TabBarIndicatorSize.label,
        dividerColor: Colors.transparent,
        indicator: BoxDecoration(
          color: AppTheme.primaryColor,
          borderRadius: BorderRadius.circular(20.r),
        ),
        labelColor: Colors.white,
        unselectedLabelColor: Colors.grey,
        labelStyle: TextStyle(
            fontSize: 12.sp, fontWeight: FontWeight.w600),
        unselectedLabelStyle: TextStyle(fontSize: 12.sp),
        // FIX 8 — reduced horizontal padding so all 4 tabs fit
        padding:
            EdgeInsets.symmetric(horizontal: 12.w, vertical: 6.h),
        tabs: _tabs
            .map(
              (t) => Tab(
                child: Container(
                  // FIX 9 — consistent tab chip padding
                  padding: EdgeInsets.symmetric(
                      horizontal: 14.w, vertical: 4.h),
                  child: Text(t.label),
                ),
              ),
            )
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
              // FIX 10 — comfortable list padding
              padding: EdgeInsets.fromLTRB(
                  14.w, 14.h, 14.w, 100.h),
              itemCount: _videos.length + (_hasMore ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _videos.length) {
                  return Padding(
                    padding: EdgeInsets.all(20.w),
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
  // VIDEO CARD — FIX 11: better internal spacing throughout
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildVideoCard(dynamic video, int index) {
    final status = video['status'] as String? ?? 'pending';
    final title = video['title'] as String? ?? 'Untitled Video';
    final thumbnail = video['thumbnail_url'] as String?;
    final duration = video['duration'] as int? ?? 0;
    final createdAt = video['created_at'] as String?;
    final niche = video['niche'] as String? ?? '';
    final style = video['style'] as String? ?? '';
    final progress =
        (video['progress'] as num?)?.toDouble() ?? 0.0;

    return Container(
      // FIX 12 — more breathing room between cards
      margin: EdgeInsets.only(bottom: 16.h),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(20.r),
        border: Border.all(
          color: _statusColor(status).withOpacity(0.18),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.07),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(20.r),
        onTap: () => _openVideo(video),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Thumbnail ─────────────────────────────────────
            ClipRRect(
              borderRadius: BorderRadius.vertical(
                  top: Radius.circular(20.r)),
              child: SizedBox(
                // FIX 13 — slightly shorter thumbnail, more space for info
                height: 155.h,
                width: double.infinity,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    // Thumbnail image
                    thumbnail != null && thumbnail.isNotEmpty
                        ? Image.network(
                            thumbnail,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) =>
                                _buildThumbnailPlaceholder(niche),
                          )
                        : _buildThumbnailPlaceholder(niche),

                    // Dark gradient overlay
                    Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            Colors.transparent,
                            Colors.black.withOpacity(0.55),
                          ],
                        ),
                      ),
                    ),

                    // Status badge — top left
                    Positioned(
                      top: 10,
                      left: 10,
                      child: _buildStatusBadge(status),
                    ),

                    // Duration — top right
                    if (duration > 0)
                      Positioned(
                        top: 10,
                        right: 10,
                        child: Container(
                          padding: EdgeInsets.symmetric(
                              horizontal: 8.w, vertical: 4.h),
                          decoration: BoxDecoration(
                            color: Colors.black54,
                            borderRadius:
                                BorderRadius.circular(8.r),
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

                    // Play button — completed
                    if (status == 'completed')
                      Center(
                        child: Container(
                          width: 50.w,
                          height: 50.w,
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            shape: BoxShape.circle,
                            border: Border.all(
                                color: Colors.white54, width: 2),
                          ),
                          child: Icon(Icons.play_arrow_rounded,
                              color: Colors.white, size: 30.w),
                        ),
                      ),

                    // Progress bar — processing / pending
                    if (status == 'processing' ||
                        status == 'pending' ||
                        status.contains('generating'))
                      Positioned(
                        bottom: 0,
                        left: 0,
                        right: 0,
                        child: Column(
                          children: [
                            Padding(
                              padding: EdgeInsets.symmetric(
                                  horizontal: 14.w, vertical: 6.h),
                              child: Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    _progressLabel(status),
                                    style: TextStyle(
                                        color: Colors.white,
                                        fontSize: 11.sp),
                                  ),
                                  if (progress > 0)
                                    Text(
                                      '${(progress * 100).toInt()}%',
                                      style: TextStyle(
                                        color: Colors.white,
                                        fontSize: 11.sp,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                ],
                              ),
                            ),
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
                          mainAxisAlignment:
                              MainAxisAlignment.center,
                          children: [
                            Icon(Icons.error_outline_rounded,
                                color: Colors.red.shade300,
                                size: 36.w),
                            SizedBox(height: 6.h),
                            Text(
                              'Generation failed',
                              style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 12.sp),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),

            // ── Info area ─────────────────────────────────────
            Padding(
              // FIX 14 — more generous info area padding
              padding: EdgeInsets.fromLTRB(
                  14.w, 12.h, 14.w, 14.h),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Title row
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: TextStyle(
                            fontSize: 14.sp,
                            fontWeight: FontWeight.w600,
                            height: 1.3,
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
                          child: Icon(Icons.more_vert_rounded,
                              size: 18.w, color: Colors.grey),
                        ),
                      ),
                    ],
                  ),

                  // FIX 15 — more space before chips
                  SizedBox(height: 10.h),

                  // Meta chips
                  Wrap(
                    // FIX 16 — better chip spacing
                    spacing: 8.w,
                    runSpacing: 6.h,
                    children: [
                      if (niche.isNotEmpty)
                        _buildMetaChip(
                            _nicheEmoji(niche), _capitalize(niche)),
                      if (style.isNotEmpty)
                        _buildMetaChip('🎨', _capitalize(style)),
                      if (createdAt != null)
                        _buildMetaChip('🕒', _formatDate(createdAt)),
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

  // FIX 17 — map raw backend status strings to friendly labels
  String _progressLabel(String status) {
    return switch (status) {
      'pending'            => '⏳ Queued...',
      'processing'         => '⚙️ Processing...',
      'script_generating'  => '✍️ Writing script...',
      'images_generating'  => '🎨 Generating images...',
      'voice_generating'   => '🎙️ Generating voice...',
      'video_composing'    => '🎬 Composing video...',
      'uploading'          => '☁️ Uploading...',
      _                    => '⏳ Generating...',
    };
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
            AppTheme.primaryColor.withOpacity(0.25),
            AppTheme.accentColor.withOpacity(0.15),
          ],
        ),
      ),
      child: Center(
        child: Text(
          _nicheEmoji(niche),
          style: TextStyle(fontSize: 52.sp),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // STATUS BADGE — FIX 18: maps raw backend statuses nicely
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStatusBadge(String status) {
    final color = _statusColor(status);
    // FIX 18 — convert raw backend status like 'images_generating'
    // to a clean readable label
    final label = _statusBadgeLabel(status);
    return Container(
      padding: EdgeInsets.symmetric(
          horizontal: 9.w, vertical: 5.h),
      decoration: BoxDecoration(
        color: color.withOpacity(0.88),
        borderRadius: BorderRadius.circular(8.r),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: Colors.white,
          fontSize: 10.sp,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // META CHIP — FIX 19: bigger touch target + better spacing
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildMetaChip(String emoji, String label) {
    return Container(
      padding:
          EdgeInsets.symmetric(horizontal: 10.w, vertical: 5.h),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(20.r),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: TextStyle(fontSize: 11.sp)),
          SizedBox(width: 5.w),
          Text(
            label,
            style: TextStyle(
              fontSize: 11.sp,
              color: AppTheme.primaryColor,
              fontWeight: FontWeight.w500,
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
                    ? 'No ${_statusBadgeLabel(_selectedStatus!)} videos'
                    : 'No videos yet',
                style:
                    Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
              ),
              SizedBox(height: 8.h),
              Text(
                isFiltered
                    ? 'Try selecting a different filter'
                    : 'Tap Create to generate your first video!',
                style:
                    Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.grey,
                        ),
                textAlign: TextAlign.center,
              ),
              if (isFiltered) ...[
                SizedBox(height: 20.h),
                TextButton.icon(
                  onPressed: () => _tabController.animateTo(0),
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
      padding: EdgeInsets.all(14.w),
      itemCount: 3,
      itemBuilder: (_, __) => Container(
        margin: EdgeInsets.only(bottom: 16.h),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(20.r),
        ),
        child: Column(
          children: [
            _shimmer(double.infinity, 155.h,
                topLeft: 20.r, topRight: 20.r),
            Padding(
              padding: EdgeInsets.all(14.w),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _shimmer(double.infinity, 16.h),
                  SizedBox(height: 8.h),
                  _shimmer(180.w, 12.h),
                  SizedBox(height: 10.h),
                  Row(
                    children: [
                      _shimmer(70.w, 24.h),
                      SizedBox(width: 8.w),
                      _shimmer(70.w, 24.h),
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

  Widget _shimmer(double width, double height,
      {double topLeft = 8,
      double topRight = 8,
      double bottomLeft = 8,
      double bottomRight = 8}) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Colors.grey.withOpacity(0.13),
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
        padding: EdgeInsets.symmetric(vertical: 16.h),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(24.r)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 36.w,
              height: 4.h,
              margin: EdgeInsets.only(bottom: 16.h),
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2.r),
              ),
            ),
            Padding(
              padding: EdgeInsets.symmetric(
                  horizontal: 20.w, vertical: 4.h),
              child: Text(
                title,
                style: TextStyle(
                    fontSize: 15.sp, fontWeight: FontWeight.bold),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            SizedBox(height: 8.h),
            if (status == 'completed') ...[
              _optionTile(Icons.play_circle_outline_rounded,
                  'Play Video', Colors.green, () => _openVideo(video)),
              _optionTile(Icons.download_outlined, 'Download',
                  AppTheme.primaryColor, () => _downloadVideo(video)),
              _optionTile(Icons.share_outlined, 'Share',
                  Colors.blue, () => _shareVideo(video)),
              _optionTile(Icons.copy_outlined, 'Copy Link',
                  Colors.orange, () => _copyVideoLink(video)),
            ],
            if (status == 'failed')
              _optionTile(Icons.refresh_rounded, 'Regenerate',
                  Colors.orange, () => _regenerateVideo(video)),
            if (status == 'processing' ||
                status == 'pending' ||
                status.contains('generating'))
              _optionTile(Icons.info_outline_rounded,
                  'View Progress', AppTheme.primaryColor,
                  () => _showProgress(video)),
            Divider(
                height: 8, color: Colors.grey.withOpacity(0.1)),
            _optionTile(Icons.delete_outline_rounded,
                'Delete Video', Colors.red,
                () => _showDeleteDialog(video)),
            SizedBox(height: 8.h),
          ],
        ),
      ),
    );
  }

  Widget _optionTile(
      IconData icon, String label, Color color, VoidCallback onTap) {
    return ListTile(
      contentPadding:
          EdgeInsets.symmetric(horizontal: 20.w, vertical: 2.h),
      leading: Container(
        width: 38.w,
        height: 38.w,
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(10.r),
        ),
        child: Icon(icon, size: 19.w, color: color),
      ),
      title: Text(label,
          style: TextStyle(
              fontSize: 14.sp,
              color: color,
              fontWeight: FontWeight.w500)),
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
        padding: EdgeInsets.all(24.w),
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
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 12.h),
            ...[
              ('newest',  '🆕 Newest First'),
              ('oldest',  '📅 Oldest First'),
              ('longest', '⏱️ Longest Duration'),
            ].map(
              (s) => ListTile(
                contentPadding: EdgeInsets.zero,
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
              ),
            ),
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
          _videos.sort((a, b) => (a['created_at'] ?? '')
              .compareTo(b['created_at'] ?? ''));
        case 'longest':
          _videos.sort((a, b) =>
              (b['duration'] ?? 0).compareTo(a['duration'] ?? 0));
        default:
          _videos.sort((a, b) => (b['created_at'] ?? '')
              .compareTo(a['created_at'] ?? ''));
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
    final status = video['status'] as String? ?? '';
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
            Text(
              _progressLabel(status),
              style: TextStyle(
                  fontSize: 13.sp,
                  fontWeight: FontWeight.w600),
            ),
            SizedBox(height: 6.h),
            Text(
              '${progress.toInt()}% complete',
              style: TextStyle(fontSize: 13.sp),
            ),
            SizedBox(height: 8.h),
            Text(
              'This may take a few minutes',
              style: TextStyle(
                  color: Colors.grey, fontSize: 12.sp),
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
                await _apiService
                    .deleteVideo(video['id'].toString());
                _showToast('🗑️ Video deleted');
                await _loadVideos(refresh: true);
              } catch (e) {
                _showToast(_apiService.handleError(e),
                    error: true);
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

  Color _statusColor(String status) {
    if (status == 'completed') return Colors.green;
    if (status == 'failed') return Colors.red;
    if (status == 'processing' ||
        status == 'pending' ||
        status.contains('generating') ||
        status.contains('composing') ||
        status.contains('uploading')) return Colors.orange;
    return Colors.grey;
  }

  // FIX 18 — clean labels for ALL raw backend status strings
  String _statusBadgeLabel(String status) => switch (status) {
        'completed'         => '✅ Done',
        'failed'            => '❌ Failed',
        'processing'        => '⏳ Processing',
        'pending'           => '🔵 Pending',
        'script_generating' => '✍️ Script',
        'images_generating' => '🎨 Images',
        'voice_generating'  => '🎙️ Voice',
        'video_composing'   => '🎬 Composing',
        'uploading'         => '☁️ Uploading',
        _                   => '⏳ Processing',
      };

  String _statusLabel(String status) => switch (status) {
        'completed'  => '✅ Done',
        'processing' => '⏳ Processing',
        'pending'    => '🔵 Pending',
        'failed'     => '❌ Failed',
        _            => _statusBadgeLabel(status),
      };

  String _nicheEmoji(String niche) =>
      switch (niche.toLowerCase()) {
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
    return m > 0 ? '$m:${s.toString().padLeft(2, '0')}' : '${s}s';
  }

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final diff = DateTime.now().difference(dt);
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

class _StatusTab {
  final String? status;
  final String label;
  const _StatusTab(this.status, this.label);
}
