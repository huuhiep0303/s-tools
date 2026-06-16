import { useQuery } from '@tanstack/react-query';
import { fetchUserStats } from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import { User, Wallet, GraduationCap, CalendarDays, CheckCircle, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export default function Profile() {
  const { user } = useAuth();
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['userStats'],
    queryFn: fetchUserStats,
  });

  if (isLoading) {
    return (
      <div className="p-8 flex justify-center">
        <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="p-8 text-center text-rose-600">
        <p>Lỗi khi tải thông tin cá nhân. Vui lòng thử lại sau.</p>
      </div>
    );
  }

  const isDebtFree = stats.feeDebt === "0 ₫";

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-2xl font-bold text-slate-800">Thông tin Cá nhân</h2>
      </div>

      <div className="glass-panel p-6 rounded-2xl flex items-center gap-6">
        <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-primary-500 to-primary-600 shadow-lg border-4 border-white flex items-center justify-center text-white font-bold text-3xl">
          {user?.name?.charAt(0).toUpperCase() || 'U'}
        </div>
        <div>
          <h3 className="text-xl font-bold text-slate-800">{user?.name}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
              <User size={14} /> {user?.facebookId}
            </span>
            <span className={cn(
              "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium uppercase border",
              user?.role === 'admin' ? "bg-purple-50 text-purple-700 border-purple-200" : "bg-blue-50 text-blue-700 border-blue-200"
            )}>
              {user?.role}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Fee Status Card */}
        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex items-center gap-3 mb-4">
            <div className={cn(
              "p-2.5 rounded-xl text-white shadow-sm",
              isDebtFree ? "bg-emerald-500" : "bg-rose-500"
            )}>
              <Wallet size={24} />
            </div>
            <h3 className="text-lg font-semibold text-slate-800">Tình trạng Quỹ</h3>
          </div>
          
          <div className="space-y-3">
            <div>
              <p className="text-sm text-slate-500 mb-1">Nợ hiện tại</p>
              <div className="flex items-baseline gap-2">
                <span className={cn(
                  "text-3xl font-bold tracking-tight",
                  isDebtFree ? "text-slate-800" : "text-rose-600"
                )}>
                  {stats.feeDebt}
                </span>
                {!isDebtFree && <AlertCircle size={18} className="text-rose-500" />}
              </div>
            </div>
            
            <div className="pt-3 border-t border-slate-100">
              <p className="text-sm font-medium text-slate-600 flex items-center gap-2">
                {isDebtFree ? <CheckCircle size={16} className="text-emerald-500" /> : <AlertCircle size={16} className="text-rose-500" />}
                {stats.feeStatus}
              </p>
            </div>
          </div>
        </div>

        {/* Training Leaves Card */}
        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-indigo-500 p-2.5 rounded-xl text-white shadow-sm">
              <GraduationCap size={24} />
            </div>
            <h3 className="text-lg font-semibold text-slate-800">Nghỉ Đào tạo</h3>
          </div>
          
          <div className="space-y-3">
            <div>
              <p className="text-sm text-slate-500 mb-1">Tháng hiện tại</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold tracking-tight text-slate-800">
                  {stats.trainingLeaves}
                </span>
                <span className="text-sm text-slate-500 font-medium">buổi</span>
              </div>
            </div>
            
            <div className="pt-3 border-t border-slate-100">
              <p className="text-xs text-slate-500">Giới hạn: 1 buổi / tháng</p>
            </div>
          </div>
        </div>

        {/* Meeting Leaves Card */}
        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-blue-500 p-2.5 rounded-xl text-white shadow-sm">
              <CalendarDays size={24} />
            </div>
            <h3 className="text-lg font-semibold text-slate-800">Nghỉ Họp tháng</h3>
          </div>
          
          <div className="space-y-3">
            <div>
              <p className="text-sm text-slate-500 mb-1">Năm hiện tại</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold tracking-tight text-slate-800">
                  {stats.meetingLeaves}
                </span>
                <span className="text-sm text-slate-500 font-medium">buổi</span>
              </div>
            </div>
            
            <div className="pt-3 border-t border-slate-100">
              <p className="text-xs text-slate-500">Giới hạn: 2 buổi / năm</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
