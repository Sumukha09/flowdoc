import { NavLink, useParams } from 'react-router-dom';
import {
  LayoutDashboard,
  List,
  FileText,
  AlertTriangle,
  CheckSquare,
  CheckCircle,
  History,
  Activity,
  Workflow,
} from 'lucide-react';

export default function Sidebar() {
  const { id: runId } = useParams();

  const globalLinks = [
    { to: '/', icon: LayoutDashboard, label: 'Overview' },
    { to: '/runs', icon: List, label: 'Runs' },
  ];

  const runLinks = runId ? [
    { to: `/runs/${runId}`, icon: Activity, label: 'Run Timeline' },
    { to: `/runs/${runId}/documents`, icon: FileText, label: 'Documents' },
    { to: `/runs/${runId}/claims`, icon: CheckCircle, label: 'Claims & Evidence' },
    { to: `/runs/${runId}/findings`, icon: AlertTriangle, label: 'Findings & Conflicts' },
    { to: `/runs/${runId}/approvals`, icon: CheckSquare, label: 'Approvals' },
    { to: `/runs/${runId}/deliverable`, icon: FileText, label: 'Deliverable' },
    { to: `/runs/${runId}/audit`, icon: History, label: 'Changelog / Cost' },
  ] : [];

  return (
    <aside className="app-sidebar flex w-full shrink-0 flex-col lg:h-full lg:w-60">
      <div className="sidebar-brand flex items-center gap-3 border-b px-4 py-3 sm:px-5 lg:py-[18px]">
        <div className="sidebar-mark size-9 rounded-xl flex items-center justify-center"><Workflow size={18} /></div>
        <div>
          <span className="block font-bold tracking-tight leading-tight">FlowDocs</span>
          <span className="sidebar-caption block text-[10px] mt-0.5 tracking-[.12em]">DOCUMENT REVIEW</span>
        </div>
      </div>

      <nav className="sidebar-links flex flex-1 gap-2 overflow-x-auto px-3 py-2 lg:flex-col lg:gap-7 lg:overflow-x-hidden lg:overflow-y-auto lg:py-7">
        <section className="shrink-0">
          <div className="sidebar-group-label mb-2 hidden px-3 text-[10px] font-bold uppercase tracking-[.16em] lg:block">Workspace</div>
          <div className="sidebar-link-list flex gap-1 lg:flex-col">
            {globalLinks.map(link => (
              <NavLink 
                key={link.to} 
                to={link.to}
                className={({ isActive }) =>
                `sidebar-link flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-control px-3 py-2 text-[12px] transition-colors lg:w-full lg:gap-3 lg:px-3 lg:py-2.5 lg:text-[13px] ${
                    isActive ? 'is-active font-semibold' : ''
                  }`
                }
              >
                <link.icon size={16} />
                {link.label}
              </NavLink>
            ))}
          </div>
        </section>

        {runLinks.length > 0 && (
          <section className="shrink-0">
            <div className="sidebar-group-label mb-2 hidden truncate px-3 text-[10px] font-bold uppercase tracking-[.16em] lg:block" title={`Run Context: ${runId}`}>
              Active Run
            </div>
            <div className="sidebar-link-list flex gap-1 lg:flex-col">
              {runLinks.map(link => (
                <NavLink 
                  key={link.to} 
                  to={link.to}
                  end
                  className={({ isActive }) =>
                    `sidebar-link flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-control px-3 py-2 text-[12px] transition-colors lg:w-full lg:gap-3 lg:px-3 lg:py-2.5 lg:text-[13px] ${
                      isActive ? 'is-active font-semibold' : ''
                    }`
                  }
                >
                  <link.icon size={16} />
                  {link.label}
                </NavLink>
              ))}
            </div>
          </section>
        )}

      </nav>
    </aside>
  );
}
