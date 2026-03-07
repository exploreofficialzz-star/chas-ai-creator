import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../config/theme.dart';
import '../../providers/auth_bloc.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_text_field.dart';
import '../../widgets/social_button.dart';

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
    if (_formKey.currentState?.validate() ?? false) {
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
  }

  void _toggleMode() {
    setState(() => _isLogin = !_isLogin);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<AuthBloc, AuthState>(
        listener: (context, state) {
          if (state is AuthError) {
            setState(() => _isLoading = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message)),
            );
          }
        },
        child: SafeArea(
          child: SingleChildScrollView(
            padding: EdgeInsets.all(24.w),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(height: 40.h),
                
                // Logo
                Container(
                  width: 100.w,
                  height: 100.w,
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(24.r),
                  ),
                  child: Icon(
                    Icons.videocam,
                    size: 48.w,
                    color: Colors.white,
                  ),
                ),
                
                SizedBox(height: 32.h),
                
                // Title
                Text(
                  _isLogin ? 'Welcome Back!' : 'Create Account',
                  style: Theme.of(context).textTheme.headlineMedium,
                  textAlign: TextAlign.center,
                ),
                
                SizedBox(height: 8.h),
                
                Text(
                  _isLogin
                      ? 'Sign in to continue creating amazing videos'
                      : 'Start your AI video creation journey',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTheme.textSecondaryLight,
                  ),
                  textAlign: TextAlign.center,
                ),
                
                SizedBox(height: 40.h),
                
                // Form
                Form(
                  key: _formKey,
                  child: Column(
                    children: [
                      CustomTextField(
                        controller: _emailController,
                        label: 'Email',
                        hint: 'Enter your email',
                        keyboardType: TextInputType.emailAddress,
                        prefixIcon: Icons.email_outlined,
                        validator: (value) {
                          if (value?.isEmpty ?? true) {
                            return 'Please enter your email';
                          }
                          if (!value!.contains('@')) {
                            return 'Please enter a valid email';
                          }
                          return null;
                        },
                      ),
                      
                      SizedBox(height: 16.h),
                      
                      CustomTextField(
                        controller: _passwordController,
                        label: 'Password',
                        hint: 'Enter your password',
                        obscureText: true,
                        prefixIcon: Icons.lock_outlined,
                        validator: (value) {
                          if (value?.isEmpty ?? true) {
                            return 'Please enter your password';
                          }
                          if (value!.length < 6) {
                            return 'Password must be at least 6 characters';
                          }
                          return null;
                        },
                      ),
                    ],
                  ),
                ),
                
                SizedBox(height: 24.h),
                
                // Submit Button
                CustomButton(
                  text: _isLogin ? 'Sign In' : 'Create Account',
                  onPressed: _submit,
                  isLoading: _isLoading,
                ),
                
                SizedBox(height: 16.h),
                
                // Toggle Mode
                TextButton(
                  onPressed: _toggleMode,
                  child: Text(
                    _isLogin
                        ? "Don't have an account? Sign Up"
                        : 'Already have an account? Sign In',
                  ),
                ),
                
                SizedBox(height: 24.h),
                
                // Divider
                Row(
                  children: [
                    Expanded(child: Divider()),
                    Padding(
                      padding: EdgeInsets.symmetric(horizontal: 16.w),
                      child: Text(
                        'OR',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    Expanded(child: Divider()),
                  ],
                ),
                
                SizedBox(height: 24.h),
                
                // Social Login
                SocialButton(
                  text: 'Continue with Google',
                  icon: 'assets/icons/google.svg',
                  onPressed: () {
                    context.read<AuthBloc>().add(LoginWithGoogle());
                  },
                ),
                
                SizedBox(height: 12.h),
                
                SocialButton(
                  text: 'Continue with Apple',
                  icon: 'assets/icons/apple.svg',
                  onPressed: () {
                    context.read<AuthBloc>().add(LoginWithApple());
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
