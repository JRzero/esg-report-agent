'use client';

import {create} from 'zustand';
import type {SessionIdentity} from '@/lib/api/types';

type AuthState = {
  identity: SessionIdentity | null;
  setIdentity: (identity: SessionIdentity) => void;
  clearIdentity: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  identity: null,
  setIdentity: (identity) => set({identity}),
  clearIdentity: () => set({identity: null}),
}));
