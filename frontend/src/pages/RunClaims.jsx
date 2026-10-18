import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRunDetails } from '../api';
import LoadingState from '../components/ui/LoadingState';
import { ChevronRight, CheckCircle, FileText } from 'lucide-react';

export default function RunClaims() {
  const { id } = useParams();
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);

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

  if (loading) return <div className="p-4 sm:p-6 lg:p-8"><LoadingState label="Loading claims..." /></div>;
  if (!details) return <div className="p-4 sm:p-6 lg:p-8">Failed to load run details.</div>;

  // Extract all claims across all findings for display
  const allClaims = details.findings.flatMap(f => f.claims);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 pb-20 sm:space-y-8 sm:p-6 sm:pb-20 lg:p-8 lg:pb-20">
      <div className="mb-2 flex flex-wrap items-center gap-y-1 text-xs font-mono text-ink-3">
        <Link to="/runs" className="hover:text-ink hover:underline">Runs</Link>
        <ChevronRight size={12} className="mx-1" />
        <Link to={`/runs/${id}`} className="hover:text-ink hover:underline">{id.substring(0,8)}</Link>
        <ChevronRight size={12} className="mx-1" />
        <span>Claims & Evidence</span>
      </div>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl text-ink flex items-center gap-2">
          <CheckCircle className="text-green" /> Claims & Evidence
        </h1>
        <p className="text-sm text-ink-3 mt-1">Information extracted from the ingested documents, grounded in evidence.</p>
      </div>

      {allClaims.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-line p-6 text-ink-3 sm:p-12">
          <CheckCircle size={32} className="mb-4 opacity-50" />
          <p className="text-sm">No claims extracted yet.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {allClaims.map(claim => (
            <div key={claim.id} className="rounded-card bg-surface border border-line shadow-card overflow-hidden">
              <div className="p-4 border-b border-line bg-inset">
                 <p className="text-sm font-semibold text-ink">{claim.statement}</p>
                 {claim.confidence && (
                    <p className="text-xs text-ink-3 mt-1">Confidence: {(claim.confidence * 100).toFixed(1)}%</p>
                 )}
              </div>
              <div className="p-4 space-y-3">
                 <h3 className="text-xs font-semibold text-ink-3 uppercase tracking-wider mb-2">Evidence Sources</h3>
                 {claim.evidence.map(ev => (
                    <div key={ev.id} className="flex gap-3 text-sm">
                       <FileText size={16} className="text-ink-3 shrink-0 mt-0.5" />
                       <div>
                          <p className="font-mono text-xs text-accent mb-1">{ev.document_name}</p>
                          <p className="text-ink-2 italic border-l-2 border-line pl-3">"{ev.snippet}"</p>
                       </div>
                    </div>
                 ))}
                 {claim.evidence.length === 0 && (
                    <p className="text-sm text-ink-3 italic">No evidence snippets recorded for this claim.</p>
                 )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
