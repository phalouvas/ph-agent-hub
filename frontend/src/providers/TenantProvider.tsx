// =============================================================================
// PH Agent Hub — TenantProvider
// =============================================================================
// React context; derives tenant info from AuthProvider.
// =============================================================================

import React, { createContext, useContext } from "react";
import { useAuth } from "./AuthProvider";

interface TenantState {
  tenantId: string | null;
  role: string | null;
}

const TenantContext = createContext<TenantState>({ tenantId: null, role: null });

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  const value: TenantState = {
    tenantId: user?.tenant_id ?? null,
    role: user?.role ?? null,
  };

  return (
    <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
  );
}

export function useTenant(): TenantState {
  return useContext(TenantContext);
}

export default TenantProvider;
