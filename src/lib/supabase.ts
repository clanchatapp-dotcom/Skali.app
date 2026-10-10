import { createClient } from '@supabase/supabase-js'

const env = (import.meta as any).env
// Public config — safe to ship in the client bundle (anon/publishable key & OAuth
// client id are designed for public exposure). Falling back to baked defaults means
// a missing CI secret can NEVER crash the app into a black screen again.
const PUBLIC_SUPABASE_URL = 'https://ixahrtibbpjruggivjik.supabase.co'
const PUBLIC_SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml4YWhydGliYnBqcnVnZ2l2amlrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk0MDI2NjMsImV4cCI6MjEwNDk3ODY2M30.4yKosj4HuCrPp5Rw1KZ9rGejkzkQdWJAHTO9-QEuCTU'

const url = (env.REACT_APP_SUPABASE_URL as string) || PUBLIC_SUPABASE_URL
const anonKey = (env.REACT_APP_SUPABASE_ANON_KEY as string) || PUBLIC_SUPABASE_ANON_KEY

export const supabase = createClient(url, anonKey, {
  auth: {
    flowType: 'pkce',
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false,
  },
})

// Web Google sign-in -> redirects the browser to Google, returns to /auth/callback
export async function signInGoogleWeb() {
  return supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: `${window.location.origin}/auth/callback` },
  })
}
