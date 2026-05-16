export type AuthMode = "signin" | "signup";

export interface AuthFieldError {
  email?: string;
  password?: string;
}

export interface AuthUser {
  id: number;
  email: string;
  createdAt: string;
  lastLoginAt: string | null;
}
