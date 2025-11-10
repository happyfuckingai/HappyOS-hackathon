"""
Live Dependency Graph Analyzer.
Analyzes and tracks dependencies between components in real-time.
"""

import ast
import logging
import asyncio
import networkx as nx
from typing import Dict, Any, List, Set, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from ...discovery.component_scanner import component_scanner, ComponentInfo
from ...registry.dynamic_registry import dynamic_registry

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """Represents a node in the dependency graph."""
    name: str
    type: str  # 'skill', 'plugin', 'mcp_server', 'module'
    path: str
    imports: Set[str] = field(default_factory=set)
    exports: Set[str] = field(default_factory=set)
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    last_analyzed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyEdge:
    """Represents an edge in the dependency graph."""
    source: str
    target: str
    edge_type: str  # 'import', 'function_call', 'inheritance', 'composition'
    strength: float = 1.0  # How strong the dependency is
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircularDependency:
    """Represents a circular dependency."""
    cycle: List[str]
    severity: str  # 'low', 'medium', 'high', 'critical'
    impact_score: float
    detected_at: datetime = field(default_factory=datetime.now)


class LiveDependencyAnalyzer:
    """
    Analyzes dependencies between components in real-time.
    Maintains a live dependency graph that updates automatically.
    """
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, DependencyNode] = {}
        self.edges: Dict[Tuple[str, str], DependencyEdge] = {}
        self.circular_dependencies: List[CircularDependency] = []
        
        # Analysis cache
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        self.last_full_analysis = None
        
        # Real-time tracking
        self.change_listeners: List[callable] = []
        self.analysis_in_progress = False
    
    async def initialize(self):
        """Initialize the dependency analyzer."""
        logger.info("Initializing live dependency analyzer...")
        
        # Perform initial full analysis
        await self.perform_full_analysis()
        
        # Set up change monitoring
        await self._setup_change_monitoring()
        
        logger.info("Live dependency analyzer initialized")
    
    async def perform_full_analysis(self):
        """Perform a complete dependency analysis of the system."""
        
        if self.analysis_in_progress:
            logger.debug("Analysis already in progress, skipping")
            return
        
        self.analysis_in_progress = True
        
        try:
            logger.info("Starting full dependency analysis...")
            start_time = datetime.now()
            
            # Clear existing graph
            self.graph.clear()
            self.nodes.clear()
            self.edges.clear()
            self.circular_dependencies.clear()
            
            # Step 1: Analyze all components
            await self._analyze_all_components()
            
            # Step 2: Build dependency graph
            await self._build_dependency_graph()
            
            # Step 3: Detect circular dependencies
            await self._detect_circular_dependencies()
            
            # Step 4: Calculate metrics
            await self._calculate_graph_metrics()
            
            self.last_full_analysis = datetime.now()
            analysis_time = (self.last_full_analysis - start_time).total_seconds()
            
            logger.info(f"Full dependency analysis completed in {analysis_time:.2f}s")
            logger.info(f"Graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
            
            # Notify listeners
            await self._notify_change_listeners("full_analysis_complete")
            
        except Exception as e:
            logger.error(f"Error during full dependency analysis: {e}")
            raise
        finally:
            self.analysis_in_progress = False
    
    async def _analyze_all_components(self):
        """Analyze all discovered components for dependencies."""
        
        # Get all discovered components
        components = component_scanner.list_components()
        
        for component in components:
            await self._analyze_component(component)
    
    async def _analyze_component(self, component: ComponentInfo) -> DependencyNode:
        """Analyze a single component for dependencies."""
        
        try:
            # Check cache first
            cache_key = f"{component.path}:{component.last_modified.timestamp()}"
            if cache_key in self.analysis_cache:
                cached_result = self.analysis_cache[cache_key]
                return self._create_node_from_cache(component, cached_result)
            
            # Read and parse the component file
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
            
            # Extract dependencies
            imports = self._extract_imports(tree)
            exports = self._extract_exports(tree, component.name)
            function_calls = self._extract_function_calls(tree)
            class_dependencies = self._extract_class_dependencies(tree)
            
            # Create dependency node
            node = DependencyNode(
                name=component.name,
                type=component.type,
                path=component.path,
                imports=imports,
                exports=exports,
                last_analyzed=datetime.now(),
                metadata={
                    "function_calls": function_calls,
                    "class_dependencies": class_dependencies,
                    "file_size": len(content),
                    "line_count": len(content.split('\n'))
                }
            )
            
            # Cache the result
            self.analysis_cache[cache_key] = {
                "imports": imports,
                "exports": exports,
                "function_calls": function_calls,
                "class_dependencies": class_dependencies
            }
            
            self.nodes[component.name] = node
            return node
            
        except Exception as e:
            logger.error(f"Error analyzing component {component.name}: {e}")
            return None
    
    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """Extract import statements from AST."""
        
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    for alias in node.names:
                        imports.add(f"{node.module}.{alias.name}")
        
        return imports
    
    def _extract_exports(self, tree: ast.AST, component_name: str) -> Set[str]:
        """Extract exported functions and classes from AST."""
        
        exports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_'):  # Public functions
                    exports.add(f"{component_name}.{node.name}")
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith('_'):  # Public classes
                    exports.add(f"{component_name}.{node.name}")
        
        return exports
    
    def _extract_function_calls(self, tree: ast.AST) -> List[str]:
        """Extract function calls from AST."""
        
        calls = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        calls.append(f"{node.func.value.id}.{node.func.attr}")
        
        return calls
    
    def _extract_class_dependencies(self, tree: ast.AST) -> List[str]:
        """Extract class inheritance dependencies from AST."""
        
        dependencies = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        dependencies.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        if isinstance(base.value, ast.Name):
                            dependencies.append(f"{base.value.id}.{base.attr}")
        
        return dependencies
    
    async def _build_dependency_graph(self):
        """Build the NetworkX dependency graph from analyzed nodes."""
        
        # Add all nodes to graph
        for node_name, node in self.nodes.items():
            self.graph.add_node(node_name, **{
                "type": node.type,
                "path": node.path,
                "imports_count": len(node.imports),
                "exports_count": len(node.exports)
            })
        
        # Add edges based on dependencies
        for node_name, node in self.nodes.items():
            # Import dependencies
            for import_name in node.imports:
                target_node = self._find_node_by_import(import_name)
                if target_node:
                    edge = DependencyEdge(
                        source=node_name,
                        target=target_node,
                        edge_type="import",
                        strength=1.0
                    )
                    self.edges[(node_name, target_node)] = edge
                    self.graph.add_edge(node_name, target_node, **{
                        "type": "import",
                        "strength": 1.0
                    })
            
            # Function call dependencies
            for call in node.metadata.get("function_calls", []):
                target_node = self._find_node_by_function_call(call)
                if target_node and target_node != node_name:
                    edge = DependencyEdge(
                        source=node_name,
                        target=target_node,
                        edge_type="function_call",
                        strength=0.5
                    )
                    edge_key = (node_name, target_node)
                    if edge_key not in self.edges:
                        self.edges[edge_key] = edge
                        self.graph.add_edge(node_name, target_node, **{
                            "type": "function_call",
                            "strength": 0.5
                        })
    
    def _find_node_by_import(self, import_name: str) -> Optional[str]:
        """Find a node that matches an import statement."""
        
        # Direct module match
        for node_name, node in self.nodes.items():
            if import_name in node.exports:
                return node_name
            
            # Check if import matches component module
            if import_name.endswith(node_name):
                return node_name
        
        return None
    
    def _find_node_by_function_call(self, call: str) -> Optional[str]:
        """Find a node that provides a function call."""
        
        for node_name, node in self.nodes.items():
            if call in node.exports:
                return node_name
            
            # Check for partial matches
            if '.' in call:
                module_part = call.split('.')[0]
                if module_part == node_name:
                    return node_name
        
        return None
    
    async def _detect_circular_dependencies(self):
        """Detect circular dependencies in the graph."""
        
        try:
            # Find all strongly connected components
            sccs = list(nx.strongly_connected_components(self.graph))
            
            for scc in sccs:
                if len(scc) > 1:  # Circular dependency found
                    # Find the actual cycle
                    subgraph = self.graph.subgraph(scc)
                    try:
                        cycle = nx.find_cycle(subgraph, orientation='original')
                        cycle_nodes = [edge[0] for edge in cycle]
                        
                        # Calculate severity
                        severity = self._calculate_cycle_severity(cycle_nodes)
                        impact_score = self._calculate_impact_score(cycle_nodes)
                        
                        circular_dep = CircularDependency(
                            cycle=cycle_nodes,
                            severity=severity,
                            impact_score=impact_score
                        )
                        
                        self.circular_dependencies.append(circular_dep)
                        
                        logger.warning(f"Circular dependency detected: {' -> '.join(cycle_nodes)}")
                        
                    except nx.NetworkXNoCycle:
                        # No cycle found in this SCC
                        pass
                        
        except Exception as e:
            logger.error(f"Error detecting circular dependencies: {e}")
    
    def _calculate_cycle_severity(self, cycle_nodes: List[str]) -> str:
        """Calculate the severity of a circular dependency."""
        
        # Simple heuristic based on cycle length and node types
        cycle_length = len(cycle_nodes)
        
        # Check if any critical components are involved
        critical_types = {'orchestrator', 'registry', 'core'}
        has_critical = any(
            any(crit in self.nodes[node].type.lower() for crit in critical_types)
            for node in cycle_nodes if node in self.nodes
        )
        
        if has_critical:
            return "critical"
        elif cycle_length > 5:
            return "high"
        elif cycle_length > 3:
            return "medium"
        else:
            return "low"
    
    def _calculate_impact_score(self, cycle_nodes: List[str]) -> float:
        """Calculate the impact score of a circular dependency."""
        
        # Calculate based on number of dependents
        total_dependents = 0
        for node in cycle_nodes:
            if node in self.nodes:
                total_dependents += len(self.nodes[node].dependents)
        
        # Normalize to 0-1 scale
        max_possible_dependents = len(self.nodes) * len(cycle_nodes)
        if max_possible_dependents > 0:
            return min(total_dependents / max_possible_dependents, 1.0)
        
        return 0.0
    
    async def _calculate_graph_metrics(self):
        """Calculate various metrics for the dependency graph."""
        
        if not self.graph.nodes():
            return
        
        # Basic metrics
        metrics = {
            "node_count": len(self.graph.nodes()),
            "edge_count": len(self.graph.edges()),
            "density": nx.density(self.graph),
            "is_dag": nx.is_directed_acyclic_graph(self.graph),
            "circular_dependencies": len(self.circular_dependencies)
        }
        
        # Centrality measures
        try:
            metrics["betweenness_centrality"] = nx.betweenness_centrality(self.graph)
            metrics["in_degree_centrality"] = nx.in_degree_centrality(self.graph)
            metrics["out_degree_centrality"] = nx.out_degree_centrality(self.graph)
        except Exception as e:
            logger.warning(f"Error calculating centrality measures: {e}")
        
        # Store metrics in graph
        self.graph.graph["metrics"] = metrics
        
        logger.info(f"Graph metrics: {metrics}")
    
    async def _setup_change_monitoring(self):
        """Set up monitoring for changes in components."""
        
        # This would integrate with the hot reload manager
        # to detect when components change and trigger re-analysis
        pass
    
    async def _notify_change_listeners(self, event_type: str):
        """Notify all change listeners of graph updates."""
        
        for listener in self.change_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event_type, self)
                else:
                    listener(event_type, self)
            except Exception as e:
                logger.error(f"Error notifying change listener: {e}")
    
    def add_change_listener(self, listener: callable):
        """Add a listener for graph changes."""
        self.change_listeners.append(listener)
    
    def get_dependency_path(self, source: str, target: str) -> Optional[List[str]]:
        """Get the dependency path between two components."""
        
        try:
            if source in self.graph and target in self.graph:
                return nx.shortest_path(self.graph, source, target)
        except nx.NetworkXNoPath:
            pass
        
        return None
    
    def get_component_dependencies(self, component_name: str) -> Dict[str, Any]:
        """Get all dependencies for a specific component."""
        
        if component_name not in self.graph:
            return {}
        
        # Direct dependencies (outgoing edges)
        dependencies = list(self.graph.successors(component_name))
        
        # Direct dependents (incoming edges)
        dependents = list(self.graph.predecessors(component_name))
        
        # Transitive dependencies
        transitive_deps = set()
        for dep in dependencies:
            transitive_deps.update(nx.descendants(self.graph, dep))
        
        return {
            "direct_dependencies": dependencies,
            "direct_dependents": dependents,
            "transitive_dependencies": list(transitive_deps),
            "dependency_count": len(dependencies),
            "dependent_count": len(dependents),
            "in_degree": self.graph.in_degree(component_name),
            "out_degree": self.graph.out_degree(component_name)
        }
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the dependency graph."""
        
        metrics = self.graph.graph.get("metrics", {})
        
        return {
            "last_analysis": self.last_full_analysis.isoformat() if self.last_full_analysis else None,
            "metrics": metrics,
            "circular_dependencies": [
                {
                    "cycle": cd.cycle,
                    "severity": cd.severity,
                    "impact_score": cd.impact_score
                }
                for cd in self.circular_dependencies
            ],
            "top_dependencies": self._get_top_dependencies(),
            "isolated_components": self._get_isolated_components()
        }
    
    def _get_top_dependencies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get components with the most dependencies."""
        
        deps = []
        for node in self.graph.nodes():
            deps.append({
                "name": node,
                "in_degree": self.graph.in_degree(node),
                "out_degree": self.graph.out_degree(node),
                "total_degree": self.graph.degree(node)
            })
        
        return sorted(deps, key=lambda x: x["total_degree"], reverse=True)[:limit]
    
    def _get_isolated_components(self) -> List[str]:
        """Get components with no dependencies."""
        
        isolated = []
        for node in self.graph.nodes():
            if self.graph.degree(node) == 0:
                isolated.append(node)
        
        return isolated


# Global dependency analyzer instance
dependency_analyzer = LiveDependencyAnalyzer()


# Convenience functions
async def analyze_dependencies():
    """Perform a full dependency analysis."""
    await dependency_analyzer.perform_full_analysis()


def get_component_dependencies(component_name: str) -> Dict[str, Any]:
    """Get dependencies for a specific component."""
    return dependency_analyzer.get_component_dependencies(component_name)


def get_dependency_graph_summary() -> Dict[str, Any]:
    """Get a summary of the dependency graph."""
    return dependency_analyzer.get_graph_summary()