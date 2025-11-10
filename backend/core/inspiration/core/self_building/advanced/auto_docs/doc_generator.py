"""
Auto-Documentation Generator - Automatically generates documentation for all components.
Creates README.md files, API docs, usage examples, and performance metrics.
"""

import ast
import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

from app.config.settings import get_settings
from app.llm.router import get_llm_client
from app.core.error_handler import safe_execute

from ...discovery.component_scanner import component_scanner, ComponentInfo
from ...registry.dynamic_registry import dynamic_registry
from ...intelligence.audit_logger import audit_logger

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ComponentDocumentation:
    """Documentation for a component."""
    component_name: str
    component_type: str
    description: str
    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    usage_examples: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    auto_generated: bool = False
    last_updated: datetime = field(default_factory=datetime.now)
    quality_score: float = 0.0


@dataclass
class DocumentationQuality:
    """Quality assessment of documentation."""
    completeness_score: float  # 0-1
    clarity_score: float       # 0-1
    example_score: float       # 0-1
    overall_score: float       # 0-1
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class AutoDocumentationGenerator:
    """
    Automatically generates comprehensive documentation for all components.
    Creates README files, API documentation, and usage examples.
    """
    
    def __init__(self):
        self.llm_client = None
        self.docs_dir = Path("/home/mr/Dokument/filee.tar/happyos/docs")
        self.component_docs_dir = self.docs_dir / "components"
        self.api_docs_dir = self.docs_dir / "api"
        
        # Ensure directories exist
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.component_docs_dir.mkdir(parents=True, exist_ok=True)
        self.api_docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Documentation cache
        self.documentation_cache: Dict[str, ComponentDocumentation] = {}
        
        # Quality thresholds
        self.quality_thresholds = {
            "minimum_score": 0.6,
            "good_score": 0.8,
            "excellent_score": 0.9
        }
        
        # Statistics
        self.stats = {
            "total_documented": 0,
            "auto_generated_docs": 0,
            "quality_issues": 0,
            "last_full_generation": None
        }
    
    async def initialize(self):
        """Initialize the auto-documentation generator."""
        
        try:
            self.llm_client = await get_llm_client()
            
            # Load existing documentation
            await self._load_existing_documentation()
            
            logger.info("Auto-documentation generator initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize auto-documentation generator: {e}")
            raise
    
    async def generate_all_documentation(self) -> Dict[str, Any]:
        """Generate documentation for all components."""
        
        try:
            logger.info("Starting full documentation generation...")
            start_time = datetime.now()
            
            # Get all components
            components = component_scanner.list_components()
            
            results = {
                "total_components": len(components),
                "documented": 0,
                "failed": 0,
                "updated": 0,
                "created": 0
            }
            
            for component in components:
                try:
                    doc_result = await self.generate_component_documentation(component)
                    
                    if doc_result["success"]:
                        results["documented"] += 1
                        if doc_result["created"]:
                            results["created"] += 1
                        else:
                            results["updated"] += 1
                    else:
                        results["failed"] += 1
                        
                except Exception as e:
                    logger.error(f"Error documenting component {component.name}: {e}")
                    results["failed"] += 1
            
            # Generate master documentation index
            await self._generate_master_index()
            
            # Generate API documentation
            await self._generate_api_documentation()
            
            generation_time = (datetime.now() - start_time).total_seconds()
            self.stats["last_full_generation"] = datetime.now()
            
            logger.info(f"Documentation generation completed in {generation_time:.2f}s")
            logger.info(f"Results: {results}")
            
            return {
                **results,
                "generation_time": generation_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error during full documentation generation: {e}")
            return {"error": str(e)}
    
    async def generate_component_documentation(self, component: ComponentInfo) -> Dict[str, Any]:
        """Generate documentation for a specific component."""
        
        try:
            logger.info(f"Generating documentation for: {component.name}")
            
            # Check if documentation already exists and is up to date
            existing_doc = self.documentation_cache.get(component.name)
            if (existing_doc and 
                existing_doc.last_updated > component.last_modified and
                existing_doc.quality_score >= self.quality_thresholds["minimum_score"]):
                
                logger.debug(f"Documentation for {component.name} is up to date")
                return {"success": True, "created": False, "reason": "up_to_date"}
            
            # Analyze component code
            code_analysis = await self._analyze_component_code(component)
            
            if not code_analysis:
                logger.error(f"Failed to analyze component code: {component.name}")
                return {"success": False, "error": "code_analysis_failed"}
            
            # Generate documentation using LLM
            doc_content = await self._generate_documentation_content(component, code_analysis)
            
            if not doc_content:
                logger.error(f"Failed to generate documentation content: {component.name}")
                return {"success": False, "error": "content_generation_failed"}
            
            # Create documentation object
            documentation = ComponentDocumentation(
                component_name=component.name,
                component_type=component.type,
                description=doc_content["description"],
                functions=code_analysis["functions"],
                classes=code_analysis["classes"],
                dependencies=code_analysis["dependencies"],
                usage_examples=doc_content["usage_examples"],
                auto_generated=component.metadata.get("auto_generated", False),
                last_updated=datetime.now()
            )
            
            # Assess documentation quality
            quality = await self._assess_documentation_quality(documentation)
            documentation.quality_score = quality.overall_score
            
            # Save documentation to files
            created = await self._save_documentation_files(documentation, doc_content)
            
            # Cache documentation
            self.documentation_cache[component.name] = documentation
            
            # Update statistics
            self.stats["total_documented"] += 1
            if documentation.auto_generated:
                self.stats["auto_generated_docs"] += 1
            if quality.overall_score < self.quality_thresholds["minimum_score"]:
                self.stats["quality_issues"] += 1
            
            # Log to audit system
            await audit_logger.log_event(
                audit_logger.AuditEventType.COMPONENT_REGISTERED,  # Using existing event type
                component_name=component.name,
                details={
                    "documentation_generated": True,
                    "quality_score": quality.overall_score,
                    "auto_generated": documentation.auto_generated
                }
            )
            
            logger.info(f"Documentation generated for {component.name} (quality: {quality.overall_score:.2f})")
            
            return {
                "success": True,
                "created": created,
                "quality_score": quality.overall_score,
                "issues": quality.issues
            }
            
        except Exception as e:
            logger.error(f"Error generating documentation for {component.name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _analyze_component_code(self, component: ComponentInfo) -> Optional[Dict[str, Any]]:
        """Analyze component code to extract documentation information."""
        
        try:
            # Read component file
            file_path = Path(component.path)
            if not file_path.exists():
                logger.warning(f"Component file not found: {component.path}")
                return None
            
            content = file_path.read_text(encoding='utf-8')
            
            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                logger.warning(f"Syntax error in {component.path}: {e}")
                return None
            
            # Extract information
            analysis = {
                "functions": self._extract_functions(tree),
                "classes": self._extract_classes(tree),
                "dependencies": self._extract_imports(tree),
                "docstrings": self._extract_docstrings(tree),
                "complexity": self._calculate_complexity(tree),
                "line_count": len(content.split('\n')),
                "file_size": len(content)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing component code: {e}")
            return None
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract function information from AST."""
        
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node),
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "is_public": not node.name.startswith('_'),
                    "line_number": node.lineno,
                    "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list]
                }
                
                # Extract return annotation
                if node.returns:
                    func_info["return_type"] = self._get_annotation_string(node.returns)
                
                # Extract argument types
                func_info["typed_args"] = []
                for arg in node.args.args:
                    arg_info = {"name": arg.arg}
                    if arg.annotation:
                        arg_info["type"] = self._get_annotation_string(arg.annotation)
                    func_info["typed_args"].append(arg_info)
                
                functions.append(func_info)
        
        return functions
    
    def _extract_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract class information from AST."""
        
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "bases": [self._get_annotation_string(base) for base in node.bases],
                    "methods": [],
                    "is_public": not node.name.startswith('_'),
                    "line_number": node.lineno
                }
                
                # Extract methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_info = {
                            "name": item.name,
                            "args": [arg.arg for arg in item.args.args],
                            "docstring": ast.get_docstring(item),
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "is_public": not item.name.startswith('_'),
                            "is_property": any(
                                self._get_decorator_name(dec) == "property" 
                                for dec in item.decorator_list
                            )
                        }
                        class_info["methods"].append(method_info)
                
                classes.append(class_info)
        
        return classes
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements from AST."""
        
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")
        
        return imports
    
    def _extract_docstrings(self, tree: ast.AST) -> Dict[str, str]:
        """Extract all docstrings from AST."""
        
        docstrings = {}
        
        # Module docstring
        module_docstring = ast.get_docstring(tree)
        if module_docstring:
            docstrings["module"] = module_docstring
        
        # Function and class docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                docstring = ast.get_docstring(node)
                if docstring:
                    docstrings[node.name] = docstring
        
        return docstrings
    
    def _calculate_complexity(self, tree: ast.AST) -> Dict[str, int]:
        """Calculate code complexity metrics."""
        
        complexity = {
            "cyclomatic": 1,  # Base complexity
            "functions": 0,
            "classes": 0,
            "branches": 0,
            "loops": 0
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity["functions"] += 1
            elif isinstance(node, ast.ClassDef):
                complexity["classes"] += 1
            elif isinstance(node, (ast.If, ast.While, ast.For, ast.Try)):
                complexity["cyclomatic"] += 1
                if isinstance(node, (ast.If,)):
                    complexity["branches"] += 1
                elif isinstance(node, (ast.While, ast.For)):
                    complexity["loops"] += 1
        
        return complexity
    
    def _get_decorator_name(self, decorator) -> str:
        """Get decorator name from AST node."""
        
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        else:
            return str(decorator)
    
    def _get_annotation_string(self, annotation) -> str:
        """Get string representation of type annotation."""
        
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return f"{self._get_annotation_string(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.Subscript):
            return f"{self._get_annotation_string(annotation.value)}[{self._get_annotation_string(annotation.slice)}]"
        else:
            return str(annotation)
    
    async def _generate_documentation_content(
        self, 
        component: ComponentInfo, 
        code_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate documentation content using LLM."""
        
        try:
            # Create prompt for documentation generation
            prompt = self._create_documentation_prompt(component, code_analysis)
            
            # Generate documentation
            response = await safe_execute(
                self.llm_client.generate,
                prompt,
                max_tokens=2000,
                temperature=0.3
            )
            
            if not response:
                return None
            
            # Parse response to extract structured content
            doc_content = self._parse_documentation_response(response)
            
            return doc_content
            
        except Exception as e:
            logger.error(f"Error generating documentation content: {e}")
            return None
    
    def _create_documentation_prompt(
        self, 
        component: ComponentInfo, 
        code_analysis: Dict[str, Any]
    ) -> str:
        """Create prompt for LLM documentation generation."""
        
        functions_info = "\n".join([
            f"- {func['name']}({', '.join(func['args'])}): {func.get('docstring', 'No docstring')}"
            for func in code_analysis["functions"] if func["is_public"]
        ])
        
        classes_info = "\n".join([
            f"- {cls['name']}: {cls.get('docstring', 'No docstring')}"
            for cls in code_analysis["classes"] if cls["is_public"]
        ])
        
        return f"""
Generate comprehensive documentation for this HappyOS component:

COMPONENT NAME: {component.name}
COMPONENT TYPE: {component.type}
AUTO-GENERATED: {component.metadata.get('auto_generated', False)}

CODE ANALYSIS:
Functions:
{functions_info}

Classes:
{classes_info}

Dependencies: {', '.join(code_analysis['dependencies'][:10])}
Complexity: {code_analysis['complexity']['cyclomatic']} cyclomatic complexity

Please provide:
1. A clear description of what this component does
2. Usage examples showing how to use the main functions
3. Any important notes about dependencies or requirements
4. Performance considerations if applicable

Format your response as JSON with these keys:
- description: Clear description of the component
- usage_examples: Array of code examples
- notes: Array of important notes
- performance_notes: Performance considerations
"""
    
    def _parse_documentation_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract documentation content."""
        
        try:
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                return json.loads(response)
            
            # Fallback: extract content manually
            lines = response.split('\n')
            
            doc_content = {
                "description": "",
                "usage_examples": [],
                "notes": [],
                "performance_notes": ""
            }
            
            current_section = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                
                if "description" in line.lower():
                    current_section = "description"
                elif "usage" in line.lower() or "example" in line.lower():
                    current_section = "usage_examples"
                elif "note" in line.lower():
                    current_section = "notes"
                elif "performance" in line.lower():
                    current_section = "performance_notes"
                elif line and current_section:
                    current_content.append(line)
            
            # Simple fallback description
            if not doc_content["description"]:
                doc_content["description"] = f"A {component.type} component that provides functionality for the HappyOS system."
            
            return doc_content
            
        except Exception as e:
            logger.error(f"Error parsing documentation response: {e}")
            return {
                "description": f"A {component.type} component for the HappyOS system.",
                "usage_examples": [],
                "notes": [],
                "performance_notes": ""
            }
    
    async def _assess_documentation_quality(self, documentation: ComponentDocumentation) -> DocumentationQuality:
        """Assess the quality of generated documentation."""
        
        try:
            # Completeness score
            completeness_factors = [
                1.0 if documentation.description else 0.0,
                1.0 if documentation.usage_examples else 0.0,
                1.0 if documentation.functions else 0.0,
                0.5 if documentation.dependencies else 0.0
            ]
            completeness_score = sum(completeness_factors) / len(completeness_factors)
            
            # Clarity score (based on description length and content)
            clarity_score = 0.5  # Base score
            if documentation.description:
                desc_length = len(documentation.description)
                if desc_length > 50:
                    clarity_score += 0.3
                if desc_length > 100:
                    clarity_score += 0.2
                if any(word in documentation.description.lower() for word in ['provides', 'enables', 'allows']):
                    clarity_score += 0.1
            
            clarity_score = min(clarity_score, 1.0)
            
            # Example score
            example_score = 0.0
            if documentation.usage_examples:
                example_score = min(len(documentation.usage_examples) * 0.3, 1.0)
            
            # Overall score
            overall_score = (completeness_score * 0.4 + clarity_score * 0.4 + example_score * 0.2)
            
            # Identify issues
            issues = []
            suggestions = []
            
            if not documentation.description:
                issues.append("Missing description")
                suggestions.append("Add a clear description of what the component does")
            
            if not documentation.usage_examples:
                issues.append("Missing usage examples")
                suggestions.append("Add code examples showing how to use the component")
            
            if len(documentation.description) < 50:
                issues.append("Description too short")
                suggestions.append("Expand the description with more details")
            
            if overall_score < self.quality_thresholds["minimum_score"]:
                issues.append("Overall quality below minimum threshold")
            
            return DocumentationQuality(
                completeness_score=completeness_score,
                clarity_score=clarity_score,
                example_score=example_score,
                overall_score=overall_score,
                issues=issues,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Error assessing documentation quality: {e}")
            return DocumentationQuality(
                completeness_score=0.0,
                clarity_score=0.0,
                example_score=0.0,
                overall_score=0.0,
                issues=["Error during quality assessment"],
                suggestions=["Manual review required"]
            )
    
    async def _save_documentation_files(
        self, 
        documentation: ComponentDocumentation, 
        doc_content: Dict[str, Any]
    ) -> bool:
        """Save documentation to files."""
        
        try:
            # Create component-specific directory
            component_dir = self.component_docs_dir / documentation.component_name
            component_dir.mkdir(exist_ok=True)
            
            # Generate README.md
            readme_content = self._generate_readme_content(documentation, doc_content)
            readme_path = component_dir / "README.md"
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            # Generate API documentation if applicable
            if documentation.functions or documentation.classes:
                api_content = self._generate_api_content(documentation)
                api_path = component_dir / "API.md"
                
                with open(api_path, 'w', encoding='utf-8') as f:
                    f.write(api_content)
            
            # Save metadata
            metadata = {
                "component_name": documentation.component_name,
                "component_type": documentation.component_type,
                "auto_generated": documentation.auto_generated,
                "last_updated": documentation.last_updated.isoformat(),
                "quality_score": documentation.quality_score,
                "functions_count": len(documentation.functions),
                "classes_count": len(documentation.classes)
            }
            
            metadata_path = component_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.debug(f"Saved documentation files for: {documentation.component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving documentation files: {e}")
            return False
    
    def _generate_readme_content(
        self, 
        documentation: ComponentDocumentation, 
        doc_content: Dict[str, Any]
    ) -> str:
        """Generate README.md content."""
        
        # Auto-generated indicator
        auto_gen_badge = "![Auto-Generated](https://img.shields.io/badge/docs-auto--generated-blue)" if documentation.auto_generated else ""
        
        # Quality badge
        quality_color = "red"
        if documentation.quality_score >= self.quality_thresholds["excellent_score"]:
            quality_color = "brightgreen"
        elif documentation.quality_score >= self.quality_thresholds["good_score"]:
            quality_color = "yellow"
        elif documentation.quality_score >= self.quality_thresholds["minimum_score"]:
            quality_color = "orange"
        
        quality_badge = f"![Quality](https://img.shields.io/badge/quality-{documentation.quality_score:.1f}-{quality_color})"
        
        # Usage examples
        examples_section = ""
        if documentation.usage_examples:
            examples_section = "## Usage Examples\n\n"
            for i, example in enumerate(documentation.usage_examples, 1):
                examples_section += f"### Example {i}\n\n```python\n{example}\n```\n\n"
        
        # API reference
        api_section = ""
        if documentation.functions:
            api_section = "## Functions\n\n"
            for func in documentation.functions:
                if func["is_public"]:
                    args_str = ", ".join(func["args"])
                    api_section += f"### `{func['name']}({args_str})`\n\n"
                    if func["docstring"]:
                        api_section += f"{func['docstring']}\n\n"
                    else:
                        api_section += "No documentation available.\n\n"
        
        if documentation.classes:
            api_section += "## Classes\n\n"
            for cls in documentation.classes:
                if cls["is_public"]:
                    api_section += f"### `{cls['name']}`\n\n"
                    if cls["docstring"]:
                        api_section += f"{cls['docstring']}\n\n"
                    else:
                        api_section += "No documentation available.\n\n"
        
        # Dependencies section
        deps_section = ""
        if documentation.dependencies:
            deps_section = "## Dependencies\n\n"
            for dep in documentation.dependencies[:10]:  # Show first 10
                deps_section += f"- `{dep}`\n"
            if len(documentation.dependencies) > 10:
                deps_section += f"\n... and {len(documentation.dependencies) - 10} more\n"
            deps_section += "\n"
        
        return f"""# {documentation.component_name}

{auto_gen_badge} {quality_badge}

**Type:** {documentation.component_type.title()}  
**Last Updated:** {documentation.last_updated.strftime('%Y-%m-%d %H:%M:%S')}

## Description

{documentation.description}

{examples_section}{api_section}{deps_section}## Performance Metrics

{doc_content.get('performance_notes', 'No performance metrics available.')}

## Notes

{chr(10).join(f'- {note}' for note in doc_content.get('notes', []))}

---

*This documentation was {'automatically generated' if documentation.auto_generated else 'manually created'} for the HappyOS system.*
"""
    
    def _generate_api_content(self, documentation: ComponentDocumentation) -> str:
        """Generate API documentation content."""
        
        content = f"# {documentation.component_name} API Reference\n\n"
        
        if documentation.functions:
            content += "## Functions\n\n"
            for func in documentation.functions:
                if func["is_public"]:
                    content += f"### {func['name']}\n\n"
                    content += f"**Signature:** `{func['name']}({', '.join(func['args'])})`\n\n"
                    
                    if func.get("typed_args"):
                        content += "**Parameters:**\n\n"
                        for arg in func["typed_args"]:
                            arg_type = arg.get("type", "Any")
                            content += f"- `{arg['name']}` ({arg_type})\n"
                        content += "\n"
                    
                    if func.get("return_type"):
                        content += f"**Returns:** {func['return_type']}\n\n"
                    
                    if func["docstring"]:
                        content += f"**Description:**\n\n{func['docstring']}\n\n"
                    
                    content += "---\n\n"
        
        if documentation.classes:
            content += "## Classes\n\n"
            for cls in documentation.classes:
                if cls["is_public"]:
                    content += f"### {cls['name']}\n\n"
                    
                    if cls["bases"]:
                        content += f"**Inherits from:** {', '.join(cls['bases'])}\n\n"
                    
                    if cls["docstring"]:
                        content += f"**Description:**\n\n{cls['docstring']}\n\n"
                    
                    if cls["methods"]:
                        content += "**Methods:**\n\n"
                        for method in cls["methods"]:
                            if method["is_public"]:
                                args_str = ", ".join(method["args"])
                                content += f"- `{method['name']}({args_str})`"
                                if method["docstring"]:
                                    content += f": {method['docstring'][:100]}..."
                                content += "\n"
                        content += "\n"
                    
                    content += "---\n\n"
        
        return content
    
    async def _generate_master_index(self):
        """Generate master documentation index."""
        
        try:
            index_content = "# HappyOS Components Documentation\n\n"
            index_content += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            
            # Group by component type
            by_type = {}
            for doc in self.documentation_cache.values():
                if doc.component_type not in by_type:
                    by_type[doc.component_type] = []
                by_type[doc.component_type].append(doc)
            
            for component_type, docs in by_type.items():
                index_content += f"## {component_type.title()}\n\n"
                
                for doc in sorted(docs, key=lambda x: x.component_name):
                    quality_indicator = "🟢" if doc.quality_score >= 0.8 else "🟡" if doc.quality_score >= 0.6 else "🔴"
                    auto_indicator = "🤖" if doc.auto_generated else "👨‍💻"
                    
                    index_content += f"- [{doc.component_name}](components/{doc.component_name}/README.md) "
                    index_content += f"{quality_indicator} {auto_indicator}\n"
                
                index_content += "\n"
            
            # Statistics
            total_docs = len(self.documentation_cache)
            auto_generated = sum(1 for doc in self.documentation_cache.values() if doc.auto_generated)
            high_quality = sum(1 for doc in self.documentation_cache.values() if doc.quality_score >= 0.8)
            
            index_content += "## Statistics\n\n"
            index_content += f"- **Total Components:** {total_docs}\n"
            index_content += f"- **Auto-Generated:** {auto_generated}\n"
            index_content += f"- **High Quality (≥0.8):** {high_quality}\n"
            index_content += f"- **Coverage:** {(total_docs / max(len(component_scanner.list_components()), 1)) * 100:.1f}%\n\n"
            
            index_content += "## Legend\n\n"
            index_content += "- 🟢 High quality documentation (≥0.8)\n"
            index_content += "- 🟡 Good documentation (≥0.6)\n"
            index_content += "- 🔴 Needs improvement (<0.6)\n"
            index_content += "- 🤖 Auto-generated\n"
            index_content += "- 👨‍💻 Manually created\n"
            
            # Save index
            index_path = self.docs_dir / "README.md"
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)
            
            logger.info("Generated master documentation index")
            
        except Exception as e:
            logger.error(f"Error generating master index: {e}")
    
    async def _generate_api_documentation(self):
        """Generate consolidated API documentation."""
        
        try:
            api_content = "# HappyOS API Reference\n\n"
            api_content += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            
            # Group by component type
            by_type = {}
            for doc in self.documentation_cache.values():
                if doc.functions or doc.classes:
                    if doc.component_type not in by_type:
                        by_type[doc.component_type] = []
                    by_type[doc.component_type].append(doc)
            
            for component_type, docs in by_type.items():
                api_content += f"## {component_type.title()}\n\n"
                
                for doc in sorted(docs, key=lambda x: x.component_name):
                    api_content += f"### {doc.component_name}\n\n"
                    
                    if doc.functions:
                        public_functions = [f for f in doc.functions if f["is_public"]]
                        if public_functions:
                            api_content += "**Functions:**\n"
                            for func in public_functions:
                                args_str = ", ".join(func["args"])
                                api_content += f"- `{func['name']}({args_str})`\n"
                            api_content += "\n"
                    
                    if doc.classes:
                        public_classes = [c for c in doc.classes if c["is_public"]]
                        if public_classes:
                            api_content += "**Classes:**\n"
                            for cls in public_classes:
                                api_content += f"- `{cls['name']}`\n"
                            api_content += "\n"
                    
                    api_content += f"[Full Documentation](components/{doc.component_name}/README.md)\n\n"
            
            # Save API documentation
            api_path = self.api_docs_dir / "README.md"
            with open(api_path, 'w', encoding='utf-8') as f:
                f.write(api_content)
            
            logger.info("Generated API documentation")
            
        except Exception as e:
            logger.error(f"Error generating API documentation: {e}")
    
    async def _load_existing_documentation(self):
        """Load existing documentation from files."""
        
        try:
            for component_dir in self.component_docs_dir.iterdir():
                if component_dir.is_dir():
                    metadata_path = component_dir / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        # Create documentation object from metadata
                        doc = ComponentDocumentation(
                            component_name=metadata["component_name"],
                            component_type=metadata["component_type"],
                            description="",  # Would need to parse from README
                            auto_generated=metadata.get("auto_generated", False),
                            last_updated=datetime.fromisoformat(metadata["last_updated"]),
                            quality_score=metadata.get("quality_score", 0.0)
                        )
                        
                        self.documentation_cache[doc.component_name] = doc
            
            logger.info(f"Loaded {len(self.documentation_cache)} existing documentation entries")
            
        except Exception as e:
            logger.error(f"Error loading existing documentation: {e}")
    
    def get_documentation_stats(self) -> Dict[str, Any]:
        """Get documentation statistics."""
        
        total_components = len(component_scanner.list_components())
        documented_components = len(self.documentation_cache)
        
        quality_distribution = {
            "excellent": 0,
            "good": 0,
            "fair": 0,
            "poor": 0
        }
        
        for doc in self.documentation_cache.values():
            if doc.quality_score >= self.quality_thresholds["excellent_score"]:
                quality_distribution["excellent"] += 1
            elif doc.quality_score >= self.quality_thresholds["good_score"]:
                quality_distribution["good"] += 1
            elif doc.quality_score >= self.quality_thresholds["minimum_score"]:
                quality_distribution["fair"] += 1
            else:
                quality_distribution["poor"] += 1
        
        return {
            **self.stats,
            "total_components": total_components,
            "documented_components": documented_components,
            "coverage_percentage": (documented_components / max(total_components, 1)) * 100,
            "quality_distribution": quality_distribution,
            "average_quality_score": (
                sum(doc.quality_score for doc in self.documentation_cache.values()) / 
                max(len(self.documentation_cache), 1)
            )
        }


# Global documentation generator instance
doc_generator = AutoDocumentationGenerator()


# Convenience functions
async def generate_all_documentation() -> Dict[str, Any]:
    """Generate documentation for all components."""
    return await doc_generator.generate_all_documentation()


async def generate_component_documentation(component: ComponentInfo) -> Dict[str, Any]:
    """Generate documentation for a specific component."""
    return await doc_generator.generate_component_documentation(component)


def get_documentation_stats() -> Dict[str, Any]:
    """Get documentation statistics."""
    return doc_generator.get_documentation_stats()