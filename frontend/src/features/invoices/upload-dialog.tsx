"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { FileUp, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUploadInvoice } from "./queries";
import { readableError } from "@/lib/query/client";
import { UploadProgress } from "@/components/shared/loading";
export function UploadDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const form = useForm<{ file: FileList }>();
  const upload = useUploadInvoice();
  const [name, setName] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!upload.isPending) {
          onOpenChange(value);
          if (!value) {
            form.reset();
            upload.reset();
            setName("");
          }
        }
      }}
    >
      <DialogContent className="sm:max-w-[470px]">
        <DialogHeader>
          <DialogTitle>Upload invoice</DialogTitle>
          <DialogDescription>
            Add a document for extraction and validation.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await upload.mutateAsync(values.file[0]);
              onOpenChange(false);
              form.reset();
              setName("");
            } catch {
              /* Persistent error remains in the dialog. */
            }
          })}
          className="space-y-5"
        >
          <div className="upload-zone">
            <span>
              <FileUp className="size-6" />
            </span>
            <h3>{name || "Choose an invoice document"}</h3>
            <p>PDF, JPG or PNG &middot; Up to 8 MiB</p>
            <Label htmlFor="invoice-file" className="sr-only">
              Invoice file
            </Label>
            <Input
              id="invoice-file"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              disabled={upload.isPending}
              {...form.register("file", {
                validate: (files) =>
                  !files?.length
                    ? "Choose an invoice file."
                    : files[0].size > 8388608
                      ? "Choose a file of 8 MiB or less."
                      : true,
                onChange: (e) => setName(e.target.files?.[0]?.name || ""),
              })}
            />
          </div>
          {form.formState.errors.file && (
            <p role="alert" className="field-error">
              {form.formState.errors.file.message}
            </p>
          )}
          <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" />
            This workspace uses mock extraction. Choose a supplied synthetic
            invoice fixture.
          </p>
          {upload.isPending && <UploadProgress />}
          {upload.error && (
            <p className="field-error" role="alert">
              {readableError(upload.error)}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={upload.isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={upload.isPending}
              loadingText="Uploading..."
            >
              Upload &amp; validate
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
