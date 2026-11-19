import { createContext } from 'react'

import type { Profile } from '../api/types'

// loading - on page load we don't know yet (refresh cookie is being checked);
// guest - not logged in; user - logged in.
export type AuthStatus = 'loading' | 'guest' | 'user'

export interface AuthContextValue {
  status: AuthStatus
  // Profile with email and group; undefined while loading or for a guest.
  profile: Profile | undefined
  isModerator: boolean
  isAdmin: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
