import * as React from "react"
import { useTenant } from "../../contexts/TenantContext"
import { cn } from "../../lib/utils"

const ThemedCard = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, style, ...props }, ref) => {
  const { currentTenant } = useTenant();
  
  const tenantStyles = React.useMemo(() => {
    if (!currentTenant) return style;
    
    return {
      borderColor: `${currentTenant.theme.primaryColor}20`, // 20% opacity
      backgroundColor: `${currentTenant.theme.primaryColor}05`, // 5% opacity
      ...style,
    };
  }, [currentTenant, style]);

  return (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-sm glass-card",
        className
      )}
      style={tenantStyles}
      {...props}
    />
  );
});
ThemedCard.displayName = "ThemedCard"

const ThemedCardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
))
ThemedCardHeader.displayName = "ThemedCardHeader"

const ThemedCardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => {
  const { currentTenant } = useTenant();
  
  const titleClasses = React.useMemo(() => {
    if (!currentTenant) return '';
    return `text-[${currentTenant.theme.primaryColor}]`;
  }, [currentTenant]);

  return (
    <h3
      ref={ref}
      className={cn(
        "text-2xl font-semibold leading-none tracking-tight",
        titleClasses,
        className
      )}
      {...props}
    />
  );
});
ThemedCardTitle.displayName = "ThemedCardTitle"

const ThemedCardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-sm text-white/65", className)} {...props} />
))
ThemedCardDescription.displayName = "ThemedCardDescription"

const ThemedCardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
ThemedCardContent.displayName = "ThemedCardContent"

const ThemedCardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
))
ThemedCardFooter.displayName = "ThemedCardFooter"

export { 
  ThemedCard, 
  ThemedCardHeader, 
  ThemedCardFooter, 
  ThemedCardTitle, 
  ThemedCardDescription, 
  ThemedCardContent 
}