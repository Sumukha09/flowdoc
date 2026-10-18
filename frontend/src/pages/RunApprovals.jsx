import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getRunDetails, approveFinding, commitCleanRun } from '../api';
import ApprovalCard from '../components/ui/ApprovalCard';
import LoadingState from '../components/ui/LoadingState';
import { ChevronRight, CheckSquare } from 'lucide-react';

export default function RunApprovals() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getRunDetails(id);
        setDetails(data);
      } catch(e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <div className="p-4 sm:p-6 lg:p-8"><LoadingState label="Loading findings for review..." /></div>;
  if (!details) return <div className="p-4 sm:p-6 lg:p-8">Failed to load run details.</div>;

  const pendingFindings = details.findings.filter(f => f.status === 'pending');

  const handleDecision = async (findingId, decision, comment) => {
    if (submitting) return; // Prevent race conditions
    setSubmitting(true);
    try {
      await approveFinding(id, findingId, decision, null, comment);
      
      // Reload details directly from authoritative backend state
      const newData = await getRunDetails(id);
      setDetails(newData);
    } catch(e) {
      console.error(e);
      alert(`Failed to submit decision: ${e.message || e}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="mb-2 flex flex-wrap items-center gap-y-1 text-xs font-mono text-ink-3">
        <Link to="/runs" className="hover:text-ink hover:underline">Runs</Link>
        <ChevronRight size={12} className="mx-1" />
        <Link to={`/runs/${id}`} className="hover:text-ink hover:underline">{id.substring(0,8)}</Link>
        <ChevronRight size={12} className="mx-1" />
        <span>Approvals</span>
      </div>
      
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl text-ink flex items-center gap-2">
          <CheckSquare className="text-accent" /> Human Review Gate
        </h1>
        <p className="text-sm text-ink-3 mt-1">Review and action the agent's findings before they are committed.</p>
      </div>

      {pendingFindings.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-line p-6 text-ink-3 sm:p-12">
          <CheckSquare size={32} className="mb-4 text-green opacity-50" />
          <p className="text-sm mb-4">No pending items require your decision.</p>
          <button 
            onClick={async () => {
              try {
                setSubmitting(true);
                await commitCleanRun(id);
                navigate(`/runs/${id}`, { replace: true });
              } catch(e) {
                console.error(e);
                alert(`Failed to commit run: ${e.message || e}`);
              } finally {
                setSubmitting(false);
              }
            }}
            disabled={submitting}
            className="w-full rounded bg-accent px-4 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50 sm:w-auto sm:py-2"
          >
            {submitting ? "Committing..." : "Commit Clean Run"}
          </button>
          <Link to={`/runs/${id}`} className="mt-4 text-ink-3 text-sm hover:underline">Return to Run Timeline</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
           <div className="space-y-4">
              <h2 className="text-sm font-semibold text-ink-3 uppercase tracking-wider">Review Queue ({pendingFindings.length})</h2>
              <ApprovalCard 
                 finding={pendingFindings[0]} 
                 totalPending={pendingFindings.length}
                 onSubmit={handleDecision}
                 isSubmitting={submitting}
              />
           </div>
           <div className="space-y-4">
              <h2 className="text-sm font-semibold text-ink-3 uppercase tracking-wider">Context</h2>
              <div className="p-4 rounded-card bg-inset border border-line text-sm text-ink-2">
                 Please review the items on the left carefully. Your decisions directly affect the final deliverable. Rejected findings will be excluded.
              </div>
           </div>
        </div>
      )}
    </div>
  );
}
