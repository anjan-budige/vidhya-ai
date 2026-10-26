import { Info } from 'lucide-react';

export default function FreeModeBanner({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <Info className="w-4 h-4 shrink-0" />
      <span>{message || 'Free mode — billing actions are disabled on this platform.'}</span>
    </div>
  );
}
