"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import Cookies from "js-cookie";
import { authApi, setAuth } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

/** Decode a JWT payload without verifying (UI-only use). Returns null on malformed tokens. */
function decodeJwtPayload(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return null;
  }
}

function claimsDriftedFrom(token: string | null, orgIndustry: string | undefined, orgModules: string[] | undefined): boolean {
  const claims = decodeJwtPayload(token);
  if (!claims) return false;
  const claimIndustry = claims["industry"] as string | undefined;
  const claimModules = (claims["modules"] as string[] | undefined) ?? [];
  if (claimIndustry && orgIndustry && claimIndustry !== orgIndustry) return true;
  if (orgModules) {
    const a = [...claimModules].sort().join(",");
    const b = [...orgModules].sort().join(",");
    if (a !== b) return true;
  }
  return false;
}

export function useLogin() {
  const { setUser, setOrg } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      setAuth(data.access_token, data.refresh_token, data.user?.org_id);
      setUser(data.user);
      if (data.user?.org) setOrg(data.user.org);
      toast.success(`Welcome back, ${data.user.full_name.split(" ")[0]}!`);
      router.push("/dashboard");
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Login failed. Check your credentials.");
    },
  });
}

export function useRegister() {
  const { setUser } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.register,
    onSuccess: (data) => {
      setAuth(data.access_token, data.refresh_token, data.org_slug);
      router.push("/dashboard");
      toast.success("Welcome to the Fairview School Portal.");
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Registration failed.");
    },
  });
}

export function useMe() {
  const { isAuthenticated, setUser, setOrg, logout } = useAuthStore();
  const router = useRouter();

  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const data = await authApi.me();
      setUser(data);
      if (data?.org) {
        setOrg(data.org);
        // Detect stale JWT: if the server now reports a different industry
        // or a different module set than what this token was issued with,
        // soft-logout so the next login reseats identity claims.
        const token = Cookies.get("access_token") ?? null;
        if (claimsDriftedFrom(token, data.org.industry, data.org.modules_enabled)) {
          toast.info("Your organisation configuration changed. Please sign in again.");
          logout();
          router.replace("/login");
        }
      }
      return data;
    },
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLogout() {
  const { logout } = useAuthStore();
  const router = useRouter();

  return () => {
    logout();
    router.push("/login");
    toast.info("Logged out successfully.");
  };
}
