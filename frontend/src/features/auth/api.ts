import {
  ApiError,
  request,
  acceptAuthentication,
  logoutAuthentication,
  authenticationTransition,
} from "@/lib/api";
import type { AuthUser, LoginFields } from "./types";
export const authApi = {
  me: async (signal?: AbortSignal): Promise<AuthUser | null> => {
    try {
      return await request<AuthUser>("/auth/me", { signal });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },
  login: async (values: LoginFields) => {
    const result = await authenticationTransition(() =>
      request<{ user: AuthUser; csrf_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      }),
    );
    acceptAuthentication(result.csrf_token);
    announce("signed-in");
    return result.user;
  },
  logout: async () => {
    await logoutAuthentication();
    announce("signed-out");
  },
};
function announce(type: string) {
  if (typeof window !== "undefined" && "BroadcastChannel" in window) {
    const channel = new BroadcastChannel("invoice-desk-auth");
    channel.postMessage(type);
    channel.close();
  }
}
