# Fix import to handle circular dependencies and path resolution issues
try:
    from .self_building_orchestrator import self_building_orchestrator as self_builder
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import self_building_orchestrator: {e}")
    logger.info("This may be due to PYTHONPATH configuration issues in Docker")
    # Provide a fallback or re-raise with more context
    raise ImportError(
        f"Cannot import self_builder from self_building_orchestrator. "
        f"This is likely due to PYTHONPATH not being set correctly in the Docker container. "
        f"Ensure PYTHONPATH includes the happyos directory. Original error: {e}"
    )

__all__ = ["self_builder"]
