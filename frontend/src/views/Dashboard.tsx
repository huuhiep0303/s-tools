import { useQuery } from '@tanstack/react-query';
import { fetchDashboard, fetchHistory } from '../api';
import { useAuth } from '../contexts/AuthContext';
import UserDashboard from './user/UserDashboard';
import { Users, UserMinus, UserCheck, DollarSign, CalendarOff, Activity } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

function StatCard({ title, value, icon: Icon, trend, colorClass }: any) {
  return (
    <div className="glass-panel rounded-2xl p-6 transition-all hover:-translate-y-1 hover:shadow-2xl duration-300">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-slate-500 mb-1">{title}</p>
          <h3 className="text-3xl font-bold text-slate-900 tracking-tight">{value}</h3>
        </div>
        <div className={cn("p-3 rounded-xl", colorClass)}>
          <Icon size={24} />
        </div>
      </div>
      {trend && (
        <div className="mt-4 flex items-center text-sm">
          <span className="text-green-600 font-medium">{trend}</span>
          <span className="text-slate-400 ml-2">vs last month</span>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    enabled: user?.role === 'admin',
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['history'],
    queryFn: fetchHistory,
    enabled: user?.role === 'admin',
  });

  if (user?.role === 'user') {
    return <UserDashboard />;
  }

  if (statsLoading || historyLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-slate-200 rounded animate-pulse"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-2xl animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-slide-up">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-800">Overview</h2>
        {stats?.lastUpdated && (
          <span className="text-sm text-slate-500 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
            Last updated: {new Date(stats.lastUpdated).toLocaleString()}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard 
          title="Active Members" 
          value={stats?.activeMembers || 0} 
          icon={Users} 
          colorClass="bg-blue-50 text-blue-600"
        />
        <StatCard 
          title="Paused Members" 
          value={stats?.pausedMembers || 0} 
          icon={UserMinus} 
          colorClass="bg-amber-50 text-amber-600"
        />
        <StatCard 
          title="Monthly Revenue" 
          value={stats?.monthlyRevenue ? `${(stats.monthlyRevenue / 1000000).toFixed(1)}M ₫` : '0'} 
          icon={DollarSign} 
          colorClass="bg-emerald-50 text-emerald-600"
        />
        <StatCard 
          title="Quit Members" 
          value={stats?.quitMembers || 0} 
          icon={UserCheck} 
          colorClass="bg-rose-50 text-rose-600"
        />
        <StatCard 
          title="Training Leaves" 
          value={stats?.trainingLeaveCount || 0} 
          icon={CalendarOff} 
          colorClass="bg-indigo-50 text-indigo-600"
        />
        <StatCard 
          title="Meeting Leaves" 
          value={stats?.meetingLeaveCount || 0} 
          icon={Activity} 
          colorClass="bg-violet-50 text-violet-600"
        />
      </div>

      <div className="mt-10">
        <h3 className="text-xl font-bold text-slate-800 mb-6">Recent Activity</h3>
        <div className="glass-panel rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-200 text-sm font-medium text-slate-500">
                  <th className="px-6 py-4">Time</th>
                  <th className="px-6 py-4">User ID</th>
                  <th className="px-6 py-4">Type</th>
                  <th className="px-6 py-4">Confidence</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history?.slice(0, 10).map((item: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4 text-sm text-slate-600">{new Date(item.timestamp).toLocaleString()}</td>
                    <td className="px-6 py-4 text-sm font-medium text-slate-900">{item.facebookId}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                        {item.requestType}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div 
                            className={cn(
                              "h-full rounded-full", 
                              item.confidence > 0.8 ? "bg-green-500" : item.confidence > 0.5 ? "bg-amber-500" : "bg-red-500"
                            )}
                            style={{ width: `${item.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500">{(item.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium",
                        item.status === 'success' ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-rose-50 text-rose-700 border border-rose-200"
                      )}>
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {!history?.length && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                      No recent activity found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
