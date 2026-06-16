import { Outlet, NavLink, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LayoutDashboard, Users, ClipboardCheck, Settings, LogOut, MessageSquare, User, ChevronDown } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', roles: ['admin', 'user'] },
    { to: '/members', icon: Users, label: 'Members', roles: ['admin'] },
    { to: '/reviews', icon: ClipboardCheck, label: 'Manual Reviews', roles: ['admin'] },
  ];

  const visibleNavItems = navItems.filter(item => 
    !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shadow-sm hidden md:flex">
        <div className="h-16 flex items-center px-6 border-b border-slate-100">
          <div className="flex items-center gap-2 text-primary-600">
            <div className="w-8 h-8 rounded-lg bg-primary-100 flex items-center justify-center">
              <MessageSquare size={20} />
            </div>
            <span className="font-bold text-lg tracking-tight">SGroup AI</span>
          </div>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1">
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )
              }
            >
              <item.icon size={20} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-100">
          <button 
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <LogOut size={20} />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-10">
          <h1 className="text-xl font-semibold text-slate-800">SGroup AI Management</h1>
          <div className="flex items-center gap-4">
            <div className="text-sm text-slate-600 hidden md:block">
              Welcome, <span className="font-semibold text-slate-800">{user?.name}</span>
              <span className="ml-2 px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium capitalize">
                {user?.role}
              </span>
            </div>
            
            <div className="relative" ref={dropdownRef}>
              <button 
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center gap-2 p-1 rounded-full hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary-500 to-primary-600 shadow-sm border border-white flex items-center justify-center text-white font-bold text-sm">
                  {user?.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <ChevronDown size={16} className="text-slate-500 hidden sm:block" />
              </button>

              {isDropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-100 py-1 z-50 animate-scale-in">
                  <div className="px-4 py-2 border-b border-slate-100 md:hidden">
                    <p className="text-sm font-medium text-slate-800 truncate">{user?.name}</p>
                    <p className="text-xs text-slate-500 capitalize">{user?.role}</p>
                  </div>
                  <Link 
                    to="/profile"
                    onClick={() => setIsDropdownOpen(false)}
                    className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <User size={16} />
                    My Profile
                  </Link>
                  <div className="border-t border-slate-100 my-1"></div>
                  <button 
                    onClick={() => {
                      setIsDropdownOpen(false);
                      handleLogout();
                    }}
                    className="flex items-center gap-2 px-4 py-2 text-sm text-rose-600 hover:bg-rose-50 w-full text-left transition-colors"
                  >
                    <LogOut size={16} />
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-6 md:p-8 animate-fade-in">
          <div className="max-w-6xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
