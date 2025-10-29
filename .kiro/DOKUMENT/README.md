# Architecture Diagrams

This directory contains visual representations of both AWS and custom infrastructure approaches.

## Diagram Files

1. **aws_architecture.md** - AWS native architecture with managed services
2. **custom_architecture.md** - Custom infrastructure implementation
3. **migration_flow.md** - Migration strategy and phases
4. **circuit_breaker.md** - Fallback mechanism visualization
5. **performance_comparison.md** - Performance and cost comparisons

## Diagram Format

All diagrams are created using Mermaid syntax for easy rendering in presentations and documentation.

## Usage

These diagrams can be:
- Rendered in GitHub/GitLab markdown
- Converted to images using Mermaid CLI
- Embedded in presentation slides
- Used in technical documentation

## Rendering Commands

```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Generate PNG images
mmdc -i aws_architecture.md -o aws_architecture.png
mmdc -i custom_architecture.md -o custom_architecture.png
mmdc -i migration_flow.md -o migration_flow.png
mmdc -i circuit_breaker.md -o circuit_breaker.png
mmdc -i performance_comparison.md -o performance_comparison.png
```