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

  Color _getStatusColor() {
    switch (status.toLowerCase()) {
      case 'completed':
        return AppTheme.successColor;
      case 'failed':
        return AppTheme.errorColor;
      case 'pending':
      case 'processing':
        return AppTheme.warningColor;
      default:
        return AppTheme.infoColor;
    }
  }

  String _formatDuration(int? seconds) {
    if (seconds == null) return '--:--';
    final minutes = seconds ~/ 60;
    final remainingSeconds = seconds % 60;
    return '$minutes:${remainingSeconds.toString().padLeft(2, '0')}';
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final date = DateTime.parse(dateStr);
      return DateFormat('MMM d, y').format(date);
    } catch (e) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
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
            // Thumbnail
            ClipRRect(
              borderRadius: BorderRadius.vertical(top: Radius.circular(16.r)),
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: thumbnailUrl != null
                    ? CachedNetworkImage(
                        imageUrl: thumbnailUrl!,
                        fit: BoxFit.cover,
                        placeholder: (context, url) => Container(
                          color: Colors.grey.shade200,
                          child: const Center(
                            child: CircularProgressIndicator(),
                          ),
                        ),
                        errorWidget: (context, url, error) => Container(
                          color: Colors.grey.shade200,
                          child: Icon(
                            Icons.video_library,
                            size: 48.w,
                            color: Colors.grey,
                          ),
                        ),
                      )
                    : Container(
                        color: Colors.grey.shade200,
                        child: Icon(
                          Icons.video_library,
                          size: 48.w,
                          color: Colors.grey,
                        ),
                      ),
              ),
            ),
            
            // Info
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
                          style: Theme.of(context).textTheme.titleMedium,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (onMoreTap != null)
                        GestureDetector(
                          onTap: onMoreTap,
                          child: Icon(
                            Icons.more_vert,
                            size: 20.w,
                            color: AppTheme.textSecondaryLight,
                          ),
                        ),
                    ],
                  ),
                  SizedBox(height: 12.h),
                  Row(
                    children: [
                      // Status
                      Container(
                        padding: EdgeInsets.symmetric(
                          horizontal: 8.w,
                          vertical: 4.h,
                        ),
                        decoration: BoxDecoration(
                          color: _getStatusColor().withOpacity(0.1),
                          borderRadius: BorderRadius.circular(6.r),
                        ),
                        child: Text(
                          status.toUpperCase(),
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: _getStatusColor(),
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
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppTheme.textSecondaryLight,
                          ),
                        ),
                      ],
                      
                      const Spacer(),
                      
                      if (createdAt != null)
                        Text(
                          _formatDate(createdAt),
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppTheme.textSecondaryLight,
                          ),
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
}
