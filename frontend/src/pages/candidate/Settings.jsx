import { useAuth } from '../../context/AuthContext'
import { useNavigate } from 'react-router-dom'

function PageHeader({ title }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
    </div>
  )
}

export default function CandidateSettings() {
  const { logout } = useAuth()
  const navigate   = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Settings" />
      <div className="flex-1 overflow-y-auto bg-zinc-50 p-6">
        <div className="max-w-lg mx-auto space-y-4">
          <div className="bg-white border border-zinc-200 rounded-xl p-5">
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Account</h2>
            <div className="space-y-3">
              <SettingRow label="Change password" description="Update your password" action="Coming soon" />
              <SettingRow label="Delete account" description="Permanently remove your account and all data" action={
                <button className="text-xs text-red-600 hover:text-red-700 font-medium transition-colors">Delete</button>
              } />
            </div>
          </div>

          <div className="bg-white border border-zinc-200 rounded-xl p-5">
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Session</h2>
            <button onClick={handleLogout}
              className="w-full text-left text-sm text-zinc-700 hover:text-zinc-900 transition-colors flex items-center justify-between">
              Sign out
              <span className="text-zinc-400 text-xs">→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SettingRow({ label, description, action }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-zinc-100 last:border-0">
      <div>
        <p className="text-sm text-zinc-800">{label}</p>
        {description && <p className="text-xs text-zinc-500 mt-0.5">{description}</p>}
      </div>
      <div className="text-xs text-zinc-400">
        {typeof action === 'string' ? action : action}
      </div>
    </div>
  )
}
