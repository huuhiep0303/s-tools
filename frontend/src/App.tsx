import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Dashboard from './views/Dashboard';
import Members from './views/Members';
import Reviews from './views/Reviews';
import Classes from './views/Classes';
import Login from './views/Login';
import Profile from './views/user/Profile';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            <Route path="/" element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="profile" element={<Profile />} />
                
                {/* Admin and Mentor routes */}
                <Route element={<ProtectedRoute allowedRoles={['admin', 'mentor']} />}>
                  <Route path="classes" element={<Classes />} />
                </Route>

                {/* Admin only routes */}
                <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
                  <Route path="members" element={<Members />} />
                  <Route path="reviews" element={<Reviews />} />
                </Route>
              </Route>
            </Route>
            
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
