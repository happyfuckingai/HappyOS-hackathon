import React from 'react';
import { UIResource, ChartPayload } from '../../../types/ui-resources';
import { ThemedCard as Card, ThemedCardHeader as CardHeader, ThemedCardTitle as CardTitle, ThemedCardContent as CardContent } from '../../ui/themed-card';
import { useTenant } from '../../../contexts/TenantContext';
import { cn } from '../../../lib/utils';

interface ChartRendererProps {
  resource: UIResource;
}

export const ChartRenderer: React.FC<ChartRendererProps> = ({ resource }) => {
  const payload = resource.payload as ChartPayload;
  const { currentTenant } = useTenant();

  // Simple bar chart implementation
  const renderBarChart = (data: any) => {
    if (!data.datasets || !data.labels) {
      return <div className="text-white/50 text-sm">Invalid chart data</div>;
    }

    const dataset = data.datasets[0];
    const values = dataset?.data || [];
    const labels = data.labels || [];
    const maxValue = Math.max(...values, 1);

    return (
      <div className="space-y-3">
        {labels.map((label: string, index: number) => {
          const value = values[index] || 0;
          const percentage = (value / maxValue) * 100;
          
          return (
            <div key={index} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-white/80">{label}</span>
                <span className="text-white/60">{value}</span>
              </div>
              <div className="w-full bg-white/10 rounded-full h-2">
                <div
                  className="h-2 rounded-full transition-all duration-300"
                  style={{ 
                    width: `${percentage}%`,
                    backgroundColor: currentTenant?.theme.primaryColor || '#3b82f6'
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // Simple pie chart implementation
  const renderPieChart = (data: any) => {
    if (!data.datasets || !data.labels) {
      return <div className="text-white/50 text-sm">Invalid chart data</div>;
    }

    const dataset = data.datasets[0];
    const values = dataset?.data || [];
    const labels = data.labels || [];
    const total = values.reduce((sum: number, val: number) => sum + val, 0);

    const colors = [
      'bg-blue-500',
      'bg-green-500',
      'bg-yellow-500',
      'bg-red-500',
      'bg-purple-500',
      'bg-pink-500',
      'bg-indigo-500',
      'bg-orange-500',
    ];

    return (
      <div className="space-y-4">
        {/* Simple visual representation */}
        <div className="flex h-4 rounded-full overflow-hidden">
          {values.map((value: number, index: number) => {
            const percentage = total > 0 ? (value / total) * 100 : 0;
            return (
              <div
                key={index}
                className={cn(colors[index % colors.length])}
                style={{ width: `${percentage}%` }}
                title={`${labels[index]}: ${value} (${percentage.toFixed(1)}%)`}
              />
            );
          })}
        </div>
        
        {/* Legend */}
        <div className="grid grid-cols-2 gap-2">
          {labels.map((label: string, index: number) => {
            const value = values[index] || 0;
            const percentage = total > 0 ? (value / total) * 100 : 0;
            
            return (
              <div key={index} className="flex items-center gap-2 text-sm">
                <div className={cn('w-3 h-3 rounded-sm', colors[index % colors.length])} />
                <span className="text-white/80 truncate">{label}</span>
                <span className="text-white/60 ml-auto">{percentage.toFixed(1)}%</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // Simple line chart implementation
  const renderLineChart = (data: any) => {
    if (!data.datasets || !data.labels) {
      return <div className="text-white/50 text-sm">Invalid chart data</div>;
    }

    const dataset = data.datasets[0];
    const values = dataset?.data || [];
    const labels = data.labels || [];
    const maxValue = Math.max(...values, 1);
    const minValue = Math.min(...values, 0);
    const range = maxValue - minValue || 1;

    return (
      <div className="space-y-4">
        {/* Simple line visualization */}
        <div className="relative h-32 bg-white/5 rounded-lg p-4">
          <div className="flex items-end justify-between h-full">
            {values.map((value: number, index: number) => {
              const height = ((value - minValue) / range) * 100;
              return (
                <div key={index} className="flex flex-col items-center gap-1">
                  <div
                    className="w-2 bg-blue-500 rounded-t"
                    style={{ height: `${height}%` }}
                    title={`${labels[index]}: ${value}`}
                  />
                  <div className="w-1 h-1 bg-blue-500 rounded-full" />
                </div>
              );
            })}
          </div>
        </div>
        
        {/* X-axis labels */}
        <div className="flex justify-between text-xs text-white/60">
          {labels.map((label: string, index: number) => (
            <span key={index} className="truncate max-w-16" title={label}>
              {label}
            </span>
          ))}
        </div>
      </div>
    );
  };

  const renderChart = () => {
    try {
      switch (payload.chartType) {
        case 'bar':
          return renderBarChart(payload.data);
        case 'pie':
        case 'doughnut':
          return renderPieChart(payload.data);
        case 'line':
          return renderLineChart(payload.data);
        default:
          return (
            <div className="text-white/50 text-sm">
              Chart type "{payload.chartType}" not supported
            </div>
          );
      }
    } catch (error) {
      console.error('Error rendering chart:', error);
      return (
        <div className="text-red-400 text-sm">
          Error rendering chart data
        </div>
      );
    }
  };

  return (
    <Card className="transition-all duration-200 hover:shadow-lg">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">{payload.title}</CardTitle>
      </CardHeader>
      
      <CardContent className="pt-0">
        {renderChart()}
      </CardContent>
    </Card>
  );
};