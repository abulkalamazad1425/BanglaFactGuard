// ============================================================
// User & Auth Models
// ============================================================

export type UserRole = 'user' | 'expert' | 'admin';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  // Auth tokens (only present after login/register)
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UserProfile {
  id: string;
  full_name: string | null;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  is_email_verified: boolean;
  avatar_url: string | null;
  phone: string | null;
  total_submissions: number;
  bio: string | null;
  verification_count: number;
}

export interface UpdateProfileRequest {
  full_name?: string;
  bio?: string;
  avatar_url?: string;
  phone?: string;
}
