import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { useTenant } from "../../contexts/TenantContext"
import { cn } from "../../lib/utils"

const themedButtonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "text-white shadow hover:opacity-90",
        destructive: "bg-red-500 text-white hover:bg-red-600",
        outline: "border border-current bg-transparent hover:bg-current/10",
        secondary: "bg-white/10 text-white hover:bg-white/20",
        ghost: "hover:bg-current/10",
        link: "text-current underline-offset-4 hover:underline",
        glass: "glass-button text-white hover:bg-white/15 active:bg-white/20",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ThemedButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof themedButtonVariants> {
  asChild?: boolean
}

const ThemedButton = React.forwardRef<HTMLButtonElement, ThemedButtonProps>(
  ({ className, variant, size, asChild = false, style, ...props }, ref) => {
    const { currentTenant } = useTenant();
    const Comp = asChild ? Slot : "button"
    
    // Generate tenant-specific styles
    const tenantStyles = React.useMemo(() => {
      if (!currentTenant || variant !== 'default') return {};
      
      return {
        backgroundColor: currentTenant.theme.primaryColor,
        '--hover-bg': currentTenant.theme.secondaryColor,
        ...style,
      };
    }, [currentTenant, variant, style]);

    const tenantClasses = React.useMemo(() => {
      if (!currentTenant) return '';
      
      switch (variant) {
        case 'outline':
          return `border-[${currentTenant.theme.primaryColor}] text-[${currentTenant.theme.primaryColor}] hover:bg-[${currentTenant.theme.primaryColor}]/10`;
        case 'ghost':
          return `text-[${currentTenant.theme.primaryColor}] hover:bg-[${currentTenant.theme.primaryColor}]/10`;
        case 'link':
          return `text-[${currentTenant.theme.primaryColor}]`;
        default:
          return '';
      }
    }, [currentTenant, variant]);

    return (
      <Comp
        className={cn(themedButtonVariants({ variant, size }), tenantClasses, className)}
        style={tenantStyles}
        ref={ref}
        {...props}
      />
    )
  }
)
ThemedButton.displayName = "ThemedButton"

export { ThemedButton, themedButtonVariants }