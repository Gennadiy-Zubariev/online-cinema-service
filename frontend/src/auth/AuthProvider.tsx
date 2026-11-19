import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'

import * as accountsApi from '../api/accounts'
import { refreshAccessToken, setAccessToken, setSessionExpiredHandler } from '../api/client'
import { AuthContext, type AuthStatus } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<AuthStatus>('loading')

  // Page load: the access token is not stored anywhere, so try to get a new one
  // from the refresh cookie. No cookie / expired -> guest.
  useEffect(() => {
    void refreshAccessToken().then((token) => setStatus(token ? 'user' : 'guest'))
    setSessionExpiredHandler(() => {
      setStatus('guest')
      queryClient.clear()
    })
    return () => setSessionExpiredHandler(null)
  }, [queryClient])

  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: accountsApi.getProfile,
    enabled: status === 'user',
  })

  async function login(email: string, password: string) {
    const { access_token } = await accountsApi.login(email, password)
    setAccessToken(access_token)
    queryClient.clear() // drop data cached for the guest
    setStatus('user')
  }

  async function logout() {
    try {
      await accountsApi.logout()
    } finally {
      setAccessToken(null)
      queryClient.clear()
      setStatus('guest')
    }
  }

  const group = profile?.group
  const value = {
    status,
    profile: status === 'user' ? profile : undefined,
    isModerator: group === 'moderator' || group === 'admin',
    isAdmin: group === 'admin',
    login,
    logout,
  }

  return <AuthContext value={value}>{children}</AuthContext>
}
