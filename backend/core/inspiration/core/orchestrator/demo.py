"""
Demo script showing how to use the orchestrator implementations.

This script demonstrates the usage of both Basic and Ultimate orchestrators
and shows how they can be used interchangeably while providing different
levels of functionality.
"""

import asyncio
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import orchestrators
from . import create_basic_orchestrator, create_ultimate_orchestrator, create_default_orchestrator
from .orchestrator_core import ProcessingResult


async def demo_basic_orchestrator():
    """Demonstrate basic orchestrator functionality."""
    print("=== Basic Self-Building Orchestrator Demo ===")
    
    # Create and initialize orchestrator
    orchestrator = await create_basic_orchestrator()
    
    # Check initialization status
    stats = orchestrator.get_basic_stats()
    print(f"Initialization status: {stats}")
    
    # Process some sample requests
    sample_requests = [
        "Hello, how are you?",
        "Create a function that calculates fibonacci numbers",
        "What is the weather today?",
        "Generate a report of sales data"
    ]
    
    for request in sample_requests:
        print(f"\nProcessing request: '{request}'")
        try:
            result = await orchestrator.process_request(request)
            print(f"Success: {result.success}")
            print(f"Message: {result.message}")
            print(f"Strategy used: {result.strategy_used}")
            print(f"Execution time: {result.execution_time:.2f}s")
            if result.skill_used:
                print(f"Skill used: {result.skill_used}")
            if result.new_skill_created:
                print(f"New skill created: {result.new_skill_created}")
        except Exception as e:
            print(f"Error processing request: {e}")
    
    # Show final statistics
    final_stats = orchestrator.get_performance_stats()
    print(f"\nFinal performance stats: {final_stats}")


async def demo_ultimate_orchestrator():
    """Demonstrate ultimate orchestrator functionality."""
    print("\n=== Ultimate Self-Building Orchestrator Demo ===")
    
    # Create and initialize orchestrator
    orchestrator = await create_ultimate_orchestrator()
    
    # Check initialization status
    stats = orchestrator.get_advanced_stats()
    print(f"Initialization status: {stats}")
    
    # Process some sample requests
    sample_requests = [
        "Create a machine learning model to predict stock prices",
        "Design a microservice architecture for e-commerce",
        "Implement a blockchain-based voting system",
        "Optimize database queries for high-traffic application"
    ]
    
    context = {
        "user_id": "demo_user",
        "session_id": "demo_session_123",
        "preferences": {"language": "english", "detail_level": "comprehensive"}
    }
    
    for request in sample_requests:
        print(f"\nProcessing advanced request: '{request}'")
        try:
            result = await orchestrator.process_request(request, context)
            print(f"Success: {result.success}")
            print(f"Message: {result.message}")
            print(f"Strategy used: {result.strategy_used}")
            print(f"Execution time: {result.execution_time:.2f}s")
            print(f"Confidence score: {result.confidence_score:.2f}")
            if result.skill_used:
                print(f"Skill used: {result.skill_used}")
            if result.new_skill_created:
                print(f"New skill created: {result.new_skill_created}")
            if result.agent_used:
                print(f"Agent used: {result.agent_used}")
            if result.metadata:
                print(f"Metadata: {result.metadata}")
        except Exception as e:
            print(f"Error processing request: {e}")
    
    # Show final statistics
    final_stats = orchestrator.get_advanced_stats()
    print(f"\nFinal advanced stats: {final_stats}")


async def demo_interchangeable_usage():
    """Demonstrate how orchestrators can be used interchangeably."""
    print("\n=== Interchangeable Orchestrator Usage Demo ===")
    
    # Function that works with any orchestrator
    async def process_with_any_orchestrator(orchestrator, request: str, context: Dict[str, Any] = None) -> ProcessingResult:
        """Process a request with any orchestrator instance."""
        print(f"Processing with {type(orchestrator).__name__}")
        return await orchestrator.process_request(request, context or {})
    
    # Create both orchestrators
    basic_orchestrator = await create_basic_orchestrator()
    ultimate_orchestrator = await create_ultimate_orchestrator()
    
    # Same request can be processed by both
    request = "Create a function to sort a list of numbers"
    
    print(f"Request: '{request}'")
    
    # Process with basic orchestrator
    basic_result = await process_with_any_orchestrator(basic_orchestrator, request)
    print(f"Basic orchestrator result: {basic_result.success} - {basic_result.message}")
    
    # Process with ultimate orchestrator
    ultimate_result = await process_with_any_orchestrator(ultimate_orchestrator, request)
    print(f"Ultimate orchestrator result: {ultimate_result.success} - {ultimate_result.message}")


async def demo_default_selection():
    """Demonstrate default orchestrator selection."""
    print("\n=== Default Orchestrator Selection Demo ===")
    
    # Create default (basic) orchestrator
    default_orchestrator = await create_default_orchestrator(advanced=False)
    print(f"Default orchestrator (basic): {type(default_orchestrator).__name__}")
    
    # Create advanced orchestrator
    advanced_orchestrator = await create_default_orchestrator(advanced=True)
    print(f"Default orchestrator (advanced): {type(advanced_orchestrator).__name__}")


async def main():
    """Run all demos."""
    print("Orchestrator System Demo")
    print("=" * 50)
    
    try:
        await demo_basic_orchestrator()
        await demo_ultimate_orchestrator()
        await demo_interchangeable_usage()
        await demo_default_selection()
        
        print("\n=== Demo Complete ===")
        print("All orchestrator demonstrations finished successfully!")
        
    except Exception as e:
        logger.error(f"Error in demo: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
