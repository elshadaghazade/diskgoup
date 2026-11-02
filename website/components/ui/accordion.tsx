'use client'

import * as React from 'react'
import * as AccordionPrimitive from '@radix-ui/react-accordion'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Accordion = AccordionPrimitive.Root

export function AccordionItem({
  className,
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Item>) {
  return <AccordionPrimitive.Item className={cn('border-b border-line', className)} {...props} />
}

export function AccordionTrigger({
  className,
  children,
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Trigger>) {
  return (
    <AccordionPrimitive.Header className="flex">
      <AccordionPrimitive.Trigger
        className={cn(
          'group flex flex-1 items-center justify-between gap-4 py-5 text-left text-base font-medium text-ink transition-colors hover:text-accent',
          className,
        )}
        {...props}
      >
        {children}
        <Plus className="size-4 shrink-0 text-faint transition-transform duration-200 group-data-[state=open]:rotate-45" />
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  )
}

export function AccordionContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Content>) {
  return (
    <AccordionPrimitive.Content
      className={cn(
        'overflow-hidden text-sm leading-relaxed text-muted data-[state=closed]:animate-none',
        className,
      )}
      {...props}
    >
      <div className="pb-5 pr-8">{children}</div>
    </AccordionPrimitive.Content>
  )
}
