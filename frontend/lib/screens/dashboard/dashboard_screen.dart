/*
 * chAs AI Creator - Dashboard Screen
 * Enhanced Global Professional Version
 */

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../models/user.dart';
import '../../providers/auth_bloc.dart';
import '../../services/ad_service.dart';
import '../../services/api_service.dart';
import '../../widgets/banner_ad_container.dart';
import '../../widgets/reward_ad_button.dart';

class DashboardScreen extends StatefulWidget {
  final Function(int)? onNavigate;
  const DashboardScreen({super.key, this.onNavigate});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  final AdService _adService = AdService();

  Map<String, dynamic>? _usageStats;
  List<dynamic> _recentVideos = [];
  bool _isLoading = true;
  bool _isRefreshing = false;
  int _credits = 0;
  int _notificationCount = 2; // FIX 1 - demo badge, wire to real notif API later

  late AnimationController _animController;
  late Animation<double> _fadeAnim;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fadeAnim = CurvedAnimation(
        parent: _animController, curve: Curves.easeOut);
    _loadData();
    _adService.showInterstitialAd();
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  Future<void> _loadData({bool silent = false}) async {
    if (!silent) setState(() => _isLoading = _recentVideos.isEmpty);

    try {
      // FIX 2 - load in parallel instead of sequential
      final results = await Future.wait([
        _apiService.getUsageStats(),
        _apiService.getVideos(limit: 5),
      ]);

      final stats = results[0] as Map<String, dynamic>;
      final videosResponse = results[1] as Map<String, dynamic>;

      // FIX 3 - handle multiple possible response keys
      final videos = (videosResponse['videos'] ??
              videosResponse['data'] ??
              videosResponse['items'] ??
              []) as List;

      if (mounted) {
        setState(() {
          _usageStats = stats;
          _recentVideos = videos;
          _credits = (stats['credits'] ?? 0) as int;
          _isLoading = false;
          _isRefreshing = false;
        });
        _animController.forward(from: 0);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _isRefreshing = false;
        });
      }
    }
  }

  Future<void> _refresh() async {
    setState(() => _isRefreshing = true);
    await _loadData(silent: true);
  }

  void _onCreditsEarned() {
    setState(() => _credits += 5);
    _showToast('🎉 You earned 5 credits!');
  }

  void _navigateTo(int index) => widget.onNavigate?.call(index);

  void _showToast(String msg, {bool error = false}) {
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
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {
        User? user;
        if (state is Authenticated) user = state.user;

        return Scaffold(
          body: RefreshIndicator(
            onRefresh: _refresh,
            color: AppTheme.primaryColor,
            child: CustomScrollView(
              slivers: [
                // ── App bar ─────────────────────────────────────────
                _buildSliverAppBar(user),

                // ── Body ────────────────────────────────────────────
                if (_isLoading)
                  const SliverFillRemaining(
                    child: Center(child: CircularProgressIndicator()),
                  )
                else
                  SliverToBoxAdapter(
                    child: FadeTransition(
                      opacity: _fadeAnim,
                      child: Padding(
                        padding: EdgeInsets.symmetric(horizontal: 16.w),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(height: 16.h),

                            // Welcome card
                            _buildWelcomeCard(user),
                            SizedBox(height: 20.h),

                            // Daily usage bar
                            _buildDailyUsageBar(),
                            SizedBox(height: 20.h),

                            // Stats grid
                            _buildSectionTitle('📊 Your Stats'),
                            SizedBox(height: 12.h),
                            _buildStatsGrid(),
                            SizedBox(height: 20.h),

                            // Upgrade banner (free users only)
                            if ((user?.subscriptionTier ?? 'free')
                                    .toLowerCase() ==
                                'free') ...[
                              _buildUpgradeBanner(),
                              SizedBox(height: 20.h),
                            ],

                            // Watch ad reward
                            RewardAdButton(
                                onRewardEarned: _onCreditsEarned),
                            SizedBox(height: 20.h),

                            // Quick actions
                            _buildSectionTitle('⚡ Quick Actions'),
                            SizedBox(height: 12.h),
                            _buildQuickActions(),
                            SizedBox(height: 20.h),

                            // Banner ad
                            const BannerAdContainer(),
                            SizedBox(height: 20.h),

                            // Recent videos
                            _buildRecentVideos(),
                            SizedBox(height: 100.h),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SLIVER APP BAR
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildSliverAppBar(User? user) {
    return SliverAppBar(
      floating: true,
      snap: true,
      title: Row(
        children: [
          Icon(Icons.auto_awesome,
              size: 22.w, color: AppTheme.primaryColor),
          SizedBox(width: 8.w),
          Text(
            'chAs AI Creator',
            style: TextStyle(
              fontSize: 18.sp,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
      actions: [
        // Credits chip
        GestureDetector(
          onTap: () => _showCreditsSheet(),
          child: Container(
            margin: EdgeInsets.only(right: 6.w),
            padding:
                EdgeInsets.symmetric(horizontal: 12.w, vertical: 6.h),
            decoration: BoxDecoration(
              color: AppTheme.warningColor.withOpacity(0.12),
              borderRadius: BorderRadius.circular(20.r),
              border: Border.all(
                  color: AppTheme.warningColor.withOpacity(0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('💰', style: TextStyle(fontSize: 14.sp)),
                SizedBox(width: 4.w),
                Text(
                  '$_credits',
                  style: TextStyle(
                    fontSize: 13.sp,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.warningColor,
                  ),
                ),
              ],
            ),
          ),
        ),

        // Notification bell with badge
        Stack(
          children: [
            IconButton(
              icon: const Icon(Icons.notifications_outlined),
              onPressed: _showNotificationsSheet,
            ),
            if (_notificationCount > 0)
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  width: 16.w,
                  height: 16.w,
                  decoration: const BoxDecoration(
                    color: Colors.red,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      '$_notificationCount',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 9.sp,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ),
          ],
        ),

        SizedBox(width: 4.w),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // WELCOME CARD
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildWelcomeCard(User? user) {
    final tier = (user?.subscriptionTier ?? 'free').toLowerCase();
    final tierEmoji =
        tier == 'pro' ? '⭐' : tier == 'basic' ? '🔵' : '🆓';
    final name =
        user?.displayName ?? user?.email?.split('@').first ?? 'Creator';
    final initial = name[0].toUpperCase();

    return Container(
      padding: EdgeInsets.all(20.w),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(24.r),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryColor.withOpacity(0.35),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          // Avatar
          Container(
            width: 60.w,
            height: 60.w,
            decoration: BoxDecoration(
              color: Colors.white24,
              shape: BoxShape.circle,
              border:
                  Border.all(color: Colors.white38, width: 2),
            ),
            child: user?.avatarUrl != null
                ? ClipOval(
                    child: Image.network(user!.avatarUrl!,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            _avatarText(initial)),
                  )
                : _avatarText(initial),
          ),

          SizedBox(width: 16.w),

          // Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Welcome back! 👋',
                  style: TextStyle(
                      fontSize: 13.sp, color: Colors.white70),
                ),
                SizedBox(height: 3.h),
                Text(
                  name,
                  style: TextStyle(
                    fontSize: 20.sp,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                SizedBox(height: 10.h),
                Row(
                  children: [
                    _welchipBadge(
                        '$tierEmoji ${tier.toUpperCase()}'),
                    SizedBox(width: 8.w),
                    _welchipBadge(
                      '🎬 ${_usageStats?['remaining_daily_videos'] ?? 0} left today',
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _avatarText(String initial) => Center(
        child: Text(initial,
            style: TextStyle(
                fontSize: 24.sp,
                fontWeight: FontWeight.bold,
                color: Colors.white)),
      );

  Widget _welchipBadge(String label) => Container(
        padding:
            EdgeInsets.symmetric(horizontal: 10.w, vertical: 5.h),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.2),
          borderRadius: BorderRadius.circular(20.r),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 11.sp,
                color: Colors.white,
                fontWeight: FontWeight.w600)),
      );

  // ─────────────────────────────────────────────────────────────────────────
  // DAILY USAGE BAR
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildDailyUsageBar() {
    final used =
        (_usageStats?['videos_today'] ?? 0) as int;
    final remaining =
        (_usageStats?['remaining_daily_videos'] ?? 0) as int;
    final total = used + remaining;
    final progress = total > 0 ? used / total : 0.0;

    return Container(
      padding: EdgeInsets.all(16.w),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(16.r),
        border: Border.all(
            color: AppTheme.primaryColor.withOpacity(0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '📅 Daily Usage',
                style: TextStyle(
                    fontSize: 13.sp,
                    fontWeight: FontWeight.w600),
              ),
              Text(
                '$used / $total videos',
                style: TextStyle(
                    fontSize: 12.sp, color: Colors.grey),
              ),
            ],
          ),
          SizedBox(height: 10.h),
          ClipRRect(
            borderRadius: BorderRadius.circular(6.r),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 8,
              backgroundColor:
                  AppTheme.primaryColor.withOpacity(0.1),
              valueColor: AlwaysStoppedAnimation<Color>(
                progress >= 1.0
                    ? Colors.red
                    : AppTheme.primaryColor,
              ),
            ),
          ),
          SizedBox(height: 8.h),
          Text(
            remaining > 0
                ? '$remaining videos remaining today'
                : '⚠️ Daily limit reached — upgrade for more!',
            style: TextStyle(
              fontSize: 11.sp,
              color: remaining > 0
                  ? Colors.grey
                  : Colors.orange,
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // STATS GRID
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStatsGrid() {
    final stats = [
      _StatItem(
        emoji: '📹',
        label: 'Total Videos',
        value:
            '${_usageStats?['total_videos_generated'] ?? 0}',
        color: AppTheme.primaryColor,
      ),
      _StatItem(
        emoji: '⏰',
        label: 'Remaining',
        value:
            '${_usageStats?['remaining_daily_videos'] ?? 0}',
        color: Colors.orange,
      ),
      _StatItem(
        emoji: '📆',
        label: 'This Month',
        value:
            '${_usageStats?['videos_this_month'] ?? 0}',
        color: Colors.green,
      ),
      _StatItem(
        emoji: '💰',
        label: 'Credits',
        value: '$_credits',
        color: AppTheme.warningColor,
      ),
    ];

    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: 12.w,
      mainAxisSpacing: 12.h,
      childAspectRatio: 1.5,
      children: stats.map(_buildStatCard).toList(),
    );
  }

  Widget _buildStatCard(_StatItem item) {
    return Container(
      padding: EdgeInsets.all(16.w),
      decoration: BoxDecoration(
        color: item.color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16.r),
        border: Border.all(
            color: item.color.withOpacity(0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                padding: EdgeInsets.all(8.w),
                decoration: BoxDecoration(
                  color: item.color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10.r),
                ),
                child: Text(item.emoji,
                    style: TextStyle(fontSize: 16.sp)),
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.value,
                style: TextStyle(
                  fontSize: 26.sp,
                  fontWeight: FontWeight.bold,
                  color: item.color,
                ),
              ),
              Text(
                item.label,
                style: TextStyle(
                  fontSize: 11.sp,
                  color: Colors.grey,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // UPGRADE BANNER
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildUpgradeBanner() {
    return GestureDetector(
      onTap: () => _navigateTo(3),
      child: Container(
        padding: EdgeInsets.all(16.w),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Colors.amber.shade700,
              Colors.orange.shade600,
            ],
          ),
          borderRadius: BorderRadius.circular(16.r),
        ),
        child: Row(
          children: [
            Text('⭐', style: TextStyle(fontSize: 28.sp)),
            SizedBox(width: 12.w),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Upgrade to Pro',
                    style: TextStyle(
                      fontSize: 15.sp,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  Text(
                    '50 videos/day · 5 min max · 4K quality',
                    style: TextStyle(
                        fontSize: 11.sp, color: Colors.white.withOpacity(0.8)),
                  ),
                ],
              ),
            ),
            Container(
              padding: EdgeInsets.symmetric(
                  horizontal: 14.w, vertical: 8.h),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20.r),
              ),
              child: Text(
                'Upgrade',
                style: TextStyle(
                  fontSize: 12.sp,
                  fontWeight: FontWeight.bold,
                  color: Colors.orange.shade700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // QUICK ACTIONS
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildQuickActions() {
    final actions = [
      _QuickAction(
        emoji: '✨',
        label: 'Create\nVideo',
        color: AppTheme.primaryColor,
        onTap: () => _navigateTo(2),
      ),
      _QuickAction(
        emoji: '🎬',
        label: 'My\nVideos',
        color: Colors.green,
        onTap: () => _navigateTo(1),
      ),
      _QuickAction(
        emoji: '⚙️',
        label: 'Settings',
        color: Colors.blueGrey,
        onTap: () => _navigateTo(3),
      ),
      _QuickAction(
        emoji: '⭐',
        label: 'Upgrade',
        color: Colors.amber.shade700,
        onTap: () => _showUpgradeSheet(),
      ),
    ];

    return Row(
      children: actions
          .map((a) => Expanded(
                child: Padding(
                  padding: EdgeInsets.only(
                    right: a != actions.last ? 10.w : 0,
                  ),
                  child: GestureDetector(
                    onTap: a.onTap,
                    child: Container(
                      padding: EdgeInsets.symmetric(
                          vertical: 16.h),
                      decoration: BoxDecoration(
                        color: a.color.withOpacity(0.1),
                        borderRadius:
                            BorderRadius.circular(16.r),
                        border: Border.all(
                            color: a.color.withOpacity(0.2)),
                      ),
                      child: Column(
                        children: [
                          Text(a.emoji,
                              style:
                                  TextStyle(fontSize: 22.sp)),
                          SizedBox(height: 6.h),
                          Text(
                            a.label,
                            style: TextStyle(
                              fontSize: 10.sp,
                              fontWeight: FontWeight.w600,
                              color: a.color,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ))
          .toList(),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RECENT VIDEOS
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildRecentVideos() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _buildSectionTitle('🎬 Recent Videos'),
            TextButton(
              onPressed: () => _navigateTo(1),
              child: Text(
                'See All →',
                style: TextStyle(
                    fontSize: 13.sp,
                    color: AppTheme.primaryColor),
              ),
            ),
          ],
        ),
        SizedBox(height: 12.h),
        _recentVideos.isEmpty
            ? _buildEmptyVideos()
            : Column(
                children: _recentVideos
                    .map((v) => _buildRecentVideoCard(v))
                    .toList(),
              ),
      ],
    );
  }

  Widget _buildRecentVideoCard(dynamic video) {
    final status = video['status'] as String? ?? 'pending';
    final title = video['title'] as String? ?? 'Untitled';
    final thumbnail = video['thumbnail_url'] as String?;
    final duration = video['duration'] as int? ?? 0;
    final createdAt = video['created_at'] as String?;
    final niche = video['niche'] as String? ?? '';
    final progress =
        (video['progress'] as num?)?.toDouble() ?? 0.0;

    return GestureDetector(
      onTap: () => _navigateTo(1),
      child: Container(
        margin: EdgeInsets.only(bottom: 12.h),
        padding: EdgeInsets.all(12.w),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(16.r),
          border: Border.all(
            color: _statusColor(status).withOpacity(0.15),
          ),
        ),
        child: Row(
          children: [
            // Thumbnail
            ClipRRect(
              borderRadius: BorderRadius.circular(12.r),
              child: SizedBox(
                width: 80.w,
                height: 60.h,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    thumbnail != null && thumbnail.isNotEmpty
                        ? Image.network(thumbnail,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) =>
                                _thumbPlaceholder(niche))
                        : _thumbPlaceholder(niche),
                    if (status == 'completed')
                      Center(
                        child: Container(
                          width: 28.w,
                          height: 28.w,
                          decoration: BoxDecoration(
                            color: Colors.black45,
                            shape: BoxShape.circle,
                          ),
                          child: Icon(Icons.play_arrow,
                              color: Colors.white,
                              size: 16.w),
                        ),
                      ),
                    if (status == 'processing' ||
                        status == 'pending')
                      Positioned(
                        bottom: 0,
                        left: 0,
                        right: 0,
                        child: LinearProgressIndicator(
                          value: progress > 0 ? progress : null,
                          minHeight: 3,
                          backgroundColor:
                              Colors.white.withOpacity(0.2),
                          color: AppTheme.primaryColor,
                        ),
                      ),
                  ],
                ),
              ),
            ),

            SizedBox(width: 12.w),

            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 13.sp,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  SizedBox(height: 6.h),
                  Row(
                    children: [
                      _statusChip(status),
                      SizedBox(width: 6.w),
                      if (duration > 0)
                        Text(
                          _formatDuration(duration),
                          style: TextStyle(
                              fontSize: 10.sp,
                              color: Colors.grey),
                        ),
                    ],
                  ),
                  if (createdAt != null) ...[
                    SizedBox(height: 4.h),
                    Text(
                      _formatDate(createdAt),
                      style: TextStyle(
                          fontSize: 10.sp,
                          color: Colors.grey),
                    ),
                  ],
                ],
              ),
            ),

            Icon(Icons.chevron_right,
                color: Colors.grey, size: 18.w),
          ],
        ),
      ),
    );
  }

  Widget _thumbPlaceholder(String niche) => Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppTheme.primaryColor.withOpacity(0.3),
              AppTheme.accentColor.withOpacity(0.2),
            ],
          ),
        ),
        child: Center(
          child: Text(_nicheEmoji(niche),
              style: TextStyle(fontSize: 24.sp)),
        ),
      );

  Widget _statusChip(String status) {
    final color = _statusColor(status);
    return Container(
      padding:
          EdgeInsets.symmetric(horizontal: 7.w, vertical: 3.h),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(6.r),
      ),
      child: Text(
        _statusLabel(status),
        style: TextStyle(
          fontSize: 9.sp,
          color: color,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _buildEmptyVideos() {
    return Container(
      padding: EdgeInsets.all(32.w),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withOpacity(0.04),
        borderRadius: BorderRadius.circular(20.r),
        border: Border.all(
            color: AppTheme.primaryColor.withOpacity(0.1)),
      ),
      child: Column(
        children: [
          Text('🎬', style: TextStyle(fontSize: 48.sp)),
          SizedBox(height: 12.h),
          Text(
            'No videos yet',
            style: TextStyle(
              fontSize: 16.sp,
              fontWeight: FontWeight.bold,
            ),
          ),
          SizedBox(height: 6.h),
          Text(
            'Tap Create to generate your first AI video!',
            textAlign: TextAlign.center,
            style:
                TextStyle(fontSize: 12.sp, color: Colors.grey),
          ),
          SizedBox(height: 16.h),
          ElevatedButton.icon(
            onPressed: () => _navigateTo(2),
            icon: const Icon(Icons.auto_awesome, size: 16),
            label: const Text('Create Video'),
            style: ElevatedButton.styleFrom(
              padding: EdgeInsets.symmetric(
                  horizontal: 20.w, vertical: 12.h),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12.r)),
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SHEETS
  // ─────────────────────────────────────────────────────────────────────────

  void _showCreditsSheet() {
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
          children: [
            Text('💰 Your Credits',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 16.h),
            Text(
              '$_credits',
              style: TextStyle(
                fontSize: 56.sp,
                fontWeight: FontWeight.bold,
                color: AppTheme.warningColor,
              ),
            ),
            Text('credits available',
                style:
                    TextStyle(fontSize: 13.sp, color: Colors.grey)),
            SizedBox(height: 20.h),
            Container(
              padding: EdgeInsets.all(14.w),
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withOpacity(0.06),
                borderRadius: BorderRadius.circular(14.r),
              ),
              child: Column(
                children: [
                  _creditRow('🎬 Generate 1 video', '1 credit'),
                  _creditRow(
                      '📺 Watch ad', '+5 credits'),
                  _creditRow('💎 Buy credits', 'From settings'),
                ],
              ),
            ),
            SizedBox(height: 20.h),
            RewardAdButton(onRewardEarned: () {
              Navigator.pop(context);
              _onCreditsEarned();
            }),
            SizedBox(height: 16.h),
          ],
        ),
      ),
    );
  }

  Widget _creditRow(String label, String value) => Padding(
        padding: EdgeInsets.symmetric(vertical: 6.h),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label,
                style: TextStyle(fontSize: 13.sp)),
            Text(value,
                style: TextStyle(
                    fontSize: 13.sp,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primaryColor)),
          ],
        ),
      );

  void _showNotificationsSheet() {
    setState(() => _notificationCount = 0);
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
            Text('🔔 Notifications',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 16.h),
            _notifTile('🎉', 'Welcome to chAs AI Creator!',
                'Start creating amazing videos today.', '2m ago'),
            _notifTile('⭐', 'Upgrade Available',
                'Get 50 videos/day with Pro plan.', '1h ago'),
            SizedBox(height: 8.h),
          ],
        ),
      ),
    );
  }

  Widget _notifTile(String emoji, String title, String body,
      String time) {
    return Container(
      margin: EdgeInsets.only(bottom: 10.h),
      padding: EdgeInsets.all(14.w),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12.r),
      ),
      child: Row(
        children: [
          Text(emoji, style: TextStyle(fontSize: 22.sp)),
          SizedBox(width: 12.w),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                        fontSize: 13.sp,
                        fontWeight: FontWeight.w600)),
                SizedBox(height: 2.h),
                Text(body,
                    style: TextStyle(
                        fontSize: 11.sp, color: Colors.grey)),
              ],
            ),
          ),
          Text(time,
              style:
                  TextStyle(fontSize: 10.sp, color: Colors.grey)),
        ],
      ),
    );
  }

  void _showUpgradeSheet() {
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
          children: [
            Text('⭐ Upgrade to Pro',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            SizedBox(height: 16.h),
            ...[
              ('🆓 Free', ['2 videos/day', '30s max', 'Watermark'], false),
              ('🔵 Basic', ['10 videos/day', '60s max', 'HD', 'No watermark'], false),
              ('⭐ Pro', ['50 videos/day', '5 min max', '4K', 'Priority', 'All AI features'], true),
            ].map((plan) => Container(
                  margin: EdgeInsets.only(bottom: 10.h),
                  padding: EdgeInsets.all(14.w),
                  decoration: BoxDecoration(
                    color: plan.$3
                        ? AppTheme.primaryColor.withOpacity(0.1)
                        : Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(14.r),
                    border: Border.all(
                      color: plan.$3
                          ? AppTheme.primaryColor
                          : Colors.grey.withOpacity(0.2),
                      width: plan.$3 ? 1.5 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment:
                              CrossAxisAlignment.start,
                          children: [
                            Text(plan.$1,
                                style: TextStyle(
                                    fontSize: 14.sp,
                                    fontWeight: FontWeight.bold)),
                            SizedBox(height: 4.h),
                            ...plan.$2.map((f) => Text('✓ $f',
                                style: TextStyle(
                                    fontSize: 11.sp,
                                    color: Colors.grey))),
                          ],
                        ),
                      ),
                      if (plan.$3)
                        Container(
                          padding: EdgeInsets.symmetric(
                              horizontal: 10.w, vertical: 6.h),
                          decoration: BoxDecoration(
                            color: AppTheme.primaryColor,
                            borderRadius:
                                BorderRadius.circular(10.r),
                          ),
                          child: Text('Best',
                              style: TextStyle(
                                  fontSize: 11.sp,
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold)),
                        ),
                    ],
                  ),
                )),
            SizedBox(height: 8.h),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  _navigateTo(3);
                },
                style: ElevatedButton.styleFrom(
                  padding: EdgeInsets.symmetric(vertical: 14.h),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14.r)),
                ),
                child: const Text('Upgrade Now'),
              ),
            ),
            SizedBox(height: 16.h),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildSectionTitle(String title) => Text(
        title,
        style: TextStyle(
          fontSize: 17.sp,
          fontWeight: FontWeight.bold,
        ),
      );

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
}

// ─────────────────────────────────────────────────────────────────────────
// DATA CLASSES
// ─────────────────────────────────────────────────────────────────────────

class _StatItem {
  final String emoji;
  final String label;
  final String value;
  final Color color;
  const _StatItem({
    required this.emoji,
    required this.label,
    required this.value,
    required this.color,
  });
}

class _QuickAction {
  final String emoji;
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _QuickAction({
    required this.emoji,
    required this.label,
    required this.color,
    required this.onTap,
  });
}
