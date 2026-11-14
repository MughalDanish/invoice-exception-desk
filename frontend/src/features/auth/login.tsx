"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  FileCheck2,
  History,
  ShieldCheck,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import { readableError } from "@/lib/query/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
const schema = z.object({
  username: z.string().min(1, "Enter your username").max(200),
  password: z.string().min(1, "Enter your password"),
});
type LoginFields = z.infer<typeof schema>;
import { authApi } from "./api";
import type { AuthUser } from "./types";
export function LoginView({
  onAuthenticated,
  expired,
}: {
  onAuthenticated: (session: AuthUser) => void;
  expired?: boolean;
}) {
  const form = useForm<LoginFields>({
    resolver: zodResolver(schema),
    defaultValues: { username: "", password: "" },
  });
  const login = useMutation({
    mutationKey: ["authentication"],
    gcTime: 0,
    mutationFn: (values: LoginFields) => authApi.login(values),
    onSuccess: (session) => {
      form.reset();
      onAuthenticated(session);
    },
  });
  return (
    <main className="login">
      <section className="login-story">
        <div className="login-brand">
          <span className="brand-symbol">
            <FileCheck2 className="size-6" />
          </span>
          <span>Invoice Desk</span>
        </div>
        <div className="login-message">
          <span className="login-kicker">FINANCIAL OPERATIONS, IN FOCUS</span>
          <h1>
            Every invoice.
            <br />A clear decision.
          </h1>
          <p>
            Review the details, resolve exceptions and keep every decision
            accounted for.
          </p>
          <div className="login-proof">
            <span>
              <Check />
              Verify the details
            </span>
            <span>
              <ShieldCheck />
              Stay in control
            </span>
            <span>
              <History />
              Trace every change
            </span>
          </div>
        </div>
        <div className="login-footer">
          <span className="status-dot" />
          Synthetic demonstration<span>No payments or ERP writeback</span>
        </div>
      </section>
      <section className="login-form">
        <form onSubmit={form.handleSubmit((values) => login.mutate(values))}>
          <span className="login-kicker">WELCOME BACK</span>
          <h2>Sign in to your workspace</h2>
          <p className="muted">Your invoice review starts here.</p>
          {(login.error || expired) && (
            <div className="notice error" role="alert">
              {login.error
                ? login.error instanceof ApiError && login.error.status === 401
                  ? "Username or password is incorrect."
                  : readableError(login.error)
                : "Your session has expired. Sign in again."}
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              autoComplete="username"
              {...form.register("username")}
              aria-invalid={!!form.formState.errors.username}
            />
            {form.formState.errors.username && (
              <p className="field-error">
                {form.formState.errors.username.message}
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...form.register("password")}
              aria-invalid={!!form.formState.errors.password}
            />
            {form.formState.errors.password && (
              <p className="field-error">
                {form.formState.errors.password.message}
              </p>
            )}
          </div>
          <Button
            className="w-full"
            loading={login.isPending}
            loadingText="Signing in..."
            type="submit"
          >
            Open workspace
            <ArrowRight className="size-4" />
          </Button>
          <p className="login-security">
            <ShieldCheck className="size-4" />
            Secure operator access. Your session uses protected cookies.
          </p>
        </form>
      </section>
    </main>
  );
}
