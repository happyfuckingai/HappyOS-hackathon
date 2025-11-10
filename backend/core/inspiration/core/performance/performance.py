"""
⚡ PRESTANDA-OPTIMERING - GÖR HAPPYOS BLIXTSNABBT

Vad gör den här filen?
- Cachar (sparar) vanliga svar så de inte behöver beräknas igen
- Optimerar databasförfrågningar
- Mäter prestanda och hittar flaskhalsar
- Gör systemet snabbare och mer responsivt

Varför behövs detta?
- Användare vill ha snabba svar
- Sparar pengar på AI-anrop genom caching
- Gör systemet skalbart för många användare
- Identifierar och löser prestandaproblem
"""

import asyncio
import time
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Callable, List, Tuple
from datetime import datetime, timedelta
from functools import wraps, lru_cache
from collections import defaultdict, deque
# import pickle # Removed pickle
# import aiofiles # Removed aiofiles
from pathlib import Path

from app.core.config.settings import BaseSettings

logger = logging.getLogger(__name__)
settings = BaseSettings()


class PerformanceCache:
    """
    Intelligent cache-system för att spara vanliga svar.
    
    Sparar resultat från dyra operationer (AI-anrop, databasförfrågningar)
    så de kan återanvändas snabbt.
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self.cache = {}  # key -> (value, expiry_time, access_count)
        self.max_size = max_size
        self.default_ttl = default_ttl  # Time to live i sekunder
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_requests": 0
        }
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        Genererar en unik nyckel för cache-lagring.
        
        Args:
            func_name: Namnet på funktionen
            args: Positionsargument
            kwargs: Nyckelord-argument
        
        Returns:
            Unik cache-nyckel
        """
        # Skapa en deterministisk representation av argumenten
        key_data = {
            "function": func_name,
            "args": args,
            "kwargs": sorted(kwargs.items()) if kwargs else {}
        }
        
        # Serialisera och hasha för att få en kort, unik nyckel
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Hämtar ett värde från cache.
        
        Args:
            key: Cache-nyckeln
        
        Returns:
            Cachat värde eller None om inte hittat/utgånget
        """
        self.stats["total_requests"] += 1
        
        if key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        value, expiry_time, access_count = self.cache[key]
        
        # Kontrollera om värdet har gått ut
        if datetime.utcnow() > expiry_time:
            del self.cache[key]
            self.stats["misses"] += 1
            return None
        
        # Uppdatera åtkomststatistik
        self.cache[key] = (value, expiry_time, access_count + 1)
        self.stats["hits"] += 1
        
        logger.debug(f"Cache hit för nyckel: {key[:8]}...")
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Sparar ett värde i cache.
        
        Args:
            key: Cache-nyckeln
            value: Värdet att spara
            ttl: Time to live i sekunder (använder default om None)
        """
        ttl = ttl or self.default_ttl
        expiry_time = datetime.utcnow() + timedelta(seconds=ttl)
        
        # Om cache är full, ta bort minst använda objekt
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[key] = (value, expiry_time, 1)
        logger.debug(f"Cache set för nyckel: {key[:8]}... (TTL: {ttl}s)")
    
    def _evict_lru(self) -> None:
        """Tar bort det minst nyligen använda objektet från cache."""
        if not self.cache:
            return
        
        # Hitta objektet med lägst access_count
        lru_key = min(self.cache.keys(), key=lambda k: self.cache[k][2])
        del self.cache[lru_key]
        self.stats["evictions"] += 1
        
        logger.debug(f"Evicted LRU cache entry: {lru_key[:8]}...")
    
    def clear(self) -> None:
        """Tömmer hela cache."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Returnerar cache-statistik.
        
        Returns:
            Statistik om cache-prestanda
        """
        total_requests = self.stats["total_requests"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_rate_percent": round(hit_rate, 2),
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "total_requests": total_requests
        }


class PerformanceMonitor:
    """
    Övervakar och mäter systemets prestanda.
    
    Spårar svarstider, identifierar flaskhalsar och samlar statistik.
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)  # function_name -> list of execution times
        self.slow_queries = deque(maxlen=100)  # Senaste 100 långsamma operationerna
        self.active_operations = {}  # operation_id -> start_time
        self.operation_counter = 0
    
    def start_operation(self, operation_name: str, details: Dict[str, Any] = None) -> str:
        """
        Startar mätning av en operation.
        
        Args:
            operation_name: Namnet på operationen
            details: Extra detaljer om operationen
        
        Returns:
            Unikt operations-ID
        """
        operation_id = f"{operation_name}_{self.operation_counter}"
        self.operation_counter += 1
        
        self.active_operations[operation_id] = {
            "name": operation_name,
            "start_time": time.time(),
            "details": details or {}
        }
        
        return operation_id
    
    def end_operation(self, operation_id: str) -> float:
        """
        Avslutar mätning av en operation.
        
        Args:
            operation_id: Operations-ID från start_operation
        
        Returns:
            Exekveringstid i sekunder
        """
        if operation_id not in self.active_operations:
            logger.warning(f"Okänt operations-ID: {operation_id}")
            return 0.0
        
        operation = self.active_operations.pop(operation_id)
        execution_time = time.time() - operation["start_time"]
        
        # Spara mätning
        operation_name = operation["name"]
        self.metrics[operation_name].append(execution_time)
        
        # Begränsa antal sparade mätningar per operation
        if len(self.metrics[operation_name]) > 1000:
            self.metrics[operation_name] = self.metrics[operation_name][-500:]
        
        # Logga långsamma operationer
        if execution_time > 5.0:  # Långsammare än 5 sekunder
            slow_operation = {
                "name": operation_name,
                "execution_time": execution_time,
                "timestamp": datetime.utcnow().isoformat(),
                "details": operation["details"]
            }
            self.slow_queries.append(slow_operation)
            logger.warning(f"Långsam operation: {operation_name} tog {execution_time:.2f}s")
        
        return execution_time
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """
        Hämtar statistik för en specifik operation.
        
        Args:
            operation_name: Namnet på operationen
        
        Returns:
            Statistik om operationens prestanda
        """
        times = self.metrics.get(operation_name, [])
        
        if not times:
            return {"operation": operation_name, "no_data": True}
        
        return {
            "operation": operation_name,
            "count": len(times),
            "avg_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "total_time": sum(times),
            "recent_avg": sum(times[-10:]) / min(len(times), 10)  # Senaste 10
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Hämtar övergripande systemstatistik.
        
        Returns:
            Systemets prestandastatistik
        """
        all_operations = []
        total_operations = 0
        total_time = 0
        
        for operation_name, times in self.metrics.items():
            stats = self.get_operation_stats(operation_name)
            all_operations.append(stats)
            total_operations += stats["count"]
            total_time += stats["total_time"]
        
        # Sortera efter genomsnittlig tid (långsammast först)
        all_operations.sort(key=lambda x: x.get("avg_time", 0), reverse=True)
        
        return {
            "total_operations": total_operations,
            "total_execution_time": total_time,
            "avg_execution_time": total_time / total_operations if total_operations > 0 else 0,
            "active_operations": len(self.active_operations),
            "slowest_operations": all_operations[:5],  # Top 5 långsammaste
            "recent_slow_queries": list(self.slow_queries)[-10:]  # Senaste 10 långsamma
        }


class DatabaseOptimizer:
    """
    Optimerar databasförfrågningar för bättre prestanda.
    """
    
    def __init__(self):
        self.query_cache = PerformanceCache(max_size=1000, default_ttl=300)  # 5 minuter
        self.query_stats = defaultdict(list)
    
    async def cached_query(self, query_func: Callable, cache_key: str, ttl: int = 300, *args, **kwargs) -> Any:
        """
        Kör en databasförfrågan med caching.
        
        Args:
            query_func: Funktionen som kör förfrågan
            cache_key: Nyckel för cache-lagring
            ttl: Cache time-to-live i sekunder
            *args, **kwargs: Argument till query_func
        
        Returns:
            Resultat från förfrågan (cachat eller nytt)
        """
        # Försök hämta från cache först
        cached_result = self.query_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Kör förfrågan och cacha resultatet
        start_time = time.time()
        result = await query_func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Spara statistik
        self.query_stats[query_func.__name__].append(execution_time)
        
        # Cacha resultatet
        self.query_cache.set(cache_key, result, ttl)
        
        logger.debug(f"Databasförfrågan {query_func.__name__} tog {execution_time:.3f}s")
        
        return result
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Returnerar statistik över databasförfrågningar."""
        stats = {}
        
        for query_name, times in self.query_stats.items():
            if times:
                stats[query_name] = {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "total_time": sum(times)
                }
        
        return {
            "query_statistics": stats,
            "cache_stats": self.query_cache.get_stats()
        }


# Globala instanser
performance_cache = PerformanceCache()
performance_monitor = PerformanceMonitor()
db_optimizer = DatabaseOptimizer()


def cached(ttl: int = 3600, key_func: Optional[Callable] = None):
    """
    Decorator för att cacha funktionsresultat.
    
    Args:
        ttl: Time to live i sekunder
        key_func: Funktion för att generera cache-nyckel (valfritt)
    
    Användning:
    @cached(ttl=1800)  # Cacha i 30 minuter
    async def expensive_function(param1, param2):
        # Dyr beräkning här
        return result
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generera cache-nyckel
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = performance_cache._generate_key(func.__name__, args, kwargs)
            
            # Försök hämta från cache
            cached_result = performance_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Kör funktionen och cacha resultatet
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            performance_cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def monitor_performance(operation_name: str = None):
    """
    Decorator för att övervaka prestanda för en funktion.
    
    Args:
        operation_name: Namn på operationen (använder funktionsnamn om None)
    
    Användning:
    @monitor_performance("create_invoice")
    async def create_invoice_function():
        # Funktionskod här
        pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            operation_id = performance_monitor.start_operation(op_name)
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
            finally:
                execution_time = performance_monitor.end_operation(operation_id)
                logger.debug(f"Operation {op_name} slutförd på {execution_time:.3f}s")
        
        return wrapper
    return decorator


class BatchProcessor:
    """
    Bearbetar flera uppgifter parallellt för bättre prestanda.
    """
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(self, tasks: List[Callable], *args, **kwargs) -> List[Any]:
        """
        Bearbetar en batch av uppgifter parallellt.
        
        Args:
            tasks: Lista med funktioner att köra
            *args, **kwargs: Argument till funktionerna
        
        Returns:
            Lista med resultat från alla uppgifter
        """
        async def process_single_task(task):
            async with self.semaphore:
                try:
                    if asyncio.iscoroutinefunction(task):
                        return await task(*args, **kwargs)
                    else:
                        return task(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Fel i batch-bearbetning: {str(e)}")
                    return None
        
        # Kör alla uppgifter parallellt
        results = await asyncio.gather(*[process_single_task(task) for task in tasks])
        return results


@lru_cache(maxsize=1000)
def cached_computation(input_data: str) -> Any:
    """
    Exempel på en cachad beräkning med LRU-cache.
    
    Args:
        input_data: Indata för beräkningen
    
    Returns:
        Beräkningsresultat
    """
    # Simulera en dyr beräkning
    import hashlib
    return hashlib.sha256(input_data.encode()).hexdigest()


async def optimize_llm_calls(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Optimerar AI-anrop genom caching och batch-bearbetning.
    
    Args:
        prompt: Prompten att skicka till AI
        model: AI-modell att använda
    
    Returns:
        AI-svar (cachat eller nytt)
    """
    # Generera cache-nyckel baserat på prompt och modell
    cache_key = hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()
    
    # Försök hämta från cache
    cached_response = performance_cache.get(cache_key)
    if cached_response:
        logger.debug("Använder cachat AI-svar")
        return cached_response
    
    # Om inte i cache, gör AI-anrop
    from app.llm.router import get_llm_client
    
    operation_id = performance_monitor.start_operation("llm_call", {"model": model})
    
    try:
        client = get_llm_client()
        if client:
            messages = [{"role": "user", "content": prompt}]
            response = await client.generate(messages, model=model)
            ai_response = response.get("content", "")
            
            # Cacha svaret (längre TTL för AI-svar eftersom de är dyra)
            performance_cache.set(cache_key, ai_response, ttl=7200)  # 2 timmar
            
            return ai_response
        else:
            return "AI-tjänst inte tillgänglig"
    
    finally:
        performance_monitor.end_operation(operation_id)


def get_performance_report() -> Dict[str, Any]:
    """
    Genererar en omfattande prestandarapport.
    
    Returns:
        Detaljerad prestandarapport
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cache_performance": performance_cache.get_stats(),
        "system_performance": performance_monitor.get_system_stats(),
        "database_performance": db_optimizer.get_query_stats(),
        "recommendations": _generate_performance_recommendations()
    }


def _generate_performance_recommendations() -> List[str]:
    """Genererar rekommendationer baserat på prestandadata."""
    recommendations = []
    
    # Analysera cache-prestanda
    cache_stats = performance_cache.get_stats()
    if cache_stats["hit_rate_percent"] < 50:
        recommendations.append("Cache hit rate är låg - överväg att öka cache-storlek eller TTL")
    
    # Analysera systemstatistik
    system_stats = performance_monitor.get_system_stats()
    if system_stats["avg_execution_time"] > 2.0:
        recommendations.append("Genomsnittlig exekveringstid är hög - undersök långsamma operationer")
    
    if len(system_stats.get("recent_slow_queries", [])) > 5:
        recommendations.append("Många långsamma förfrågningar - optimera databasförfrågningar")
    
    if not recommendations:
        recommendations.append("Systemet presterar bra - inga optimeringar behövs för tillfället")
    
    return recommendations


# Exportera viktiga funktioner och klasser
__all__ = [
    'PerformanceCache',
    'PerformanceMonitor',
    'DatabaseOptimizer',
    'BatchProcessor',
    'performance_cache',
    'performance_monitor',
    'db_optimizer',
    'cached',
    'monitor_performance',
    'optimize_llm_calls',
    'get_performance_report'
]
