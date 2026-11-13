"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useState, type FormEvent } from "react";
import { API, ApiError, request, title } from "@/lib/api";

const Context = createContext<{ token: string; fail: (e: unknown) => string }>({ token: "", fail: () => "Request failed" });
export const useDesk = () => useContext(Context);
export function Badge({ status }: { status: string }) { return <span className={`badge ${status.toLowerCase()}`}><span aria-hidden="true">●</span> {title(status)}</span>; }
export function Notice({ error, children }: { error?: boolean; children: React.ReactNode }) { return <div role={error ? "alert" : "status"} className={`notice ${error ? "error" : ""}`}>{children}</div>; }
export function DeskProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState(""); const [user, setUser] = useState("");
  const [error, setError] = useState(""); const [pending, setPending] = useState(false);
  const pathname = usePathname();
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setPending(true); setError("");
    const form = new FormData(e.currentTarget);
    const bytes = new TextEncoder().encode(`${form.get("username")}:${form.get("password")}`);
    const value = btoa(Array.from(bytes, b => String.fromCharCode(b)).join(""));
    try { await request(value, "/stats"); setUser(String(form.get("username"))); setToken(value); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Cannot reach the API. Check that the backend is running."); }
    finally { setPending(false); }
  }
  function fail(e: unknown) {
    if (e instanceof ApiError && e.status === 401) { setToken(""); setError("Your session has expired. Sign in again."); }
    return e instanceof ApiError ? `${e.message} (${e.code})${e.status === 409 ? " The latest invoice has been reloaded; review it before trying again." : ""}` : "Cannot reach the API. Check your connection and try again.";
  }
  if (!token) return <main className="login"><section className="login-story"><div className="wordmark"><span className="brand-mark">ie</span> Invoice Exception Desk</div><div><p className="eyebrow">ACCOUNTS PAYABLE · UNDER CONTROL</p><h1>A second look.<br/>Before the ledger.</h1><p>Catch invoice mistakes before they reach your ledger.</p><div className="flow"><span>Extract</span><b>→</b><span>Validate</span><b>→</b><span>Review</span></div></div><small>Synthetic invoice demonstration · No payments or ERP writeback</small></section><section className="login-form"><form onSubmit={login}><p className="eyebrow">YOUR WORKSPACE</p><h2>Welcome to the desk</h2><p className="muted">Sign in with your local operator credentials.</p>{error && <Notice error>{error}</Notice>}<label>Username<input name="username" autoComplete="username" required maxLength={200}/></label><label>Password<input name="password" type="password" autoComplete="current-password" required/></label><button className="primary w-full" disabled={pending}>{pending ? "Connecting…" : "Open workspace →"}</button><p className="fine">Credentials stay in memory for this browser tab. Find your operator login in the project’s local .env file.</p><p className="fine">API: {API}</p></form></section></main>;
  const nav = [["/", "Overview", "◫"], ["/invoices/", "All invoices", "▤"], ["/exceptions/", "Exception queue", "◇"], ["/ledger/", "Ledger", "▦"], ["/vendors/", "Suppliers", "▱"]];
  return <Context.Provider value={{ token, fail }}><div className="workspace"><aside className="sidebar"><Link className="wordmark" href="/"><span className="brand-mark">ie</span><span>Invoice <br/>Exception Desk</span></Link><p className="nav-label">WORKSPACE</p><nav>{nav.map(([href, label, icon]) => <Link key={href} href={href} className={(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? "active" : ""}><span aria-hidden="true">{icon}</span>{label}</Link>)}</nav><div className="sidebar-bottom"><span className="live-dot"/> Local demonstration<p>Synthetic data. Human decisions.<br/>No external financial actions.</p></div></aside><div className="workspace-body"><header className="topbar"><span><span className="live-dot"/> Local workspace <span className="muted">/ Accounts payable</span></span><div className="operator"><span className="avatar">{user.slice(0, 2).toUpperCase()}</span><span>{user}</span><button className="link-button" onClick={() => setToken("")}>Sign out</button></div></header><main className="main-content">{children}</main><footer>INVOICE EXCEPTION DESK <span>Internal ledger · Synthetic demonstration</span></footer></div></div></Context.Provider>;
}
export function Heading({ eyebrow, title: heading, subtitle, children }: { eyebrow: string; title: string; subtitle: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{heading}</h1><p className="muted">{subtitle}</p></div><div className="heading-actions">{children}</div></div>;
}
export function Pager({ page, total, onChange }: { page: number; total: number; onChange: (p: number) => void }) {
  return <div className="pager"><span>{total} record{total === 1 ? "" : "s"} · Page {page} of {Math.max(1, Math.ceil(total / 20))}</span><div><button disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button><button disabled={page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button></div></div>;
}
