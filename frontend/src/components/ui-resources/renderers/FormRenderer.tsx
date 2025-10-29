import React, { useState } from 'react';
import { UIResource, FormPayload, FormField } from '../../../types/ui-resources';
import { ThemedCard as Card, ThemedCardHeader as CardHeader, ThemedCardTitle as CardTitle, ThemedCardContent as CardContent, ThemedCardFooter as CardFooter } from '../../ui/themed-card';
import { ThemedButton as Button } from '../../ui/themed-button';
import { Input } from '../../ui/input';
// import { useTenant } from '../../../contexts/TenantContext'; // Available for future theming
import { cn } from '../../../lib/utils';

interface FormRendererProps {
  resource: UIResource;
}

export const FormRenderer: React.FC<FormRendererProps> = ({ resource }) => {
  const payload = resource.payload as FormPayload;
  // const { currentTenant } = useTenant(); // Available for future theming
  const [formData, setFormData] = useState<Record<string, any>>(() => {
    const initialData: Record<string, any> = {};
    payload.fields.forEach(field => {
      initialData[field.name] = field.value || '';
    });
    return initialData;
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const handleInputChange = (fieldName: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));
    setSubmitError(null);
    setSubmitSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!payload.submitUrl) {
      console.warn('No submit URL provided for form');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(false);

    try {
      const method = payload.submitMethod || 'POST';
      const response = await fetch(payload.submitUrl, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      setSubmitSuccess(true);
      console.log('Form submitted successfully');
    } catch (error) {
      console.error('Form submission failed:', error);
      setSubmitError(error instanceof Error ? error.message : 'Form submission failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (field: FormField) => {
    const commonProps = {
      id: field.name,
      name: field.name,
      required: field.required,
      placeholder: field.placeholder,
      value: formData[field.name] || '',
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        handleInputChange(field.name, e.target.value);
      },
      className: "bg-white/5 border-white/20 text-white placeholder:text-white/50 focus:border-white/40"
    };

    switch (field.type) {
      case 'textarea':
        return (
          <textarea
            {...commonProps}
            rows={3}
            className={cn(commonProps.className, "resize-none")}
          />
        );

      case 'select':
        return (
          <select
            {...commonProps}
            className={cn(commonProps.className, "cursor-pointer")}
          >
            <option value="">Select an option</option>
            {field.options?.map((option, index) => (
              <option key={index} value={option} className="bg-gray-800 text-white">
                {option}
              </option>
            ))}
          </select>
        );

      case 'checkbox':
        return (
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id={field.name}
              name={field.name}
              checked={!!formData[field.name]}
              onChange={(e) => handleInputChange(field.name, e.target.checked)}
              className="rounded border-white/20 bg-white/5 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
            <label htmlFor={field.name} className="text-sm text-white/80 cursor-pointer">
              {field.label}
            </label>
          </div>
        );

      default:
        return (
          <Input
            {...commonProps}
            type={field.type}
          />
        );
    }
  };

  return (
    <Card className="transition-all duration-200 hover:shadow-lg">
      <form onSubmit={handleSubmit}>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">{payload.title}</CardTitle>
        </CardHeader>
        
        <CardContent className="pt-0 space-y-4">
          {payload.fields.map((field) => (
            <div key={field.name} className="space-y-2">
              {field.type !== 'checkbox' && (
                <label 
                  htmlFor={field.name}
                  className="block text-sm font-medium text-white/90"
                >
                  {field.label}
                  {field.required && <span className="text-red-400 ml-1">*</span>}
                </label>
              )}
              {renderField(field)}
            </div>
          ))}
          
          {submitError && (
            <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-md p-2">
              {submitError}
            </div>
          )}
          
          {submitSuccess && (
            <div className="text-green-400 text-sm bg-green-500/10 border border-green-500/20 rounded-md p-2">
              Form submitted successfully!
            </div>
          )}
        </CardContent>
        
        {payload.submitUrl && (
          <CardFooter className="pt-0">
            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full"
            >
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </Button>
          </CardFooter>
        )}
      </form>
    </Card>
  );
};