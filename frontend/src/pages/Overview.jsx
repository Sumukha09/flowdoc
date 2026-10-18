import { useEffect, useState } from 'react';
import { getGlobalStats, getRuns } from '../api';
import { Activity, FileText, CheckCircle, AlertTriangle, PlayCircle, List } from 'lucide-react';
import { Link } from 'react-router-dom';
import FilterTable from '../components/ui/FilterTable';

function StatCard({ title, value, label, icon: Icon, colorClass }) {
  return (
    <div className="rounded-card bg-surface shadow-card p-4 flex flex-col justify-between">
      <div className="flex items-start justify-between">
        <span className="text-sm font-medium text-ink-2">{title}</span>
        <div className={`p-2 rounded-control bg-field ${colorClass}`}>
          <Icon size={16} />
        </div>
      </div>
      <div className="mt-4">
        <div className="text-2xl font-bold text-ink tracking-tight">{value}</div>
        <div className="text-xs text-ink-3 mt-1 uppercase tracking-wider">{label}</div>
      </div>
    </div>
  );
}

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, runsData] = await Promise.all([
          getGlobalStats().catch(() => null),
          getRuns().catch(() => [])
        ]);
        if (statsData) setStats(statsData);
        setRuns(runsData);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full flex-col p-4 sm:p-6 lg:p-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 bg-field rounded-full animate-pulse" />
          <div className="space-y-2">
            <div className="w-48 h-6 bg-field rounded animate-pulse" />
            <div className="w-32 h-4 bg-field rounded animate-pulse" />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
            <div key={i} className="h-32 rounded-card bg-field animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const s = stats || {
    total_runs: 0, active_runs: 0, successful_runs: 0, failed_runs: 0,
    total_documents: 0, total_claims: 0, total_findings: 0, pending_approvals: 0, total_cost_micro: 0
  };

  const tableFilters = [
    { key: "all", label: "All Runs", count: runs.length },
    { key: "running", label: "Running", dot: "var(--accent)", count: runs.filter(r => r.status === 'running' || r.status === 'pending').length },
    { key: "completed", label: "Completed", dot: "var(--green)", count: runs.filter(r => r.status === 'completed').length },
    { key: "failed", label: "Failed", dot: "var(--red)", count: runs.filter(r => r.status === 'failed').length },
  ];

  const tableRows = runs.map(r => {
    const isRunning = r.status === 'running' || r.status === 'pending';
    const isFailed = r.status === 'failed';
    const pillClass = isRunning ? "text-accent bg-accent-tint" : isFailed ? "text-red bg-red/10" : "text-green bg-green/10";
    
    return {
      statusKey: isRunning ? 'running' : r.status,
      cells: [
        <Link key={r.id} to={`/runs/${r.id}`} className="hover:underline text-ink font-mono">{r.id.substring(0, 8)}</Link>,
        <span key="date" className="tabular-nums">{new Date().toLocaleDateString()}</span>, // Fake date until we get it from backend
        <span key="status" className={`inline-flex h-5 items-center rounded-[5px] px-1.5 text-[11px] font-medium uppercase ${pillClass}`}>{r.status}</span>,
        <Link key="action" to={`/runs/${r.id}`} className="text-accent-ink hover:underline">View details</Link>
      ]
    };
  });

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 pb-20 sm:space-y-8 sm:p-6 sm:pb-20 lg:p-8 lg:pb-20">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold text-accent mb-2">DOCUMENT REVIEW WORKSPACE</p>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl text-ink">Your review desk</h1>
          <p className="text-sm text-ink-3 mt-2">Follow each document from intake through verified findings.</p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
           <Link 
             to="/runs/new"
             className="flex w-full items-center justify-center gap-2 rounded-control bg-accent px-3 py-2 text-sm font-medium text-white shadow-btn transition-colors hover:bg-accent-ink sm:w-auto"
           >
              <PlayCircle size={16} /> Start a review
           </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4 sm:gap-4">
        <StatCard title="Active Runs" value={s.active_runs} label="Currently Executing" icon={Activity} colorClass="text-accent" />
        <StatCard title="Documents Processed" value={s.total_documents} label="Total Ingested" icon={FileText} colorClass="text-ink" />
        <StatCard title="Claims Extracted" value={s.total_claims} label="Grounded Statements" icon={CheckCircle} colorClass="text-green" />
        <StatCard title="Pending Approvals" value={s.pending_approvals} label="Awaiting Human Review" icon={AlertTriangle} colorClass="text-orange" />
        <StatCard title="Total Findings" value={s.total_findings} label="Detected issues" icon={AlertTriangle} colorClass="text-red" />
        <StatCard title="Total Runs" value={s.total_runs} label="All time" icon={List} colorClass="text-ink-2" />
      </div>

      <div className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold tracking-tight text-ink">Recent reviews</h2>
          <Link to="/runs" className="text-sm font-medium text-accent-ink hover:underline">View all runs</Link>
        </div>
        {runs.length > 0 ? (
          <FilterTable 
            columns={{
              template: '1fr 1fr 1fr 1fr',
              headers: ['Run ID', 'Date', 'Status', 'Actions']
            }}
            filters={tableFilters} 
            rows={tableRows} 
          />
        ) : (
          <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-line p-6 text-ink-3 sm:p-12">
            <Activity size={32} className="mb-4 opacity-50" />
            <p className="text-sm">No runs executed yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
