# auth_service.py - Supabase Authentication
import os
from typing import Optional, Dict
from supabase import create_client, Client
import jwt
from datetime import datetime, timedelta

class AuthService:
    """Handles user authentication with Supabase"""
    
    def __init__(self):
        """Initialize Supabase client"""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("⚠️  SUPABASE credentials not set - authentication disabled")
            self.supabase: Optional[Client] = None
            self.enabled = False
        else:
            self.supabase = create_client(supabase_url, supabase_key)
            self.enabled = True
            print("✅ Supabase authentication initialized")
    
    async def sign_up(self, email: str, password: str, name: str) -> Dict:
        """
        Register a new user
        
        Args:
            email: User email
            password: User password (min 6 chars)
            name: User display name
            
        Returns:
            dict with status, user data, or error
        """
        if not self.enabled:
            return {
                "status": "error",
                "error": "Authentication not configured"
            }
        
        try:
            # Sign up user with Supabase Auth
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "created_at": datetime.now().isoformat()
                    }
                }
            })
            
            if response.user:
                print(f"✅ New user registered: {email}")
                return {
                    "status": "success",
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "name": name
                    },
                    "session": {
                        "access_token": response.session.access_token if response.session else None,
                        "refresh_token": response.session.refresh_token if response.session else None
                    },
                    "message": "Account created! Check your email to verify."
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to create account"
                }
        
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Sign up error: {error_msg}")
            
            # Handle common errors
            if "already registered" in error_msg.lower():
                return {
                    "status": "error",
                    "error": "Email already registered"
                }
            elif "invalid email" in error_msg.lower():
                return {
                    "status": "error",
                    "error": "Invalid email format"
                }
            elif "password" in error_msg.lower():
                return {
                    "status": "error",
                    "error": "Password must be at least 6 characters"
                }
            else:
                return {
                    "status": "error",
                    "error": "Registration failed. Please try again."
                }
    
    async def sign_in(self, email: str, password: str) -> Dict:
        """
        Sign in existing user
        
        Args:
            email: User email
            password: User password
            
        Returns:
            dict with status, user data, session tokens, or error
        """
        if not self.enabled:
            return {
                "status": "error",
                "error": "Authentication not configured"
            }
        
        try:
            # Sign in with Supabase
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Get user metadata
                user_metadata = response.user.user_metadata or {}
                name = user_metadata.get("name", email.split("@")[0])
                
                print(f"✅ User signed in: {email}")
                
                return {
                    "status": "success",
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "name": name
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at
                    },
                    "message": "Signed in successfully!"
                }
            else:
                return {
                    "status": "error",
                    "error": "Invalid credentials"
                }
        
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Sign in error: {error_msg}")
            
            if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
                return {
                    "status": "error",
                    "error": "Invalid email or password"
                }
            else:
                return {
                    "status": "error",
                    "error": "Sign in failed. Please try again."
                }
    
    async def sign_out(self, access_token: str) -> Dict:
        """
        Sign out user
        
        Args:
            access_token: User's access token
            
        Returns:
            dict with status
        """
        if not self.enabled:
            return {
                "status": "error",
                "error": "Authentication not configured"
            }
        
        try:
            # Set the session
            self.supabase.auth.set_session(access_token, access_token)
            
            # Sign out
            self.supabase.auth.sign_out()
            
            print(f"✅ User signed out")
            
            return {
                "status": "success",
                "message": "Signed out successfully"
            }
        
        except Exception as e:
            print(f"❌ Sign out error: {e}")
            return {
                "status": "error",
                "error": "Sign out failed"
            }
    
    async def verify_token(self, access_token: str) -> Optional[Dict]:
        """
        Verify access token and return user data
        
        Args:
            access_token: JWT access token
            
        Returns:
            User data dict or None if invalid
        """
        if not self.enabled:
            return None
        
        try:
            # Get user from token
            response = self.supabase.auth.get_user(access_token)
            
            if response.user:
                user_metadata = response.user.user_metadata or {}
                name = user_metadata.get("name", response.user.email.split("@")[0])
                
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": name
                }
            else:
                return None
        
        except Exception as e:
            print(f"❌ Token verification error: {e}")
            return None
    
    async def refresh_session(self, refresh_token: str) -> Dict:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            dict with new session or error
        """
        if not self.enabled:
            return {
                "status": "error",
                "error": "Authentication not configured"
            }
        
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            
            if response.session:
                return {
                    "status": "success",
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at
                    }
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to refresh session"
                }
        
        except Exception as e:
            print(f"❌ Token refresh error: {e}")
            return {
                "status": "error",
                "error": "Session expired. Please sign in again."
            }
    
    async def update_profile(self, access_token: str, name: str) -> Dict:
        """
        Update user profile
        
        Args:
            access_token: User's access token
            name: New display name
            
        Returns:
            dict with status
        """
        if not self.enabled:
            return {
                "status": "error",
                "error": "Authentication not configured"
            }
        
        try:
            # Set the session
            self.supabase.auth.set_session(access_token, access_token)
            
            # Update user metadata
            response = self.supabase.auth.update_user({
                "data": {
                    "name": name
                }
            })
            
            if response.user:
                print(f"✅ Profile updated for user")
                return {
                    "status": "success",
                    "message": "Profile updated successfully"
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to update profile"
                }
        
        except Exception as e:
            print(f"❌ Profile update error: {e}")
            return {
                "status": "error",
                "error": "Failed to update profile"
            }
    
    async def reset_password_request(self, email: str) -> Dict:
        """
        Request password reset email
        
        Args:
            email: User email
            
        Returns:
            dict with status
        """
        if not self.enabled:
            return {
                "status": "error",
                "error": "Authentication not configured"
            }
        
        try:
            self.supabase.auth.reset_password_email(email)
            
            return {
                "status": "success",
                "message": "Password reset email sent! Check your inbox."
            }
        
        except Exception as e:
            print(f"❌ Password reset request error: {e}")
            # Don't reveal if email exists
            return {
                "status": "success",
                "message": "If that email exists, a reset link was sent."
            }