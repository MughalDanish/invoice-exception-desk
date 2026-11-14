"use client";
import { type ComponentProps } from "react";
import { RotateCw, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { readableError } from "@/lib/query/client";
export function IconAction({
  icon: Icon,
  label,
  ...props
}: { icon: LucideIcon; label: string } & ComponentProps<typeof Button>) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={label} {...props}>
          <Icon className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  allLabel: string;
}) {
  return (
    <Select
      value={value || "all"}
      onValueChange={(value) => onChange(value === "all" ? "" : value)}
    >
      <SelectTrigger
        aria-label={label}
        className="min-w-36 bg-card text-xs shadow-none"
      >
        <SelectValue placeholder={allLabel} />
      </SelectTrigger>
      <SelectContent position="popper">
        <SelectItem value="all">{allLabel}</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
export function QueryError({
  error,
  retry,
  compact = false,
}: {
  error: unknown;
  retry?: () => void;
  compact?: boolean;
}) {
  return (
    <div className={`query-error ${compact ? "compact" : ""}`} role="alert">
      <div>
        <strong>We couldn&apos;t refresh this information</strong>
        <p>{readableError(error)}</p>
      </div>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          <RotateCw className="size-3.5" />
          Try again
        </Button>
      )}
    </div>
  );
}
