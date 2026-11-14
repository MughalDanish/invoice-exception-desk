"use client";
import { useDesk } from "../desk";
import { Code2 } from "lucide-react";
import { Button } from "../ui/button";
export function TechnicalDetails({
  value,
  label = "Technical details",
}: {
  value: unknown;
  label?: string;
}) {
  const { inspect } = useDesk();
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="technical-link"
      onClick={() => inspect(label, value)}
    >
      <Code2 className="size-3.5" />
      {label}
    </Button>
  );
}
