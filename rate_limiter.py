# rate_limiter.py - Protect Against Cost Overruns
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict
import time

class RateLimiter:
    """
    Rate limiter to enforce usage limits and prevent cost abuse
    
    Features:
    - Guest mode: 5 translations per session
    - Free tier: 50 translations per day
    - Paid tier: Unlimited
    - Video: Auth required
    """
    
    def __init__(self):
        # Store usage data
        # Key: user_id or session_id
        # Value: {translations: int, video_minutes: int, last_reset: datetime}
        self.usage_data = defaultdict(lambda: {
            'translations': 0,
            'video_minutes': 0,
            'last_reset': datetime.now(),
            'first_seen': datetime.now()
        })
        
        # Session data for guests (no auth)
        # Key: session_id
        # Value: {messages: int, created_at: datetime}
        self.guest_sessions = defaultdict(lambda: {
            'messages': 0,
            'created_at': datetime.now()
        })
        
        # User tier limits
        self.LIMITS = {
            'guest': {
                'translations_per_session': 5,
                'video_enabled': False,
                'session_duration_minutes': 30
            },
            'free': {
                'translations_per_day': 50,
                'video_minutes_per_day': 10,
                'max_room_participants': 2
            },
            'paid': {
                'translations_per_day': 999999,  # Unlimited
                'video_minutes_per_day': 999999,
                'max_room_participants': 10
            }
        }
    
    def check_guest_limit(self, session_id: str) -> Dict:
        """
        Check if guest session is within limits
        
        Args:
            session_id: Guest session identifier
            
        Returns:
            dict with allowed: bool, remaining: int, message: str
        """
        session = self.guest_sessions[session_id]
        limit = self.LIMITS['guest']['translations_per_session']
        
        # Check session age (expire after 30 minutes)
        session_age = datetime.now() - session['created_at']
        if session_age > timedelta(minutes=30):
            # Reset session
            session['messages'] = 0
            session['created_at'] = datetime.now()
        
        # Check message limit
        if session['messages'] >= limit:
            return {
                'allowed': False,
                'remaining': 0,
                'limit': limit,
                'message': f"Guest limit reached ({limit} messages). Sign up for unlimited translations!",
                'upgrade_required': True
            }
        
        # Increment and allow
        session['messages'] += 1
        remaining = limit - session['messages']
        
        return {
            'allowed': True,
            'remaining': remaining,
            'limit': limit,
            'message': f"{remaining} messages remaining in guest mode" if remaining <= 2 else "OK",
            'upgrade_required': False
        }
    
    def check_translation_limit(
        self, 
        user_id: str, 
        user_tier: str = 'free'
    ) -> Dict:
        """
        Check if user is within translation limits
        
        Args:
            user_id: User identifier
            user_tier: 'free' or 'paid'
            
        Returns:
            dict with allowed: bool, remaining: int, message: str
        """
        if user_tier not in ['free', 'paid']:
            user_tier = 'free'
        
        # Paid users have unlimited
        if user_tier == 'paid':
            return {
                'allowed': True,
                'remaining': 999999,
                'limit': 999999,
                'message': 'Unlimited (Pro plan)',
                'upgrade_required': False
            }
        
        # Check free tier limits
        user = self.usage_data[user_id]
        limit = self.LIMITS['free']['translations_per_day']
        
        # Reset daily at midnight
        now = datetime.now()
        time_since_reset = now - user['last_reset']
        
        if time_since_reset > timedelta(days=1):
            user['translations'] = 0
            user['last_reset'] = now
        
        # Check limit
        if user['translations'] >= limit:
            return {
                'allowed': False,
                'remaining': 0,
                'limit': limit,
                'message': f"Daily limit reached ({limit} translations). Upgrade to Pro for unlimited!",
                'upgrade_required': True,
                'reset_at': (user['last_reset'] + timedelta(days=1)).isoformat()
            }
        
        # Increment and allow
        user['translations'] += 1
        remaining = limit - user['translations']
        
        return {
            'allowed': True,
            'remaining': remaining,
            'limit': limit,
            'message': f"{remaining} translations remaining today" if remaining <= 10 else "OK",
            'upgrade_required': False
        }
    
    def check_video_access(
        self, 
        user_id: Optional[str], 
        user_tier: str = 'free'
    ) -> Dict:
        """
        Check if user can access video chat
        
        Args:
            user_id: User identifier (None for guests)
            user_tier: 'free' or 'paid'
            
        Returns:
            dict with allowed: bool, message: str
        """
        # Guests cannot use video
        if not user_id:
            return {
                'allowed': False,
                'message': 'Video chat requires an account. Sign up free!',
                'auth_required': True
            }
        
        # Check video minute limits
        user = self.usage_data[user_id]
        
        if user_tier == 'paid':
            return {
                'allowed': True,
                'remaining_minutes': 999999,
                'message': 'Unlimited video (Pro plan)'
            }
        
        # Free tier video limits
        limit = self.LIMITS['free']['video_minutes_per_day']
        
        # Reset daily
        now = datetime.now()
        time_since_reset = now - user['last_reset']
        
        if time_since_reset > timedelta(days=1):
            user['video_minutes'] = 0
            user['last_reset'] = now
        
        if user['video_minutes'] >= limit:
            return {
                'allowed': False,
                'remaining_minutes': 0,
                'message': f"Daily video limit reached ({limit} minutes). Upgrade to Pro!",
                'upgrade_required': True,
                'reset_at': (user['last_reset'] + timedelta(days=1)).isoformat()
            }
        
        return {
            'allowed': True,
            'remaining_minutes': limit - user['video_minutes'],
            'message': 'OK'
        }
    
    def record_video_usage(self, user_id: str, minutes: float):
        """Record video minutes used"""
        user = self.usage_data[user_id]
        user['video_minutes'] += minutes
    
    def get_usage_stats(self, user_id: str, user_tier: str = 'free') -> Dict:
        """Get user's current usage statistics"""
        user = self.usage_data[user_id]
        limits = self.LIMITS[user_tier]
        
        # Calculate time until reset
        next_reset = user['last_reset'] + timedelta(days=1)
        hours_until_reset = (next_reset - datetime.now()).total_seconds() / 3600
        
        return {
            'tier': user_tier,
            'translations': {
                'used': user['translations'],
                'limit': limits['translations_per_day'],
                'remaining': max(0, limits['translations_per_day'] - user['translations'])
            },
            'video': {
                'used_minutes': user['video_minutes'],
                'limit_minutes': limits['video_minutes_per_day'],
                'remaining_minutes': max(0, limits['video_minutes_per_day'] - user['video_minutes'])
            },
            'reset_in_hours': max(0, hours_until_reset),
            'next_reset': next_reset.isoformat()
        }
    
    def cleanup_old_sessions(self):
        """Clean up expired guest sessions (run periodically)"""
        now = datetime.now()
        expired = []
        
        for session_id, data in self.guest_sessions.items():
            age = now - data['created_at']
            if age > timedelta(hours=1):
                expired.append(session_id)
        
        for session_id in expired:
            del self.guest_sessions[session_id]
        
        print(f"🗑️ Cleaned up {len(expired)} expired guest sessions")
        
        return len(expired)
    
    def get_all_stats(self) -> Dict:
        """Get global statistics"""
        total_guests = len(self.guest_sessions)
        total_users = len(self.usage_data)
        
        total_translations = sum(u['translations'] for u in self.usage_data.values())
        total_video_minutes = sum(u['video_minutes'] for u in self.usage_data.values())
        
        return {
            'active_guests': total_guests,
            'registered_users': total_users,
            'total_translations_today': total_translations,
            'total_video_minutes_today': total_video_minutes,
            'estimated_daily_cost': {
                'azure': round(total_translations * 100 / 1_000_000 * 10, 2),  # $10 per 1M chars
                'daily': round(total_video_minutes * 0.0016, 2)  # $0.0016 per minute
            }
        }