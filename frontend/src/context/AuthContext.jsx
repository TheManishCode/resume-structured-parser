import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const AuthContext = createContext(null)

const STORAGE_KEY = 'atp_auth'

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(loadStored)

  useEffect(() => {
    if (auth) localStorage.setItem(STORAGE_KEY, JSON.stringify(auth))
    else localStorage.removeItem(STORAGE_KEY)
  }, [auth])

  const login = useCallback((tokenResponse) => {
    setAuth({
      token:          tokenResponse.access_token,
      role:           tokenResponse.role,
      userId:         tokenResponse.user_id,
      email:          tokenResponse.email,
      name:           tokenResponse.name,
      onboardingDone: tokenResponse.onboarding_done,
    })
  }, [])

  const logout = useCallback(() => setAuth(null), [])

  const updateProfile = useCallback((patch) => {
    setAuth(prev => prev ? { ...prev, ...patch } : prev)
  }, [])

  const value = useMemo(() => ({
    auth,
    login,
    logout,
    updateProfile,
    isAuthenticated: !!auth,
    isCandidate:     auth?.role === 'candidate',
    isRecruiter:     auth?.role === 'recruiter',
    token:           auth?.token,
  }), [auth, login, logout, updateProfile])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
