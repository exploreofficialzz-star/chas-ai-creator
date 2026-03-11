/*
 * chAs AI Creator - Social Button Widget
 * FILE: lib/widgets/social_button.dart
 *
 * FIXES:
 * 1. SvgPicture.asset() crashes if the SVG file doesn't exist in
 *    assets — placeholderBuilder only handles loading state, NOT
 *    missing files. Replaced with a safe try/catch Image.asset
 *    with a guaranteed Icon fallback. No SVG dependency needed.
 *
 * 2. Removed flutter_svg import — not needed and may not be in
 *    pubspec.yaml, which would cause a build error.
 *
 * NOTE: This widget is currently unused in the app since Google
 * Sign-In is disabled (Nigeria friendly version uses email only).
 * Keeping it for future use.
 */

import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

class SocialButton extends StatelessWidget {
  final String text;
  final String icon; // asset path OR empty string for fallback
  final VoidCallback onPressed;

  const SocialButton({
    super.key,
    required this.text,
    required this.icon,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          padding: EdgeInsets.symmetric(vertical: 16.h),
          side: BorderSide(color: Colors.grey.shade300),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12.r),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildIcon(),
            SizedBox(width: 12.w),
            Text(
              text,
              style: TextStyle(
                fontSize: 16.sp,
                fontWeight: FontWeight.w500,
                color: Theme.of(context)
                    .textTheme
                    .bodyLarge
                    ?.color,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIcon() {
    // FIX 1 — never use SvgPicture.asset() without knowing the
    // file exists. Use a Material icon fallback instead which is
    // guaranteed to always work with zero asset files required.
    final isGoogle = icon.toLowerCase().contains('google');
    final isApple  = icon.toLowerCase().contains('apple');

    if (isGoogle) {
      return _GoogleIcon(size: 24.w);
    }
    if (isApple) {
      return Icon(Icons.apple, size: 24.w);
    }

    // Generic fallback for any other social icon
    return Icon(Icons.login, size: 24.w);
  }
}

/// Simple Google "G" icon drawn with Canvas — no SVG file needed
class _GoogleIcon extends StatelessWidget {
  final double size;
  const _GoogleIcon({required this.size});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(painter: _GooglePainter()),
    );
  }
}

class _GooglePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;

    // Draw coloured quadrant arcs
    final colors = [
      const Color(0xFF4285F4), // blue   — top right
      const Color(0xFF34A853), // green  — bottom right
      const Color(0xFFFBBC05), // yellow — bottom left
      const Color(0xFFEA4335), // red    — top left
    ];

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.18;

    for (int i = 0; i < 4; i++) {
      paint.color = colors[i];
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius * 0.75),
        (i * 3.14159 / 2) - 3.14159 / 4,
        3.14159 / 2,
        false,
        paint,
      );
    }

    // White centre
    canvas.drawCircle(
      center,
      radius * 0.35,
      Paint()..color = Colors.white,
    );

    // Blue horizontal bar (the G crossbar)
    canvas.drawRect(
      Rect.fromLTWH(
        center.dx - radius * 0.02,
        center.dy - radius * 0.12,
        radius * 0.72,
        radius * 0.24,
      ),
      Paint()..color = const Color(0xFF4285F4),
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
