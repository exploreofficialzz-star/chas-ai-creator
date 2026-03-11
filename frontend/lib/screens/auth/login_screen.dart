/*
 * chAs AI Creator - Login Screen
 * FILE: lib/screens/auth/login_screen.dart
 *
 * This screen now stays mounted during the ENTIRE login attempt
 * because app.dart's buildWhen no longer swaps it out for SplashScreen
 * on AuthLoading. This means:
 *  - BlocListener catches ALL states: AuthLoading, AuthError, Authenticated
 *  - Spinner works on first tap
 *  - Error snackbars always show
 *  - _isLoading state is never silently reset by widget rebuild
 */

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../providers/auth_bloc.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_text_field.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLogin = true;
  bool _isLoading = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    if (_isLoading) return; // Prevent double-tap

    if (_isLogin) {
      context.read<AuthBloc>().add(
            LoginWithEmail(
              email: _emailController.text.trim(),
              password: _passwordController.text,
            ),
          );
    } else {
      context.read<AuthBloc>().add(
            RegisterWithEmail(
              email: _emailController.text.trim(),
              password: _passwordController.text,
            ),
          );
    }
  }

  void _toggleMode() {
    setState(() {
      _isLogin = !_isLogin;
      _isLoading = false;
    });
    _formKey.currentState?.reset();
    _emailController.clear();
    _passwordController.clear();
    ScaffoldMessenger.of(context).clearSnackBars();
  }

  void _showSnackBar(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          content: Text(msg),
          backgroundColor:
              error ? Colors.red.shade700 : Colors.green.shade700,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12.r)),
          margin: EdgeInsets.all(16.w),
          duration: const Duration(seconds: 4),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<AuthBloc, AuthState>(
        listener: (context, state) {
          if (state is AuthLoading) {
            // Show spinner — LoginScreen is still mounted thanks to
            // app.dart's buildWhen fix. Previously this state caused
            // app.dart to unmount LoginScreen entirely.
            if (mounted && !_isLoading) {
              setState(() => _isLoading = true);
            }
          } else if (state is AuthError) {
            // Show error — LoginScreen is still mounted because
            // app.dart's buildWhen skips AuthError rebuilds.
            if (mounted) {
              setState(() => _isLoading = false);
              _showSnackBar(state.message, error: true);
            }
          } else if (state is Authenticated) {
            // Navigation handled entirely by app.dart BlocBuilder.
            // Just reset spinner here — do NOT call Navigator.
            if (mounted) setState(() => _isLoading = false);
          } else if (state is PasswordResetSent) {
            if (mounted) {
              setState(() => _isLoading = false);
              _showSnackBar(
                  '✅ Reset link sent to ${state.email}! Check your inbox.');
            }
          } else if (state is Unauthenticated) {
            // Covers logout or ClearAuthError
            if (mounted) setState(() => _isLoading = false);
          }
        },
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                const Color(0xFF0F0F1A),
                AppTheme.primaryColor.withOpacity(0.15),
                const Color(0xFF0F0F1A),
              ],
            ),
          ),
          child: SafeArea(
            child: Column(
              children: [
                // ── Scrollable body ────────────────────────────────
                Expanded(
                  child: SingleChildScrollView(
                    padding: EdgeInsets.symmetric(horizontal: 28.w),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        SizedBox(height: 50.h),

                        // Logo
                        Container(
                          width: 110.w,
                          height: 110.w,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                AppTheme.primaryColor,
                                AppTheme.primaryColor
                                    .withOpacity(0.8),
                                const Color(0xFF8B5CF6),
                              ],
                            ),
                            borderRadius:
                                BorderRadius.circular(28.r),
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.primaryColor
                                    .withOpacity(0.3),
                                blurRadius: 20,
                                offset: const Offset(0, 10),
                              ),
                            ],
                          ),
                          child: Icon(
                            Icons.auto_fix_high_rounded,
                            size: 52.w,
                            color: Colors.white,
                          ),
                        ),

                        SizedBox(height: 32.h),

                        // App name
                        Text(
                          'chAs AI Creator',
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                        ),

                        SizedBox(height: 8.h),

                        // Login / register title
                        AnimatedSwitcher(
                          duration:
                              const Duration(milliseconds: 300),
                          child: Text(
                            _isLogin
                                ? 'Welcome Back!'
                                : 'Create Account',
                            key: ValueKey(_isLogin),
                            style: Theme.of(context)
                                .textTheme
                                .headlineMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                  fontSize: 28.sp,
                                ),
                            textAlign: TextAlign.center,
                          ),
                        ),

                        SizedBox(height: 8.h),

                        // Subtitle
                        Text(
                          _isLogin
                              ? 'Sign in to continue creating amazing AI videos'
                              : 'Start your journey to viral video content',
                          style: Theme.of(context)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(
                                color:
                                    Colors.white.withOpacity(0.7),
                                fontSize: 14.sp,
                              ),
                          textAlign: TextAlign.center,
                        ),

                        SizedBox(height: 40.h),

                        // ── Form card ──────────────────────────────
                        Container(
                          padding: EdgeInsets.all(24.w),
                          decoration: BoxDecoration(
                            color:
                                Colors.white.withOpacity(0.05),
                            borderRadius:
                                BorderRadius.circular(20.r),
                            border: Border.all(
                              color:
                                  Colors.white.withOpacity(0.1),
                            ),
                          ),
                          child: Form(
                            key: _formKey,
                            child: Column(
                              children: [
                                // Email
                                CustomTextField(
                                  controller: _emailController,
                                  label: 'Email Address',
                                  hint: 'name@example.com',
                                  keyboardType: TextInputType
                                      .emailAddress,
                                  prefixIcon:
                                      Icons.email_outlined,
                                  enabled: !_isLoading,
                                  validator: (value) {
                                    if (value?.isEmpty ?? true) {
                                      return 'Please enter your email';
                                    }
                                    if (!value!.contains('@') ||
                                        !value.contains('.')) {
                                      return 'Please enter a valid email';
                                    }
                                    return null;
                                  },
                                ),

                                SizedBox(height: 20.h),

                                // Password
                                CustomTextField(
                                  controller:
                                      _passwordController,
                                  label: 'Password',
                                  hint: _isLogin
                                      ? 'Your password'
                                      : 'Min 8 characters',
                                  obscureText: true,
                                  prefixIcon: Icons
                                      .lock_outline_rounded,
                                  enabled: !_isLoading,
                                  validator: (value) {
                                    if (value?.isEmpty ?? true) {
                                      return 'Please enter your password';
                                    }
                                    if (!_isLogin &&
                                        value!.length < 8) {
                                      return 'Password must be at least 8 characters';
                                    }
                                    if (_isLogin &&
                                        value!.length < 6) {
                                      return 'Password too short';
                                    }
                                    return null;
                                  },
                                ),

                                // Forgot password (login only)
                                if (_isLogin) ...[
                                  SizedBox(height: 8.h),
                                  Align(
                                    alignment:
                                        Alignment.centerRight,
                                    child: TextButton(
                                      onPressed: _isLoading
                                          ? null
                                          : _showForgotPassword,
                                      child: Text(
                                        'Forgot Password?',
                                        style: TextStyle(
                                          color: AppTheme
                                              .primaryColor,
                                          fontSize: 12.sp,
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ),

                        SizedBox(height: 24.h),

                        // ── Render warm-up note ────────────────────
                        // Shown when loading to explain a slow first
                        // login (Render free tier cold start = 50s+)
                        AnimatedSwitcher(
                          duration:
                              const Duration(milliseconds: 400),
                          child: _isLoading
                              ? Container(
                                  key: const ValueKey('loading_hint'),
                                  padding: EdgeInsets.symmetric(
                                      horizontal: 16.w,
                                      vertical: 10.h),
                                  decoration: BoxDecoration(
                                    color: AppTheme.primaryColor
                                        .withOpacity(0.1),
                                    borderRadius:
                                        BorderRadius.circular(
                                            12.r),
                                    border: Border.all(
                                      color: AppTheme.primaryColor
                                          .withOpacity(0.2),
                                    ),
                                  ),
                                  child: Row(
                                    mainAxisSize:
                                        MainAxisSize.min,
                                    children: [
                                      SizedBox(
                                        width: 14.w,
                                        height: 14.w,
                                        child:
                                            CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: AppTheme
                                              .primaryColor,
                                        ),
                                      ),
                                      SizedBox(width: 10.w),
                                      Text(
                                        'Connecting… this may take up to 30s',
                                        style: TextStyle(
                                          fontSize: 12.sp,
                                          color: Colors.white70,
                                        ),
                                      ),
                                    ],
                                  ),
                                )
                              : const SizedBox.shrink(
                                  key: ValueKey('idle')),
                        ),

                        SizedBox(height: 16.h),

                        // Submit button
                        CustomButton(
                          text: _isLogin
                              ? 'Sign In'
                              : 'Create Account',
                          onPressed: _isLoading ? null : _submit,
                          isLoading: _isLoading,
                        ),

                        SizedBox(height: 20.h),

                        // Toggle login / register
                        TextButton(
                          onPressed:
                              _isLoading ? null : _toggleMode,
                          style: TextButton.styleFrom(
                            padding: EdgeInsets.symmetric(
                                horizontal: 16.w,
                                vertical: 8.h),
                          ),
                          child: RichText(
                            text: TextSpan(
                              text: _isLogin
                                  ? "Don't have an account? "
                                  : "Already have an account? ",
                              style: TextStyle(
                                color:
                                    Colors.white.withOpacity(0.7),
                                fontSize: 14.sp,
                              ),
                              children: [
                                TextSpan(
                                  text: _isLogin
                                      ? 'Sign Up'
                                      : 'Sign In',
                                  style: TextStyle(
                                    color: AppTheme.primaryColor,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14.sp,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                        SizedBox(height: 30.h),
                      ],
                    ),
                  ),
                ),

                // ── Footer ─────────────────────────────────────────
                Container(
                  padding: EdgeInsets.symmetric(vertical: 20.h),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.transparent,
                        Colors.black.withOpacity(0.3),
                      ],
                    ),
                  ),
                  child: Column(
                    children: [
                      Container(
                        margin: EdgeInsets.symmetric(
                            horizontal: 40.w),
                        height: 1,
                        color: Colors.white.withOpacity(0.1),
                      ),
                      SizedBox(height: 16.h),
                      Row(
                        mainAxisAlignment:
                            MainAxisAlignment.center,
                        children: [
                          Text(
                            'Made with ',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 12.sp,
                            ),
                          ),
                          Icon(Icons.favorite,
                              color: Colors.red.shade400,
                              size: 14.sp),
                          Text(
                            ' by ',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 12.sp,
                            ),
                          ),
                          Text(
                            'chAs tech group',
                            style: TextStyle(
                              color: AppTheme.primaryColor,
                              fontSize: 12.sp,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                      SizedBox(height: 4.h),
                      Text(
                        '© 2025 All rights reserved',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.4),
                          fontSize: 10.sp,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FORGOT PASSWORD
  // ─────────────────────────────────────────────────────────────────────────

  void _showForgotPassword() {
    final emailCtrl = TextEditingController(
      text: _emailController.text.trim(),
    );

    showDialog(
      context: context,
      builder: (dialogCtx) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16.r)),
        title: const Text('Reset Password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
                'Enter your email and we will send you a reset link.'),
            SizedBox(height: 16.h),
            TextField(
              controller: emailCtrl,
              keyboardType: TextInputType.emailAddress,
              autofocus: true,
              decoration: InputDecoration(
                labelText: 'Email Address',
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10.r)),
                prefixIcon: const Icon(Icons.email_outlined),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogCtx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              final email = emailCtrl.text.trim();
              if (email.isEmpty || !email.contains('@')) return;
              Navigator.pop(dialogCtx);
              context
                  .read<AuthBloc>()
                  .add(ResetPassword(email: email));
            },
            child: const Text('Send Link'),
          ),
        ],
      ),
    );
  }
}
