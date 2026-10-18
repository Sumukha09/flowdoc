import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRunDetails } from '../api';
import LoadingState from '../components/ui/LoadingState';
import { ChevronRight, FileText, CheckCircle } from 'lucide-react';

export default function RunDeliverable() {
  const { id } = useParams();
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeEvidence, setActiveEvidence] = useState(null);

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

  if (loading) return <div className="p-4 sm:p-6 lg:p-8"><LoadingState label="Loading deliverable..." /></div>;
  if (!details) return <div className="p-4 sm:p-6 lg:p-8">Failed to load run details.</div>;

  const approvedFindings = details.findings.filter(f => f.status === 'approved');

  return (
    <div className="deliverable-layout mx-auto flex max-w-6xl flex-col gap-6 p-4 pb-20 sm:gap-8 sm:p-6 sm:pb-20 lg:flex-row lg:p-8 lg:pb-20">
      <div className="min-w-0 flex-1 space-y-6 sm:space-y-8">
         <div className="mb-2 flex flex-wrap items-center gap-y-1 text-xs font-mono text-ink-3">
            <Link to="/runs" className="hover:text-ink hover:underline">Runs</Link>
            <ChevronRight size={12} className="mx-1" />
            <Link to={`/runs/${id}`} className="hover:text-ink hover:underline">{id.substring(0,8)}</Link>
            <ChevronRight size={12} className="mx-1" />
            <span>Deliverable</span>
         </div>
         
         <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl text-ink flex items-center gap-2">
               <FileText className="text-accent" /> Grounded Deliverable
            </h1>
            <p className="text-sm text-ink-3 mt-1">Final output with full evidence traceability.</p>
         </div>

         <div className="bg-surface rounded-card shadow-card border border-line overflow-hidden text-ink font-sans leading-relaxed">
            <div className="p-5 sm:p-8 xl:p-12">
               <h2 className="text-2xl font-bold mb-6 border-b pb-4">Verification Report</h2>
               
               {approvedFindings.length === 0 ? (
                  <p className="text-ink-2">No verified findings to report. The corpus is clean.</p>
               ) : (
                  <div className="space-y-8">
                     {approvedFindings.map(finding => (
                        <div key={finding.id} className="space-y-3">
                           <h3 className="text-lg font-semibold">{finding.title}</h3>
                           <p className="text-ink-2">{finding.summary}</p>
                           
                           <ul className="list-disc pl-5 space-y-2">
                              {finding.claims.map(claim => (
                                 <li key={claim.id} className="text-ink">
                                    {claim.statement}
                                    <button 
                                       onClick={() => setActiveEvidence(claim.evidence)}
                                       className="ml-2 inline-flex items-center gap-1 text-[10px] font-mono bg-accent-tint text-accent-ink px-1.5 py-0.5 rounded border border-accent/20 hover:bg-hover-2 transition-colors"
                                    >
                                       [Evidence]
                                    </button>
                                 </li>
                              ))}
                           </ul>
                        </div>
                     ))}
                  </div>
               )}
            </div>
         </div>
      </div>
      
      {/* Evidence Sidebar */}
      <div className="w-full shrink-0 lg:w-80">
         <div className="flex h-64 flex-col rounded-card border border-line bg-surface p-4 shadow-card sm:h-72 lg:sticky lg:top-8 lg:h-[calc(100svh-8rem)]">
            <h3 className="text-sm font-semibold text-ink uppercase tracking-wider mb-4 border-b border-line pb-2 flex items-center gap-2">
               <CheckCircle size={16} className="text-green" /> Traceability
            </h3>
            
            <div className="flex-1 overflow-y-auto">
               {!activeEvidence ? (
                  <p className="text-sm text-ink-3">Click an [Evidence] marker in the document to trace its origin.</p>
               ) : (
                  <div className="space-y-4">
                     {activeEvidence.map((ev, i) => (
                        <div key={ev.id || i} className="space-y-2 bg-inset p-3 rounded-control border border-line">
                           <span className="text-xs font-mono text-accent">Source Document</span>
                           <p className="text-sm font-medium text-ink break-all">{ev.document_name}</p>
                           
                           <span className="text-xs font-mono text-accent block mt-3">Exact Quote</span>
                           <p className="text-sm text-ink-2 italic border-l-2 border-line pl-2">"{ev.snippet}"</p>
                        </div>
                     ))}
                  </div>
               )}
            </div>
         </div>
      </div>
    </div>
  );
}
