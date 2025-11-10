"""
Graph Visualizer - Creates live visualizations of the dependency graph.
Supports Graphviz, D3.js, and interactive web-based visualizations.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

try:
    import graphviz
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False

from .graph_analyzer import dependency_analyzer, DependencyNode, CircularDependency

logger = logging.getLogger(__name__)


class GraphVisualizer:
    """
    Creates various visualizations of the dependency graph.
    Supports static (Graphviz) and interactive (D3.js) formats.
    """
    
    def __init__(self, output_dir: str = "/home/mr/Dokument/filee.tar/happyos/logs/dependency_graphs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Visualization settings
        self.settings = {
            "node_colors": {
                "skills": "#4CAF50",      # Green
                "plugins": "#2196F3",     # Blue  
                "mcp_servers": "#FF9800", # Orange
                "core": "#9C27B0",        # Purple
                "generated": "#FFC107"    # Amber
            },
            "edge_colors": {
                "import": "#666666",
                "function_call": "#999999",
                "inheritance": "#FF5722",
                "composition": "#795548"
            },
            "layout": "dot",  # dot, neato, fdp, sfdp, circo, twopi
            "show_labels": True,
            "show_edge_labels": False,
            "cluster_by_type": True
        }
    
    async def generate_all_visualizations(self) -> Dict[str, str]:
        """Generate all types of visualizations."""
        
        results = {}
        
        try:
            # Graphviz visualizations
            if GRAPHVIZ_AVAILABLE:
                results["graphviz_svg"] = await self.generate_graphviz_visualization("svg")
                results["graphviz_png"] = await self.generate_graphviz_visualization("png")
                results["graphviz_pdf"] = await self.generate_graphviz_visualization("pdf")
            
            # D3.js data
            results["d3_json"] = await self.generate_d3_data()
            
            # Interactive HTML
            results["interactive_html"] = await self.generate_interactive_html()
            
            # Circular dependency report
            results["circular_deps_html"] = await self.generate_circular_dependency_report()
            
            logger.info(f"Generated {len(results)} visualizations")
            return results
            
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")
            return {}
    
    async def generate_graphviz_visualization(self, format: str = "svg") -> Optional[str]:
        """Generate a Graphviz visualization of the dependency graph."""
        
        if not GRAPHVIZ_AVAILABLE:
            logger.warning("Graphviz not available")
            return None
        
        try:
            # Create Graphviz graph
            dot = graphviz.Digraph(
                name='dependency_graph',
                comment='HappyOS Dependency Graph',
                format=format,
                engine=self.settings["layout"]
            )
            
            # Set graph attributes
            dot.attr(rankdir='TB', size='12,8', dpi='300')
            dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
            dot.attr('edge', fontname='Arial', fontsize='10')
            
            # Add clusters if enabled
            if self.settings["cluster_by_type"]:
                await self._add_clusters_to_graphviz(dot)
            else:
                await self._add_nodes_to_graphviz(dot)
            
            # Add edges
            await self._add_edges_to_graphviz(dot)
            
            # Generate output
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dependency_graph_{timestamp}"
            
            output_path = self.output_dir / filename
            dot.render(str(output_path), cleanup=True)
            
            final_path = f"{output_path}.{format}"
            logger.info(f"Generated Graphviz visualization: {final_path}")
            
            return final_path
            
        except Exception as e:
            logger.error(f"Error generating Graphviz visualization: {e}")
            return None
    
    async def _add_clusters_to_graphviz(self, dot):
        """Add clustered nodes to Graphviz graph."""
        
        # Group nodes by type
        nodes_by_type = {}
        for node_name, node in dependency_analyzer.nodes.items():
            if node.type not in nodes_by_type:
                nodes_by_type[node.type] = []
            nodes_by_type[node.type].append((node_name, node))
        
        # Create clusters
        for node_type, nodes in nodes_by_type.items():
            with dot.subgraph(name=f'cluster_{node_type}') as cluster:
                cluster.attr(label=f'{node_type.title()}', style='filled', 
                           fillcolor='lightgrey', fontsize='16', fontweight='bold')
                
                for node_name, node in nodes:
                    color = self.settings["node_colors"].get(node_type, "#CCCCCC")
                    
                    # Add auto-generated indicator
                    if "auto_generated" in node.metadata and node.metadata["auto_generated"]:
                        color = self.settings["node_colors"]["generated"]
                    
                    label = node_name
                    if self.settings["show_labels"]:
                        label += f"\\n({len(node.imports)} imports)"
                    
                    cluster.node(node_name, label=label, fillcolor=color)
    
    async def _add_nodes_to_graphviz(self, dot):
        """Add individual nodes to Graphviz graph."""
        
        for node_name, node in dependency_analyzer.nodes.items():
            color = self.settings["node_colors"].get(node.type, "#CCCCCC")
            
            # Add auto-generated indicator
            if "auto_generated" in node.metadata and node.metadata["auto_generated"]:
                color = self.settings["node_colors"]["generated"]
            
            label = node_name
            if self.settings["show_labels"]:
                label += f"\\n{node.type}\\n({len(node.imports)} imports)"
            
            dot.node(node_name, label=label, fillcolor=color)
    
    async def _add_edges_to_graphviz(self, dot):
        """Add edges to Graphviz graph."""
        
        for (source, target), edge in dependency_analyzer.edges.items():
            color = self.settings["edge_colors"].get(edge.edge_type, "#666666")
            
            # Edge style based on strength
            style = "solid"
            if edge.strength < 0.5:
                style = "dashed"
            elif edge.strength < 0.3:
                style = "dotted"
            
            label = ""
            if self.settings["show_edge_labels"]:
                label = edge.edge_type
            
            dot.edge(source, target, label=label, color=color, style=style)
    
    async def generate_d3_data(self) -> Optional[str]:
        """Generate D3.js compatible JSON data."""
        
        try:
            # Prepare nodes data
            nodes = []
            for node_name, node in dependency_analyzer.nodes.items():
                nodes.append({
                    "id": node_name,
                    "name": node_name,
                    "type": node.type,
                    "group": self._get_node_group(node.type),
                    "imports": len(node.imports),
                    "exports": len(node.exports),
                    "path": node.path,
                    "auto_generated": node.metadata.get("auto_generated", False),
                    "size": self._calculate_node_size(node)
                })
            
            # Prepare links data
            links = []
            for (source, target), edge in dependency_analyzer.edges.items():
                links.append({
                    "source": source,
                    "target": target,
                    "type": edge.edge_type,
                    "strength": edge.strength,
                    "value": edge.strength * 10  # For D3 visualization
                })
            
            # Add circular dependencies
            circular_deps = []
            for cd in dependency_analyzer.circular_dependencies:
                circular_deps.append({
                    "cycle": cd.cycle,
                    "severity": cd.severity,
                    "impact_score": cd.impact_score,
                    "detected_at": cd.detected_at.isoformat()
                })
            
            # Create complete data structure
            d3_data = {
                "nodes": nodes,
                "links": links,
                "circular_dependencies": circular_deps,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "node_count": len(nodes),
                    "link_count": len(links),
                    "circular_count": len(circular_deps)
                }
            }
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dependency_graph_d3_{timestamp}.json"
            output_path = self.output_dir / filename
            
            with open(output_path, 'w') as f:
                json.dump(d3_data, f, indent=2)
            
            logger.info(f"Generated D3.js data: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating D3.js data: {e}")
            return None
    
    def _get_node_group(self, node_type: str) -> int:
        """Get numeric group for D3.js visualization."""
        
        type_groups = {
            "skills": 1,
            "plugins": 2,
            "mcp_servers": 3,
            "core": 4
        }
        
        return type_groups.get(node_type, 0)
    
    def _calculate_node_size(self, node: DependencyNode) -> int:
        """Calculate node size based on connections and importance."""
        
        base_size = 10
        import_factor = len(node.imports) * 2
        export_factor = len(node.exports) * 3
        
        return base_size + import_factor + export_factor
    
    async def generate_interactive_html(self) -> Optional[str]:
        """Generate an interactive HTML visualization."""
        
        try:
            # Get D3 data
            d3_data_path = await self.generate_d3_data()
            if not d3_data_path:
                return None
            
            # Read D3 data
            with open(d3_data_path, 'r') as f:
                d3_data = json.load(f)
            
            # Create HTML template
            html_template = self._get_interactive_html_template()
            
            # Replace placeholders
            html_content = html_template.replace(
                "{{GRAPH_DATA}}", 
                json.dumps(d3_data, indent=2)
            )
            
            # Save HTML file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dependency_graph_interactive_{timestamp}.html"
            output_path = self.output_dir / filename
            
            with open(output_path, 'w') as f:
                f.write(html_content)
            
            logger.info(f"Generated interactive HTML: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating interactive HTML: {e}")
            return None
    
    def _get_interactive_html_template(self) -> str:
        """Get the HTML template for interactive visualization."""
        
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HappyOS Dependency Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        
        .controls {
            margin-bottom: 20px;
            text-align: center;
        }
        
        .controls button {
            margin: 0 5px;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            background: #007bff;
            color: white;
            cursor: pointer;
        }
        
        .controls button:hover {
            background: #0056b3;
        }
        
        .graph-container {
            border: 1px solid #ddd;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .node {
            stroke: #fff;
            stroke-width: 2px;
            cursor: pointer;
        }
        
        .link {
            stroke: #999;
            stroke-opacity: 0.6;
        }
        
        .node-label {
            font-size: 12px;
            text-anchor: middle;
            pointer-events: none;
        }
        
        .tooltip {
            position: absolute;
            padding: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 4px;
            pointer-events: none;
            font-size: 12px;
            z-index: 1000;
        }
        
        .legend {
            margin-top: 20px;
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 15px;
        }
        
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .stats {
            margin-top: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }
        
        .stat-label {
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 HappyOS Dependency Graph</h1>
        
        <div class="controls">
            <button onclick="restartSimulation()">Restart Layout</button>
            <button onclick="toggleLabels()">Toggle Labels</button>
            <button onclick="highlightCircularDeps()">Highlight Circular Dependencies</button>
            <button onclick="resetHighlight()">Reset Highlight</button>
        </div>
        
        <div class="graph-container">
            <svg id="graph"></svg>
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background-color: #4CAF50;"></div>
                <span>Skills</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #2196F3;"></div>
                <span>Plugins</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FF9800;"></div>
                <span>MCP Servers</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #9C27B0;"></div>
                <span>Core</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFC107;"></div>
                <span>Auto-Generated</span>
            </div>
        </div>
        
        <div class="stats" id="stats"></div>
    </div>
    
    <div class="tooltip" id="tooltip" style="display: none;"></div>
    
    <script>
        // Graph data
        const graphData = {{GRAPH_DATA}};
        
        // Set up SVG
        const width = 1160;
        const height = 600;
        
        const svg = d3.select("#graph")
            .attr("width", width)
            .attr("height", height);
        
        // Color scale
        const colorScale = d3.scaleOrdinal()
            .domain([1, 2, 3, 4])
            .range(["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]);
        
        // Create simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => d.size + 5));
        
        // Create links
        const link = svg.append("g")
            .selectAll("line")
            .data(graphData.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.value));
        
        // Create nodes
        const node = svg.append("g")
            .selectAll("circle")
            .data(graphData.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.size)
            .attr("fill", d => d.auto_generated ? "#FFC107" : colorScale(d.group))
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", showTooltip)
            .on("mouseout", hideTooltip);
        
        // Create labels
        const labels = svg.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .enter().append("text")
            .attr("class", "node-label")
            .text(d => d.name)
            .style("display", "block");
        
        // Update positions on simulation tick
        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            labels
                .attr("x", d => d.x)
                .attr("y", d => d.y + 4);
        });
        
        // Drag functions
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        // Tooltip functions
        function showTooltip(event, d) {
            const tooltip = d3.select("#tooltip");
            tooltip.style("display", "block")
                .html(`
                    <strong>${d.name}</strong><br>
                    Type: ${d.type}<br>
                    Imports: ${d.imports}<br>
                    Exports: ${d.exports}<br>
                    Auto-generated: ${d.auto_generated ? 'Yes' : 'No'}
                `)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px");
        }
        
        function hideTooltip() {
            d3.select("#tooltip").style("display", "none");
        }
        
        // Control functions
        function restartSimulation() {
            simulation.alpha(1).restart();
        }
        
        let labelsVisible = true;
        function toggleLabels() {
            labelsVisible = !labelsVisible;
            labels.style("display", labelsVisible ? "block" : "none");
        }
        
        function highlightCircularDeps() {
            // Reset all styles
            node.attr("stroke", "#fff").attr("stroke-width", 2);
            link.attr("stroke", "#999").attr("stroke-opacity", 0.6);
            
            // Highlight circular dependencies
            graphData.circular_dependencies.forEach(cd => {
                cd.cycle.forEach(nodeName => {
                    node.filter(d => d.id === nodeName)
                        .attr("stroke", "#ff0000")
                        .attr("stroke-width", 4);
                });
            });
        }
        
        function resetHighlight() {
            node.attr("stroke", "#fff").attr("stroke-width", 2);
            link.attr("stroke", "#999").attr("stroke-opacity", 0.6);
        }
        
        // Display stats
        function displayStats() {
            const stats = document.getElementById("stats");
            stats.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${graphData.metadata.node_count}</div>
                    <div class="stat-label">Components</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${graphData.metadata.link_count}</div>
                    <div class="stat-label">Dependencies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${graphData.metadata.circular_count}</div>
                    <div class="stat-label">Circular Dependencies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${graphData.nodes.filter(n => n.auto_generated).length}</div>
                    <div class="stat-label">Auto-Generated</div>
                </div>
            `;
        }
        
        // Initialize
        displayStats();
    </script>
</body>
</html>'''
    
    async def generate_circular_dependency_report(self) -> Optional[str]:
        """Generate a detailed report of circular dependencies."""
        
        try:
            if not dependency_analyzer.circular_dependencies:
                logger.info("No circular dependencies found")
                return None
            
            html_content = self._get_circular_dependency_html()
            
            # Save HTML file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"circular_dependencies_report_{timestamp}.html"
            output_path = self.output_dir / filename
            
            with open(output_path, 'w') as f:
                f.write(html_content)
            
            logger.info(f"Generated circular dependency report: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating circular dependency report: {e}")
            return None
    
    def _get_circular_dependency_html(self) -> str:
        """Generate HTML content for circular dependency report."""
        
        circular_deps_html = ""
        
        for i, cd in enumerate(dependency_analyzer.circular_dependencies):
            severity_color = {
                "low": "#28a745",
                "medium": "#ffc107", 
                "high": "#fd7e14",
                "critical": "#dc3545"
            }.get(cd.severity, "#6c757d")
            
            cycle_path = " → ".join(cd.cycle + [cd.cycle[0]])
            
            circular_deps_html += f'''
            <div class="circular-dep" style="border-left: 4px solid {severity_color};">
                <h3>Circular Dependency #{i+1}</h3>
                <p><strong>Severity:</strong> <span style="color: {severity_color};">{cd.severity.upper()}</span></p>
                <p><strong>Impact Score:</strong> {cd.impact_score:.2f}</p>
                <p><strong>Detected:</strong> {cd.detected_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Cycle:</strong></p>
                <div class="cycle-path">{cycle_path}</div>
                <p><strong>Components Involved:</strong> {len(cd.cycle)}</p>
            </div>
            '''
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Circular Dependencies Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }}
        
        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }}
        
        .summary {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 30px;
        }}
        
        .circular-dep {{
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        
        .cycle-path {{
            background: #e9ecef;
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            margin: 10px 0;
        }}
        
        .severity-low {{ color: #28a745; }}
        .severity-medium {{ color: #ffc107; }}
        .severity-high {{ color: #fd7e14; }}
        .severity-critical {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 Circular Dependencies Report</h1>
        
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Total Circular Dependencies:</strong> {len(dependency_analyzer.circular_dependencies)}</p>
            <p><strong>Report Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        {circular_deps_html}
    </div>
</body>
</html>'''


# Global visualizer instance
graph_visualizer = GraphVisualizer()


# Convenience functions
async def generate_dependency_visualizations() -> Dict[str, str]:
    """Generate all dependency visualizations."""
    return await graph_visualizer.generate_all_visualizations()


async def generate_interactive_graph() -> Optional[str]:
    """Generate interactive HTML dependency graph."""
    return await graph_visualizer.generate_interactive_html()