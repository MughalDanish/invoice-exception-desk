"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  QueryClientProvider,
  useIsMutating,
  useQuery,
  useQueryClient,
  useMutation,
} from "@tanstack/react-query";
import {
  Building2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Eye,
  FileCheck2,
  Files,
  LayoutDashboard,
  ListChecks,
  LogOut,
  PanelLeftClose,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { request, forgetAuthentication } from "@/lib/api";
import { toast } from "sonner";
import { stateLabel } from "@/lib/presentation";
import { createQueryClient, readableError } from "@/lib/query/client";
import { LoginView } from "@/features/auth/login";
import type { AuthUser } from "@/features/auth/types";
import { authApi } from "@/features/auth/api";
import { authKeys, useCurrentUser } from "@/features/auth/queries";
import {
  PausedState,
  AppLoader,
  BackgroundActivity,
  OfflineIndicator,
} from "./shared/loading";
import { Button } from "./ui/button";
import { Badge as UiBadge } from "./ui/badge";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "./ui/sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "./ui/breadcrumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Avatar, AvatarFallback } from "./ui/avatar";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "./ui/sheet";
import { Separator } from "./ui/separator";
import { JsonInspector } from "./evidence/json-inspector";

const Context = createContext<{
  readOnly: boolean;
  fail: (error: unknown) => string;
  inspect: (title: string, value: unknown) => void;
}>({ readOnly: false, fail: readableError, inspect: () => {} });
export const useDesk = () => useContext(Context);
export function Badge({ status }: { status: string }) {
  return (
    <UiBadge
      variant="outline"
      className={`status-badge ${status.toLowerCase()}`}
    >
      <span className="status-dot" />
      {stateLabel(status)}
    </UiBadge>
  );
}
export function Notice({
  error,
  children,
}: {
  error?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={`notice ${error ? "error" : ""}`}
    >
      {error ? (
        <TriangleAlert className="size-4 shrink-0" />
      ) : (
        <CircleCheck className="size-4 shrink-0" />
      )}
      <div>{children}</div>
    </div>
  );
}
const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/invoices/", label: "All invoices", icon: Files },
  { href: "/exceptions/", label: "Exception queue", icon: ListChecks },
  { href: "/ledger/", label: "Ledger", icon: FileCheck2 },
  { href: "/vendors/", label: "Suppliers", icon: Building2 },
];
export function DeskProvider({ children }: { children: ReactNode }) {
  const rootClient = useQueryClient();
  const [expired, setExpired] = useState(false);
  const configuration = useQuery({
    queryKey: ["configuration"],
    queryFn: ({ signal }) =>
      request<{ read_only: boolean }>("/config", { signal }),
    staleTime: Infinity,
  });
  const authentication = useCurrentUser(
    configuration.data?.read_only === false,
  );
  useEffect(() => {
    if (!("BroadcastChannel" in window)) return;
    const channel = new BroadcastChannel("invoice-desk-auth");
    channel.onmessage = (event) => {
      forgetAuthentication();
      if (event.data === "signed-out")
        rootClient.setQueryData(authKeys.me, null);
      if (event.data === "signed-in")
        void rootClient.resetQueries({ queryKey: authKeys.me });
    };
    return () => channel.close();
  }, [rootClient]);
  function endSession(id: string, wasExpired = false) {
    forgetAuthentication();
    rootClient.setQueryData<AuthUser | null>(authKeys.me, (current) =>
      current?.session_id === id ? null : current,
    );
    setExpired(wasExpired);
  }
  if (
    (configuration.isPending && !configuration.error) ||
    (configuration.data?.read_only === false && authentication.isPending)
  )
    return configuration.isPaused || authentication.isPaused ? (
      <PausedState />
    ) : (
      <AppLoader />
    );
  const error =
    configuration.error ||
    (configuration.data?.read_only === false ? authentication.error : null);
  if (!configuration.data || error)
    return (
      <div className="connection-screen">
        <h1>Reconnect your workspace</h1>
        <p className="muted">{readableError(error)}</p>
        <Button
          onClick={() => {
            if (!configuration.data) void configuration.refetch();
            else void authentication.refetch();
          }}
          loading={configuration.isFetching || authentication.isFetching}
        >
          Try again
        </Button>
      </div>
    );
  const readOnly = configuration.data.read_only;
  const session = readOnly ? null : (authentication.data ?? null);
  if (!readOnly && !session)
    return (
      <LoginView
        expired={expired}
        onAuthenticated={(user) => {
          setExpired(false);
          rootClient.setQueryData(authKeys.me, user);
        }}
      />
    );
  return (
    <FinancialSession
      key={session?.session_id || "public"}
      session={session}
      readOnly={readOnly}
      onSignOut={endSession}
    >
      {children}
    </FinancialSession>
  );
}
function FinancialSession({
  children,
  session,
  readOnly,
  onSignOut,
}: {
  children: ReactNode;
  session: AuthUser | null;
  readOnly: boolean;
  onSignOut: (id: string, expired?: boolean) => void;
}) {
  // A fresh client per authentication boundary. Protected data is never persisted.
  const [client] = useState(() =>
    createQueryClient(() => {
      if (session) onSignOut(session.session_id, true);
    }),
  );
  const [technical, setTechnical] = useState<{
    title: string;
    value: unknown;
  } | null>(null);
  useEffect(
    () => () => {
      void client.cancelQueries();
      client.clear();
    },
    [client],
  );
  const logout = useMutation({
    mutationKey: ["authentication", "logout"],
    mutationFn: authApi.logout,
    retry: false,
    onSuccess: async () => {
      await client.cancelQueries();
      client.clear();
      if (session) onSignOut(session.session_id);
    },
    onError: (error) => toast.error(readableError(error)),
  });
  return (
    <QueryClientProvider client={client}>
      <Context.Provider
        value={{
          readOnly,
          fail: readableError,
          inspect: (title, value) => setTechnical({ title, value }),
        }}
      >
        <SidebarProvider
          style={
            {
              "--sidebar-width": "14rem",
              "--sidebar-width-icon": "4rem",
            } as CSSProperties
          }
        >
          <WorkspaceShell
            user={session?.username || "Public workspace"}
            onSignOut={() => logout.mutate()}
            signingOut={logout.isPending}
          >
            {children}
          </WorkspaceShell>
        </SidebarProvider>
        <Sheet
          open={technical !== null}
          onOpenChange={(open) => {
            if (!open) setTechnical(null);
          }}
        >
          <SheetContent className="technical-sheet w-full sm:max-w-xl">
            <SheetHeader>
              <SheetTitle>{technical?.title || "Technical details"}</SheetTitle>
              <SheetDescription>
                Preserved source data. Read only.
              </SheetDescription>
            </SheetHeader>
            <JsonInspector key={technical?.title} value={technical?.value} />
          </SheetContent>
        </Sheet>
      </Context.Provider>
    </QueryClientProvider>
  );
}
function WorkspaceShell({
  children,
  user,
  onSignOut,
  signingOut,
}: {
  children: ReactNode;
  user: string;
  onSignOut: () => void;
  signingOut?: boolean;
}) {
  const pathname = usePathname();
  const { readOnly } = useDesk();
  const { setOpenMobile, state, toggleSidebar } = useSidebar();
  const pending = useIsMutating() + (signingOut ? 1 : 0);
  const active =
    navigation.find(
      (item) => item.href !== "/" && pathname.startsWith(item.href),
    ) || navigation[0];
  const detail = pathname.includes("/detail");
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <Sidebar collapsible="icon" className="app-sidebar">
        <SidebarHeader className="px-4 py-5 group-data-[collapsible=icon]:px-3">
          <Link href="/" className="brand" aria-label="Invoice Desk home">
            <span className="brand-symbol">
              <FileCheck2 className="size-5" />
            </span>
            <span className="brand-text group-data-[collapsible=icon]:hidden">
              Invoice Desk<span>Exception management</span>
            </span>
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup className="px-3">
            <SidebarGroupLabel className="mb-2 px-2 text-[10px] font-semibold tracking-[.12em] text-sidebar-foreground/55">
              WORKSPACE
            </SidebarGroupLabel>
            <SidebarMenu className="gap-1">
              {navigation.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={active.href === item.href}
                    tooltip={item.label}
                    className="h-10 gap-3 rounded-md px-3 font-medium group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:size-10! group-data-[collapsible=icon]:p-2.5!"
                  >
                    <Link
                      href={item.href}
                      aria-current={
                        active.href === item.href ? "page" : undefined
                      }
                      aria-label={item.label}
                      onClick={() => setOpenMobile(false)}
                    >
                      <item.icon className="size-[18px]!" />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
          <div className="sidebar-assurance group-data-[collapsible=icon]:hidden">
            <ShieldCheck className="size-4" />
            <p>
              Human decisions.<span>Every change accounted for.</span>
            </p>
          </div>
        </SidebarContent>
        <SidebarFooter className="gap-3 p-3">
          <Button
            variant="ghost"
            size="sm"
            className="hidden justify-start gap-3 text-sidebar-foreground/65 hover:bg-sidebar-accent hover:text-sidebar-foreground md:flex group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:size-10"
            aria-label={
              state === "expanded" ? "Collapse sidebar" : "Expand sidebar"
            }
            onClick={toggleSidebar}
          >
            <PanelLeftClose className="size-4" />
            <span className="group-data-[collapsible=icon]:hidden">
              Collapse sidebar
            </span>
          </Button>
          <Separator className="bg-sidebar-border" />
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    className="h-12 gap-3 rounded-md px-2 hover:bg-sidebar-accent"
                    aria-label="Account menu"
                  >
                    <Avatar className="size-8 rounded-md">
                      <AvatarFallback className="rounded-md bg-[#33564b] text-xs text-white">
                        {readOnly ? "RO" : user.slice(0, 2).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <div className="grid gap-0.5 text-left text-xs group-data-[collapsible=icon]:hidden">
                      <span className="max-w-32 truncate font-medium">
                        {user}
                      </span>
                      <span className="text-sidebar-foreground/55">
                        {readOnly ? "Read-only access" : "Local operator"}
                      </span>
                    </div>
                    <ChevronDown className="ml-auto size-3.5 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent side="top" align="start" className="w-52">
                  <DropdownMenuLabel>Finance workspace</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {!readOnly ? (
                    <DropdownMenuItem
                      disabled={pending > 0}
                      onSelect={onSignOut}
                    >
                      <LogOut className="size-4" />
                      Sign out
                    </DropdownMenuItem>
                  ) : (
                    <DropdownMenuLabel className="font-normal text-muted-foreground">
                      Read-only access
                    </DropdownMenuLabel>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
      <div className="workspace-body">
        <header className="topbar">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger
              aria-label="Toggle navigation"
              className="size-8 text-muted-foreground"
            />
            <Separator orientation="vertical" className="h-4!" />
            <Breadcrumb>
              <BreadcrumbList className="flex-nowrap gap-2 text-xs">
                <BreadcrumbItem className="hidden sm:inline-flex">
                  Workspace
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>{active.label}</BreadcrumbPage>
                </BreadcrumbItem>
                {detail && (
                  <>
                    <BreadcrumbSeparator />
                    <BreadcrumbItem className="truncate">
                      <BreadcrumbPage>Invoice review</BreadcrumbPage>
                    </BreadcrumbItem>
                  </>
                )}
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          <div className="flex items-center gap-4">
            <BackgroundActivity />
            <span className="environment-label">
              <span className="status-dot" />
              Local demo
            </span>
            <Avatar className="operator size-7">
              <AvatarFallback className="bg-secondary text-[10px] font-semibold">
                {readOnly ? "RO" : user.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
          </div>
        </header>
        {readOnly && (
          <div className="demo-banner">
            <Eye className="size-3.5" />
            <span>
              Read-only synthetic demonstration
              <span className="hidden sm:inline">
                {" "}
                &middot; Mock extraction &middot; No financial actions
              </span>
            </span>
          </div>
        )}
        <main
          id="main-content"
          className={`main-content ${detail ? "detail-main" : ""}`}
          tabIndex={-1}
        >
          <OfflineIndicator />
          {children}
        </main>
        <footer>
          <span>Invoice Exception Desk</span>
          <span>Internal ledger &middot; Synthetic data</span>
        </footer>
      </div>
    </>
  );
}
export function Heading({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function Pager({
  page,
  total,
  onChange,
  size = 20,
  disabled = false,
}: {
  page: number;
  total: number;
  onChange: (page: number) => void;
  size?: number;
  disabled?: boolean;
}) {
  return (
    <div className="pager">
      <span>
        {total === 0
          ? "No records"
          : `${(page - 1) * size + 1}-${Math.min(page * size, total)} of ${total} records`}
      </span>
      <div>
        <Button
          variant="outline"
          size="sm"
          aria-label="Previous page"
          disabled={disabled || page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft className="size-3.5" />
          <span className="hidden sm:inline">Previous</span>
        </Button>
        <span>
          {page} / {Math.max(1, Math.ceil(total / size))}
        </span>
        <Button
          variant="outline"
          size="sm"
          aria-label="Next page"
          disabled={disabled || page * size >= total}
          onClick={() => onChange(page + 1)}
        >
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
