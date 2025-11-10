"""
🛡️ ROBUST FELHANTERING - SÄKERSTÄLLER ATT SYSTEMET ALDRIG KRASCHAR

Vad gör den här filen?
- Fångar upp alla fel som kan uppstå i systemet
- Försöker automatiskt återhämta sig från problem
- Loggar allt för felsökning
- Ger användaren begripliga felmeddelanden

Varför behövs detta?
- Gör systemet mycket mer stabilt
- Användaren får aldrig se tekniska felmeddelanden
- Systemet kan fortsätta fungera även när något går fel
- Hjälper utvecklare att hitta och fixa problem snabbt
"""

import asyncio
import logging
import traceback
from typing import Any, Dict, Optional, Callable, Union
from datetime import datetime
from functools import wraps
from contextlib import asynccontextmanager

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class HappyOSError(Exception):
    """Bas-exception för alla HappyOS-fel."""
    
    def __init__(self, message: str, error_code: str = "GENERAL_ERROR", details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)


class SkillExecutionError(HappyOSError):
    """Fel vid utförande av skills."""
    pass


class LLMError(HappyOSError):
    """Fel vid kommunikation med AI-modeller."""
    pass


class DatabaseError(HappyOSError):
    """Databasrelaterade fel."""
    pass


class ValidationError(HappyOSError):
    """Valideringsfel för användarinput."""
    pass


class RobustExecutor:
    """
    Robust exekvering med automatisk återhämtning.
    
    Den här klassen ser till att funktioner körs säkert och försöker
    automatiskt igen om något går fel.
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def execute_with_retry(
        self, 
        func: Callable, 
        *args, 
        fallback_response: Optional[Any] = None,
        **kwargs
    ) -> Any:
        """
        Kör en funktion med automatiska återförsök.
        
        Args:
            func: Funktionen som ska köras
            *args: Argument till funktionen
            fallback_response: Vad som ska returneras om allt misslyckas
            **kwargs: Nyckelord-argument till funktionen
        
        Returns:
            Resultatet från funktionen eller fallback_response
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Försök {attempt + 1}/{self.max_retries} för {func.__name__}")
                
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"Lyckades efter {attempt + 1} försök: {func.__name__}")
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Försök {attempt + 1} misslyckades för {func.__name__}: {str(e)}")
                
                # Om det här var sista försöket, ge upp
                if attempt == self.max_retries - 1:
                    break
                
                # Vänta innan nästa försök (exponential backoff)
                delay = self.base_delay * (2 ** attempt)
                logger.debug(f"Väntar {delay} sekunder innan nästa försök")
                await asyncio.sleep(delay)
        
        # Alla försök misslyckades
        logger.error(f"Alla {self.max_retries} försök misslyckades för {func.__name__}: {str(last_error)}")
        
        if fallback_response is not None:
            logger.info(f"Använder fallback-svar för {func.__name__}")
            return fallback_response
        
        # Om inget fallback finns, kasta ett begripligt fel
        raise HappyOSError(
            f"Kunde inte utföra {func.__name__} efter {self.max_retries} försök",
            error_code="EXECUTION_FAILED",
            details={"original_error": str(last_error), "function": func.__name__}
        )


def safe_execute(
    max_retries: int = 3,
    fallback_response: Any = None,
    error_message: str = "Ett oväntat fel uppstod"
):
    """
    Decorator för säker funktionsexekvering.
    
    Användning:
    @safe_execute(fallback_response="Kunde inte utföra uppgiften")
    async def min_funktion():
        # Kod som kan misslyckas
        pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            executor = RobustExecutor(max_retries=max_retries)
            try:
                return await executor.execute_with_retry(
                    func, *args, fallback_response=fallback_response, **kwargs
                )
            except Exception as e:
                logger.error(f"Säker exekvering misslyckades för {func.__name__}: {str(e)}")
                return {
                    "success": False,
                    "error": error_message,
                    "details": str(e) if settings.debug else None
                }
        return wrapper
    return decorator


class ErrorReporter:
    """
    Rapporterar och spårar fel för analys och förbättring.
    """
    
    def __init__(self):
        self.error_counts = {}
        self.recent_errors = []
        self.max_recent_errors = 100
    
    def report_error(self, error: Exception, context: Dict[str, Any] = None):
        """
        Rapporterar ett fel för spårning och analys.
        
        Args:
            error: Felet som uppstod
            context: Extra information om när/var felet uppstod
        """
        error_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context or {},
            "traceback": traceback.format_exc() if settings.debug else None
        }
        
        # Lägg till i recent errors
        self.recent_errors.append(error_info)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
        
        # Räkna fel-typer
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Logga felet
        logger.error(f"Fel rapporterat: {error_type} - {str(error)}", extra={"context": context})
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Returnerar statistik över fel."""
        return {
            "total_errors": len(self.recent_errors),
            "error_counts": self.error_counts,
            "recent_errors": self.recent_errors[-10:],  # Senaste 10 felen
            "most_common_error": max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None
        }


# Global error reporter
error_reporter = ErrorReporter()


@asynccontextmanager
async def error_context(operation_name: str, user_id: str = None):
    """
    Context manager för att fånga och hantera fel i en operation.
    
    Användning:
    async with error_context("skapa_faktura", user_id="user123"):
        # Kod som kan misslyckas
        pass
    """
    try:
        logger.info(f"Startar operation: {operation_name}")
        yield
        logger.info(f"Operation slutförd: {operation_name}")
    except Exception as e:
        context = {
            "operation": operation_name,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        error_reporter.report_error(e, context)
        
        # Konvertera tekniska fel till användarvänliga meddelanden
        user_message = get_user_friendly_error_message(e, operation_name)
        
        raise HappyOSError(
            user_message,
            error_code=getattr(e, 'error_code', 'OPERATION_FAILED'),
            details=context
        )


def get_user_friendly_error_message(error: Exception, operation: str) -> str:
    """
    Konverterar tekniska felmeddelanden till användarvänliga beskrivningar.
    """
    error_type = type(error).__name__
    
    # Mappning av tekniska fel till användarvänliga meddelanden
    error_messages = {
        "ConnectionError": f"Kunde inte ansluta till tjänsten. Kontrollera din internetanslutning och försök igen.",
        "TimeoutError": f"Operationen tog för lång tid. Försök igen om en stund.",
        "ValidationError": f"Informationen du angav är inte korrekt. Kontrollera och försök igen.",
        "FileNotFoundError": f"Kunde inte hitta filen. Kontrollera att den finns och försök igen.",
        "PermissionError": f"Har inte behörighet att utföra denna operation. Kontrollera dina rättigheter.",
        "DatabaseError": f"Problem med databasen. Försök igen om en stund.",
        "LLMError": f"Problem med AI-tjänsten. Kontrollera din API-nyckel och försök igen.",
        "SkillExecutionError": f"Kunde inte utföra uppgiften. Försök igen eller kontakta support."
    }
    
    base_message = error_messages.get(error_type, f"Ett oväntat fel uppstod vid {operation}")
    
    # Lägg till specifik information om det finns
    if hasattr(error, 'message') and error.message:
        return f"{base_message} Detaljer: {error.message}"
    
    return base_message


class HealthChecker:
    """
    Övervakar systemets hälsa och prestanda.
    """
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.request_count = 0
        self.error_count = 0
        self.last_health_check = None
    
    async def check_system_health(self) -> Dict[str, Any]:
        """
        Kontrollerar systemets hälsa.
        
        Returns:
            Dict med hälsoinformation
        """
        try:
            # Kontrollera databas
            from app.db.database import get_db
            db_healthy = await self._check_database()
            
            # Kontrollera AI-tjänster
            ai_healthy = await self._check_ai_services()
            
            # Kontrollera filsystem
            fs_healthy = await self._check_filesystem()
            
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            error_rate = (self.error_count / max(self.request_count, 1)) * 100
            
            health_status = {
                "status": "healthy" if all([db_healthy, ai_healthy, fs_healthy]) else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": uptime,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate_percent": round(error_rate, 2),
                "components": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "ai_services": "healthy" if ai_healthy else "unhealthy",
                    "filesystem": "healthy" if fs_healthy else "unhealthy"
                },
                "error_statistics": error_reporter.get_error_statistics()
            }
            
            self.last_health_check = health_status
            return health_status
            
        except Exception as e:
            logger.error(f"Hälsokontroll misslyckades: {str(e)}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def _check_database(self) -> bool:
        """Kontrollerar databasanslutning."""
        try:
            from app.db.database import engine
            async with engine.begin() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"Databaskontroll misslyckades: {str(e)}")
            return False
    
    async def _check_ai_services(self) -> bool:
        """Kontrollerar AI-tjänster."""
        try:
            from app.llm.router import get_llm_client
            client = get_llm_client()
            if client and hasattr(client, 'is_available'):
                return client.is_available
            return True  # Om ingen klient finns, anta att det är OK
        except Exception as e:
            logger.warning(f"AI-tjänstkontroll misslyckades: {str(e)}")
            return False
    
    async def _check_filesystem(self) -> bool:
        """Kontrollerar filsystem."""
        try:
            import tempfile
            import os
            
            # Testa att skriva en temporär fil
            with tempfile.NamedTemporaryFile(delete=True) as tmp:
                tmp.write(b"health_check")
                tmp.flush()
                os.fsync(tmp.fileno())
            
            return True
        except Exception as e:
            logger.warning(f"Filsystemkontroll misslyckades: {str(e)}")
            return False
    
    def record_request(self):
        """Registrerar en förfrågan."""
        self.request_count += 1
    
    def record_error(self):
        """Registrerar ett fel."""
        self.error_count += 1


# Global health checker
health_checker = HealthChecker()


def create_error_response(error: Exception, request_id: str = None) -> Dict[str, Any]:
    """
    Skapar ett standardiserat felsvar.
    
    Args:
        error: Felet som uppstod
        request_id: Unikt ID för förfrågan (för spårning)
    
    Returns:
        Standardiserat felsvar
    """
    if isinstance(error, HappyOSError):
        return {
            "success": False,
            "error": {
                "message": error.message,
                "code": error.error_code,
                "details": error.details if settings.debug else None,
                "timestamp": error.timestamp.isoformat(),
                "request_id": request_id
            }
        }
    else:
        # Konvertera okänt fel till användarvänligt meddelande
        user_message = get_user_friendly_error_message(error, "operation")
        return {
            "success": False,
            "error": {
                "message": user_message,
                "code": "UNKNOWN_ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id,
                "details": str(error) if settings.debug else None
            }
        }


# Exportera viktiga funktioner och klasser
__all__ = [
    'HappyOSError',
    'SkillExecutionError', 
    'LLMError',
    'DatabaseError',
    'ValidationError',
    'RobustExecutor',
    'safe_execute',
    'error_context',
    'error_reporter',
    'health_checker',
    'create_error_response',
    'get_user_friendly_error_message'
]