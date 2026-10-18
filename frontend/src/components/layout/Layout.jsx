import Sidebar from './Sidebar';

export default function Layout({ children }) {
  return (
    <div className="app-shell flex min-h-svh flex-col bg-canvas text-ink font-sans lg:h-svh lg:min-h-0 lg:overflow-hidden">
      <div className="app-body flex min-h-0 flex-1 flex-col lg:flex-row lg:overflow-hidden">
        <Sidebar />
        <main className="app-main relative min-h-0 min-w-0 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
