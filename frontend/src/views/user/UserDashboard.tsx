import { useAuth } from '../../contexts/AuthContext';
import { Calendar, DollarSign, Activity, FileText } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchUserStats, submitLeaveRequest } from '../../api';
import { useState } from 'react';

export default function UserDashboard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  
  const [leaveType, setLeaveType] = useState('training_leave');
  const [leaveDate, setLeaveDate] = useState('');
  const [leaveReason, setLeaveReason] = useState('');
  
  const { data: userStats, isLoading } = useQuery({
    queryKey: ['userStats'],
    queryFn: fetchUserStats,
  });

  const leaveMutation = useMutation({
    mutationFn: () => submitLeaveRequest(leaveType, leaveDate, leaveReason),
    onSuccess: () => {
      alert("Đã gửi đơn xin nghỉ thành công! Bot sẽ gửi thông báo đến Facebook của bạn.");
      setLeaveDate('');
      setLeaveReason('');
      queryClient.invalidateQueries({ queryKey: ['userStats'] });
    },
    onError: (err) => {
      alert("Lỗi khi gửi đơn: " + err.message);
    }
  });

  const handleSubmitLeave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!leaveDate || !leaveReason) {
      alert("Vui lòng điền đầy đủ ngày và lý do.");
      return;
    }
    leaveMutation.mutate();
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-slate-200 rounded"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-2xl"></div>
          ))}
        </div>
      </div>
    );
  }

  // Fallback data if error
  const stats = userStats || {
    feeStatus: 'Chưa có dữ liệu',
    feeDebt: '0 ₫',
    trainingLeaves: 0,
    meetingLeaves: 0,
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Trang cá nhân</h2>
        <p className="text-slate-500 mt-1">Xin chào, {user?.name}!</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-500">Tình trạng quỹ</h3>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <DollarSign size={20} />
            </div>
          </div>
          <p className="text-xl font-bold text-slate-800">{stats.feeStatus}</p>
          <p className="text-sm text-slate-500 mt-1">Nợ: <span className="text-emerald-600 font-medium">{stats.feeDebt}</span></p>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-500">Nghỉ Đào tạo</h3>
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Calendar size={20} />
            </div>
          </div>
          <p className="text-3xl font-bold text-slate-800">{stats.trainingLeaves}</p>
          <p className="text-sm text-slate-500 mt-1">Trong tháng này</p>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-500">Nghỉ Họp tháng</h3>
            <div className="p-2 bg-violet-50 text-violet-600 rounded-lg">
              <Activity size={20} />
            </div>
          </div>
          <p className="text-3xl font-bold text-slate-800">{stats.meetingLeaves}</p>
          <p className="text-sm text-slate-500 mt-1">Trong năm nay</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <FileText size={20} />
            </div>
            <h3 className="text-lg font-bold text-slate-800">Nội quy S-Group</h3>
          </div>
          <div className="prose prose-slate prose-sm max-w-none text-slate-600">
            <p>1. Tham gia đầy đủ các buổi họp tháng và đào tạo.</p>
            <p>2. Đóng quỹ đúng hạn vào ngày 10 hàng tháng.</p>
            <p>3. Tôn trọng các thành viên khác trong tổ chức.</p>
            <p>4. Nếu cần xin nghỉ, vui lòng điền form hoặc báo bot trước 24h.</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-orange-50 text-orange-600 rounded-lg">
              <Calendar size={20} />
            </div>
            <h3 className="text-lg font-bold text-slate-800">Đăng ký xin nghỉ</h3>
          </div>
          
          <form className="space-y-4" onSubmit={handleSubmitLeave}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Loại xin nghỉ</label>
              <select 
                className="w-full border-slate-200 rounded-lg text-sm focus:ring-blue-500 focus:border-blue-500 p-2.5 border bg-white"
                value={leaveType}
                onChange={e => setLeaveType(e.target.value)}
              >
                <option value="training_leave">Nghỉ đào tạo</option>
                <option value="meeting_leave">Nghỉ họp tháng</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Ngày xin nghỉ</label>
              <input 
                type="date" 
                className="w-full border-slate-200 rounded-lg text-sm focus:ring-blue-500 focus:border-blue-500 p-2.5 border"
                value={leaveDate}
                onChange={e => setLeaveDate(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Lý do</label>
              <textarea 
                rows={3} 
                className="w-full border-slate-200 rounded-lg text-sm focus:ring-blue-500 focus:border-blue-500 p-2.5 border placeholder:text-slate-400" 
                placeholder="Nhập lý do chính đáng..."
                value={leaveReason}
                onChange={e => setLeaveReason(e.target.value)}
              ></textarea>
            </div>
            <button 
              type="submit" 
              disabled={leaveMutation.isPending}
              className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {leaveMutation.isPending ? "Đang gửi..." : "Gửi yêu cầu"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
