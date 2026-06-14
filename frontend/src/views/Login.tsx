import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getPublicUsers, requestMagicLink, verifyMagicLink } from '../api';

export default function Login() {
  const [users, setUsers] = useState<{id: string, full_name: string}[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
  const from = location.state?.from?.pathname || '/dashboard';

  useEffect(() => {
    // 1. Fetch users for dropdown
    getPublicUsers().then(data => {
      setUsers(data);
      if (data.length > 0) setSelectedUserId(data[0].id);
    }).catch(err => {
      console.error("Failed to load users", err);
    });

    // 2. Check for token in URL
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    
    if (token) {
      setIsVerifying(true);
      verifyMagicLink(token)
        .then(data => {
          login(data.access_token, data.user);
          navigate(from, { replace: true });
        })
        .catch(err => {
          setError(err.message || 'Link đăng nhập không hợp lệ hoặc đã hết hạn.');
          setIsVerifying(false);
          // Remove token from URL
          window.history.replaceState({}, document.title, window.location.pathname);
        });
    }
  }, [login, navigate, from]);

  const handleRequestMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsLoading(true);
    
    try {
      await requestMagicLink(selectedUserId);
      setSuccess('Đã gửi link đăng nhập. Vui lòng kiểm tra tin nhắn Messenger từ S-Group Bot.');
    } catch (err: any) {
      setError(err.message || 'Không thể gửi link đăng nhập. Vui lòng thử lại.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isVerifying) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 sm:px-6 lg:px-8">
        <div className="w-full max-w-md space-y-8 rounded-xl bg-white p-10 shadow-lg text-center">
          <h2 className="mt-6 text-2xl font-bold tracking-tight text-gray-900 animate-pulse">
            Đang xác thực...
          </h2>
          <p className="text-gray-500">Vui lòng đợi trong giây lát</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-xl bg-white p-10 shadow-lg">
        <div>
          <h2 className="mt-6 text-center text-3xl font-bold tracking-tight text-gray-900">
            S-Group Platform
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Chọn tên của bạn để nhận link đăng nhập qua Messenger
          </p>
        </div>
        
        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <h3 className="text-sm font-medium text-red-800">{error}</h3>
          </div>
        )}

        {success && (
          <div className="rounded-md bg-emerald-50 p-4">
            <h3 className="text-sm font-medium text-emerald-800">{success}</h3>
          </div>
        )}

        <form className="mt-8 space-y-6" onSubmit={handleRequestMagicLink}>
          <div className="-space-y-px rounded-md shadow-sm">
            <div>
              <label htmlFor="userId" className="block text-sm font-medium text-gray-700 mb-2">
                Họ và Tên
              </label>
              <select
                id="userId"
                name="userId"
                required
                className="relative block w-full rounded-md border-0 py-2.5 px-3 text-gray-900 ring-1 ring-inset ring-gray-300 focus:z-10 focus:ring-2 focus:ring-inset focus:ring-blue-600 sm:text-sm sm:leading-6 bg-white"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                disabled={isLoading}
              >
                {users.map(u => (
                  <option key={u.id} value={u.id}>{u.full_name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading || !selectedUserId || !!success}
              className="group relative flex w-full justify-center rounded-md bg-blue-600 py-2.5 px-3 text-sm font-semibold text-white hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Đang gửi...' : 'Nhận link đăng nhập'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
