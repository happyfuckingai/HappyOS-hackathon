"""
🔐 SÄKERHETSSYSTEM - SKYDDAR HAPPYOS OCH ANVÄNDARDATA

Vad gör den här filen?
- Hanterar användarautentisering (inloggning)
- Skyddar mot attacker och missbruk
- Krypterar känslig data
- Begränsar hur ofta någon kan använda systemet (rate limiting)

Varför behövs detta?
- Skyddar användarnas data från obehöriga
- Förhindrar att systemet överbelastas
- Gör systemet säkert nog för produktion
- Följer säkerhetsstandarder
"""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import wraps
import asyncio
import logging
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Depends, Header, WebSocket, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from app.config.settings import get_settings
from app.core.utils.error_handler import HappyOSError, ValidationError

logger = logging.getLogger(__name__)
settings = get_settings()

# Kryptografi-inställningar
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class SecurityManager:
    """
    Huvudklass för säkerhetshantering.
    
    Hanterar allt från lösenordskryptering till API-nycklar.
    """
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or settings.security.secret_key
        self.algorithm = settings.security.jwt_algorithm
        self.access_token_expire_minutes = settings.security.access_token_expire_minutes
        self._api_key_store: Dict[str, Dict[str, Any]] = {}
    
    def _add_api_key_to_store(self, api_key: str, user_id: str, name: str, permissions: Optional[List[str]] = None):
        """
        Internal method to store API key details.
        """
        self._api_key_store[api_key] = {
            "user_id": user_id,
            "name": name,
            "permissions": permissions or [],
            "created_at": datetime.utcnow(),
            "is_active": True
        }

    def hash_password(self, password: str) -> str:
        """
        Krypterar ett lösenord säkert.
        
        Args:
            password: Lösenordet i klartext
        
        Returns:
            Krypterat lösenord
        """
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifierar att ett lösenord är korrekt.
        
        Args:
            plain_password: Lösenordet användaren skrev
            hashed_password: Det krypterade lösenordet från databasen
        
        Returns:
            True om lösenordet är korrekt
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Skapar en säker åtkomsttoken (JWT).
        
        Args:
            data: Data som ska inkluderas i token (t.ex. användar-ID)
            expires_delta: Hur länge token ska vara giltig
        
        Returns:
            JWT-token som sträng
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verifierar och dekoderar en åtkomsttoken.
        
        Args:
            token: JWT-token att verifiera
        
        Returns:
            Dekodad token-data
        
        Raises:
            ValidationError: Om token är ogiltig eller utgången
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValidationError("Token har gått ut", error_code="TOKEN_EXPIRED")
        except jwt.PyJWTError as e:
            raise ValidationError(f"Ogiltig token: {e}", error_code="INVALID_TOKEN")
    
    def generate_api_key(self, user_id: str, name: str = "default", permissions: Optional[List[str]] = None) -> str:
        """
        Genererar en säker API-nyckel för en användare.
        
        Args:
            user_id: Användarens ID
            name: Namn på API-nyckeln (för identifiering)
            permissions: Lista med behörigheter för nyckeln
        
        Returns:
            Säker API-nyckel
        """
        # Skapa en unik nyckel baserad på användar-ID, namn och slumpmässig data
        random_data = secrets.token_urlsafe(32)
        key_data = f"{user_id}:{name}:{random_data}:{datetime.utcnow().isoformat()}"
        
        # Hasha för säkerhet
        hashed_key_part = hashlib.sha256(key_data.encode()).hexdigest()

        api_key = f"hpos_{hashed_key_part[:32]}"  # HappyOS prefix + första 32 tecken
        
        self._add_api_key_to_store(api_key, user_id, name, permissions)
        return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validerar en API-nyckel.
        
        Args:
            api_key: API-nyckeln att validera
        
        Returns:
            API-nyckeldata om giltig, annars None
        """
        if not api_key or not isinstance(api_key, str) or \
           not api_key.startswith("hpos_") or len(api_key) != 37:
            return None

        key_data = self._api_key_store.get(api_key)
        
        if key_data and key_data.get("is_active"):
            return key_data
        return None

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Återkallar en API-nyckel.

        Args:
            api_key: API-nyckeln att återkalla

        Returns:
            True om nyckeln fanns och återkallades, annars False
        """
        key_data = self._api_key_store.get(api_key)
        if key_data and key_data.get("is_active"):
            key_data["is_active"] = False
            return True
        return False


class RateLimiter:
    """
    Begränsar hur ofta användare kan göra förfrågningar.
    
    Förhindrar missbruk och överbelastning av systemet.
    """
    
    def __init__(self):
        self.requests = defaultdict(deque)  # user_id -> deque of timestamps
        self.blocked_users = {}  # user_id -> block_until_timestamp
    
    def is_allowed(self, user_id: str, max_requests: int = None, window_seconds: int = None) -> bool:
        """
        Kontrollerar om en användare får göra en förfrågan.
        
        Args:
            user_id: Användarens ID
            max_requests: Max antal förfrågningar per tidsfönster
            window_seconds: Tidsfönster i sekunder
        
        Returns:
            True om förfrågan är tillåten
        """
        if not settings.security.rate_limit_enabled:
            return True
        
        max_requests = max_requests or settings.security.rate_limit_requests
        window_seconds = window_seconds or settings.security.rate_limit_window
        
        now = datetime.utcnow()
        
        # Kontrollera om användaren är blockerad
        if user_id in self.blocked_users:
            if now < self.blocked_users[user_id]:
                return False
            else:
                # Blockeringen har gått ut
                del self.blocked_users[user_id]
        
        # Rensa gamla förfrågningar
        user_requests = self.requests[user_id]
        cutoff_time = now - timedelta(seconds=window_seconds)
        
        while user_requests and user_requests[0] < cutoff_time:
            user_requests.popleft()
        
        # Kontrollera om användaren har överskridit gränsen
        if len(user_requests) >= max_requests:
            # Blockera användaren i 5 minuter
            self.blocked_users[user_id] = now + timedelta(minutes=5)
            logger.warning(f"Användare {user_id} blockerad för rate limiting")
            return False
        
        # Lägg till denna förfrågan
        user_requests.append(now)
        return True
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Hämtar statistik för en användare.
        
        Args:
            user_id: Användarens ID
        
        Returns:
            Statistik om användarens förfrågningar
        """
        user_requests = self.requests[user_id]
        now = datetime.utcnow()
        
        # Räkna förfrågningar senaste timmen
        hour_ago = now - timedelta(hours=1)
        recent_requests = sum(1 for req_time in user_requests if req_time > hour_ago)
        
        is_blocked = user_id in self.blocked_users and now < self.blocked_users[user_id]
        block_until = self.blocked_users.get(user_id) if is_blocked else None
        
        return {
            "user_id": user_id,
            "requests_last_hour": recent_requests,
            "total_requests": len(user_requests),
            "is_blocked": is_blocked,
            "blocked_until": block_until.isoformat() if block_until else None
        }


class InputSanitizer:
    """
    Rengör och validerar användarinput för säkerhet.
    """
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """
        Rengör en sträng från farliga tecken.
        
        Args:
            input_str: Strängen att rengöra
            max_length: Max längd på strängen
        
        Returns:
            Rengjord sträng
        """
        if not isinstance(input_str, str):
            raise ValidationError("Input måste vara en sträng", error_code="INVALID_INPUT_TYPE")
        
        # Begränsa längd
        if len(input_str) > max_length:
            raise ValidationError(f"Input för lång (max {max_length} tecken)", error_code="INPUT_TOO_LONG")
        
        # Ta bort farliga tecken (grundläggande XSS-skydd)
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
        sanitized = input_str
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Ta bort extra whitespace
        sanitized = sanitized.strip()
        
        return sanitized
    
    @staticmethod
    def validate_email(email: str) -> str:
        """
        Validerar och rengör en e-postadress.
        
        Args:
            email: E-postadressen att validera
        
        Returns:
            Validerad e-postadress
        """
        import re
        
        email = InputSanitizer.sanitize_string(email, max_length=254)
        
        # Grundläggande e-postvalidering
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError("Ogiltig e-postadress", error_code="INVALID_EMAIL")
        
        return email.lower()
    
    @staticmethod
    def validate_filename(filename: str) -> str:
        """
        Validerar och rengör ett filnamn.
        
        Args:
            filename: Filnamnet att validera
        
        Returns:
            Säkert filnamn
        """
        import re
        
        if not filename:
            raise ValidationError("Filnamn kan inte vara tomt", error_code="EMPTY_FILENAME")
        
        # Ta bort farliga tecken från filnamn
        safe_filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
        
        # Ta bort punkter i början (förhindrar dolda filer)
        safe_filename = safe_filename.lstrip('.')
        
        # Begränsa längd
        if len(safe_filename) > 255:
            name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
            safe_filename = name[:250] + ('.' + ext if ext else '')
        
        if not safe_filename:
            raise ValidationError("Ogiltigt filnamn", error_code="INVALID_FILENAME")
        
        return safe_filename


class AuditLogger:
    """
    Loggar säkerhetsrelaterade händelser för granskning.
    """
    
    def __init__(self):
        self.audit_log = []
        self.max_log_entries = 10000
    
    def log_event(self, event_type: str, user_id: str = None, details: Dict[str, Any] = None):
        """
        Loggar en säkerhetshändelse.
        
        Args:
            event_type: Typ av händelse (t.ex. "login", "api_key_created")
            user_id: Användarens ID (om tillämpligt)
            details: Extra detaljer om händelsen
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details or {}
        }
        
        self.audit_log.append(event)
        
        # Begränsa logg-storlek
        if len(self.audit_log) > self.max_log_entries:
            self.audit_log.pop(0)
        
        # Logga till vanlig logg också
        logger.info(f"Säkerhetshändelse: {event_type}", extra={"audit_event": event})
    
    def get_recent_events(self, limit: int = 100, event_type: str = None) -> List[Dict[str, Any]]:
        """
        Hämtar senaste säkerhetshändelser.
        
        Args:
            limit: Max antal händelser att returnera
            event_type: Filtrera på händelsetyp (valfritt)
        
        Returns:
            Lista med säkerhetshändelser
        """
        events = self.audit_log
        
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        
        return events[-limit:]


# Globala instanser
security_manager = SecurityManager()
rate_limiter = RateLimiter()
input_sanitizer = InputSanitizer()
audit_logger = AuditLogger()

# API key storage (for secure access to external services)
_api_key_cache = {}

async def get_secure_api_key(service_name: str) -> str:
    """
    Retrieve a secure API key for an external service.
    
    This function first checks environment variables, then secure storage,
    and finally falls back to a default if available.
    
    Args:
        service_name: Name of the service (e.g., 'owl', 'openai', 'deepseek')
        
    Returns:
        API key as string
        
    Raises:
        ValueError: If no API key is found for the service
    """
    import os
    from dotenv import load_dotenv
    
    # Check if we already have this key in cache
    if service_name in _api_key_cache:
        return _api_key_cache[service_name]
    
    # Ensure environment variables are loaded
    load_dotenv()
    
    # Try to get from environment variables first (most secure)
    env_var_name = f"{service_name.upper()}_API_KEY"
    api_key = os.getenv(env_var_name)
    
    if api_key:
        _api_key_cache[service_name] = api_key
        return api_key
    
    # Try alternative environment variable formats
    alt_env_var_names = [
        f"{service_name.upper()}_KEY",
        f"{service_name.upper()}_SECRET",
        f"{service_name}_api_key",
        f"{service_name}_key"
    ]
    
    for var_name in alt_env_var_names:
        api_key = os.getenv(var_name)
        if api_key:
            _api_key_cache[service_name] = api_key
            return api_key
    
    # If we're in development mode, use default test keys
    if os.getenv("APP_ENV") == "development" or os.getenv("DEBUG") == "true":
        if service_name == "owl":
            test_key = "owl_test_key_for_development_only"
            _api_key_cache[service_name] = test_key
            logger.warning(f"Using test API key for {service_name} in development mode")
            return test_key
    
    # No API key found
    raise ValueError(f"No API key found for service: {service_name}. Please set {env_var_name} environment variable.")


def require_auth(optional: bool = False):
    """
    Decorator som kräver autentisering för en endpoint.
    
    Args:
        optional: Om True, tillåt åtkomst även utan token (men validera om token finns)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Hitta request-objektet i argumenten
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                raise HappyOSError("Kunde inte hitta request-objekt", error_code="INTERNAL_ERROR")
            
            # Försök hämta token
            authorization = request.headers.get("Authorization")
            token = None
            
            if authorization and authorization.startswith("Bearer "):
                token = authorization.split(" ")[1]
            
            # Kontrollera om token krävs
            if not optional and not token:
                raise HTTPException(status_code=401, detail="Åtkomsttoken krävs")
            
            # Validera token om den finns
            user_data = None
            if token:
                try:
                    user_data = security_manager.verify_token(token)
                    audit_logger.log_event("authenticated_request", user_data.get("user_id"))
                except ValidationError as e:
                    if not optional:
                        raise HTTPException(status_code=401, detail=str(e))
            
            # Lägg till användardata i kwargs
            kwargs["current_user"] = user_data
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_rate_limit(max_requests: int = None, window_seconds: int = None):
    """
    Decorator som tillämpar rate limiting på en endpoint.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Hitta request och användardata
            request = None
            current_user = kwargs.get("current_user")
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Bestäm användar-ID för rate limiting
            user_id = "anonymous"
            if current_user and "user_id" in current_user:
                user_id = current_user["user_id"]
            elif request:
                # Använd IP-adress för anonyma användare
                user_id = f"ip_{request.client.host}"
            
            # Kontrollera rate limit
            if not rate_limiter.is_allowed(user_id, max_requests, window_seconds):
                audit_logger.log_event("rate_limit_exceeded", user_id)
                raise HTTPException(
                    status_code=429, 
                    detail="För många förfrågningar. Försök igen senare."
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


async def get_current_user(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to get the current user from either a WebSocket connection
    (via a 'token' query parameter) or a standard HTTP Authorization header.
    Args:
        websocket: The WebSocket connection (required for context).
        token: The JWT token from the query string (for WebSockets).
        credentials: The HTTP Authorization credentials (for standard requests).
    Returns:
        User data from the token, or raises WebSocketException on failure.
    """
    auth_token = token
    logger.info(f"WebSocket auth attempt for user: {websocket.path_params.get('user_id')}")

    if not auth_token:
        logger.warning(f"WebSocket connection for user {websocket.path_params.get('user_id')} failed: Missing token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return None

    try:
        user_data = security_manager.verify_token(auth_token)
        logger.info(f"WebSocket authentication successful for user: {user_data.get('user_id')}")
        return user_data
    except ValidationError as e:
        logger.error(f"WebSocket connection failed: Invalid token for user {websocket.path_params.get('user_id')}. Reason: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Invalid token: {e}")
        return None


def create_user_session(user_id: str, additional_data: Dict[str, Any] = None) -> str:
    """
    Skapar en användarsession och returnerar åtkomsttoken.
    
    Args:
        user_id: Användarens ID
        additional_data: Extra data att inkludera i token
    
    Returns:
        JWT åtkomsttoken
    """
    token_data = {"user_id": user_id, "type": "access_token"}
    if additional_data:
        token_data.update(additional_data)
    
    token = security_manager.create_access_token(token_data)
    
    audit_logger.log_event("session_created", user_id, {"token_created": True})
    
    return token


async def get_current_api_key_user(api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    """
    FastAPI dependency för att hämta användardata baserat på API-nyckel.

    Args:
        api_key: API-nyckel från X-API-Key header

    Returns:
        Användardata kopplat till API-nyckeln

    Raises:
        HTTPException: Om API-nyckel saknas, är ogiltig eller återkallad
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required in X-API-Key header")

    user_data = security_manager.validate_api_key(api_key)

    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid, revoked, or unauthorized API key")

    audit_logger.log_event("api_key_authenticated", user_data.get("user_id"), {"key_name": user_data.get("name")})
    return user_data


# Exportera viktiga funktioner och klasser
__all__ = [
    'SecurityManager',
    'RateLimiter', 
    'InputSanitizer',
    'AuditLogger',
    'security_manager',
    'rate_limiter',
    'input_sanitizer',
    'audit_logger',
    'require_auth',
    'require_rate_limit',
    'get_current_user',
    'create_user_session',
    'get_current_api_key_user'
]