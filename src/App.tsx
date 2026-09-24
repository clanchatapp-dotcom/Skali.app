import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from './lib/auth'
import { applyTheme } from './lib/theme'
import { useAndroidBackButton } from './lib/useAndroidBackButton'
import { configurePush } from './lib/pushNotifications'
import Layout from './components/Layout'
import Login from './pages/Login'
import Feed from './pages/Feed'
import Profile from './pages/Profile'
import Links from './pages/Links'
import Messages from './pages/Messages'
import ConversationInfo from './pages/ConversationInfo'
import SearchPage from './pages/Search'
import Interest from './pages/Interest'
import Activity from './pages/Activity'
import Admin from './pages/Admin'
import Verify from './pages/Verify'
import Settings from './pages/Settings'
import Plans from './pages/Plans'
import Connections from './pages/Connections'
import Groups from './pages/Groups'
import Reels from './pages/Reels'
import AuthCallback from './pages/AuthCallback'
import Legal from './pages/Legal'
import { Loader2 } from 'lucide-react'

export default function App() {
  const { user, loading } = useAuth()
  const [backHint, setBackHint] = useState(false)
  useAndroidBackButton()

  useEffect(() => {
    const u = user as any
    applyTheme({ theme: u?.theme, accent: u?.accent, font_size: u?.font_size })
    if (u?.id) configurePush()  // register for FCM push once signed in (native Android only)
  }, [user])

  useEffect(() => {
    const on = () => { setBackHint(true); setTimeout(() => setBackHint(false), 1800) }
    window.addEventListener('cc-back-hint', on)
    return () => window.removeEventListener('cc-back-hint', on)
  }, [])

  return (
    <>
      {backHint && (
        <div className="fixed bottom-24 inset-x-0 z-[70] flex justify-center pointer-events-none">
          <div className="bg-panel border border-edge rounded-full px-4 py-2 text-sm text-slate-200 shadow-lg">Press back again to exit</div>
        </div>
      )}
      <Routes>
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/legal" element={<Legal />} />
      <Route path="/legal/:doc" element={<Legal />} />
      {loading ? (
        <Route path="*" element={<div className="h-full grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>} />
      ) : !user ? (
        <Route path="*" element={<Login />} />
      ) : (
        <Route element={<Layout />}>
          <Route path="/" element={<Feed />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/interest/:tag" element={<Interest />} />
          <Route path="/messages" element={<Messages />} />
          <Route path="/messages/:handle" element={<Messages />} />
          <Route path="/messages/:handle/info" element={<ConversationInfo />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/verify" element={<Verify />} />
          <Route path="/plans" element={<Plans />} />
          <Route path="/connections" element={<Connections />} />
          <Route path="/groups" element={<Groups />} />
          <Route path="/reels" element={<Reels />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/u/:handle/links" element={<Links />} />
          <Route path="/u/:handle" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      )}
      </Routes>
    </>
  )
}
