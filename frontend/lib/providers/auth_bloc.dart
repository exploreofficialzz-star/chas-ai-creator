import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../models/user.dart';
import '../services/auth_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// EVENTS
// ─────────────────────────────────────────────────────────────────────────────

abstract class AuthEvent extends Equatable {
  const AuthEvent();
  @override
  List<Object?> get props => [];
}

class AppStarted extends AuthEvent {}

class LoggedIn extends AuthEvent {
  final User user;
  const LoggedIn({required this.user});
  @override
  List<Object?> get props => [user];
}

class LoggedOut extends AuthEvent {}

class LoginWithEmail extends AuthEvent {
  final String email;
  final String password;
  const LoginWithEmail({required this.email, required this.password});
  @override
  List<Object?> get props => [email, password];
}

class RegisterWithEmail extends AuthEvent {
  final String email;
  final String password;
  final String? displayName;
  const RegisterWithEmail({
    required this.email,
    required this.password,
    this.displayName,
  });
  @override
  List<Object?> get props => [email, password, displayName];
}

// FIX 1 — was missing entirely, caused build error in login_screen.dart
class ResetPassword extends AuthEvent {
  final String email;
  const ResetPassword({required this.email});
  @override
  List<Object?> get props => [email];
}

// FIX 2 — removed LoginWithApple (app uses custom JWT, no Apple Sign In)
// Kept Google as optional social login
class LoginWithGoogle extends AuthEvent {}

// New — update user profile after edit
class UpdateUser extends AuthEvent {
  final User user;
  const UpdateUser({required this.user});
  @override
  List<Object?> get props => [user];
}

// New — refresh user from backend (credits changed, tier upgraded etc.)
class RefreshUser extends AuthEvent {}

// New — clear auth error without triggering full reload
class ClearAuthError extends AuthEvent {}

// ─────────────────────────────────────────────────────────────────────────────
// STATES
// ─────────────────────────────────────────────────────────────────────────────

abstract class AuthState extends Equatable {
  const AuthState();
  @override
  List<Object?> get props => [];
}

class AuthInitial extends AuthState {}

class AuthLoading extends AuthState {}

class Authenticated extends AuthState {
  final User user;
  const Authenticated({required this.user});
  @override
  List<Object?> get props => [user];
}

class Unauthenticated extends AuthState {}

class AuthError extends AuthState {
  final String message;
  const AuthError({required this.message});
  @override
  List<Object?> get props => [message];
}

// FIX 3 — dedicated state so UI can show "check your email" message
// without getting confused with AuthError
class PasswordResetSent extends AuthState {
  final String email;
  const PasswordResetSent({required this.email});
  @override
  List<Object?> get props => [email];
}

// ─────────────────────────────────────────────────────────────────────────────
// BLOC
// ─────────────────────────────────────────────────────────────────────────────

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final AuthService authService;

  AuthBloc({required this.authService}) : super(AuthInitial()) {
    on<AppStarted>(_onAppStarted);
    on<LoginWithEmail>(_onLoginWithEmail);
    on<RegisterWithEmail>(_onRegisterWithEmail);
    on<LoginWithGoogle>(_onLoginWithGoogle);
    on<LoggedIn>(_onLoggedIn);
    on<LoggedOut>(_onLoggedOut);
    on<ResetPassword>(_onResetPassword);   // FIX 1
    on<UpdateUser>(_onUpdateUser);
    on<RefreshUser>(_onRefreshUser);
    on<ClearAuthError>(_onClearAuthError);
  }

  // ── App started ────────────────────────────────────────────────────────────

  Future<void> _onAppStarted(
    AppStarted event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      final isSignedIn = await authService.isSignedIn();
      if (isSignedIn) {
        final user = await authService.getCurrentUser();
        if (user != null) {
          emit(Authenticated(user: user));
        } else {
          // FIX 4 — token exists but user fetch failed → force logout
          await authService.signOut();
          emit(Unauthenticated());
        }
      } else {
        emit(Unauthenticated());
      }
    } catch (e) {
      emit(Unauthenticated());
    }
  }

  // ── Login ──────────────────────────────────────────────────────────────────

  Future<void> _onLoginWithEmail(
    LoginWithEmail event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      final user = await authService.signInWithEmail(
        event.email,
        event.password,
      );
      emit(Authenticated(user: user));
    } catch (e) {
      // FIX 5 — clean error messages, don't expose raw exceptions
      emit(AuthError(message: _cleanError(e)));
    }
  }

  // ── Register ───────────────────────────────────────────────────────────────

  Future<void> _onRegisterWithEmail(
    RegisterWithEmail event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      final user = await authService.registerWithEmail(
        event.email,
        event.password,
        displayName: event.displayName,
      );
      emit(Authenticated(user: user));
    } catch (e) {
      emit(AuthError(message: _cleanError(e)));
    }
  }

  // ── Google login ───────────────────────────────────────────────────────────

  Future<void> _onLoginWithGoogle(
    LoginWithGoogle event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      final user = await authService.signInWithGoogle();
      emit(Authenticated(user: user));
    } catch (e) {
      emit(AuthError(message: _cleanError(e)));
    }
  }

  // ── Reset password — FIX 1 ────────────────────────────────────────────────

  Future<void> _onResetPassword(
    ResetPassword event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      await authService.resetPassword(event.email);
      // FIX 3 — emit dedicated state, not generic AuthError
      emit(PasswordResetSent(email: event.email));
    } catch (e) {
      emit(AuthError(message: _cleanError(e)));
    }
  }

  // ── Logged in directly ─────────────────────────────────────────────────────

  Future<void> _onLoggedIn(
    LoggedIn event,
    Emitter<AuthState> emit,
  ) async {
    emit(Authenticated(user: event.user));
  }

  // ── Logout ─────────────────────────────────────────────────────────────────

  Future<void> _onLoggedOut(
    LoggedOut event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      await authService.signOut();
    } catch (_) {
      // FIX 6 — always emit Unauthenticated even if signOut API fails
      // so the user is never stuck on a loading screen
    } finally {
      emit(Unauthenticated());
    }
  }

  // ── Update user ────────────────────────────────────────────────────────────

  Future<void> _onUpdateUser(
    UpdateUser event,
    Emitter<AuthState> emit,
  ) async {
    // FIX 7 — update user in state without full reload
    // Used after profile edit, credit change, tier upgrade
    if (state is Authenticated) {
      emit(Authenticated(user: event.user));
    }
  }

  // ── Refresh user ───────────────────────────────────────────────────────────

  Future<void> _onRefreshUser(
    RefreshUser event,
    Emitter<AuthState> emit,
  ) async {
    // Keep current state visible while refreshing
    final current = state;
    try {
      final user = await authService.getCurrentUser();
      if (user != null) {
        emit(Authenticated(user: user));
      }
    } catch (_) {
      // Silently fail — keep current state
      emit(current);
    }
  }

  // ── Clear error ────────────────────────────────────────────────────────────

  Future<void> _onClearAuthError(
    ClearAuthError event,
    Emitter<AuthState> emit,
  ) async {
    if (state is AuthError) {
      emit(Unauthenticated());
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  // FIX 5 — map raw exceptions to user-friendly messages
  String _cleanError(Object e) {
    final raw = e.toString().toLowerCase();

    if (raw.contains('invalid') && raw.contains('credential') ||
        raw.contains('wrong password') ||
        raw.contains('incorrect password')) {
      return 'Incorrect email or password. Please try again.';
    }
    if (raw.contains('user not found') ||
        raw.contains('no user') ||
        raw.contains('404')) {
      return 'No account found with this email.';
    }
    if (raw.contains('email already') ||
        raw.contains('already registered') ||
        raw.contains('already exists') ||
        raw.contains('409')) {
      return 'An account with this email already exists.';
    }
    if (raw.contains('network') ||
        raw.contains('socket') ||
        raw.contains('connection') ||
        raw.contains('timeout')) {
      return 'Network error. Please check your connection.';
    }
    if (raw.contains('too many') || raw.contains('rate limit') ||
        raw.contains('429')) {
      return 'Too many attempts. Please wait a moment and try again.';
    }
    if (raw.contains('weak password') || raw.contains('password too short')) {
      return 'Password must be at least 8 characters.';
    }
    if (raw.contains('invalid email') || raw.contains('email format')) {
      return 'Please enter a valid email address.';
    }
    if (raw.contains('500') || raw.contains('server error')) {
      return 'Server error. Please try again in a moment.';
    }

    // Last resort — don't expose raw Dart/HTTP error text
    return 'Something went wrong. Please try again.';
  }
}
