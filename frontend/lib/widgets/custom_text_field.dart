import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../config/theme.dart';

class CustomTextField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String? hint;
  final bool obscureText;
  final TextInputType keyboardType;
  final IconData? prefixIcon;
  final Widget? prefixWidget;
  final IconData? suffixIcon;
  final Widget? suffixWidget;
  final VoidCallback? onSuffixTap;
  final String? Function(String?)? validator;
  final int? maxLines;
  final int? minLines;
  final int? maxLength;
  final bool readOnly;
  final bool enabled;               // FIX 1 — was missing, caused build error
  final bool autofocus;
  final VoidCallback? onTap;
  final Function(String)? onChanged;
  final Function(String)? onSubmitted;
  final TextInputAction? textInputAction;
  final TextCapitalization textCapitalization;
  final List<TextInputFormatter>? inputFormatters;
  final String? errorText;          // FIX 2 — allow external error injection
  final String? helperText;
  final FocusNode? focusNode;
  final bool showCounter;

  const CustomTextField({
    super.key,
    required this.controller,
    required this.label,
    this.hint,
    this.obscureText = false,
    this.keyboardType = TextInputType.text,
    this.prefixIcon,
    this.prefixWidget,
    this.suffixIcon,
    this.suffixWidget,
    this.onSuffixTap,
    this.validator,
    this.maxLines = 1,
    this.minLines,
    this.maxLength,
    this.readOnly = false,
    this.enabled = true,            // FIX 1 — default true so nothing breaks
    this.autofocus = false,
    this.onTap,
    this.onChanged,
    this.onSubmitted,
    this.textInputAction,
    this.textCapitalization = TextCapitalization.none,
    this.inputFormatters,
    this.errorText,
    this.helperText,
    this.focusNode,
    this.showCounter = false,
  });

  @override
  State<CustomTextField> createState() => _CustomTextFieldState();
}

class _CustomTextFieldState extends State<CustomTextField> {
  late bool _obscure;
  bool _isFocused = false;
  late FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _obscure = widget.obscureText;
    _focusNode = widget.focusNode ?? FocusNode();
    _focusNode.addListener(() {
      if (mounted) setState(() => _isFocused = _focusNode.hasFocus);
    });
  }

  @override
  void dispose() {
    // Only dispose if we created it internally
    if (widget.focusNode == null) _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Label ──────────────────────────────────────────────────
        Row(
          children: [
            Text(
              widget.label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    fontSize: 13.sp,
                    color: _isFocused
                        ? AppTheme.primaryColor
                        : isDark
                            ? Colors.white70
                            : Colors.grey.shade700,
                  ),
            ),
            if (widget.helperText != null) ...[
              SizedBox(width: 6.w),
              Text(
                widget.helperText!,
                style: TextStyle(
                  fontSize: 11.sp,
                  color: Colors.grey,
                ),
              ),
            ],
          ],
        ),

        SizedBox(height: 8.h),

        // ── Field ───────────────────────────────────────────────────
        AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14.r),
            boxShadow: _isFocused
                ? [
                    BoxShadow(
                      color: AppTheme.primaryColor.withOpacity(0.15),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    )
                  ]
                : [],
          ),
          child: TextFormField(
            controller: widget.controller,
            focusNode: _focusNode,
            obscureText: _obscure,
            keyboardType: widget.keyboardType,
            validator: widget.validator,
            // FIX 3 — maxLines must be 1 when obscureText is true
            maxLines: _obscure ? 1 : widget.maxLines,
            minLines: widget.minLines,
            maxLength: widget.showCounter ? widget.maxLength : null,
            readOnly: widget.readOnly,
            enabled: widget.enabled,
            autofocus: widget.autofocus,
            onTap: widget.onTap,
            onChanged: widget.onChanged,
            onFieldSubmitted: widget.onSubmitted,
            textInputAction: widget.textInputAction,
            textCapitalization: widget.textCapitalization,
            inputFormatters: [
              // FIX 4 — apply maxLength as hard limit without showing counter
              if (widget.maxLength != null && !widget.showCounter)
                LengthLimitingTextInputFormatter(widget.maxLength!),
              ...?widget.inputFormatters,
            ],
            style: TextStyle(
              fontSize: 15.sp,
              color: widget.enabled
                  ? null
                  : Colors.grey, // FIX 5 — visually dim when disabled
            ),
            decoration: InputDecoration(
              hintText: widget.hint,
              errorText: widget.errorText,
              counterText: widget.showCounter ? null : '',

              // Prefix
              prefixIcon: widget.prefixWidget ??
                  (widget.prefixIcon != null
                      ? Icon(
                          widget.prefixIcon,
                          size: 20.w,
                          color: _isFocused
                              ? AppTheme.primaryColor
                              : AppTheme.textSecondaryLight,
                        )
                      : null),

              // Suffix — auto-toggle eye for password fields
              suffixIcon: widget.obscureText
                  ? GestureDetector(
                      onTap: () =>
                          setState(() => _obscure = !_obscure),
                      child: Icon(
                        _obscure
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                        size: 20.w,
                        color: _isFocused
                            ? AppTheme.primaryColor
                            : AppTheme.textSecondaryLight,
                      ),
                    )
                  : widget.suffixWidget ??
                      (widget.suffixIcon != null
                          ? GestureDetector(
                              onTap: widget.onSuffixTap,
                              child: Icon(
                                widget.suffixIcon,
                                size: 20.w,
                                color: _isFocused
                                    ? AppTheme.primaryColor
                                    : AppTheme.textSecondaryLight,
                              ),
                            )
                          : null),

              // Borders
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14.r),
                borderSide: BorderSide(
                  color: isDark
                      ? Colors.white12
                      : Colors.grey.shade300,
                  width: 1.2,
                ),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14.r),
                borderSide: BorderSide(
                  color: AppTheme.primaryColor,
                  width: 1.8,
                ),
              ),
              errorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14.r),
                borderSide: BorderSide(
                  color: Colors.red.shade400,
                  width: 1.2,
                ),
              ),
              focusedErrorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14.r),
                borderSide: BorderSide(
                  color: Colors.red.shade400,
                  width: 1.8,
                ),
              ),
              disabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14.r),
                borderSide: BorderSide(
                  color: Colors.grey.withOpacity(0.15),
                  width: 1,
                ),
              ),

              // Fill
              filled: true,
              fillColor: !widget.enabled
                  ? Colors.grey.withOpacity(0.06)
                  : _isFocused
                      ? AppTheme.primaryColor.withOpacity(0.04)
                      : isDark
                          ? Colors.white.withOpacity(0.05)
                          : Colors.grey.shade50,

              // Padding & text sizes
              contentPadding: EdgeInsets.symmetric(
                horizontal: 16.w,
                vertical: widget.maxLines != null && widget.maxLines! > 1
                    ? 14.h
                    : 0,
              ),
              hintStyle: TextStyle(
                fontSize: 14.sp,
                color: Colors.grey.shade400,
              ),
              errorStyle: TextStyle(fontSize: 11.sp),
            ),
          ),
        ),
      ],
    );
  }
}
