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

class ResetPassword extends AuthEvent {
  final String email;
  const ResetPassword({required this.email});
  @override
  List<Object?> get props => [email];
}

class LoginWithGoogle extends AuthEvent {}

class UpdateUser extends AuthEvent {
  final User user;
  const UpdateUser({required this.user});
  @override
  List<Object?> get props => [user];
}

class RefreshUser extends AuthEvent {}

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

// FIX 1 — PasswordResetSent now EXTENDS Unauthenticated so app.dart's
// BlocBuilder treats it like Unauthenticated and keeps LoginScreen visible.
// Previously it fell through to the default `return SplashScreen()` case
// and the app got stuck on a blank splash screen after reset.
class PasswordResetSent extends Unauthenticated {
  final String email;
  PasswordResetSent({required this.email});
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
    on<ResetPassword>(_onResetPassword);
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
          // Token exists but user fetch failed — force clean logout
          await authService.signOut();
          emit(Unauthenticated());
        }
      } else {
        emit(Unauthenticated());
      }
    } catch (e) {
      // FIX 2 — never stay stuck on AuthLoading if AppStarted throws
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
      // FIX 3 — emit Authenticated directly; app.dart BlocBuilder handles
      // the navigation to HomeScreen automatically. Do NOT navigate manually
      // in login_screen.dart — that causes a double navigation bug.
      emit(Authenticated(user: user));
    } catch (e) {
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

  // ── Reset password ─────────────────────────────────────────────────────────

  Future<void> _onResetPassword(
    ResetPassword event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());
    try {
      await authService.resetPassword(event.email);
      // FIX 1 — PasswordResetSent extends Unauthenticated so LoginScreen
      // stays visible. The BlocListener in login_screen.dart catches this
      // state and shows the "check your email" snackbar.
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
      // FIX 4 — always reach Unauthenticated even if API signOut fails
      // so user is never stuck on loading screen
    } finally {
      emit(Unauthenticated());
    }
  }

  // ── Update user ────────────────────────────────────────────────────────────

  Future<void> _onUpdateUser(
    UpdateUser event,
    Emitter<AuthState> emit,
  ) async {
    // FIX 5 — only update if currently authenticated, never downgrade state
    if (state is Authenticated) {
      emit(Authenticated(user: event.user));
    }
  }

  // ── Refresh user ───────────────────────────────────────────────────────────

  Future<void> _onRefreshUser(
    RefreshUser event,
    Emitter<AuthState> emit,
  ) async {
    final current = state;
    try {
      final user = await authService.getCurrentUser();
      if (user != null) {
        emit(Authenticated(user: user));
      } else {
        // FIX 6 — if refresh returns null, restore previous state
        // rather than silently doing nothing
        emit(current);
      }
    } catch (_) {
      emit(current);
    }
  }

  // ── Clear error ────────────────────────────────────────────────────────────

  Future<void> _onClearAuthError(
    ClearAuthError event,
    Emitter<AuthState> emit,
  ) async {
    // FIX 7 — also clear PasswordResetSent state (extends Unauthenticated)
    if (state is AuthError || state is PasswordResetSent) {
      emit(Unauthenticated());
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  String _cleanError(Object e) {
    final raw = e.toString().toLowerCase();

    if ((raw.contains('invalid') && raw.contains('credential')) ||
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
    if (raw.contains('too many') ||
        raw.contains('rate limit') ||
        raw.contains('429')) {
      return 'Too many attempts. Please wait a moment and try again.';
    }
    if (raw.contains('weak password') ||
        raw.contains('password too short')) {
      return 'Password must be at least 8 characters.';
    }
    if (raw.contains('invalid email') ||
        raw.contains('email format')) {
      return 'Please enter a valid email address.';
    }
    if (raw.contains('500') || raw.contains('server error')) {
      return 'Server error. Please try again in a moment.';
    }

    return 'Something went wrong. Please try again.';
  }
}
