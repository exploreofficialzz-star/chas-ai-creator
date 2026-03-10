/*
 * chAs AI Creator - Dashboard Screen
 * Created by: chAs
 * User-friendly dashboard with stats and quick actions
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
import '../../widgets/stat_card.dart';
import '../../widgets/video_card.dart';

class DashboardScreen extends StatefulWidget {
  final Function(int)? onNavigate;
  
  const DashboardScreen({super.key, this.onNavigate});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();
  final AdService _adService = AdService();
  
  Map<String, dynamic>? _usageStats;
  List<dynamic>? _recentVideos;
  bool _isLoading = true;
  int _credits = 0;

  @override
  void initState() {
    super.initState();
    _loadData();
    _showInterstitialAdIfNeeded();
  }

  Future<void> _showInterstitialAdIfNeeded() async {
    await _adService.showInterstitialAd();
  }

  Future<void> _loadData() async {
    try {
      final stats = await _apiService.getUsageStats();
      final videos = await _apiService.getVideos(limit: 5);
      
      setState(() {
        _usageStats = stats;
        _recentVideos = videos['videos'];
        _credits = stats['credits'] ?? 0;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _refresh() async {
    setState(() => _isLoading = true);
    await _loadData();
  }

  void _onCreditsEarned() {
    setState(() {
      _credits += 5;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('🎉 You earned 5 credits!'),
        backgroundColor: AppTheme.successColor,
      ),
    );
  }

  void _navigateTo(int index) {
    if (widget.onNavigate != null) {
      widget.onNavigate!(index);
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {
        User? user;
        if (state is Authenticated) {
          user = state.user;
        }

        return Scaffold(
          appBar: AppBar(
            title: Row(
              children: [
                Icon(Icons.auto_awesome, size: 24.w, color: AppTheme.primaryColor),
                SizedBox(width: 8.w),
                const Text('chAs AI Creator'),
              ],
            ),
            actions: [
              Container(
                margin: EdgeInsets.only(right: 8.w),
                padding: EdgeInsets.symmetric(horizontal: 12.w, vertical: 6.h),
                decoration: BoxDecoration(
                  color: AppTheme.warningColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20.r),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.monetization_on,
                      size: 16.w,
                      color: AppTheme.warningColor,
                    ),
                    SizedBox(width: 4.w),
                    Text(
                      '$_credits',
                      style: TextStyle(
                        fontSize: 14.sp,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.warningColor,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.notifications_outlined),
                onPressed: () => _navigateTo(3),
              ),
            ],
          ),
          body: RefreshIndicator(
            onRefresh: _refresh,
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : CustomScrollView(
                    slivers: [
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: EdgeInsets.all(16.w),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _buildWelcomeSection(user),
                              SizedBox(height: 20.h),
                              const BannerAdContainer(),
                              SizedBox(height: 20.h),
                              _buildStatsSection(),
                              SizedBox(height: 20.h),
                              RewardAdButton(
                                onRewardEarned: _onCreditsEarned,
                              ),
                              SizedBox(height: 20.h),
                              _buildQuickActions(),
                              SizedBox(height: 20.h),
                              const BannerAdContainer(isLarge: true),
                              SizedBox(height: 20.h),
                              _buildRecentVideos(),
                              SizedBox(height: 20.h),
                              const BannerAdContainer(),
                            ],
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

  Widget _buildWelcomeSection(User? user) {
    return Container(
      padding: EdgeInsets.all(20.w),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(20.r),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryColor.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 32.w,
                backgroundColor: Colors.white24,
                child: Text(
                  user?.displayName?.substring(0, 1).toUpperCase() ??
                      user?.email.substring(0, 1).toUpperCase() ??
                      'U',
                  style: TextStyle(
                    fontSize: 28.sp,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
              SizedBox(width: 16.w),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Welcome back! 👋',
                      style: TextStyle(
                        fontSize: 14.sp,
                        color: Colors.white70,
                      ),
                    ),
                    SizedBox(height: 4.h),
                    Text(
                      user?.displayName ?? user?.email ?? 'Creator',
                      style: TextStyle(
                        fontSize: 22.sp,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
          SizedBox(height: 20.h),
          Row(
            children: [
              Container(
                padding: EdgeInsets.symmetric(horizontal: 12.w, vertical: 8.h),
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(8.r),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.workspace_premium, size: 16.w, color: Colors.white),
                    SizedBox(width: 8.w),
                    Text(
                      (user?.subscriptionTier ?? 'FREE').toUpperCase(),
                      style: TextStyle(
                        fontSize: 12.sp,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
              SizedBox(width: 12.w),
              Container(
                padding: EdgeInsets.symmetric(horizontal: 12.w, vertical: 8.h),
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(8.r),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.video_call, size: 16.w, color: Colors.white),
                    SizedBox(width: 8.w),
                    Text(
                      '${_usageStats?['remaining_daily_videos'] ?? 0} left today',
                      style: TextStyle(
                        fontSize: 12.sp,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '📊 Your Stats',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        SizedBox(height: 16.h),
        Row(
          children: [
            Expanded(
              child: StatCard(
                title: 'Total Videos',
                value: _usageStats?['total_videos_generated']?.toString() ?? '0',
                icon: Icons.video_library,
                color: AppTheme.primaryColor,
              ),
            ),
            SizedBox(width: 12.w),
            Expanded(
              child: StatCard(
                title: 'Remaining',
                value: _usageStats?['remaining_daily_videos']?.toString() ?? '0',
                icon: Icons.timer,
                color: AppTheme.accentColor,
              ),
            ),
          ],
        ),
        SizedBox(height: 12.h),
        Row(
          children: [
            Expanded(
              child: StatCard(
                title: 'This Month',
                value: _usageStats?['videos_this_month']?.toString() ?? '0',
                icon: Icons.calendar_today,
                color: AppTheme.secondaryColor,
              ),
            ),
            SizedBox(width: 12.w),
            Expanded(
              child: StatCard(
                title: 'Credits',
                value: '$_credits',
                icon: Icons.monetization_on,
                color: AppTheme.warningColor,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildQuickActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '⚡ Quick Actions',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        SizedBox(height: 16.h),
        Row(
          children: [
            Expanded(
              child: _ActionCard(
                title: 'Create\nVideo',
                icon: Icons.add_circle,
                color: AppTheme.primaryColor,
                onTap: () => _navigateTo(2),
              ),
            ),
            SizedBox(width: 12.w),
            Expanded(
              child: _ActionCard(
                title: 'Schedule',
                icon: Icons.schedule,
                color: AppTheme.accentColor,
                onTap: () => _navigateTo(1),
              ),
            ),
            SizedBox(width: 12.w),
            Expanded(
              child: _ActionCard(
                title: 'Upgrade',
                icon: Icons.workspace_premium,
                color: AppTheme.secondaryColor,
                onTap: () => _navigateTo(3),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildRecentVideos() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '🎬 Recent Videos',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            TextButton(
              onPressed: () => _navigateTo(1),
              child: const Text('See All →'),
            ),
          ],
        ),
        SizedBox(height: 16.h),
        if (_recentVideos?.isEmpty ?? true)
          Container(
            padding: EdgeInsets.all(32.w),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(16.r),
            ),
            child: Center(
              child: Column(
                children: [
                  Icon(
                    Icons.video_library_outlined,
                    size: 64.w,
                    color: Colors.grey,
                  ),
                  SizedBox(height: 16.h),
                  Text(
                    'No videos yet',
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: Colors.grey,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  SizedBox(height: 8.h),
                  Text(
                    'Create your first video! 🎥',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.grey,
                    ),
                  ),
                  SizedBox(height: 16.h),
                  ElevatedButton.icon(
                    onPressed: () => _navigateTo(2),
                    icon: const Icon(Icons.add),
                    label: const Text('Create Video'),
                  ),
                ],
              ),
            ),
          )
        else
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _recentVideos?.length ?? 0,
            itemBuilder: (context, index) {
              final video = _recentVideos![index];
              return VideoCard(
                title: video['title'] ?? 'Untitled',
                thumbnailUrl: video['thumbnail_url'],
                status: video['status'],
                duration: video['duration'],
                createdAt: video['created_at'],
                onTap: () => _navigateTo(1),
              );
            },
          ),
      ],
    );
  }
}

class _ActionCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _ActionCard({
    required this.title,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.all(16.w),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(16.r),
          border: Border.all(
            color: color.withOpacity(0.2),
            width: 1,
          ),
        ),
        child: Column(
          children: [
            Icon(
              icon,
              size: 32.w,
              color: color,
            ),
            SizedBox(height: 8.h),
            Text(
              title,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: color,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
