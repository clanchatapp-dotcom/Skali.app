import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { setToken } from '../lib/api'
import { useAuth } from '../lib/auth'

// A PKCE authorization code is single-use: exchanging it consumes the code and
// clears the stored code_verifier. React 18 StrictMode mounts effects twice in
// dev, so without this dedupe the second run exchanges an already-spent code and
// reports "Could not complete sign-in" even though sign-in actually succeeded.
const inflight = new Map<string, ReturnType<typeof supabase.auth.exchangeCodeForSession>>()

function exchangeOnce(code: string) {
  let p = inflight.get(code)
  if (!p) {
    p = supabase.auth.exchangeCodeForSession(code)
    inflight.set(code, p)
  }
  return p
}

export default function AuthCallback() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [msg, setMsg] = useState('Completing sign-in…')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    const fail = (m: string) => { if (!cancelled) { setFailed(true); setMsg(m) } }

    ;(async () => {
      const params = new URLSearchParams(window.location.search)
      const oauthErr = params.get('error_description')
      const code = params.get('code')
      if (oauthErr) return fail(oauthErr)
      if (!code) return fail('Missing authorization code')

      const { data, error } = await exchangeOnce(code)
      if (error) return fail('Could not complete sign-in. Please try again.')
      if (data.session?.access_token) setToken(data.session.access_token)

      // Load the profile BEFORE leaving this screen. If we navigate while the
      // auth context still has user === null, App renders <Login /> and the
      // sign-in looks like it silently bounced back to the login page.
      const user = await refresh()
      if (!user) {
        // Signed in with Google, but our own API would not accept the token.
        // Say so instead of dropping the user on the login screen with no clue.
        return fail('Signed in with Google, but this app could not verify your session. Please try again.')
      }
      if (!cancelled) navigate('/', { replace: true })
    })()

    return () => { cancelled = true }
  }, [navigate, refresh])

  return (
    <div className="h-full grid place-items-center p-6">
      <div className="bg-panel border border-edge rounded-2xl p-8 text-center max-w-sm">
        <p className={failed ? 'text-rose-400' : 'text-slate-200'}>{msg}</p>
        {failed && (
          <button onClick={() => navigate('/', { replace: true })}
            className="mt-5 bg-indigo-500 rounded-xl px-5 py-2.5 font-semibold hover:bg-indigo-400 transition">
            Back to sign-in
          </button>
        )}
      </div>
    </div>
  )
}
