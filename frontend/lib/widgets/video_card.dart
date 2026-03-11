/*
 * chAs AI Creator - Video Card Widget
 * FILE: lib/widgets/video_card.dart
 *
 * FIXES:
 * 1. AspectRatio was 16/9 (landscape) — this app generates vertical
 *    videos for TikTok/Reels (9:16). Thumbnails were showing with
 *    wide black bars. Changed to 9/16 portrait ratio.
 *
 * 2. Placeholder used Colors.grey.shade200 which is nearly invisible
 *    on dark theme. Replaced with theme-aware color.
 */

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:intl/intl.dart';

import '../config/theme.dart';

class VideoCard extends StatelessWidget {
  final String title;
  final String? thumbnailUrl;
  final String status;
  final int? duration;
  final String? createdAt;
  final VoidCallback? onTap;
  final VoidCallback? onMoreTap;

  const VideoCard({
    super.key,
    required this.title,
    this.thumbnailUrl,
    required this.status,
    this.duration,
    this.createdAt,
    this.onTap,
    this.onMoreTap,
  });

  Color _statusColor() {
    return switch (status.toLowerCase()) {
      'completed'  => AppTheme.successColor,
      'failed'     => AppTheme.errorColor,
      'pending'    => AppTheme.warningColor,
      'processing' => AppTheme.warningColor,
      _            => AppTheme.infoColor,
    };
  }

  String _formatDuration(int? seconds) {
    if (seconds == null) return '--:--';
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      return DateFormat('MMM d, y').format(DateTime.parse(dateStr));
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    // FIX 2 — theme-aware placeholder color
    final placeholderColor =
        isDark ? const Color(0xFF3D3D4A) : Colors.grey.shade200;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: EdgeInsets.only(bottom: 12.h),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(16.r),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Thumbnail ─────────────────────────────────────────
            ClipRRect(
              borderRadius: BorderRadius.vertical(
                  top: Radius.circular(16.r)),
              child: AspectRatio(
                // FIX 1 — was 16/9 (landscape). App generates
                // vertical videos for TikTok/Reels → 9/16.
                aspectRatio: 9 / 16,
                child: thumbnailUrl != null &&
                        thumbnailUrl!.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: thumbnailUrl!,
                        fit: BoxFit.cover,
                        placeholder: (context, url) => Container(
                          color: placeholderColor,
                          child: Center(
                            child: CircularProgressIndicator(
                              color: AppTheme.primaryColor,
                              strokeWidth: 2,
                            ),
                          ),
                        ),
                        errorWidget: (context, url, error) =>
                            _thumbPlaceholder(placeholderColor),
                      )
                    : _thumbPlaceholder(placeholderColor),
              ),
            ),

            // ── Info ──────────────────────────────────────────────
            Padding(
              padding: EdgeInsets.all(16.w),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (onMoreTap != null)
                        GestureDetector(
                          onTap: onMoreTap,
                          child: Padding(
                            padding: EdgeInsets.only(left: 8.w),
                            child: Icon(
                              Icons.more_vert,
                              size: 20.w,
                              color: AppTheme.textSecondaryLight,
                            ),
                          ),
                        ),
                    ],
                  ),

                  SizedBox(height: 12.h),

                  Row(
                    children: [
                      // Status chip
                      Container(
                        padding: EdgeInsets.symmetric(
                            horizontal: 8.w, vertical: 4.h),
                        decoration: BoxDecoration(
                          color: _statusColor().withOpacity(0.1),
                          borderRadius:
                              BorderRadius.circular(6.r),
                        ),
                        child: Text(
                          status.toUpperCase(),
                          style: Theme.of(context)
                              .textTheme
                              .labelSmall
                              ?.copyWith(
                                color: _statusColor(),
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                      ),

                      if (duration != null) ...[
                        SizedBox(width: 12.w),
                        Icon(
                          Icons.timer,
                          size: 14.w,
                          color: AppTheme.textSecondaryLight,
                        ),
                        SizedBox(width: 4.w),
                        Text(
                          _formatDuration(duration),
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(
                                  color:
                                      AppTheme.textSecondaryLight),
                        ),
                      ],

                      const Spacer(),

                      if (createdAt != null)
                        Text(
                          _formatDate(createdAt),
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(
                                  color:
                                      AppTheme.textSecondaryLight),
                        ),
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

  Widget _thumbPlaceholder(Color bg) => Container(
        color: bg,
        child: Center(
          child: Icon(
            Icons.video_library_outlined,
            size: 48.w,
            color: AppTheme.primaryColor.withOpacity(0.4),
          ),
        ),
      );
}
