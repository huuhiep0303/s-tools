import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchCourses, createCourse, fetchCourseSessions, createCourseSession, fetchCourseMembers, addCourseMember, removeCourseMember, fetchMembers } from '../api';
import { BookOpen, Calendar, Users, Plus, X, Trash2, Link as LinkIcon } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useAuth } from '../contexts/AuthContext';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export default function Classes() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedCourse, setSelectedCourse] = useState<string | null>(null);
  
  // Modals
  const [isCourseModalOpen, setIsCourseModalOpen] = useState(false);
  const [isSessionModalOpen, setIsSessionModalOpen] = useState(false);
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  
  // Form states
  const [courseForm, setCourseForm] = useState({ name: '', description: '', mentor_id: '' });
  const [sessionForm, setSessionForm] = useState({ session_number: '', title: '', date: '', materials_url: '', homework_desc: '', homework_deadline: '' });
  const [memberForm, setMemberForm] = useState({ userId: '' });

  // Queries
  const { data: courses, isLoading: loadingCourses } = useQuery({
    queryKey: ['courses'],
    queryFn: fetchCourses
  });
  
  const { data: sessions, isLoading: loadingSessions } = useQuery({
    queryKey: ['course_sessions', selectedCourse],
    queryFn: () => fetchCourseSessions(selectedCourse!),
    enabled: !!selectedCourse
  });
  
  const { data: members, isLoading: loadingMembers } = useQuery({
    queryKey: ['course_members', selectedCourse],
    queryFn: () => fetchCourseMembers(selectedCourse!),
    enabled: !!selectedCourse
  });

  const { data: allUsers } = useQuery({
    queryKey: ['members'],
    queryFn: fetchMembers
  });

  // Mutations
  const createCourseMut = useMutation({
    mutationFn: () => createCourse({ ...courseForm }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      setIsCourseModalOpen(false);
      setCourseForm({ name: '', description: '', mentor_id: '' });
    }
  });

  const createSessionMut = useMutation({
    mutationFn: () => createCourseSession({ courseId: selectedCourse!, data: sessionForm }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course_sessions', selectedCourse] });
      setIsSessionModalOpen(false);
      setSessionForm({ session_number: '', title: '', date: '', materials_url: '', homework_desc: '', homework_deadline: '' });
    }
  });

  const addMemberMut = useMutation({
    mutationFn: () => addCourseMember({ courseId: selectedCourse!, userId: memberForm.userId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course_members', selectedCourse] });
      setIsMemberModalOpen(false);
      setMemberForm({ userId: '' });
    }
  });

  const removeMemberMut = useMutation({
    mutationFn: (userId: string) => removeCourseMember({ courseId: selectedCourse!, userId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course_members', selectedCourse] });
    }
  });

  const handleCreateCourse = (e: React.FormEvent) => {
    e.preventDefault();
    createCourseMut.mutate();
  };

  const handleCreateSession = (e: React.FormEvent) => {
    e.preventDefault();
    createSessionMut.mutate();
  };

  const handleAddMember = (e: React.FormEvent) => {
    e.preventDefault();
    addMemberMut.mutate();
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Quản lý Đào tạo</h2>
          <p className="text-slate-500 mt-1">Quản lý lớp học, buổi học và bài tập</p>
        </div>
        <button
          onClick={() => setIsCourseModalOpen(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors flex items-center gap-2 shadow-sm shadow-blue-200"
        >
          <Plus size={16} />
          Tạo Lớp Mới
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Course List (Left Sidebar) */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden flex flex-col h-[calc(100vh-12rem)]">
          <div className="p-4 border-b border-slate-100 bg-slate-50">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <BookOpen size={18} className="text-blue-600" />
              Danh sách Lớp học
            </h3>
          </div>
          <div className="overflow-y-auto flex-1 p-2 space-y-1">
            {loadingCourses ? (
              <p className="text-sm text-slate-500 p-4">Đang tải...</p>
            ) : courses?.length === 0 ? (
              <p className="text-sm text-slate-500 p-4">Chưa có lớp học nào.</p>
            ) : (
              courses?.map((c: any) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCourse(c.id)}
                  className={cn(
                    "w-full text-left p-3 rounded-xl transition-all duration-200",
                    selectedCourse === c.id 
                      ? "bg-blue-50 border-blue-100 border text-blue-700 shadow-sm" 
                      : "hover:bg-slate-50 border border-transparent text-slate-700"
                  )}
                >
                  <p className="font-semibold">{c.name}</p>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-1">{c.description || "Chưa có mô tả"}</p>
                  <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                    <Users size={12} /> Mentor: {c.mentorName}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Course Details (Main Area) */}
        <div className="lg:col-span-2 space-y-6 h-[calc(100vh-12rem)] overflow-y-auto pr-2">
          {!selectedCourse ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 bg-white rounded-2xl border border-slate-100 border-dashed">
              <BookOpen size={48} className="mb-4 text-slate-300" />
              <p>Chọn một lớp học để xem chi tiết</p>
            </div>
          ) : (
            <>
              {/* Sessions */}
              <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <Calendar size={18} className="text-emerald-600" />
                    Các buổi Đào tạo
                  </h3>
                  <button 
                    onClick={() => setIsSessionModalOpen(true)}
                    className="text-sm text-blue-600 font-medium hover:text-blue-700 flex items-center gap-1 bg-white px-2 py-1 rounded border border-blue-100"
                  >
                    <Plus size={14} /> Thêm buổi
                  </button>
                </div>
                <div className="p-4 space-y-4">
                  {loadingSessions ? <p className="text-sm text-slate-500">Đang tải...</p> : sessions?.length === 0 ? <p className="text-sm text-slate-500">Chưa có buổi học nào.</p> : sessions?.map((s: any) => (
                    <div key={s.id} className="border border-slate-100 rounded-xl p-4 bg-slate-50/50 hover:border-slate-200 transition-colors">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-bold text-slate-800 text-lg">
                          <span className="text-emerald-600 mr-2">{s.sessionNumber}:</span> 
                          {s.title}
                        </h4>
                        {s.date && <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded-md border border-slate-200">
                          {new Date(s.date).toLocaleDateString('vi-VN')}
                        </span>}
                      </div>
                      
                      {s.materialsUrl && (
                        <a href={s.materialsUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline mb-3">
                          <LinkIcon size={14} /> Tài liệu buổi học
                        </a>
                      )}
                      
                      {s.homeworkDesc && (
                        <div className="mt-3 bg-white p-3 rounded-lg border border-orange-100 shadow-sm">
                          <p className="text-sm font-semibold text-orange-800 mb-1">Bài tập về nhà:</p>
                          <p className="text-sm text-slate-600 whitespace-pre-wrap">{s.homeworkDesc}</p>
                          {s.homeworkDeadline && (
                            <p className="text-xs font-medium text-rose-600 mt-2 flex items-center gap-1">
                              <Calendar size={12} /> 
                              Deadline: {new Date(s.homeworkDeadline).toLocaleString('vi-VN')}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Members */}
              <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <Users size={18} className="text-indigo-600" />
                    Danh sách Học viên
                  </h3>
                  <button 
                    onClick={() => setIsMemberModalOpen(true)}
                    className="text-sm text-blue-600 font-medium hover:text-blue-700 flex items-center gap-1 bg-white px-2 py-1 rounded border border-blue-100"
                  >
                    <Plus size={14} /> Thêm Học viên
                  </button>
                </div>
                <div className="p-0">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50/50 text-slate-500 font-medium">
                      <tr>
                        <th className="px-4 py-3">Họ Tên</th>
                        <th className="px-4 py-3">Thao tác</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {loadingMembers ? <tr><td colSpan={2} className="p-4">Đang tải...</td></tr> : members?.length === 0 ? <tr><td colSpan={2} className="p-4 text-slate-500 text-center">Chưa có học viên.</td></tr> : members?.map((m: any) => (
                        <tr key={m.userId} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-4 py-3 font-medium text-slate-700">{m.name}</td>
                          <td className="px-4 py-3">
                            <button 
                              onClick={() => {
                                if (window.confirm(`Xoá ${m.name} khỏi lớp này?`)) removeMemberMut.mutate(m.userId);
                              }}
                              className="text-slate-400 hover:text-rose-600 transition-colors p-1"
                            >
                              <Trash2 size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Modals */}
      {isCourseModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-scale-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-800">Tạo Lớp Mới</h3>
              <button onClick={() => setIsCourseModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <form onSubmit={handleCreateCourse} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Tên lớp</label>
                <input required type="text" value={courseForm.name} onChange={e => setCourseForm({...courseForm, name: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="VD: Lớp React K10" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Mô tả (Tùy chọn)</label>
                <textarea rows={3} value={courseForm.description} onChange={e => setCourseForm({...courseForm, description: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="Mô tả tóm tắt lớp học" />
              </div>
              {user?.role === 'admin' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Chọn Mentor (Admin only)</label>
                  <select
                    value={courseForm.mentor_id}
                    onChange={e => setCourseForm({...courseForm, mentor_id: e.target.value})}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                  >
                    <option value="">-- Mặc định (Chính bạn) --</option>
                    {allUsers?.map((u: any) => (
                      <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                    ))}
                  </select>
                </div>
              )}
              <button type="submit" disabled={createCourseMut.isPending} className="w-full bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 transition-colors">
                {createCourseMut.isPending ? "Đang tạo..." : "Tạo Lớp"}
              </button>
            </form>
          </div>
        </div>
      )}

      {isSessionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-scale-in max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-slate-100 sticky top-0 bg-white">
              <h3 className="text-lg font-bold text-slate-800">Thêm Buổi Học</h3>
              <button onClick={() => setIsSessionModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <form onSubmit={handleCreateSession} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Số thứ tự/Buổi</label>
                  <input required type="text" value={sessionForm.session_number} onChange={e => setSessionForm({...sessionForm, session_number: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="VD: Buổi 1" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Ngày học</label>
                  <input type="datetime-local" value={sessionForm.date} onChange={e => setSessionForm({...sessionForm, date: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Chủ đề/Tiêu đề</label>
                <input required type="text" value={sessionForm.title} onChange={e => setSessionForm({...sessionForm, title: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="VD: Giới thiệu HTML CSS" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Link Tài liệu (Tùy chọn)</label>
                <input type="url" value={sessionForm.materials_url} onChange={e => setSessionForm({...sessionForm, materials_url: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="https://..." />
              </div>
              <div className="pt-4 border-t border-slate-100">
                <h4 className="font-medium text-slate-800 mb-3 flex items-center gap-2"><BookOpen size={16}/> Bài tập về nhà</h4>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Mô tả bài tập</label>
                  <textarea rows={3} value={sessionForm.homework_desc} onChange={e => setSessionForm({...sessionForm, homework_desc: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="Yêu cầu bài tập..." />
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-slate-700 mb-1">Hạn nộp (Deadline)</label>
                  <input type="datetime-local" value={sessionForm.homework_deadline} onChange={e => setSessionForm({...sessionForm, homework_deadline: e.target.value})} className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
                </div>
              </div>
              
              <button type="submit" disabled={createSessionMut.isPending} className="w-full bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 transition-colors mt-6">
                {createSessionMut.isPending ? "Đang lưu..." : "Lưu Buổi học"}
              </button>
            </form>
          </div>
        </div>
      )}

      {isMemberModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-scale-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-800">Thêm Học viên</h3>
              <button onClick={() => setIsMemberModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <form onSubmit={handleAddMember} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Chọn thành viên</label>
                <select 
                  required
                  value={memberForm.userId}
                  onChange={e => setMemberForm({userId: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                >
                  <option value="">-- Chọn thành viên --</option>
                  {allUsers?.map((u: any) => (
                    <option key={u.id} value={u.id}>{u.name}</option>
                  ))}
                </select>
              </div>
              <button type="submit" disabled={addMemberMut.isPending || !memberForm.userId} className="w-full bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
                {addMemberMut.isPending ? "Đang thêm..." : "Thêm vào lớp"}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
