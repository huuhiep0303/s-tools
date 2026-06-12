import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchReviews, resolveReview } from '../api';
import { Check, X, AlertCircle } from 'lucide-react';


export default function Reviews() {
  const queryClient = useQueryClient();
  const { data: reviews, isLoading } = useQuery({
    queryKey: ['reviews'],
    queryFn: fetchReviews,
  });

  const resolveMutation = useMutation({
    mutationFn: ({ recordId, finalCategory }: { recordId: string; finalCategory: string }) => 
      resolveReview(recordId, finalCategory),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const handleApprove = (review: any) => {
    const category = review.manualClassification || 'unclassified';
    resolveMutation.mutate({ recordId: review.recordId, finalCategory: category });
  };
  
  const handleReclassify = (review: any) => {
    const newCategory = prompt("Enter new category (e.g., training_leave, pause_membership):", review.manualClassification);
    if (newCategory) {
      resolveMutation.mutate({ recordId: review.recordId, finalCategory: newCategory });
    }
  };

  const pendingReviews = reviews?.filter((r: any) => !r.reviewed) || [];
  const completedReviews = reviews?.filter((r: any) => r.reviewed) || [];

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Manual Review Queue</h2>
          <p className="text-slate-500 mt-1">Messages that AI couldn't classify with high confidence.</p>
        </div>
        <div className="px-4 py-2 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 font-medium flex items-center gap-2">
          <AlertCircle size={18} />
          {pendingReviews.length} Pending
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 flex justify-center glass-panel rounded-2xl">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold text-slate-800">Needs Attention</h3>
          
          {pendingReviews.length === 0 ? (
            <div className="glass-panel rounded-2xl p-12 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mb-4">
                <Check size={32} />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-2">All caught up!</h3>
              <p className="text-slate-500">There are no pending reviews in the queue.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {pendingReviews.map((review: any, i: number) => (
                <div key={i} className="glass-panel rounded-xl p-6 border-l-4 border-l-amber-400 flex flex-col md:flex-row gap-6">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-sm font-medium text-slate-900">{review.senderName || review.senderId}</span>
                      <span className="text-xs text-slate-500">{new Date(review.timestamp).toLocaleString()}</span>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-lg border border-slate-100 text-slate-700 mb-4">
                      "{review.messageContent}"
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-slate-500">AI Suggested:</span>
                      <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 font-medium">
                        {review.manualClassification || 'unknown'}
                      </span>
                      <span className="text-xs text-slate-400">({(review.confidence * 100).toFixed(0)}% confidence)</span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col gap-2 justify-center border-t md:border-t-0 md:border-l border-slate-100 pt-4 md:pt-0 md:pl-6 min-w-[200px]">
                    <button 
                      className="btn-primary w-full flex items-center justify-center gap-2"
                      onClick={() => handleApprove(review)}
                      disabled={resolveMutation.isPending}
                    >
                      <Check size={18} /> Approve Suggestion
                    </button>
                    <button 
                      className="btn-secondary w-full flex items-center justify-center gap-2"
                      onClick={() => handleReclassify(review)}
                      disabled={resolveMutation.isPending}
                    >
                      <AlertCircle size={18} /> Reclassify Manually
                    </button>
                    <button className="px-4 py-2 text-rose-600 bg-rose-50 hover:bg-rose-100 rounded-lg transition-colors font-medium text-sm flex items-center justify-center gap-2 mt-auto disabled:opacity-50"
                      disabled={resolveMutation.isPending}>
                      <X size={18} /> Ignore
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {completedReviews.length > 0 && (
            <div className="mt-12">
              <h3 className="text-lg font-semibold text-slate-800 mb-4">Recently Reviewed</h3>
              <div className="glass-panel rounded-2xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50/50 border-b border-slate-200 text-sm font-medium text-slate-500">
                      <th className="px-6 py-4">Sender ID</th>
                      <th className="px-6 py-4">Message</th>
                      <th className="px-6 py-4">Final Class</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {completedReviews.slice(0, 5).map((review: any, i: number) => (
                      <tr key={i}>
                        <td className="px-6 py-4 text-sm font-medium text-slate-900">{review.senderName || review.senderId}</td>
                        <td className="px-6 py-4 text-sm text-slate-600 truncate max-w-xs">{review.messageContent}</td>
                        <td className="px-6 py-4">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {review.manualClassification}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
