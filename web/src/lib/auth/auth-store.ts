'use client';

import {create} from 'zustand';

type AuthState = {
  accessToken: string | null;
  tenantId: string | null;
  membershipId: string | null;
  setSession: (session: {
    accessToken: string;
    tenantId?: string | null;
    membershipId?: string | null;
  }) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  tenantId: null,
  membershipId: null,
  setSession: ({accessToken, tenantId = null, membershipId = null}) =>
    set({accessToken, tenantId, membershipId}),
  clearSession: () =>
    set({accessToken: null, tenantId: null, membershipId: null}),
}));
