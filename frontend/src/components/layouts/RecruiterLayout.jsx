import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const NAV = [
  { to: '/recruiter/dashboard', label: 'Dashboard',  Icon: IconDash },
  { to: '/recruiter/jobs',      label: 'Jobs',        Icon: IconBriefcase },
  { to: '/recruiter/analytics', label: 'Analytics',  Icon: IconChart },
  { to: '/recruiter/profile',   label: 'Profile',    Icon: IconBuilding },
  { to: '/recruiter/settings',  label: 'Settings',   Icon: IconCog },
]

export default function RecruiterLayout() {
  const { auth, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const initials = auth?.name
    ? auth.name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
    : auth?.email?.[0]?.toUpperCase() || 'R'

  return (
    <div className="flex h-screen bg-zinc-50">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col bg-zinc-950 text-zinc-300 border-r border-zinc-800">
        {/* Wordmark */}
        <div className="px-5 h-14 flex items-center border-b border-zinc-800">
          <span className="text-white font-semibold tracking-tight text-sm">ResumeIQ</span>
          <span className="ml-2 text-[10px] bg-indigo-600/20 text-indigo-400 px-1.5 py-0.5 rounded font-medium">Recruiter</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-zinc-800 text-white'
                    : 'hover:bg-zinc-800/60 text-zinc-400 hover:text-zinc-100'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="px-4 py-4 border-t border-zinc-800 flex items-center gap-3">
          <div className="w-7 h-7 rounded-full bg-violet-600 flex items-center justify-center text-xs font-medium text-white shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-zinc-200 truncate">{auth?.name || auth?.email}</p>
            <p className="text-[10px] text-zinc-500 truncate">{auth?.email}</p>
          </div>
          <button onClick={handleLogout} className="text-zinc-500 hover:text-zinc-300 transition-colors" title="Sign out">
            <IconLogout size={14} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  )
}

function IconDash({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  )
}
function IconBriefcase({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="2" y="5" width="12" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 5V3.5A1.5 1.5 0 016.5 2h3A1.5 1.5 0 0111 3.5V5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M2 9h12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}
function IconChart({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M2 12l4-4 3 3 5-7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
function IconBuilding({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="2" y="3" width="12" height="11" rx="1" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 14V10h2v4M9 14V10h2v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <path d="M5 6h2M9 6h2M5 8h2M9 8h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}
function IconCog({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  )
}
function IconLogout({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <path d="M11 11l3-3-3-3M14 8H6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
