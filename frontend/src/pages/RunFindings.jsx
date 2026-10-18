import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRunDetails } from '../api';
import LoadingState from '../components/ui/LoadingState';
import { ChevronRight, AlertTriangle, FileText } from 'lucide-react';

export default function RunFindings() {
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

  if (loading) return <div className="p-4 sm:p-6 lg:p-8"><LoadingState label="Loading findings..." /></div>;
  if (!details) return <div className="p-4 sm:p-6 lg:p-8">Failed to load run details.</div>;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 pb-20 sm:space-y-8 sm:p-6 sm:pb-20 lg:p-8 lg:pb-20">
      <div className="mb-2 flex flex-wrap items-center gap-y-1 text-xs font-mono text-ink-3">
        <Link to="/runs" className="hover:text-ink hover:underline">Runs</Link>
        <ChevronRight size={12} className="mx-1" />
        <Link to={`/runs/${id}`} className="hover:text-ink hover:underline">{id.substring(0,8)}</Link>
        <ChevronRight size={12} className="mx-1" />
        <span>Findings & Conflicts</span>
      </div>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl text-ink flex items-center gap-2">
          <AlertTriangle className="text-red" /> Findings & Conflicts
        </h1>
        <p className="text-sm text-ink-3 mt-1">Detailed breakdown of issues detected during analysis.</p>
      </div>

      {details.findings.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-line p-6 text-ink-3 sm:p-12">
          <AlertTriangle size={32} className="mb-4 opacity-50 text-green" />
          <p className="text-sm font-medium">Verification completed successfully.</p>
          <p className="text-xs mt-1">All compared claims were consistent across the supplied sources. No findings were detected.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {details.findings.map(finding => (
            <div key={finding.id} className="rounded-card bg-surface border border-line shadow-card overflow-hidden">
              <div className="flex flex-col items-start justify-between gap-3 border-b border-line bg-inset p-4 sm:flex-row sm:gap-4">
                <div>
                   <h2 className="text-sm font-bold text-ink">{finding.title}</h2>
                   <p className="text-xs text-ink-2 mt-1">{finding.summary}</p>
                </div>
                <div className={`px-2 py-1 rounded text-[11px] font-bold uppercase tracking-wider
                   ${finding.status === 'pending' ? 'bg-orange/10 text-orange' : 
                     finding.status === 'approved' ? 'bg-green/10 text-green' : 'bg-red/10 text-red'}`}>
                   {finding.status}
                </div>
              </div>
              <div className="p-4 bg-surface space-y-4">
                 <h3 className="text-xs font-semibold text-ink-3 uppercase tracking-wider">Supporting Evidence</h3>
                 
                 {finding.claims.map(claim => (
                    <div key={claim.id} className="p-3 rounded-control border border-line bg-canvas">
                       <p className="text-sm font-medium text-ink mb-3">{claim.statement}</p>
                       <div className="space-y-2">
                          {claim.evidence.map(ev => (
                             <div key={ev.id} className="flex gap-3 text-xs">
                                <FileText size={14} className="text-ink-3 shrink-0 mt-0.5" />
                                <div>
                                   <p className="font-mono text-ink-2 mb-1">{ev.document_name || 'Unknown source'}</p>
                                   <p className="text-ink-3 italic border-l-2 border-line pl-2">"{ev.snippet}"</p>
                                </div>
                             </div>
                          ))}
                       </div>
                    </div>
                 ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
