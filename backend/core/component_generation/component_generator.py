"""
Component Generation Service for HappyOS.

This service uses LLM to generate React components based on natural language requests.
It leverages the NLU analysis to create functional, styled components that integrate
with the HappyOS ecosystem.
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from app.llm.openrouter import OpenRouterClient
from app.core.nlp.nlu_service import nlu_service, IntentType, EntityType

logger = logging.getLogger(__name__)


class ComponentGenerator:
    """
    Component Generation Service.

    Generates React components from natural language descriptions using LLM.
    Supports various component types with proper TypeScript types, styling, and functionality.
    """

    def __init__(self):
        self.llm_client = OpenRouterClient()
        self.templates = self._load_component_templates()
        self.generation_history = []

    def _load_component_templates(self) -> Dict[str, str]:
        """Load component templates for different types."""
        return {
            "button": """
import React from 'react';
import { Button } from '@/components/ui/button';

interface {ComponentName}Props {{
  text?: string;
  onClick?: () => void;
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  disabled?: boolean;
}}

export default function {ComponentName}({{
  text = "{DefaultText}",
  onClick,
  variant = "default",
  size = "default",
  disabled = false
}}: {ComponentName}Props) {{
  return (
    <Button
      variant={{variant}}
      size={{size}}
      onClick={{onClick}}
      disabled={{disabled}}
      className="transition-all duration-200 hover:scale-105"
    >
      {{text}}
    </Button>
  );
}}
""",
            "input": """
import React, {{ useState }} from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface {ComponentName}Props {{
  label?: string;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  type?: 'text' | 'email' | 'password' | 'number';
  required?: boolean;
}}

export default function {ComponentName}({{
  label = "{DefaultLabel}",
  placeholder = "{DefaultPlaceholder}",
  value = "",
  onChange,
  type = "text",
  required = false
}}: {ComponentName}Props) {{
  const [inputValue, setInputValue] = useState(value);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {{
    const newValue = e.target.value;
    setInputValue(newValue);
    onChange?.(newValue);
  }};

  return (
    <div className="space-y-2">
      {{label && <Label htmlFor="{componentNameLower}">{{label}}</Label>}}
      <Input
        id="{componentNameLower}"
        type={{type}}
        placeholder={{placeholder}}
        value={{inputValue}}
        onChange={{handleChange}}
        required={{required}}
        className="transition-all duration-200 focus:scale-105"
      />
    </div>
  );
}}
""",
            "card": """
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface {ComponentName}Props {{
  title?: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}}

export default function {ComponentName}({{
  title = "{DefaultTitle}",
  description,
  children,
  className = ""
}}: {ComponentName}Props) {{
  return (
    <Card className={{`transition-all duration-200 hover:shadow-lg ${{className}}`}}>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
        {{description && <CardDescription>{{description}}</CardDescription>}}
      </CardHeader>
      <CardContent>
        {{children || <p>Card content goes here...</p>}}
      </CardContent>
    </Card>
  );
}}
""",
            "dashboard": """
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface {ComponentName}Props {{
  title?: string;
  metrics?: Array<{{label: string, value: string, change?: string}}>;
}}

export default function {ComponentName}({{
  title = "{DefaultTitle}",
  metrics = [
    {{ label: "Total Users", value: "1,234", change: "+12%" }},
    {{ label: "Active Sessions", value: "89", change: "+5%" }},
    {{ label: "Revenue", value: "$12,345", change: "+8%" }}
  ]
}}: {ComponentName}Props) {{
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">{{title}}</h2>
        <Badge variant="outline">Live</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {{metrics.map((metric, index) => (
          <Card key={{index}}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{{metric.label}}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{{metric.value}}</div>
              {{metric.change && (
                <p className="text-xs text-muted-foreground">
                  {{metric.change}} from last month
                </p>
              )}}
            </CardContent>
          </Card>
        ))}}
      </div>
    </div>
  );
}}
""",
            "chart": """
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {{ LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer }} from 'recharts';

interface {ComponentName}Props {{
  title?: string;
  description?: string;
  data?: Array<{{name: string, value: number}}>;
}}

export default function {ComponentName}({{
  title = "{DefaultTitle}",
  description = "A simple line chart",
  data = [
    {{ name: 'Jan', value: 400 }},
    {{ name: 'Feb', value: 300 }},
    {{ name: 'Mar', value: 600 }},
    {{ name: 'Apr', value: 800 }},
    {{ name: 'May', value: 500 }}
  ]
}}: {ComponentName}Props) {{
  return (
    <Card>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
        <CardDescription>{{description}}</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={{300}}>
          <LineChart data={{data}}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#8884d8"
              strokeWidth={{2}}
              dot={{{{fill: '#8884d8'}}}}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}}
""",
            "form": """
import React, {{ useState }} from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface {ComponentName}Props {{
  title?: string;
  onSubmit?: (data: any) => void;
  fields?: Array<{{name: string, label: string, type: string, placeholder: string}}>;
}}

export default function {ComponentName}({{
  title = "{DefaultTitle}",
  onSubmit,
  fields = [
    {{ name: 'name', label: 'Name', type: 'text', placeholder: 'Enter your name' }},
    {{ name: 'email', label: 'Email', type: 'email', placeholder: 'Enter your email' }}
  ]
}}: {ComponentName}Props) {{
  const [formData, setFormData] = useState<any>({{}});

  const handleChange = (name: string, value: string) => {{
    setFormData(prev => ({{ ...prev, [name]: value }}));
  }};

  const handleSubmit = (e: React.FormEvent) => {{
    e.preventDefault();
    onSubmit?.(formData);
  }};

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
        <CardDescription>Fill in the form below</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={{handleSubmit}} className="space-y-4">
          {{fields.map((field, index) => (
            <div key={{index}} className="space-y-2">
              <Label htmlFor={{field.name}}>{{field.label}}</Label>
              <Input
                id={{field.name}}
                type={{field.type}}
                placeholder={{field.placeholder}}
                value={{formData[field.name] || ''}}
                onChange={{(e) => handleChange(field.name, e.target.value)}}
                required
              />
            </div>
          ))}}
          <Button type="submit" className="w-full">
            Submit
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}}
""",
            "table": """
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {{ Table, TableBody, TableCell, TableHead, TableHeader, TableRow }} from '@/components/ui/table';

interface {ComponentName}Props {{
  title?: string;
  description?: string;
  data?: Array<any>;
  columns?: Array<{{key: string, label: string}}>;
}}

export default function {ComponentName}({{
  title = "{DefaultTitle}",
  description,
  data = [
    {{ id: 1, name: 'John Doe', email: 'john@example.com', status: 'Active' }},
    {{ id: 2, name: 'Jane Smith', email: 'jane@example.com', status: 'Inactive' }}
  ],
  columns = [
    {{ key: 'name', label: 'Name' }},
    {{ key: 'email', label: 'Email' }},
    {{ key: 'status', label: 'Status' }}
  ]
}}: {ComponentName}Props) {{
  return (
    <Card>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
        {{description && <CardDescription>{{description}}</CardDescription>}}
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              {{columns.map((column, index) => (
                <TableHead key={{index}}>{{column.label}}</TableHead>
              ))}}
            </TableRow>
          </TableHeader>
          <TableBody>
            {{data.map((row, index) => (
              <TableRow key={{index}}>
                {{columns.map((column, colIndex) => (
                  <TableCell key={{colIndex}}>{{row[column.key]}}</TableCell>
                ))}}
              </TableRow>
            ))}}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}}
"""
        }

    async def generate_component(self, user_request: str, analysis_result: Dict[str, Any],
                              context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a React component based on user request and NLU analysis.

        Args:
            user_request: Original user request
            analysis_result: Result from NLU analysis
            context: Additional context

        Returns:
            Generated component data with code, metadata, and configuration
        """
        try:
            component_type = analysis_result.get("component_type", "component")
            entities = analysis_result.get("entities", [])
            action_plan = analysis_result.get("action_plan", {})

            # Generate component name
            component_name = self._generate_component_name(component_type, entities)

            # Get or create template
            template = self.templates.get(component_type, self._get_default_template())

            # Generate component code using LLM
            component_code = await self._generate_component_code(
                user_request, component_type, component_name, entities, template
            )

            # Generate component metadata
            metadata = self._generate_component_metadata(
                component_name, component_type, entities, action_plan
            )

            # Store generation history
            self.generation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user_request": user_request,
                "component_name": component_name,
                "component_type": component_type,
                "success": True
            })

            return {
                "success": True,
                "component": {
                    "name": component_name,
                    "type": component_type,
                    "code": component_code,
                    "metadata": metadata,
                    "dependencies": self._extract_dependencies(component_code),
                    "props_interface": self._extract_props_interface(component_code)
                },
                "window_config": self._generate_window_config(component_name, component_type, entities),
                "integration_code": self._generate_integration_code(component_name)
            }

        except Exception as e:
            logger.error(f"Error generating component: {e}")
            return {
                "success": False,
                "error": str(e),
                "component": None
            }

    def _generate_component_name(self, component_type: str, entities: List[Dict]) -> str:
        """Generate a descriptive component name."""
        # Check if user specified a name
        for entity in entities:
            if entity.get("type") == EntityType.COMPONENT_NAME:
                return self._camel_case(entity["value"])

        # Generate based on type and context
        base_name = component_type.replace("_", " ").title().replace(" ", "")
        return f"{base_name}Component"

    def _camel_case(self, text: str) -> str:
        """Convert text to CamelCase."""
        words = re.findall(r'\w+', text.lower())
        return ''.join(word.capitalize() for word in words)

    async def _generate_component_code(self, user_request: str, component_type: str,
                                     component_name: str, entities: List[Dict],
                                     template: str) -> str:
        """Generate component code using LLM with enhanced context."""
        # Extract entity values for context
        colors = [e["value"] for e in entities if e.get("type") == EntityType.COLOR]
        sizes = [e["value"] for e in entities if e.get("type") == EntityType.SIZE]
        properties = [e["value"] for e in entities if e.get("type") == EntityType.PROPERTY]

        # Build enhanced prompt
        prompt = f"""
Generate a React component based on this user request: "{user_request}"

Component Details:
- Type: {component_type}
- Name: {component_name}
- Colors mentioned: {', '.join(colors) if colors else 'none'}
- Sizes mentioned: {', '.join(sizes) if sizes else 'none'}
- Properties mentioned: {', '.join(properties) if properties else 'none'}

Requirements:
1. Use TypeScript with proper interfaces
2. Use Tailwind CSS for styling
3. Use shadcn/ui components where appropriate
4. Make it functional and interactive
5. Include proper error handling
6. Add smooth animations and transitions
7. Ensure responsive design
8. Follow React best practices

Base template:
{template}

Generate the complete component code with all necessary imports, interfaces, and functionality.
Return only the component code without markdown formatting or explanations.
"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )

            component_code = response["text"].strip()

            # Clean up any markdown formatting
            if component_code.startswith("```"):
                component_code = component_code.split("```")[1]
                if component_code.startswith("typescript") or component_code.startswith("tsx"):
                    component_code = component_code[10:].strip()

            return component_code

        except Exception as e:
            logger.error(f"LLM component generation failed: {e}")
            return self._generate_fallback_component(component_name, component_type)

    def _generate_fallback_component(self, component_name: str, component_type: str) -> str:
        """Generate a fallback component when LLM generation fails."""
        return f"""
import React from 'react';
import {{ Card, CardContent, CardHeader, CardTitle }} from '@/components/ui/card';

interface {component_name}Props {{
  title?: string;
}}

export default function {component_name}({{
  title = "{component_type.title()} Component"
}}: {component_name}Props) {{
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Generated {component_type} component</p>
        <p className="text-sm text-muted-foreground mt-2">
          This is a fallback component. The AI generation failed, but you can still use this component.
        </p>
      </CardContent>
    </Card>
  );
}}
"""

    def _generate_component_metadata(self, component_name: str, component_type: str,
                                   entities: List[Dict], action_plan: Dict) -> Dict[str, Any]:
        """Generate metadata for the component."""
        return {
            "name": component_name,
            "type": component_type,
            "generated_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "entities_used": entities,
            "complexity": action_plan.get("estimated_complexity", "medium"),
            "capabilities": self._infer_capabilities(component_type, entities),
            "integration_points": ["window_manager", "websocket", "ui_components"]
        }

    def _infer_capabilities(self, component_type: str, entities: List[Dict]) -> List[str]:
        """Infer component capabilities based on type and entities."""
        capabilities = []

        if component_type in ["dashboard", "chart", "table"]:
            capabilities.extend(["data_display", "visualization"])
        if component_type in ["form", "input"]:
            capabilities.extend(["data_input", "validation"])
        if component_type in ["button"]:
            capabilities.extend(["interaction", "action"])
        if component_type in ["modal", "card"]:
            capabilities.extend(["overlay", "information"])

        # Add capabilities based on entities
        for entity in entities:
            if entity.get("type") == EntityType.COLOR:
                capabilities.append("theming")
            if entity.get("type") == EntityType.SIZE:
                capabilities.append("responsive")

        return list(set(capabilities))

    def _extract_dependencies(self, component_code: str) -> List[str]:
        """Extract dependencies from component code."""
        dependencies = []

        # Common React/UI dependencies
        if 'import React' in component_code:
            dependencies.append('react')
        if 'useState' in component_code or 'useEffect' in component_code:
            dependencies.append('react')
        if 'lucide-react' in component_code:
            dependencies.append('lucide-react')
        if 'recharts' in component_code:
            dependencies.append('recharts')

        # UI component dependencies
        ui_imports = ['Button', 'Input', 'Card', 'Label', 'Table', 'Badge']
        for ui_comp in ui_imports:
            if ui_comp in component_code:
                dependencies.append('@/components/ui')

        return list(set(dependencies))

    def _extract_props_interface(self, component_code: str) -> Dict[str, Any]:
        """Extract Props interface from component code."""
        interface_match = re.search(r'interface\s+(\w+Props)\s*{([^}]*)}', component_code, re.DOTALL)
        if interface_match:
            interface_name = interface_match.group(1)
            interface_content = interface_match.group(2)

            props = {}
            for line in interface_content.split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('//'):
                    prop_match = re.match(r'(\w+)\??:\s*([^;]+)', line)
                    if prop_match:
                        prop_name = prop_match.group(1)
                        prop_type = prop_match.group(2).strip()
                        props[prop_name] = prop_type

            return {
                "interface_name": interface_name,
                "properties": props
            }

        return {"interface_name": "ComponentProps", "properties": {}}

    def _generate_window_config(self, component_name: str, component_type: str,
                              entities: List[Dict]) -> Dict[str, Any]:
        """Generate window configuration for the component."""
        # Default dimensions based on component type
        dimensions_map = {
            "dashboard": {"width": 800, "height": 600},
            "chart": {"width": 700, "height": 500},
            "table": {"width": 900, "height": 400},
            "form": {"width": 500, "height": 400},
            "card": {"width": 400, "height": 300},
            "button": {"width": 200, "height": 100},
            "input": {"width": 300, "height": 100}
        }

        dimensions = dimensions_map.get(component_type, {"width": 400, "height": 300})

        return {
            "id": f"window-{component_name.lower()}",
            "title": f"{component_name}",
            "type": "dynamic-component",
            "position": {"x": 100, "y": 100},
            "size": dimensions,
            "isMinimized": False,
            "zIndex": 1000
        }

    def _generate_integration_code(self, component_name: str) -> str:
        """Generate code for integrating the component with the system."""
        return f"""
// Integration code for {component_name}
// This code can be used to dynamically import and use the component

import dynamic from 'next/dynamic';

const {component_name} = dynamic(() => import('./{component_name}'), {{
  loading: () => <div>Loading {component_name}...</div>,
  ssr: false
}});

// Usage in window manager
const componentWindow = {{
  id: '{component_name.lower()}-window',
  component: {component_name},
  props: {{
    // Add default props here
  }}
}};
"""

    def _get_default_template(self) -> str:
        """Get default template for unknown component types."""
        return """
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface {ComponentName}Props {{
  title?: string;
}}

export default function {ComponentName}({{
  title = "{DefaultTitle}"
}}: {ComponentName}Props) {{
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
      </CardHeader>
      <CardContent>
        <p>This is a custom generated component.</p>
      </CardContent>
    </Card>
  );
}}
"""

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get statistics about component generation."""
        total_generated = len(self.generation_history)
        successful = len([h for h in self.generation_history if h["success"]])
        failed = total_generated - successful

        return {
            "total_generated": total_generated,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_generated if total_generated > 0 else 0,
            "recent_history": self.generation_history[-10:]  # Last 10 generations
        }


# Global component generator instance
component_generator = ComponentGenerator()


async def generate_component_from_request(user_request: str, analysis_result: Dict[str, Any],
                                        context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to generate components from user requests."""
    return await component_generator.generate_component(user_request, analysis_result, context)