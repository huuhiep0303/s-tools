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
  if (!res.ok) throw new Error('Failed to request magic link');
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
