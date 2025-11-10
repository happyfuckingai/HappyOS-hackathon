"""
Component Template Library for HappyOS.

A comprehensive library of React component templates with variations,
configurations, and best practices for generating high-quality UI components.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentCategory(Enum):
    """Component categories for organization."""
    BASIC = "basic"
    FORM = "form"
    DATA_DISPLAY = "data_display"
    NAVIGATION = "navigation"
    FEEDBACK = "feedback"
    LAYOUT = "layout"
    ADVANCED = "advanced"


class TemplateVariant(Enum):
    """Template variants for different use cases."""
    SIMPLE = "simple"
    INTERACTIVE = "interactive"
    ANIMATED = "animated"
    RESPONSIVE = "responsive"
    ACCESSIBLE = "accessible"
    DARK_MODE = "dark_mode"


@dataclass
class ComponentTemplate:
    """Component template with metadata."""
    id: str
    name: str
    category: ComponentCategory
    description: str
    template: str
    variants: Dict[str, str]
    default_props: Dict[str, Any]
    dependencies: List[str]
    complexity: str
    tags: List[str]


class ComponentTemplateLibrary:
    """
    Component Template Library.

    Provides a comprehensive collection of React component templates
    with variations, accessibility features, and best practices.
    """

    def __init__(self):
        self.templates = {}
        self._initialize_templates()

    def _initialize_templates(self):
        """Initialize all component templates."""
        self._add_basic_templates()
        self._add_form_templates()
        self._add_data_display_templates()
        self._add_navigation_templates()
        self._add_feedback_templates()
        self._add_layout_templates()
        self._add_advanced_templates()

    def _add_basic_templates(self):
        """Add basic component templates."""

        # Button Template
        self.templates["button"] = ComponentTemplate(
            id="button",
            name="Button",
            category=ComponentCategory.BASIC,
            description="Interactive button component with multiple variants",
            template="""import React from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ButtonComponentProps {{
  text?: string;
  onClick?: () => void;
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  className?: string;
}}

export default function ButtonComponent({{
  text = "Click me",
  onClick,
  variant = "default",
  size = "default",
  disabled = false,
  loading = false,
  fullWidth = false,
  className
}}: ButtonComponentProps) {{
  return (
    <Button
      variant={{variant}}
      size={{size}}
      onClick={{onClick}}
      disabled={{disabled || loading}}
      className={{cn(
        "transition-all duration-200 hover:scale-105",
        fullWidth && "w-full",
        className
      )}}
    >
      {{loading && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2" />}}
      {{text}}
    </Button>
  );
}}
""",
            variants={
                "simple": """// Simple variant - minimal button
<Button onClick={onClick} className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
  {text}
</Button>""",
                "animated": """// Animated variant with ripple effect
<div className="relative overflow-hidden">
  <Button
    onClick={onClick}
    className="relative overflow-hidden transform transition-all duration-200 hover:scale-105 active:scale-95"
  >
    <span className="relative z-10">{text}</span>
    <div className="absolute inset-0 bg-white/20 transform scale-0 transition-transform duration-300 group-hover:scale-100" />
  </Button>
</div>""",
                "loading": """// Loading state variant
<Button disabled={loading} className="relative">
  {loading && (
    <div className="absolute left-1/2 transform -translate-x-1/2">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
    </div>
  )}
  <span className={loading ? 'opacity-0' : 'opacity-100'}>{text}</span>
</Button>"""
            },
            default_props={
                "text": "Click me",
                "variant": "default",
                "size": "default",
                "disabled": False,
                "loading": False,
                "fullWidth": False
            },
            dependencies=["@/components/ui/button", "@/lib/utils"],
            complexity="low",
            tags=["interactive", "action", "click", "ui"]
        )

        # Card Template
        self.templates["card"] = ComponentTemplate(
            id="card",
            name="Card",
            category=ComponentCategory.BASIC,
            description="Content container with header, body, and footer",
            template="""import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface CardComponentProps {{
  title?: string;
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  hover?: boolean;
  padding?: 'sm' | 'md' | 'lg';
}}

const paddingClasses = {{
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8'
}};

export default function CardComponent({{
  title,
  description,
  children,
  footer,
  className,
  hover = false,
  padding = 'md'
}}: CardComponentProps) {{
  return (
    <Card className={{cn(
      "transition-all duration-200",
      hover && "hover:shadow-lg hover:scale-[1.02]",
      className
    )}}>
      {{(title || description) && (
        <CardHeader>
          {{title && <CardTitle>{{title}}</CardTitle>}}
          {{description && <CardDescription>{{description}}</CardDescription>}}
        </CardHeader>
      )}}
      <CardContent className={{paddingClasses[padding]}}>
        {{children || <p>Card content goes here...</p>}}
      </CardContent>
      {{footer && <CardFooter>{{footer}}</CardFooter>}}
    </Card>
  );
}}
""",
            variants={},
            default_props={
                "title": "Card Title",
                "description": None,
                "hover": False,
                "padding": "md"
            },
            dependencies=["@/components/ui/card", "@/lib/utils"],
            complexity="low",
            tags=["container", "content", "layout"]
        )

    def _add_form_templates(self):
        """Add form component templates."""

        # Input Template
        self.templates["input"] = ComponentTemplate(
            id="input",
            name="Input",
            category=ComponentCategory.FORM,
            description="Text input field with validation and accessibility",
            template="""import React, {{ useState }} from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

interface InputComponentProps {{
  label?: string;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url';
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}}

const sizeClasses = {{
  sm: 'h-8 text-sm',
  md: 'h-10',
  lg: 'h-12 text-lg'
}};

export default function InputComponent({{
  label,
  placeholder = "Enter text...",
  value = "",
  onChange,
  type = "text",
  required = false,
  disabled = false,
  error,
  helperText,
  className,
  size = 'md'
}}: InputComponentProps) {{
  const [inputValue, setInputValue] = useState(value);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {{
    const newValue = e.target.value;
    setInputValue(newValue);
    onChange?.(newValue);
  }};

  return (
    <div className="space-y-2">
      {{label && (
        <Label htmlFor={{`input-${label?.toLowerCase().replace(/\s+/g, '-')}`}} className="text-sm font-medium">
          {{label}}
          {{required && <span className="text-red-500 ml-1">*</span>}}
        </Label>
      )}}
      <Input
        id={{`input-${label?.toLowerCase().replace(/\s+/g, '-')}`}}
        type={{type}}
        placeholder={{placeholder}}
        value={{inputValue}}
        onChange={{handleChange}}
        disabled={{disabled}}
        required={{required}}
        className={{cn(
          "transition-all duration-200 focus:scale-105",
          error && "border-red-500 focus:border-red-500",
          sizeClasses[size],
          className
        )}}
      />
      {{error && <p className="text-sm text-red-500">{{error}}</p>}}
      {{helperText && !error && <p className="text-sm text-gray-500">{{helperText}}</p>}}
    </div>
  );
}}
""",
            variants={},
            default_props={
                "placeholder": "Enter text...",
                "type": "text",
                "required": False,
                "disabled": False,
                "size": "md"
            },
            dependencies=["@/components/ui/input", "@/components/ui/label", "@/lib/utils"],
            complexity="low",
            tags=["form", "input", "text", "validation"]
        )

        # Form Template
        self.templates["form"] = ComponentTemplate(
            id="form",
            name="Form",
            category=ComponentCategory.FORM,
            description="Complete form with multiple fields and validation",
            template="""import React, {{ useState }} from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface FormField {{
  name: string;
  label: string;
  type: string;
  placeholder: string;
  required?: boolean;
  validation?: (value: string) => string | null;
}}

interface FormComponentProps {{
  title?: string;
  description?: string;
  fields?: FormField[];
  onSubmit?: (data: Record<string, string>) => void;
  submitText?: string;
  className?: string;
}}

export default function FormComponent({{
  title = "Contact Form",
  description = "Fill in the form below",
  fields = [
    {{
      name: 'name',
      label: 'Full Name',
      type: 'text',
      placeholder: 'Enter your full name',
      required: true,
      validation: (value) => value.length < 2 ? 'Name must be at least 2 characters' : null
    }},
    {{
      name: 'email',
      label: 'Email Address',
      type: 'email',
      placeholder: 'Enter your email',
      required: true,
      validation: (value) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? 'Invalid email format' : null
    }},
    {{
      name: 'message',
      label: 'Message',
      type: 'textarea',
      placeholder: 'Enter your message',
      required: true
    }}
  ],
  onSubmit,
  submitText = "Submit",
  className
}}: FormComponentProps) {{
  const [formData, setFormData] = useState<Record<string, string>>({{}});
  const [errors, setErrors] = useState<Record<string, string>>({{}});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (name: string, value: string) => {{
    setFormData(prev => ({{ ...prev, [name]: value }}));
    // Clear error when user starts typing
    if (errors[name]) {{
      setErrors(prev => ({{ ...prev, [name]: '' }}));
    }}
  }};

  const validateForm = (): boolean => {{
    const newErrors: Record<string, string> = {{}};

    fields.forEach(field => {{
      const value = formData[field.name] || '';

      if (field.required && !value.trim()) {{
        newErrors[field.name] = `${{field.label}} is required`;
      }} else if (field.validation && value) {{
        const validationError = field.validation(value);
        if (validationError) {{
          newErrors[field.name] = validationError;
        }}
      }}
    }});

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }};

  const handleSubmit = async (e: React.FormEvent) => {{
    e.preventDefault();

    if (!validateForm()) {{
      return;
    }}

    setIsSubmitting(true);
    try {{
      await onSubmit?.(formData);
    }} finally {{
      setIsSubmitting(false);
    }}
  }};

  return (
    <Card className={{cn("w-full max-w-md mx-auto", className)}}>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
        <CardDescription>{{description}}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={{handleSubmit}} className="space-y-4">
          {{fields.map((field, index) => (
            <div key={{index}} className="space-y-2">
              <Label htmlFor={{field.name}} className="text-sm font-medium">
                {{field.label}}
                {{field.required && <span className="text-red-500 ml-1">*</span>}}
              </Label>
              {{field.type === 'textarea' ? (
                <textarea
                  id={{field.name}}
                  placeholder={{field.placeholder}}
                  value={{formData[field.name] || ''}}
                  onChange={{(e) => handleChange(field.name, e.target.value)}}
                  className={{cn(
                    "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    errors[field.name] && "border-red-500"
                  )}}
                  rows={{4}}
                  required={{field.required}}
                />
              ) : (
                <Input
                  id={{field.name}}
                  type={{field.type}}
                  placeholder={{field.placeholder}}
                  value={{formData[field.name] || ''}}
                  onChange={{(e) => handleChange(field.name, e.target.value)}}
                  className={{errors[field.name] && "border-red-500"}}
                  required={{field.required}}
                />
              )}}
              {{errors[field.name] && (
                <p className="text-sm text-red-500">{{errors[field.name]}}</p>
              )}}
            </div>
          ))}}
          <Button type="submit" disabled={{isSubmitting}} className="w-full">
            {{isSubmitting ? 'Submitting...' : submitText}}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}}
""",
            variants={},
            default_props={
                "title": "Contact Form",
                "submitText": "Submit"
            },
            dependencies=["@/components/ui/button", "@/components/ui/input", "@/components/ui/label", "@/components/ui/card", "@/lib/utils"],
            complexity="medium",
            tags=["form", "validation", "submission", "interactive"]
        )

    def _add_data_display_templates(self):
        """Add data display component templates."""

        # Table Template
        self.templates["table"] = ComponentTemplate(
            id="table",
            name="Table",
            category=ComponentCategory.DATA_DISPLAY,
            description="Data table with sorting, pagination, and actions",
            template="""import React, {{ useState, useMemo }} from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {{ Table, TableBody, TableCell, TableHead, TableHeader, TableRow }} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface TableColumn {{
  key: string;
  label: string;
  sortable?: boolean;
  width?: string;
}}

interface TableComponentProps {{
  title?: string;
  description?: string;
  data?: Record<string, any>[];
  columns?: TableColumn[];
  searchable?: boolean;
  pagination?: boolean;
  pageSize?: number;
  className?: string;
  onRowClick?: (row: Record<string, any>) => void;
  actions?: (row: Record<string, any>) => React.ReactNode;
}}

export default function TableComponent({{
  title = "Data Table",
  description,
  data = [
    {{ id: 1, name: 'John Doe', email: 'john@example.com', status: 'Active', created: '2024-01-15' }},
    {{ id: 2, name: 'Jane Smith', email: 'jane@example.com', status: 'Inactive', created: '2024-01-20' }},
    {{ id: 3, name: 'Bob Johnson', email: 'bob@example.com', status: 'Active', created: '2024-01-25' }}
  ],
  columns = [
    {{ key: 'name', label: 'Name', sortable: true }},
    {{ key: 'email', label: 'Email', sortable: true }},
    {{ key: 'status', label: 'Status', sortable: true }},
    {{ key: 'created', label: 'Created', sortable: true }}
  ],
  searchable = true,
  pagination = true,
  pageSize = 10,
  className,
  onRowClick,
  actions
}}: TableComponentProps) {{
  const [searchTerm, setSearchTerm] = useState('');
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);

  // Filter data based on search term
  const filteredData = useMemo(() => {{
    if (!searchTerm) return data;
    return data.filter(row =>
      Object.values(row).some(value =>
        String(value).toLowerCase().includes(searchTerm.toLowerCase())
      )
    );
  }}, [data, searchTerm]);

  // Sort data
  const sortedData = useMemo(() => {{
    if (!sortColumn) return filteredData;
    return [...filteredData].sort((a, b) => {{
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    }});
  }}, [filteredData, sortColumn, sortDirection]);

  // Paginate data
  const paginatedData = useMemo(() => {{
    if (!pagination) return sortedData;
    const startIndex = (currentPage - 1) * pageSize;
    return sortedData.slice(startIndex, startIndex + pageSize);
  }}, [sortedData, currentPage, pageSize, pagination]);

  const totalPages = Math.ceil(sortedData.length / pageSize);

  const handleSort = (columnKey: string) => {{
    if (sortColumn === columnKey) {{
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    }} else {{
      setSortColumn(columnKey);
      setSortDirection('asc');
    }}
  }};

  return (
    <Card className={{cn("w-full", className)}}>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
        {{description && <CardDescription>{{description}}</CardDescription>}}
        {{searchable && (
          <Input
            placeholder="Search..."
            value={{searchTerm}}
            onChange={{(e) => setSearchTerm(e.target.value)}}
            className="max-w-sm"
          />
        )}}
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                {{columns.map((column, index) => (
                  <TableHead
                    key={{index}}
                    className={{cn(
                      column.sortable && "cursor-pointer hover:bg-gray-50",
                      column.width && `w-[${{column.width}}]`
                    )}}
                    onClick={{() => column.sortable && handleSort(column.key)}}
                  >
                    <div className="flex items-center gap-2">
                      {{column.label}}
                      {{column.sortable && sortColumn === column.key && (
                        <span>{{sortDirection === 'asc' ? '↑' : '↓'}}</span>
                      )}}
                    </div>
                  </TableHead>
                ))}}
                {{actions && <TableHead className="w-[100px]">Actions</TableHead>}}
              </TableRow>
            </TableHeader>
            <TableBody>
              {{paginatedData.map((row, rowIndex) => (
                <TableRow
                  key={{rowIndex}}
                  className={{cn(
                    onRowClick && "cursor-pointer hover:bg-gray-50",
                    "transition-colors"
                  )}}
                  onClick={{() => onRowClick?.(row)}}
                >
                  {{columns.map((column, colIndex) => (
                    <TableCell key={{colIndex}}>{{row[column.key]}}</TableCell>
                  ))}}
                  {{actions && (
                    <TableCell>{{actions(row)}}</TableCell>
                  )}}
                </TableRow>
              ))}}
            </TableBody>
          </Table>
        </div>

        {{pagination && totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-500">
              Showing {{(currentPage - 1) * pageSize + 1}} to {{Math.min(currentPage * pageSize, sortedData.length)}} of {{sortedData.length}} results
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={{() => setCurrentPage(prev => Math.max(1, prev - 1))}}
                disabled={{currentPage === 1}}
              >
                Previous
              </Button>
              <span className="text-sm self-center">
                Page {{currentPage}} of {{totalPages}}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={{() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}}
                disabled={{currentPage === totalPages}}
              >
                Next
              </Button>
            </div>
          </div>
        )}}
      </CardContent>
    </Card>
  );
}}
""",
            variants={},
            default_props={
                "title": "Data Table",
                "searchable": True,
                "pagination": True,
                "pageSize": 10
            },
            dependencies=["@/components/ui/card", "@/components/ui/table", "@/components/ui/button", "@/components/ui/input", "@/lib/utils"],
            complexity="high",
            tags=["data", "table", "pagination", "sorting", "search"]
        )

    def _add_navigation_templates(self):
        """Add navigation component templates."""
        pass  # Will add navigation templates

    def _add_feedback_templates(self):
        """Add feedback component templates."""
        pass  # Will add feedback templates

    def _add_layout_templates(self):
        """Add layout component templates."""
        pass  # Will add layout templates

    def _add_advanced_templates(self):
        """Add advanced component templates."""
        pass  # Will add advanced templates

    def get_template(self, template_id: str) -> Optional[ComponentTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def get_templates_by_category(self, category: ComponentCategory) -> List[ComponentTemplate]:
        """Get all templates in a category."""
        return [template for template in self.templates.values() if template.category == category]

    def get_templates_by_tag(self, tag: str) -> List[ComponentTemplate]:
        """Get all templates with a specific tag."""
        return [template for template in self.templates.values() if tag in template.tags]

    def search_templates(self, query: str) -> List[ComponentTemplate]:
        """Search templates by name, description, or tags."""
        query_lower = query.lower()
        results = []

        for template in self.templates.values():
            if (query_lower in template.name.lower() or
                query_lower in template.description.lower() or
                any(query_lower in tag for tag in template.tags)):
                results.append(template)

        return results

    def get_template_suggestions(self, user_context: Dict[str, Any]) -> List[ComponentTemplate]:
        """Get template suggestions based on user context."""
        # Simple suggestion logic - can be enhanced with ML
        recent_templates = user_context.get("recent_components", [])
        if recent_templates:
            last_type = recent_templates[-1].get("component", {}).get("type")
            if last_type and last_type in self.templates:
                return [self.templates[last_type]]

        # Default suggestions
        return [
            self.templates.get("button"),
            self.templates.get("card"),
            self.templates.get("input")
        ]

    def get_all_templates(self) -> List[ComponentTemplate]:
        """Get all available templates."""
        return list(self.templates.values())

    def get_template_stats(self) -> Dict[str, Any]:
        """Get statistics about the template library."""
        categories = {}
        complexities = {"low": 0, "medium": 0, "high": 0}
        tags = {}

        for template in self.templates.values():
            # Count by category
            cat_name = template.category.value
            categories[cat_name] = categories.get(cat_name, 0) + 1

            # Count by complexity
            complexities[template.complexity] += 1

            # Count tags
            for tag in template.tags:
                tags[tag] = tags.get(tag, 0) + 1

        return {
            "total_templates": len(self.templates),
            "categories": categories,
            "complexities": complexities,
            "top_tags": sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10],
            "templates_per_category": categories
        }


# Global template library instance
template_library = ComponentTemplateLibrary()