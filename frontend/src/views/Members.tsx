import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchMembers, createMember, updateMember, deleteMember } from '../api';
import { Search, Users, CheckCircle, AlertCircle, GraduationCap, CalendarDays, Plus, Edit2, Trash2, X } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useState } from 'react';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export default function Members() {
  const queryClient = useQueryClient();
  const { data: members, isLoading } = useQuery({
    queryKey: ['members'],
    queryFn: fetchMembers,
  });

  const [search, setSearch] = useState('');
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingId, setEditingId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    facebookId: '',
    phone: '',
    name: '',
    activeStatus: 'active',
    feeEligibility: 'eligible',
    role: 'user'
  });
  const [formError, setFormError] = useState('');

  const filteredMembers = members?.filter((m: any) => 
    m.name?.toLowerCase().includes(search.toLowerCase()) ||
    m.facebookId?.toLowerCase().includes(search.toLowerCase())
  );

  const createMut = useMutation({
    mutationFn: createMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setIsModalOpen(false);
    },
    onError: (err: any) => setFormError(err.message)
  });

  const updateMut = useMutation({
    mutationFn: updateMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setIsModalOpen(false);
    },
    onError: (err: any) => setFormError(err.message)
  });

  const deleteMut = useMutation({
    mutationFn: deleteMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
    },
    onError: (err: any) => alert(err.message)
  });

  const handleOpenCreate = () => {
    setModalMode('create');
    setEditingId(null);
    setFormData({ facebookId: '', phone: '', name: '', activeStatus: 'active', feeEligibility: 'eligible', role: 'user' });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleOpenEdit = (member: any) => {
    setModalMode('edit');
    setEditingId(member.id);
    setFormData({
      facebookId: member.facebookId,
      phone: member.phone || '',
      name: member.name,
      activeStatus: member.activeStatus,
      feeEligibility: member.feeEligibility,
      role: member.role || 'user'
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleDelete = (id: string, name: string) => {
    if (window.confirm(`Bạn có chắc chắn muốn xóa thành viên ${name}? Hành động này có thể gây lỗi nếu thành viên đã có dữ liệu đóng quỹ/xin nghỉ.`)) {
      deleteMut.mutate(id);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (modalMode === 'create') {
      createMut.mutate(formData);
    } else if (modalMode === 'edit' && editingId) {
      updateMut.mutate({ id: editingId, data: formData });
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-2xl font-bold text-slate-800">Quản lý Thành viên</h2>
        
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input 
              type="text" 
              placeholder="Tìm kiếm thành viên..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-sm w-full sm:w-64"
            />
          </div>
          <button onClick={handleOpenCreate} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors shadow-sm font-medium">
            <Plus size={18} />
            Thêm mới
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
                <tr className="bg-slate-50/50 border-b border-slate-200 text-sm font-medium text-slate-500 whitespace-nowrap">
                  <th className="px-6 py-4">Họ và Tên</th>
                  <th className="px-6 py-4">Facebook PSID</th>
                  <th className="px-6 py-4">SĐT</th>
                  <th className="px-6 py-4">Trạng thái</th>
                  <th className="px-6 py-4">Tình trạng quỹ</th>
                  <th className="px-6 py-4">Quyền</th>
                  <th className="px-6 py-4 text-center">Nghỉ phép</th>
                  <th className="px-6 py-4 text-right">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredMembers?.map((member: any) => (
                  <tr key={member.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-900 whitespace-nowrap">{member.name || 'Unknown'}</td>
                    <td className="px-6 py-4 font-mono text-sm text-slate-500">{member.facebookId}</td>
                    <td className="px-6 py-4 font-mono text-sm text-slate-500">{member.phone || '-'}</td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border uppercase",
                        member.activeStatus === 'active' ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                        member.activeStatus === 'paused' ? "bg-amber-50 text-amber-700 border-amber-200" :
                        "bg-rose-50 text-rose-700 border-rose-200"
                      )}>
                        {member.activeStatus}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {member.feeEligibility === 'exempt' ? (
                        <span className="text-xs text-slate-500 italic">Được miễn</span>
                      ) : member.feeAmount > 0 ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
                          <AlertCircle size={14} /> Nợ {(member.feeAmount / 1000).toFixed(0)}k ₫
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle size={14} /> Đã đóng
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {member.role === 'admin' ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
                          User
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-center gap-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100" title="Nghỉ đào tạo">
                          <GraduationCap size={14} /> {member.trainingLeaveCount || 0}
                        </span>
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100" title="Nghỉ họp tháng">
                          <CalendarDays size={14} /> {member.meetingLeaveCount || 0}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button 
                          onClick={() => handleOpenEdit(member)}
                          className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title="Sửa thông tin"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button 
                          onClick={() => handleDelete(member.id, member.name)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                          title="Xóa thành viên"
                          disabled={deleteMut.isPending}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!filteredMembers?.length && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                      <div className="flex flex-col items-center justify-center">
                        <Users size={48} className="text-slate-300 mb-4" />
                        <p className="text-lg font-medium text-slate-600">Không tìm thấy thành viên</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-scale-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-800">
                {modalMode === 'create' ? 'Thêm Thành viên mới' : 'Chỉnh sửa Thành viên'}
              </h3>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 text-sm text-rose-600 bg-rose-50 rounded-lg">
                  {formError}
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Họ và Tên</label>
                <input
                  required
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Ví dụ: Nguyễn Văn A"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Quyền hạn (Role)</label>
                <select
                  value={formData.role}
                  onChange={e => setFormData({...formData, role: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="user">User (Thành viên)</option>
                  <option value="admin">Admin (Quản trị viên)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Facebook PSID</label>
                <input
                  required
                  type="text"
                  value={formData.facebookId}
                  onChange={e => setFormData({...formData, facebookId: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                  placeholder="Ví dụ: 1234567890123456"
                />
                <p className="mt-1 text-xs text-slate-500">Phải là Page-Scoped ID hợp lệ từ Messenger</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Số điện thoại (Nhận diện nộp quỹ SePay)</label>
                <input
                  type="text"
                  value={formData.phone}
                  onChange={e => setFormData({...formData, phone: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                  placeholder="Ví dụ: 0987654321"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Trạng thái</label>
                  <select
                    value={formData.activeStatus}
                    onChange={e => setFormData({...formData, activeStatus: e.target.value})}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="active">Active (Đang hoạt động)</option>
                    <option value="paused">Paused (Tạm nghỉ)</option>
                    <option value="quit">Quit (Đã rời nhóm)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Thuộc diện nộp quỹ</label>
                  <select
                    value={formData.feeEligibility}
                    onChange={e => setFormData({...formData, feeEligibility: e.target.value})}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="eligible">Phải nộp (Eligible)</option>
                    <option value="exempt">Được miễn (Exempt)</option>
                  </select>
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium transition-colors"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={createMut.isPending || updateMut.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium transition-colors disabled:opacity-70"
                >
                  {createMut.isPending || updateMut.isPending ? 'Đang lưu...' : 'Lưu lại'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
