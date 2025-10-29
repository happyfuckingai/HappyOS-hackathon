#!/usr/bin/env python3
"""
Configuration Validation Script

This script validates the MeetMind backend configuration without starting the full application.
Useful for CI/CD pipelines and deployment validation.

Usage:
    python scripts/validate_config.py [--env-file .env] [--fail-fast] [--verbose]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from modules.config import settings, validate_configuration, validate_secrets_strength
    from modules.config.settings import ConfigurationError
except ImportError as e:
    print(f"Error importing configuration modules: {e}")
    print("Make sure you're running this script from the backend directory")
    sys.exit(1)


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def validate_environment_file(env_file: str) -> bool:
    """Validate that environment file exists and is readable"""
    if not os.path.exists(env_file):
        logging.error(f"Environment file not found: {env_file}")
        return False
    
    if not os.access(env_file, os.R_OK):
        logging.error(f"Environment file not readable: {env_file}")
        return False
    
    # Check file permissions (should not be world-readable)
    stat_info = os.stat(env_file)
    if stat_info.st_mode & 0o044:  # World or group readable
        logging.warning(f"Environment file {env_file} has overly permissive permissions")
        logging.warning("Consider running: chmod 600 {env_file}")
    
    return True


def print_configuration_summary():
    """Print a summary of the current configuration"""
    print("\n" + "="*60)
    print("CONFIGURATION SUMMARY")
    print("="*60)
    
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Backend Host: {settings.BACKEND_HOST}")
    print(f"Backend Port: {settings.BACKEND_PORT}")
    print(f"Debug Mode: {settings.BACKEND_DEBUG}")
    print(f"Log Level: {settings.LOG_LEVEL}")
    
    print(f"\nConfiguration Validation:")
    print(f"  Fail Fast: {settings.FAIL_FAST_ON_CONFIG_ERROR}")
    print(f"  Validate Secrets: {settings.VALIDATE_SECRETS_ON_STARTUP}")
    
    print(f"\nExternal Secret Management:")
    print(f"  AWS Secrets Manager: {settings.AWS_SECRETS_MANAGER_ENABLED}")
    print(f"  HashiCorp Vault: {settings.VAULT_ENABLED}")
    
    print(f"\nServices Configuration:")
    print(f"  Database: {'✓' if settings.DATABASE_URL else '✗'}")
    print(f"  OpenAI: {'✓' if settings.OPENAI_API_KEY else '✗'}")
    print(f"  Google AI: {'✓' if settings.GOOGLE_AI_API_KEY else '✗'}")
    print(f"  Anthropic: {'✓' if settings.ANTHROPIC_API_KEY else '✗'}")
    print(f"  LiveKit: {'✓' if settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY else '✗'}")
    print(f"  Supabase: {'✓' if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY else '✗'}")
    print(f"  Qdrant: {'✓' if settings.QDRANT_URL else '✗'}")
    print(f"  Redis: {'✓' if settings.REDIS_URL else '✗'}")
    print(f"  Sentry: {'✓' if settings.SENTRY_DSN else '✗'}")


def validate_secrets() -> Dict[str, List[str]]:
    """Validate secret strength and return results"""
    print("\n" + "="*60)
    print("SECRET VALIDATION")
    print("="*60)
    
    if not settings.VALIDATE_SECRETS_ON_STARTUP:
        print("Secret validation is disabled")
        return {}
    
    try:
        secret_results = validate_secrets_strength()
        
        for secret_name, issues in secret_results.items():
            if issues:
                if any("not configured" in issue for issue in issues):
                    print(f"{secret_name}: Not configured")
                else:
                    print(f"{secret_name}: {len(issues)} issues")
                    for issue in issues:
                        print(f"  - {issue}")
            else:
                print(f"{secret_name}: ✓ Valid")
        
        return secret_results
        
    except Exception as e:
        logging.error(f"Secret validation failed: {e}")
        return {"validation_error": [str(e)]}


def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(
        description="Validate MeetMind backend configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/validate_config.py
    python scripts/validate_config.py --env-file .env.production
    python scripts/validate_config.py --fail-fast --verbose
        """
    )
    
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file (default: .env)"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Exit immediately on critical errors"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--secrets-only",
        action="store_true",
        help="Only validate secrets, skip other configuration"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    print("MeetMind Backend Configuration Validator")
    print("="*60)
    
    # Validate environment file
    if not validate_environment_file(args.env_file):
        sys.exit(1)
    
    print(f"Using environment file: {args.env_file}")
    
    # Load environment file
    from dotenv import load_dotenv
    load_dotenv(args.env_file)
    
    # Reload settings after loading environment
    from modules.config.settings import Settings
    global settings
    settings = Settings()
    
    try:
        # Print configuration summary
        if not args.secrets_only:
            print_configuration_summary()
        
        # Validate secrets
        secret_results = validate_secrets()
        
        # Validate overall configuration
        if not args.secrets_only:
            print("\n" + "="*60)
            print("CONFIGURATION VALIDATION")
            print("="*60)
            
            try:
                validation_messages = validate_configuration(fail_fast=args.fail_fast)
                
                if not validation_messages:
                    print("✓ All configuration validation passed")
                else:
                    critical_count = len([msg for msg in validation_messages if "CRITICAL" in msg])
                    warning_count = len(validation_messages) - critical_count
                    
                    if critical_count > 0:
                        print(f"✗ {critical_count} critical errors found:")
                        for msg in validation_messages:
                            if "CRITICAL" in msg:
                                print(f"  ERROR: {msg}")
                    
                    if warning_count > 0:
                        print(f"⚠ {warning_count} warnings found:")
                        for msg in validation_messages:
                            if "CRITICAL" not in msg:
                                print(f"  WARNING: {msg}")
                    
                    if critical_count > 0:
                        print(f"\n✗ Configuration validation failed with {critical_count} critical errors")
                        sys.exit(1)
                    else:
                        print(f"\n⚠ Configuration validation passed with {warning_count} warnings")
                        
            except ConfigurationError as e:
                print(f"✗ Configuration validation failed: {e}")
                sys.exit(1)
        
        # Summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        
        # Count secret issues
        total_secrets = len(secret_results)
        secrets_with_issues = len([name for name, issues in secret_results.items() if issues])
        
        if secrets_with_issues == 0:
            print("✓ All secrets are properly configured")
        else:
            print(f"⚠ {secrets_with_issues}/{total_secrets} secrets have issues")
        
        if settings.ENVIRONMENT == "production":
            print("\nProduction Environment Checklist:")
            checklist = [
                ("JWT_SECRET_KEY is secure", len(settings.SECRET_KEY) >= 32 and settings.SECRET_KEY not in ["your-secret-key", "change-me"]),
                ("Debug mode disabled", not settings.BACKEND_DEBUG),
                ("Fail-fast enabled", settings.FAIL_FAST_ON_CONFIG_ERROR),
                ("Secret validation enabled", settings.VALIDATE_SECRETS_ON_STARTUP),
                ("AI service configured", bool(settings.OPENAI_API_KEY or settings.GOOGLE_AI_API_KEY or settings.ANTHROPIC_API_KEY)),
                ("LiveKit configured", bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY)),
                ("Production database", not settings.DATABASE_URL.startswith("sqlite:")),
                ("External secrets enabled", settings.AWS_SECRETS_MANAGER_ENABLED or settings.VAULT_ENABLED),
            ]
            
            for check_name, passed in checklist:
                status = "✓" if passed else "✗"
                print(f"  {status} {check_name}")
        
        print(f"\n✓ Configuration validation completed successfully")
        
    except Exception as e:
        logging.error(f"Validation failed with unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()