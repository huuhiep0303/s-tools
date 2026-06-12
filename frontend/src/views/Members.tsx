import { useQuery } from '@tanstack/react-query';
import { fetchMembers } from '../api';
import { Search, Filter, Users, CheckCircle, AlertCircle, GraduationCap, CalendarDays } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useState } from 'react';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export default function Members() {
  const { data: members, isLoading } = useQuery({
    queryKey: ['members'],
    queryFn: fetchMembers,
  });

  const [search, setSearch] = useState('');

  const filteredMembers = members?.filter((m: any) => 
    m.name?.toLowerCase().includes(search.toLowerCase()) ||
    m.facebookId?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-2xl font-bold text-slate-800">Members Directory</h2>
        
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input 
              type="text" 
              placeholder="Search members..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-sm w-full sm:w-64"
            />
          </div>
          <button className="p-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 transition-colors shadow-sm">
            <Filter size={20} />
          </button>
        </div>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 flex justify-center">
            <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-200 text-sm font-medium text-slate-500">
                  <th className="px-6 py-4">Name</th>
                  <th className="px-6 py-4">Facebook ID</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Fee Status</th>
                  <th className="px-6 py-4">Missed Activities</th>
                  <th className="px-6 py-4">Last Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredMembers?.map((member: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-900">{member.name || 'Unknown'}</td>
                    <td className="px-6 py-4 text-sm text-slate-500">{member.facebookId}</td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border",
                        member.activeStatus === 'active' ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                        member.activeStatus === 'paused' ? "bg-amber-50 text-amber-700 border-amber-200" :
                        "bg-rose-50 text-rose-700 border-rose-200"
                      )}>
                        {member.activeStatus || 'inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {member.feeAmount > 0 ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
                          <AlertCircle size={14} /> Owes {(member.feeAmount / 1000).toFixed(0)}k ₫
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle size={14} /> Paid
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100" title="Missed Trainings">
                          <GraduationCap size={14} /> {member.trainingLeaveCount || 0}
                        </span>
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100" title="Missed Meetings">
                          <CalendarDays size={14} /> {member.meetingLeaveCount || 0}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{member.statusDate}</td>
                  </tr>
                ))}
                {!filteredMembers?.length && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                      <div className="flex flex-col items-center justify-center">
                        <Users size={48} className="text-slate-300 mb-4" />
                        <p className="text-lg font-medium text-slate-600">No members found</p>
                        <p className="text-sm">Try adjusting your search criteria</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
