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

    setState(() => _isLoading = true);

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
      // FIX 1 - clear errors when switching between login/register
      _formKey.currentState?.reset();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<AuthBloc, AuthState>(
        listener: (context, state) {
          if (state is AuthLoading) {
            // FIX 2 - sync loading state with bloc
            if (!_isLoading) setState(() => _isLoading = true);
          } else if (state is AuthError) {
            setState(() => _isLoading = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: Colors.red.shade700,
                behavior: SnackBarBehavior.floating,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12.r),
                ),
                margin: EdgeInsets.all(16.w),
                duration: const Duration(seconds: 4),
              ),
            );
          } else if (state is Authenticated) {
            setState(() => _isLoading = false);
            // FIX 3 - KEY FIX: use addPostFrameCallback so navigation fires
            // AFTER the current build cycle completes — this stops the blank screen bug
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                Navigator.of(context).pushReplacementNamed('/home');
              }
            });
          }
        },
        child: Container(
          // FIX 4 - wrap in gradient container so background looks good
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
                                AppTheme.primaryColor.withOpacity(0.8),
                                const Color(0xFF8B5CF6),
                              ],
                            ),
                            borderRadius: BorderRadius.circular(28.r),
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.primaryColor.withOpacity(0.3),
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

                        // App Name
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

                        // Title
                        AnimatedSwitcher(
                          duration: const Duration(milliseconds: 300),
                          child: Text(
                            _isLogin ? 'Welcome Back!' : 'Create Account',
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
                          style:
                              Theme.of(context).textTheme.bodyMedium?.copyWith(
                                    color: Colors.white.withOpacity(0.7),
                                    fontSize: 14.sp,
                                  ),
                          textAlign: TextAlign.center,
                        ),

                        SizedBox(height: 40.h),

                        // Form
                        Container(
                          padding: EdgeInsets.all(24.w),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.05),
                            borderRadius: BorderRadius.circular(20.r),
                            border: Border.all(
                              color: Colors.white.withOpacity(0.1),
                            ),
                          ),
                          child: Form(
                            key: _formKey,
                            child: Column(
                              children: [
                                CustomTextField(
                                  controller: _emailController,
                                  label: 'Email Address',
                                  hint: 'name@example.com',
                                  keyboardType: TextInputType.emailAddress,
                                  prefixIcon: Icons.email_outlined,
                                  // FIX 5 - disable fields while loading
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

                                CustomTextField(
                                  controller: _passwordController,
                                  label: 'Password',
                                  hint: _isLogin
                                      ? 'Your password'
                                      : 'Min 8 characters',
                                  obscureText: true,
                                  prefixIcon: Icons.lock_outline_rounded,
                                  enabled: !_isLoading,
                                  validator: (value) {
                                    if (value?.isEmpty ?? true) {
                                      return 'Please enter your password';
                                    }
                                    if (!_isLogin && value!.length < 8) {
                                      return 'Password must be at least 8 characters';
                                    }
                                    if (_isLogin && value!.length < 6) {
                                      return 'Password too short';
                                    }
                                    return null;
                                  },
                                ),

                                // FIX 6 - show forgot password on login mode
                                if (_isLogin) ...[
                                  SizedBox(height: 8.h),
                                  Align(
                                    alignment: Alignment.centerRight,
                                    child: TextButton(
                                      onPressed: _isLoading
                                          ? null
                                          : _showForgotPassword,
                                      child: Text(
                                        'Forgot Password?',
                                        style: TextStyle(
                                          color: AppTheme.primaryColor,
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

                        // Submit Button
                        CustomButton(
                          text: _isLogin ? 'Sign In' : 'Create Account',
                          onPressed: _isLoading ? null : _submit,
                          isLoading: _isLoading,
                        ),

                        SizedBox(height: 20.h),

                        // Toggle Mode
                        TextButton(
                          onPressed: _isLoading ? null : _toggleMode,
                          style: TextButton.styleFrom(
                            padding: EdgeInsets.symmetric(
                                horizontal: 16.w, vertical: 8.h),
                          ),
                          child: RichText(
                            text: TextSpan(
                              text: _isLogin
                                  ? "Don't have an account? "
                                  : "Already have an account? ",
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.7),
                                fontSize: 14.sp,
                              ),
                              children: [
                                TextSpan(
                                  text: _isLogin ? 'Sign Up' : 'Sign In',
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

                // Footer
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
                        margin: EdgeInsets.symmetric(horizontal: 40.w),
                        height: 1,
                        color: Colors.white.withOpacity(0.1),
                      ),
                      SizedBox(height: 16.h),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            'Made with ',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 12.sp,
                            ),
                          ),
                          Icon(
                            Icons.favorite,
                            color: Colors.red.shade400,
                            size: 14.sp,
                          ),
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

  // FIX 7 - implemented forgot password dialog
  void _showForgotPassword() {
    final emailController = TextEditingController(
      text: _emailController.text,
    );
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset Password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Enter your email and we will send you a reset link.',
            ),
            SizedBox(height: 16.h),
            TextField(
              controller: emailController,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(
                labelText: 'Email Address',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<AuthBloc>().add(
                    ResetPassword(email: emailController.text.trim()),
                  );
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('✅ Password reset link sent to your email!'),
                ),
              );
            },
            child: const Text('Send Link'),
          ),
        ],
      ),
    );
  }
}
