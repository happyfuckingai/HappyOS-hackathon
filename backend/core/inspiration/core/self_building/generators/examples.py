"""
Generators Examples

This module contains practical examples of how to use the Auto-Generation system
for creating skills, plugins, and MCP servers dynamically based on user requests.
"""

import asyncio
import logging
from typing import Dict, Any, List
from pathlib import Path

from app.core.self_building.generators.skill_auto_generator import (
    SkillAutoGenerator,
    skill_auto_generator
)

logger = logging.getLogger(__name__)


async def basic_skill_generation_example():
    """Basic skill generation example."""

    print("=== Basic Skill Generation Example ===")

    # Create generator instance
    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Simple skill generation request
    user_request = "Create a skill that calculates the area of different geometric shapes"
    
    print(f"🎯 Generating skill for request: {user_request}")
    
    try:
        skill_info = await generator.generate_skill(
            user_request=user_request,
            skill_name="geometry_calculator",
            skill_type="computational"
        )
        
        if skill_info:
            print(f"✅ Skill generated successfully!")
            print(f"   Name: {skill_info.get('name')}")
            print(f"   File: {skill_info.get('file_path')}")
            print(f"   Type: {skill_info.get('type')}")
            print(f"   Description: {skill_info.get('description', 'N/A')}")
        else:
            print("❌ Skill generation failed")
    
    except Exception as e:
        print(f"❌ Error during generation: {e}")
    
    print()


async def api_integration_skill_example():
    """Example of generating an API integration skill."""

    print("=== API Integration Skill Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # API integration request
    user_request = """
    Create a skill that can get weather information for any city.
    It should use a weather API to fetch current conditions and forecast.
    Include error handling for invalid cities and API failures.
    """
    
    print(f"🌤️  Generating weather API skill...")
    
    try:
        skill_info = await generator.generate_skill(
            user_request=user_request,
            skill_name="weather_api",
            skill_type="api_integration"
        )
        
        if skill_info:
            print(f"✅ Weather skill generated!")
            print(f"   File: {skill_info.get('file_path')}")
            
            # Show generated code preview
            if 'generated_code' in skill_info:
                code_lines = skill_info['generated_code'].split('\n')[:20]
                print(f"   Code preview (first 20 lines):")
                for i, line in enumerate(code_lines, 1):
                    print(f"     {i:2d}: {line}")
                if len(skill_info['generated_code'].split('\n')) > 20:
                    print(f"     ... and more lines")
        else:
            print("❌ Weather skill generation failed")
    
    except Exception as e:
        print(f"❌ Error generating weather skill: {e}")
    
    print()


async def data_processing_skill_example():
    """Example of generating a data processing skill."""

    print("=== Data Processing Skill Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Data processing request
    user_request = """
    Create a skill for processing CSV files. It should be able to:
    - Read CSV files and validate format
    - Filter rows based on criteria
    - Perform basic statistical operations (mean, median, mode)
    - Export results to different formats (JSON, XML, another CSV)
    - Handle missing data gracefully
    """
    
    print(f"📊 Generating CSV processing skill...")
    
    try:
        skill_info = await generator.generate_skill(
            user_request=user_request,
            skill_name="csv_processor",
            skill_type="data_processing"
        )
        
        if skill_info:
            print(f"✅ CSV processing skill generated!")
            print(f"   File: {skill_info.get('file_path')}")
            print(f"   Capabilities: {skill_info.get('capabilities', [])}")
            
            # Show metadata if available
            if 'metadata' in skill_info:
                metadata = skill_info['metadata']
                print(f"   Dependencies: {metadata.get('dependencies', [])}")
                print(f"   Functions: {metadata.get('functions', [])}")
        else:
            print("❌ CSV processing skill generation failed")
    
    except Exception as e:
        print(f"❌ Error generating CSV processing skill: {e}")
    
    print()


async def custom_parameters_example():
    """Example of using custom generation parameters."""

    print("=== Custom Parameters Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Custom parameters for generation
    custom_params = {
        "complexity": "advanced",
        "include_tests": True,
        "include_documentation": True,
        "error_handling": "comprehensive",
        "performance_optimized": True,
        "dependencies": ["numpy", "pandas", "requests"],
        "style": "object_oriented"
    }
    
    user_request = """
    Create a machine learning skill that can train and evaluate classification models.
    Include support for different algorithms (SVM, Random Forest, Neural Networks).
    """
    
    print(f"🤖 Generating ML skill with custom parameters...")
    
    try:
        skill_info = await generator.generate_skill(
            user_request=user_request,
            skill_name="ml_classifier",
            skill_type="machine_learning",
            additional_context=custom_params
        )
        
        if skill_info:
            print(f"✅ ML classification skill generated!")
            print(f"   File: {skill_info.get('file_path')}")
            print(f"   Complexity: {custom_params['complexity']}")
            print(f"   Tests included: {custom_params['include_tests']}")
            print(f"   Style: {custom_params['style']}")
        else:
            print("❌ ML skill generation failed")
    
    except Exception as e:
        print(f"❌ Error generating ML skill: {e}")
    
    print()


async def iterative_refinement_example():
    """Example of iterative skill refinement."""

    print("=== Iterative Refinement Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Initial request
    initial_request = "Create a simple calculator skill"
    
    print(f"🔢 Initial generation: {initial_request}")
    
    try:
        # Generate initial skill
        skill_info = await generator.generate_skill(
            user_request=initial_request,
            skill_name="calculator_v1",
            skill_type="computational"
        )
        
        if not skill_info:
            print("❌ Initial generation failed")
            return
        
        print(f"✅ Initial calculator generated")
        
        # Refinement request
        refinement_request = """
        Enhance the existing calculator skill to include:
        - Scientific functions (sin, cos, tan, log, exp)
        - Support for complex numbers
        - Unit conversions
        - History of calculations
        - Memory functions (store, recall, clear)
        """
        
        print(f"🔧 Refining with: {refinement_request}")
        
        # Generate enhanced version
        enhanced_skill = await generator.generate_skill(
            user_request=refinement_request,
            skill_name="calculator_v2",
            skill_type="computational",
            base_skill_path=skill_info.get('file_path')  # Use previous as base
        )
        
        if enhanced_skill:
            print(f"✅ Enhanced calculator generated!")
            print(f"   Original: {skill_info.get('file_path')}")
            print(f"   Enhanced: {enhanced_skill.get('file_path')}")
        else:
            print("❌ Enhancement failed")
    
    except Exception as e:
        print(f"❌ Error during iterative refinement: {e}")
    
    print()


async def batch_generation_example():
    """Example of generating multiple skills in batch."""

    print("=== Batch Generation Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Batch of skill requests
    skill_requests = [
        {
            "user_request": "Create a skill for generating QR codes",
            "skill_name": "qr_generator",
            "skill_type": "utility"
        },
        {
            "user_request": "Create a skill for password generation and validation",
            "skill_name": "password_manager",
            "skill_type": "security"
        },
        {
            "user_request": "Create a skill for image resizing and format conversion",
            "skill_name": "image_processor",
            "skill_type": "media"
        }
    ]
    
    print(f"🏭 Batch generating {len(skill_requests)} skills...")
    
    results = []
    for i, request in enumerate(skill_requests, 1):
        print(f"  Generating {i}/{len(skill_requests)}: {request['skill_name']}")
        
        try:
            skill_info = await generator.generate_skill(**request)
            if skill_info:
                results.append({
                    "request": request,
                    "result": skill_info,
                    "success": True
                })
                print(f"    ✅ Success")
            else:
                results.append({
                    "request": request,
                    "result": None,
                    "success": False
                })
                print(f"    ❌ Failed")
        except Exception as e:
            results.append({
                "request": request,
                "result": None,
                "success": False,
                "error": str(e)
            })
            print(f"    ❌ Error: {e}")
    
    # Summary
    successful = len([r for r in results if r["success"]])
    print(f"\n📊 Batch generation results:")
    print(f"   Successful: {successful}/{len(skill_requests)}")
    print(f"   Failed: {len(skill_requests) - successful}/{len(skill_requests)}")
    
    print()


async def validation_and_testing_example():
    """Example of skill validation and testing during generation."""

    print("=== Validation and Testing Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Request with validation requirements
    user_request = """
    Create a skill for JSON validation and manipulation.
    Include comprehensive error handling and input validation.
    The skill should be thoroughly tested.
    """
    
    print(f"🔍 Generating JSON skill with validation...")
    
    try:
        skill_info = await generator.generate_skill(
            user_request=user_request,
            skill_name="json_validator",
            skill_type="data_processing",
            validate_generated=True,  # Enable validation
            generate_tests=True       # Generate tests
        )
        
        if skill_info:
            print(f"✅ JSON validation skill generated!")
            print(f"   File: {skill_info.get('file_path')}")
            
            # Show validation results
            if 'validation_results' in skill_info:
                validation = skill_info['validation_results']
                print(f"   Validation passed: {validation.get('passed', False)}")
                if 'errors' in validation:
                    print(f"   Validation errors: {len(validation['errors'])}")
            
            # Show test results
            if 'test_results' in skill_info:
                tests = skill_info['test_results']
                print(f"   Tests passed: {tests.get('passed', 0)}")
                print(f"   Tests failed: {tests.get('failed', 0)}")
        else:
            print("❌ JSON skill generation failed")
    
    except Exception as e:
        print(f"❌ Error during validation: {e}")
    
    print()


async def global_generator_example():
    """Example using the global generator instance."""

    print("=== Global Generator Example ===")

    # Use the global skill_auto_generator instance
    print("🌐 Using global generator instance...")
    
    try:
        # Initialize if needed
        await skill_auto_generator.initialize()
        
        # Simple generation using global instance
        skill_info = await skill_auto_generator.generate_skill(
            user_request="Create a skill for URL shortening and expansion",
            skill_name="url_shortener",
            skill_type="web_utility"
        )
        
        if skill_info:
            print(f"✅ URL shortener skill generated via global instance!")
            print(f"   File: {skill_info.get('file_path')}")
        else:
            print("❌ Global generation failed")
    
    except Exception as e:
        print(f"❌ Error with global generator: {e}")
    
    print()


async def generation_monitoring_example():
    """Example of monitoring generation performance and statistics."""

    print("=== Generation Monitoring Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Monitor generation statistics
    print("📊 Generation monitoring...")
    
    import time
    start_time = time.time()
    
    # Generate a skill with timing
    user_request = "Create a skill for text sentiment analysis"
    
    skill_info = await generator.generate_skill(
        user_request=user_request,
        skill_name="sentiment_analyzer",
        skill_type="nlp"
    )
    
    generation_time = time.time() - start_time
    
    print(f"⏱️  Generation Performance:")
    print(f"   Request: {user_request}")
    print(f"   Duration: {generation_time:.2f} seconds")
    
    if skill_info:
        print(f"   Success: Yes")
        print(f"   File size: {Path(skill_info.get('file_path', '')).stat().st_size if Path(skill_info.get('file_path', '')).exists() else 'N/A'} bytes")
        print(f"   Lines of code: {skill_info.get('generated_code', '').count('\\n') if 'generated_code' in skill_info else 'N/A'}")
    else:
        print(f"   Success: No")
    
    print()


async def error_handling_example():
    """Example of handling generation errors gracefully."""

    print("=== Error Handling Example ===")

    generator = SkillAutoGenerator()
    await generator.initialize()
    
    # Test various error scenarios
    error_scenarios = [
        {
            "name": "Invalid skill name",
            "request": {
                "user_request": "Create a test skill",
                "skill_name": "invalid/skill/name",  # Invalid characters
                "skill_type": "test"
            }
        },
        {
            "name": "Empty request",
            "request": {
                "user_request": "",  # Empty request
                "skill_name": "empty_skill",
                "skill_type": "test"
            }
        },
        {
            "name": "Complex impossible request",
            "request": {
                "user_request": "Create a skill that can travel through time and predict the future with 100% accuracy",
                "skill_name": "time_travel",
                "skill_type": "impossible"
            }
        }
    ]
    
    print(f"🚨 Testing error handling scenarios...")
    
    for scenario in error_scenarios:
        print(f"\n  Testing: {scenario['name']}")
        
        try:
            skill_info = await generator.generate_skill(**scenario['request'])
            
            if skill_info:
                print(f"    ✅ Unexpectedly succeeded")
            else:
                print(f"    ❌ Failed as expected")
        
        except Exception as e:
            print(f"    ❌ Error (expected): {type(e).__name__}: {e}")
    
    print()


async def run_all_examples():
    """Run all skill generation examples."""
    
    print("🚀 Starting Skill Auto-Generation Examples")
    print("=" * 60)
    
    try:
        await basic_skill_generation_example()
        await api_integration_skill_example()
        await data_processing_skill_example()
        await custom_parameters_example()
        await iterative_refinement_example()
        await batch_generation_example()
        await validation_and_testing_example()
        await global_generator_example()
        await generation_monitoring_example()
        await error_handling_example()
        
        print("✅ All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        print(f"❌ Examples failed: {e}")


# Convenience functions for common generation tasks
async def quick_generation_demo():
    """Quick demonstration of skill generation capabilities."""
    
    print("🎯 Quick Skill Generation Demo")
    print("-" * 35)
    
    try:
        # Quick generation using global instance
        await skill_auto_generator.initialize()
        
        skill_info = await skill_auto_generator.generate_skill(
            user_request="Create a simple greeting skill that says hello in different languages",
            skill_name="multilingual_greeter",
            skill_type="utility"
        )
        
        if skill_info:
            print(f"✅ Demo skill generated!")
            print(f"   Name: {skill_info.get('name')}")
            print(f"   File: {skill_info.get('file_path')}")
        else:
            print("❌ Demo generation failed")
    
    except Exception as e:
        print(f"❌ Demo error: {e}")
    
    print("✅ Quick demo completed!")


async def generate_utility_skill(description: str, name: str = None):
    """Generate a utility skill with simplified interface."""
    
    if not name:
        # Auto-generate name from description
        name = description.lower().replace(" ", "_")[:30]
    
    print(f"🔧 Generating utility skill: {name}")
    
    try:
        await skill_auto_generator.initialize()
        
        skill_info = await skill_auto_generator.generate_skill(
            user_request=description,
            skill_name=name,
            skill_type="utility"
        )
        
        if skill_info:
            print(f"✅ Utility skill generated: {skill_info.get('file_path')}")
            return skill_info
        else:
            print(f"❌ Failed to generate utility skill")
            return None
    
    except Exception as e:
        print(f"❌ Utility generation error: {e}")
        return None


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())