"""
Self-Building System Configuration.
All configuration is centralized here to avoid hardcoding.
"""

import os
from typing import Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class SelfBuildingConfig:
    """Configuration for the self-building system."""
    
    # Base paths
    base_path: str = "/home/mr/Dokument/filee.tar/happyos"
    skills_directory: str = "/home/mr/Dokument/filee.tar/happyos/app/skills"
    plugins_directory: str = "/home/mr/Dokument/filee.tar/happyos/app/plugins"
    mcp_servers_directory: str = "/home/mr/Dokument/filee.tar/happyos/app/mcp/servers"
    generated_skills_directory: str = "/home/mr/Dokument/filee.tar/happyos/app/skills/generated"
    generated_plugins_directory: str = "/home/mr/Dokument/filee.tar/happyos/app/plugins/generated"
    generated_mcp_directory: str = "/home/mr/Dokument/filee.tar/happyos/app/mcp/servers/generated"

    # Documentation
    docs_directory: str = "/home/mr/Dokument/filee.tar/happyos/docs"
    component_docs_directory: str = "/home/mr/Dokument/filee.tar/happyos/docs/components"
    api_docs_directory: str = "/home/mr/Dokument/filee.tar/happyos/docs/api"

    # Logs and data
    logs_directory: str = "/home/mr/Dokument/filee.tar/happyos/logs"
    audit_log_directory: str = "/home/mr/Dokument/filee.tar/happyos/logs/audit"
    dependency_graphs_directory: str = "/home/mr/Dokument/filee.tar/happyos/logs/dependency_graphs"

    # Marketplace
    marketplace_directory: str = "/home/mr/Dokument/filee.tar/happyos/marketplace"
    marketplace_downloads_directory: str = "/home/mr/Dokument/filee.tar/happyos/marketplace/downloads"
    marketplace_quarantine_directory: str = "/home/mr/Dokument/filee.tar/happyos/marketplace/quarantine"
    
    # Sandbox
    sandbox_directory: str = "/tmp/happyos_sandbox"
    container_runtime: str = "docker"  # or "podman"
    
    # Component scanning
    scan_interval_seconds: int = 3600  # 1 hour
    file_extensions: List[str] = field(default_factory=lambda: [".py"])
    excluded_directories: List[str] = field(default_factory=lambda: ["__pycache__", ".git", ".pytest_cache"])
    
    # Auto-generation
    auto_generation_enabled: bool = True
    max_generation_attempts: int = 3
    generation_timeout_seconds: int = 300
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    skill_type_keywords: Dict[str, List[str]] = field(default_factory=lambda: {
        "web_scraping": ["scrape", "web", "url", "website", "html", "crawl"],
        "api_integration": ["api", "rest", "http", "endpoint", "request"],
        "file_operations": ["file", "read", "write", "save", "load", "csv", "json"],
        "data_processing": ["data", "process", "analyze", "filter", "sort", "calculate"],
        "communication": ["email", "send", "mail", "notify", "message"],
        "image_processing": ["image", "photo", "picture", "resize", "convert"],
        "text_processing": ["text", "string", "parse", "extract", "format"],
        "general": [] # Default for others
    })
    skill_name_min_keyword_length: int = 3
    skill_name_stopwords: List[str] = field(default_factory=lambda: [
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'can', 'could', 'may', 'might', 'must', 'for', 'with', 'from', 'to',
        'in', 'on', 'at', 'by'
    ])
    skill_name_max_parts: int = 3
    skill_name_default_parts: List[str] = field(default_factory=lambda: ['auto', 'skill'])
    generation_history_max_size: int = 1000
    generation_history_trim_to_size: int = 500
    
    # Self-healing
    auto_healing_enabled: bool = True
    max_healing_attempts: int = 3
    healing_timeout_seconds: int = 300
    rollback_enabled: bool = True
    regeneration_enabled: bool = True
    
    # Hot reload
    hot_reload_enabled: bool = True
    reload_debounce_seconds: float = 2.0
    
    # Documentation
    auto_docs_enabled: bool = True
    doc_quality_threshold: float = 0.6
    doc_generation_timeout: int = 120
    
    # Marketplace
    marketplace_enabled: bool = True
    auto_sync_enabled: bool = False
    sync_interval_seconds: int = 3600
    max_file_size_mb: int = 10
    validation_timeout_seconds: int = 300
    quarantine_suspicious: bool = True
    
    # Security
    security_scanning_enabled: bool = True
    sandbox_execution: bool = True
    validate_generated_code: bool = True
    max_execution_time_seconds: int = 300
    max_memory_mb: int = 256
    max_cpu_percent: float = 50.0
    network_isolation: bool = True
    file_system_isolation: bool = True
    
    # Optimization
    optimization_enabled: bool = True
    benchmark_interval_seconds: int = 3600
    optimization_threshold: float = 0.1  # 10% improvement needed
    ab_test_duration_seconds: int = 86400  # 24 hours
    max_concurrent_tests: int = 3
    
    # Meta-building
    meta_building_enabled: bool = True
    self_analysis_interval_seconds: int = 3600
    improvement_threshold: float = 0.15
    confidence_threshold: float = 0.8
    rollback_threshold: float = -0.05
    
    # Dependency graph
    dependency_analysis_enabled: bool = True
    graph_update_interval_seconds: int = 1800  # 30 minutes
    circular_dependency_detection: bool = True
    
    # Audit logging
    audit_logging_enabled: bool = True
    audit_retention_days: int = 30
    audit_export_enabled: bool = True
    
    # Performance
    performance_monitoring_enabled: bool = True
    performance_history_days: int = 30
    
    # Ports and networking
    ui_port: int = 12000
    api_port: int = 12001
    websocket_port: int = 12002
    allow_cors: bool = True
    allow_iframes: bool = True
    
    # External sources
    default_external_sources: List[Dict[str, Any]] = field(default_factory=lambda: [
        {
            "name": "happyos_community",
            "type": "git_repo",
            "url": "https://github.com/happyos/community-skills.git",
            "trusted": True,
            "auto_sync": False
        }
    ])
    
    # Blacklisted patterns for security
    security_patterns: Dict[str, List[str]] = field(default_factory=lambda: {
        "dangerous_imports": [
            r"import\s+os\s*$",
            r"import\s+subprocess\s*$",
            r"import\s+sys\s*$",
            r"from\s+os\s+import",
            r"from\s+subprocess\s+import"
        ],
        "dangerous_functions": [
            r"os\.system\s*\(",
            r"subprocess\.call\s*\(",
            r"subprocess\.run\s*\(",
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__\s*\(",
            r"open\s*\([^)]*['\"]w['\"]"
        ],
        "suspicious_strings": [
            "/etc/passwd", "/etc/shadow", "rm -rf", "sudo", "chmod 777",
            "wget", "curl", "nc ", "netcat", "bash -i", "/bin/sh"
        ]
    })


def get_self_building_config() -> SelfBuildingConfig:
    """Get self-building configuration with environment variable overrides."""
    
    config = SelfBuildingConfig()
    
    # Override with environment variables
    config.base_path = os.getenv("HAPPYOS_BASE_PATH", config.base_path)
    config.skills_directory = os.getenv("HAPPYOS_SKILLS_DIR", config.skills_directory)
    config.plugins_directory = os.getenv("HAPPYOS_PLUGINS_DIR", config.plugins_directory)
    config.mcp_servers_directory = os.getenv("HAPPYOS_MCP_DIR", config.mcp_servers_directory)
    
    config.docs_directory = os.getenv("HAPPYOS_DOCS_DIR", config.docs_directory)
    config.logs_directory = os.getenv("HAPPYOS_LOGS_DIR", config.logs_directory)
    config.marketplace_directory = os.getenv("HAPPYOS_MARKETPLACE_DIR", config.marketplace_directory)
    config.sandbox_directory = os.getenv("HAPPYOS_SANDBOX_DIR", config.sandbox_directory)
    
    # Boolean settings
    config.auto_generation_enabled = os.getenv("HAPPYOS_AUTO_GENERATION", "true").lower() == "true"
    config.auto_healing_enabled = os.getenv("HAPPYOS_AUTO_HEALING", "true").lower() == "true"
    config.hot_reload_enabled = os.getenv("HAPPYOS_HOT_RELOAD", "true").lower() == "true"
    config.auto_docs_enabled = os.getenv("HAPPYOS_AUTO_DOCS", "true").lower() == "true"
    config.marketplace_enabled = os.getenv("HAPPYOS_MARKETPLACE", "true").lower() == "true"
    config.security_scanning_enabled = os.getenv("HAPPYOS_SECURITY_SCAN", "true").lower() == "true"
    config.sandbox_execution = os.getenv("HAPPYOS_SANDBOX", "true").lower() == "true"
    config.optimization_enabled = os.getenv("HAPPYOS_OPTIMIZATION", "true").lower() == "true"
    config.meta_building_enabled = os.getenv("HAPPYOS_META_BUILDING", "true").lower() == "true"
    
    # Numeric settings
    config.scan_interval_seconds = int(os.getenv("HAPPYOS_SCAN_INTERVAL", str(config.scan_interval_seconds)))
    config.max_generation_attempts = int(os.getenv("HAPPYOS_MAX_GEN_ATTEMPTS", str(config.max_generation_attempts)))
    config.generation_timeout_seconds = int(os.getenv("HAPPYOS_GEN_TIMEOUT", str(config.generation_timeout_seconds)))
    config.max_healing_attempts = int(os.getenv("HAPPYOS_MAX_HEAL_ATTEMPTS", str(config.max_healing_attempts)))
    config.healing_timeout_seconds = int(os.getenv("HAPPYOS_HEAL_TIMEOUT", str(config.healing_timeout_seconds)))
    
    # LLM settings
    config.llm_model = os.getenv("HAPPYOS_LLM_MODEL", config.llm_model)
    config.llm_temperature = float(os.getenv("HAPPYOS_LLM_TEMPERATURE", str(config.llm_temperature)))
    config.llm_max_tokens = int(os.getenv("HAPPYOS_LLM_MAX_TOKENS", str(config.llm_max_tokens)))
    
    # Security settings
    config.max_execution_time_seconds = int(os.getenv("HAPPYOS_MAX_EXEC_TIME", str(config.max_execution_time_seconds)))
    config.max_memory_mb = int(os.getenv("HAPPYOS_MAX_MEMORY", str(config.max_memory_mb)))
    config.max_cpu_percent = float(os.getenv("HAPPYOS_MAX_CPU", str(config.max_cpu_percent)))
    config.network_isolation = os.getenv("HAPPYOS_NETWORK_ISOLATION", "true").lower() == "true"
    config.file_system_isolation = os.getenv("HAPPYOS_FS_ISOLATION", "true").lower() == "true"
    
    # Container runtime
    config.container_runtime = os.getenv("HAPPYOS_CONTAINER_RUNTIME", config.container_runtime)
    
    # Ports
    config.ui_port = int(os.getenv("HAPPYOS_UI_PORT", str(config.ui_port)))
    config.api_port = int(os.getenv("HAPPYOS_API_PORT", str(config.api_port)))
    config.websocket_port = int(os.getenv("HAPPYOS_WS_PORT", str(config.websocket_port)))
    
    return config


def validate_config(config: SelfBuildingConfig) -> List[str]:
    """Validate configuration and return list of issues."""
    
    issues = []
    
    # Check required directories
    required_dirs = [
        config.base_path,
        config.skills_directory,
        config.plugins_directory,
        config.mcp_servers_directory
    ]
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory {dir_path}: {e}")
    
    # Check numeric ranges
    if config.max_generation_attempts < 1:
        issues.append("max_generation_attempts must be >= 1")
    
    if config.max_healing_attempts < 1:
        issues.append("max_healing_attempts must be >= 1")
    
    if config.generation_timeout_seconds < 10:
        issues.append("generation_timeout_seconds must be >= 10")
    
    if config.healing_timeout_seconds < 10:
        issues.append("healing_timeout_seconds must be >= 10")
    
    if config.llm_temperature < 0 or config.llm_temperature > 2:
        issues.append("llm_temperature must be between 0 and 2")
    
    if config.llm_max_tokens < 100:
        issues.append("llm_max_tokens must be >= 100")
    
    if config.max_memory_mb < 64:
        issues.append("max_memory_mb must be >= 64")
    
    if config.max_cpu_percent < 10 or config.max_cpu_percent > 100:
        issues.append("max_cpu_percent must be between 10 and 100")
    
    # Check ports
    if config.ui_port < 1024 or config.ui_port > 65535:
        issues.append("ui_port must be between 1024 and 65535")
    
    if config.api_port < 1024 or config.api_port > 65535:
        issues.append("api_port must be between 1024 and 65535")
    
    if config.websocket_port < 1024 or config.websocket_port > 65535:
        issues.append("websocket_port must be between 1024 and 65535")
    
    return issues


def create_default_config_file(file_path: str = "/home/mr/Dokument/filee.tar/happyos/self_building_config.json"):
    """Create a default configuration file."""
    
    import json
    from dataclasses import asdict
    
    config = SelfBuildingConfig()
    config_dict = asdict(config)
    
    # Convert Path objects to strings
    for key, value in config_dict.items():
        if isinstance(value, Path):
            config_dict[key] = str(value)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config_dict, f, indent=2)
    
    print(f"Default configuration created at: {file_path}")


def load_config_from_file(file_path: str) -> SelfBuildingConfig:
    """Load configuration from a JSON file."""
    
    import json
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        # Create config object with loaded values
        config = SelfBuildingConfig()
        
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
        
    except Exception as e:
        print(f"Error loading config from {file_path}: {e}")
        print("Using default configuration")
        return SelfBuildingConfig()


# Global configuration instance
_config = None


def get_config() -> SelfBuildingConfig:
    """Get the global configuration instance."""
    
    global _config
    
    if _config is None:
        # Try to load from file first
        config_file = "/home/mr/Dokument/filee.tar/happyos/self_building_config.json"
        if Path(config_file).exists():
            _config = load_config_from_file(config_file)
        else:
            _config = get_self_building_config()
        
        # Validate configuration
        issues = validate_config(_config)
        if issues:
            print("Configuration issues found:")
            for issue in issues:
                print(f"  - {issue}")
    
    return _config


def reload_config():
    """Reload configuration from environment and files."""
    
    global _config
    _config = None
    return get_config()


# Export main functions
__all__ = [
    "SelfBuildingConfig",
    "get_self_building_config", 
    "get_config",
    "reload_config",
    "validate_config",
    "create_default_config_file",
    "load_config_from_file"
]