const API_BASE = '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('sgroup_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

export const getPublicUsers = async () => {
  const res = await fetch(`${API_BASE}/v1/auth/users`);
  if (!res.ok) throw new Error('Failed to fetch users');
  return res.json();
};

export const requestMagicLink = async (userId: string) => {
  const res = await fetch(`${API_BASE}/v1/auth/request-magic-link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to request magic link');
  }
  return res.json();
};

export const verifyMagicLink = async (token: string) => {
  const res = await fetch(`${API_BASE}/v1/auth/verify-magic-link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error('Invalid or expired token');
  return res.json();
};

export const fetchUserStats = async () => {
  const res = await fetch(`${API_BASE}/v1/users/me/stats`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch user stats');
  return res.json();
};

export const submitLeaveRequest = async (type: string, date: string, reason: string) => {
  const res = await fetch(`${API_BASE}/v1/leaves`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ type, date, reason }),
  });
  if (!res.ok) throw new Error('Failed to submit leave request');
  return res.json();
};

export const fetchDashboard = async () => {
  const res = await fetch(`${API_BASE}/v1/dashboard`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch dashboard stats');
  return res.json();
};

export const fetchMembers = async () => {
  const res = await fetch(`${API_BASE}/v1/members`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch members');
  return res.json();
};

export const fetchReviews = async () => {
  const res = await fetch(`${API_BASE}/v1/manual-reviews`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch reviews');
  return res.json();
};

export const fetchHistory = async () => {
  const res = await fetch(`${API_BASE}/v1/history`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
};

export const resolveReview = async (recordId: string, finalCategory: string) => {
  const res = await fetch(`${API_BASE}/v1/manual-reviews/${recordId}/resolve`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ finalCategory }),
  });
  if (!res.ok) throw new Error('Failed to resolve review');
  return res.json();
};

export const createMember = async (data: any) => {
  const res = await fetch(`${API_BASE}/v1/admin/members`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create member');
  }
  return res.json();
};

export const updateMember = async ({ id, data }: { id: string, data: any }) => {
  const res = await fetch(`${API_BASE}/v1/admin/members/${id}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to update member');
  }
  return res.json();
};

export const deleteMember = async (id: string) => {
  const res = await fetch(`${API_BASE}/v1/admin/members/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to delete member');
  }
  return res.json();
};

export const fetchCourses = async () => {
  const res = await fetch(`${API_BASE}/v1/training/courses`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch courses');
  return res.json();
};

export const createCourse = async (data: any) => {
  const res = await fetch(`${API_BASE}/v1/training/courses`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create course');
  return res.json();
};

export const fetchCourseSessions = async (courseId: string) => {
  const res = await fetch(`${API_BASE}/v1/training/courses/${courseId}/sessions`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch course sessions');
  return res.json();
};

export const createCourseSession = async ({ courseId, data }: { courseId: string, data: any }) => {
  const res = await fetch(`${API_BASE}/v1/training/courses/${courseId}/sessions`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create course session');
  return res.json();
};

export const fetchCourseMembers = async (courseId: string) => {
  const res = await fetch(`${API_BASE}/v1/training/courses/${courseId}/members`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch course members');
  return res.json();
};

export const addCourseMember = async ({ courseId, userId }: { courseId: string, userId: string }) => {
  const res = await fetch(`${API_BASE}/v1/training/courses/${courseId}/members`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ userId }),
  });
  if (!res.ok) throw new Error('Failed to add course member');
  return res.json();
};

export const removeCourseMember = async ({ courseId, userId }: { courseId: string, userId: string }) => {
  const res = await fetch(`${API_BASE}/v1/training/courses/${courseId}/members/${userId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to remove course member');
  return res.json();
};
