const API_BASE = 'http://localhost:8000/api';

export const fetchDashboard = async () => {
  const res = await fetch(`${API_BASE}/v1/dashboard`);
  if (!res.ok) throw new Error('Failed to fetch dashboard stats');
  return res.json();
};

export const fetchMembers = async () => {
  const res = await fetch(`${API_BASE}/v1/members`);
  if (!res.ok) throw new Error('Failed to fetch members');
  return res.json();
};

export const fetchReviews = async () => {
  const res = await fetch(`${API_BASE}/v1/manual-reviews`);
  if (!res.ok) throw new Error('Failed to fetch reviews');
  return res.json();
};

export const fetchHistory = async () => {
  const res = await fetch(`${API_BASE}/v1/history`);
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
};

export const resolveReview = async (recordId: string, finalCategory: string) => {
  const res = await fetch(`${API_BASE}/v1/manual-reviews/${recordId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ finalCategory }),
  });
  if (!res.ok) throw new Error('Failed to resolve review');
  return res.json();
};
