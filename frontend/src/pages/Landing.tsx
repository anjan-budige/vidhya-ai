import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  BookOpen,
  Building2,
  Check,
  ChevronRight,
  Database,
  FileText,
  GraduationCap,
  Headset,
  HeartPulse,
  Layers,
  LineChart,
  Mail,
  Menu,
  MessagesSquare,
  Minus,
  Plus,
  Scale,
  Search,
  Server,
  ShieldCheck,
  Users,
  Wallet,
  X,
  Zap,
} from 'lucide-react';
import { animate, stagger } from 'animejs';
import { LogoFull } from '../components/brand/Logo';

const BOT_URL = 'https://t.me/vidhya_hub_bot';

const navLinks = [
  { label: 'Platform', href: '#what' },
  { label: 'Method', href: '#method' },
  { label: 'Capabilities', href: '#features' },
  { label: 'Commercial model', href: '#models' },
  { label: 'Field notes', href: '#use-cases' },
  { label: 'Questions', href: '#faq' },
];

const advantages = [
  { icon: Database, title: 'One complete system', line: 'Ingestion, retrieval, accounts, entitlements and audit.' },
  { icon: FileText, title: 'Receipts included', line: 'Every answer can point back to its document and page.' },
  { icon: MessagesSquare, title: 'Two front doors', line: 'A web workspace and a Telegram bot over one account.' },
];

const steps = [
  {
    icon: Layers,
    index: '01',
    label: 'Ingest',
    title: 'Publish the source material',
    text: 'An administrator publishes the organisation’s source material — curricula, manuals, policies, procedures or research. Every document is chunked, embedded and tracked until it can answer questions.',
    footnote: 'PDF → chunks → verified index',
  },
  {
    icon: Search,
    index: '02',
    label: 'Retrieve',
    title: 'Find the useful passage',
    text: 'A question is matched against your knowledge. Retrieval stays inside the permitted context budget, trims by tokens, and keeps the answer coherent instead of stuffing a prompt.',
    footnote: 'Embedding match → ranked passages',
  },
  {
    icon: MessagesSquare,
    index: '03',
    label: 'Answer',
    title: 'Explain with provenance',
    text: 'The same account, memory and usage rules follow the learner across web and Telegram. Conversations are preserved, compressed when they grow, and never mixed between users.',
    footnote: 'Answer → source document + page',
  },
];

const comparison = [
  { point: 'Retrieved text', rag: 'Dumps similar chunks into a prompt and hopes they fit.', vidhya: 'Caps retrieval at 35% of the allowed input budget, trims by token count and preserves coherence.' },
  { point: 'Long conversations', rag: 'History is truncated, so early context silently disappears.', vidhya: 'Older turns become a stored summary while the most recent turns stay whole.' },
  { point: 'Identity', rag: 'One shared API key, or no real accounts at all.', vidhya: 'Individual accounts, hashed keys, email verification and a linked Telegram identity.' },
  { point: 'Fair use', rag: 'The first heavy user can exhaust the whole budget.', vidhya: 'Daily and monthly windows, saved-chat limits and token accounting for each subscription tier.' },
  { point: 'Fresh knowledge', rag: 'Re-indexing the corpus is a manual script.', vidhya: 'Changing the embedding model re-indexes automatically with visible per-document progress.' },
  { point: 'Model choice', rag: 'Hard-wired to one vendor.', vidhya: 'Chat and embedding providers sit side by side, with custom endpoints and per-model prompts.' },
  { point: 'Governance', rag: 'No reliable answer to who asked what.', vidhya: 'Query history, usage analytics, entitlement control and an append-only audit trail.' },
  { point: 'Commerce', rag: 'Left as an exercise for the deployment team.', vidhya: 'Owner-defined subscription models through five Indian gateways, or billing switched off entirely.' },
];

type Feature = {
  icon: LucideIcon;
  title: string;
  text: string;
  span: string;
  tone: string;
  marker?: string;
};

const features: Feature[] = [
  { icon: Search, title: 'Knowledge with visible status', text: 'Upload documents, follow embedding chunk by chunk, and know exactly how much of the corpus the active model can answer from.', span: 'lg:col-span-7', tone: 'bg-[#F1F6E6]', marker: 'Corpus / live' },
  { icon: Zap, title: 'Streaming web workspace', text: 'Saved conversations, live token streaming, stop at any time, rename or remove, and citations beneath each reply.', span: 'lg:col-span-5', tone: 'bg-[#EDF2FF]', marker: 'Web app' },
  { icon: MessagesSquare, title: 'Telegram bot', text: 'One login connects the entire knowledge base. Usage, subscription state and session controls stay available in plain commands.', span: 'lg:col-span-4', tone: 'bg-[#FFF5EC]', marker: 'Field access' },
  { icon: Users, title: 'Accounts and roles', text: 'Username or email sign-in, OTP verification, recovery, admin-created accounts and profile controls.', span: 'lg:col-span-4', tone: 'bg-[#FFFEFA]' },
  { icon: Wallet, title: 'Owner-defined subscriptions', text: 'Platform owners set price, duration, message allowances, saved-chat limits and token ceilings — or run open access.', span: 'lg:col-span-4', tone: 'bg-[#F6F1FF]', marker: 'Your rules' },
  { icon: Server, title: 'Multiple AI providers', text: 'Separate chat and embedding models, live-tested before activation, with custom URLs and system prompts.', span: 'lg:col-span-5', tone: 'bg-[#FFFEFA]' },
  { icon: ShieldCheck, title: 'Admin control and audit', text: 'Usage and revenue views, people management, payment reconciliation, system health and a durable audit record.', span: 'lg:col-span-7', tone: 'bg-[#EFF8F4]', marker: 'Operations' },
  { icon: Server, title: 'Self-hosted by design', text: 'API, workers, database, storage and bot run in containers on infrastructure you control. Documents are not used to train anything.', span: 'lg:col-span-6', tone: 'bg-[#FBF7ED]' },
  { icon: Mail, title: 'Email in your name', text: 'Verification, password reset, account setup and security notices use your branding and your sending provider.', span: 'lg:col-span-6', tone: 'bg-[#FFFEFA]' },
];

const audiences = [
  { icon: GraduationCap, title: 'Schools and coaching institutes', text: 'Students ask from the syllabus they actually study, not the internet’s average.' },
  { icon: Building2, title: 'Colleges and universities', text: 'Curricula, lab manuals, admission rules, exam notices and library material under one login.' },
  { icon: Layers, title: 'Manufacturing and industry', text: 'Machine manuals, SOPs, safety protocols and quality documents on the device already in hand.' },
  { icon: Headset, title: 'Support and service teams', text: 'Grounded answers from product documentation and resolved-ticket history, with the source attached.' },
  { icon: HeartPulse, title: 'Healthcare and pharma', text: 'Protocols, formularies and device guidance searchable inside your own perimeter.' },
  { icon: Scale, title: 'Legal and compliance', text: 'Contracts, regulations, policy and precedent with citations that reach the exact page.' },
  { icon: LineChart, title: 'Corporate learning', text: 'Onboarding packs and training material become a mentor for every employee.' },
  { icon: Users, title: 'EdTech and publishers', text: 'Ship a study companion with your own content as the moat and owner-defined access rules.' },
];

const reasons = [
  'Paid subscriptions or open access — one server-side switch, no rewrite.',
  'Two delivery channels from one identity: web workspace and Telegram.',
  'Vendor-neutral chat and embedding models with custom endpoints.',
  'Allowances enforced on the server, not hidden in the interface.',
  'Answers can show their source, making them usable in study and compliance.',
  'Real operational visibility: queries, tokens, latency, revenue and failed documents.',
  'Containers on your machine, VPS or private cloud.',
];

const faqs = [
  {
    q: 'Does it answer from the open internet?',
    a: 'No. Answers are grounded in the documents your organisation publishes. When the material does not cover a question, the assistant answers from general knowledge and does not pretend it came from your corpus.',
  },
  {
    q: 'Who can see what?',
    a: 'Knowledge belongs to the organisation and is shared with its people; conversations belong to the individual. Administrators control accounts, entitlements and publishing, and every administrative action is recorded.',
  },
  {
    q: 'Can we run it without charging people?',
    a: 'Yes. Switch the platform to free mode and every account uses the free tier’s allowances. Subscription assignment and checkout are disabled on the server, not merely hidden in the interface.',
  },
  {
    q: 'Can platform owners define their own subscription model?',
    a: 'Yes. The owner controls price, access duration, daily and monthly message allowances, saved-chat limits and token ceilings. Tiers can be published, revised or removed from the admin console.',
  },
  {
    q: 'What does it need to run?',
    a: 'Docker, Postgres with vector search, Redis, object storage and the AI credentials you choose — hosted model keys or a model running on your own hardware.',
  },
  {
    q: 'Which payment gateways are supported?',
    a: 'Razorpay, Cashfree, Paytm, PhonePe and PayU across demo, sandbox and production modes, with one active provider per mode and signed, replay-safe webhooks.',
  },
];

export default function Landing() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [commercialMode, setCommercialMode] = useState<'subscription' | 'open'>('subscription');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    animate('.hero-line', {
      y: [34, 0],
      rotate: [0.6, 0],
      duration: 820,
      delay: stagger(80),
      ease: 'outExpo',
    });
    animate('.hero-sheet', {
      y: [22, 0],
      rotate: [1.8, 0],
      scale: [0.975, 1],
      duration: 1000,
      delay: 160,
      ease: 'outExpo',
    });
    animate('.hero-marginal', {
      y: [14, 0],
      duration: 650,
      delay: stagger(100, { start: 480 }),
      ease: 'outExpo',
    });

    const sceneObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const scene = entry.target as HTMLElement;
          const rise = scene.querySelectorAll('[data-rise]');
          const slide = scene.querySelectorAll('[data-slide]');
          if (rise.length) {
            animate(rise, {
              y: [26, 0],
              duration: 720,
              delay: stagger(55),
              ease: 'outExpo',
            });
          }
          if (slide.length) {
            animate(slide, {
              x: [18, 0],
              duration: 680,
              delay: stagger(45),
              ease: 'outExpo',
            });
          }
          const line = scene.querySelector('[data-draw-line]');
          if (line) {
            animate(line, { scaleX: [0, 1], duration: 900, ease: 'outExpo' });
          }
          sceneObserver.unobserve(scene);
        }
      },
      { threshold: 0.1 }
    );
    document.querySelectorAll('[data-scene]').forEach((scene) => sceneObserver.observe(scene));
    return () => sceneObserver.disconnect();
  }, []);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animate('.commercial-sheet', {
      y: [7, 0],
      rotate: [commercialMode === 'subscription' ? -0.5 : 0.5, 0],
      duration: 400,
      ease: 'outQuad',
    });
  }, [commercialMode]);

  return (
    <div className="landing-paper min-h-screen font-sans">
      <header className={`sticky top-0 z-50 px-3 pt-3 transition-all duration-300 md:px-5 ${scrolled ? 'pb-2' : 'pb-3'}`}>
        <div className={`mx-auto flex h-[66px] max-w-[1280px] items-center gap-5 rounded-2xl border px-3.5 transition-all duration-300 md:px-5 ${
          scrolled
            ? 'border-[#d9d4c6] bg-[#fffef8]/92 shadow-[0_14px_40px_-32px_rgba(24,53,44,0.55)] backdrop-blur-xl'
            : 'border-[#ddd8ca]/80 bg-[#fffef8]/65 backdrop-blur-md'
        }`}>
          <a href="#overview" className="flex shrink-0 items-center" aria-label="Vidhya AI overview">
            <LogoFull height={36} />
          </a>

          <nav className="mx-auto hidden items-center gap-0.5 lg:flex" aria-label="Main navigation">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-full px-3 py-2 text-[12px] font-medium text-[#52645c] transition-colors hover:bg-[#18352c]/5 hover:text-[#18352c]"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            <a href={BOT_URL} target="_blank" rel="noopener noreferrer" className="hidden text-[12px] font-semibold text-[#52645c] transition-colors hover:text-[#18352c] sm:inline-flex">
              Telegram
            </a>
            <a href="/login" className="inline-flex items-center gap-2 rounded-xl bg-[#2d59f0] px-4 py-2.5 text-[12px] font-semibold text-white shadow-[0_12px_24px_-16px_rgba(45,89,240,0.9)] transition-all hover:-translate-y-0.5 hover:bg-[#244bd4]">
              Enter workspace <ArrowRight className="h-3.5 w-3.5" />
            </a>
            <button
              className="rounded-lg p-2 text-[#52645c] hover:bg-[#18352c]/5 lg:hidden"
              onClick={() => setMenuOpen((value) => !value)}
              aria-label="Toggle navigation"
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="mx-auto mt-2 max-w-[1280px] rounded-2xl border border-[#ddd8ca] bg-[#fffef8] p-3 shadow-xl lg:hidden">
            {navLinks.map((link, index) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[#3c5148] hover:bg-[#f3f0e7]"
              >
                <span className="font-mono text-[9px] text-[#8b988f]">{String(index + 1).padStart(2, '0')}</span>
                {link.label}
              </a>
            ))}
            <a href={BOT_URL} target="_blank" rel="noopener noreferrer" className="mt-1 flex items-center gap-2 border-t border-[#e5e0d4] px-3 pt-3 text-sm font-medium text-[#3c5148]">
              <MessagesSquare className="h-4 w-4" /> Ask on Telegram
            </a>
          </div>
        )}
      </header>

      <main className="flex flex-col">
        <section id="overview" className="order-1 relative overflow-hidden px-4 pb-16 pt-16 md:px-8 md:pb-24 md:pt-24">
          <div className="pointer-events-none absolute inset-0 -z-10 landing-ring-field opacity-70" />
          <div className="pointer-events-none absolute -right-28 top-24 -z-10 h-[480px] w-[480px] rounded-full border border-[#18352c]/10 md:-right-10" />
          <div className="pointer-events-none absolute -right-10 top-40 -z-10 h-[330px] w-[330px] rounded-full border border-dashed border-[#18352c]/15" />

          <div className="mx-auto grid max-w-[1240px] items-center gap-16 lg:grid-cols-[1.02fr_0.98fr] lg:gap-10">
            <div>
              <div className="hero-line landing-kicker">
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[#18352c]/20 bg-[#fffef8]">
                  <BookOpen className="h-3 w-3" />
                </span>
                Self-hosted AI knowledge system · Any industry <span className="font-mono text-[9px] text-[#7f8e85]">EST. 01</span>
              </div>

              <h1 className="hero-line landing-display mt-7 text-[46px] font-semibold leading-[0.98] text-[#18352c] sm:text-[62px] lg:text-[76px]">
                Your knowledge
                <span className="block">has a source.</span>
                <span className="landing-serif mt-1 block text-[#2d59f0] italic">Answers should too.</span>
              </h1>

              <p className="hero-line mt-7 max-w-[560px] text-[15px] leading-[1.8] text-[#52645c] md:text-base">
                Vidhya AI is a self-hosted AI knowledge system for every industry. It turns your
                organisation’s own documents into accurate, source-backed answers — for classrooms,
                factory floors, hospitals, law offices, support desks and any team with knowledge to
                share. People ask in a focused web workspace or on Telegram, and every useful answer
                can lead them back to the exact source.
              </p>

              <div className="hero-line mt-8 flex flex-col gap-3 sm:flex-row">
                <a href="/login" className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#2d59f0] px-6 py-3.5 text-sm font-semibold text-white shadow-[0_14px_30px_-20px_rgba(45,89,240,0.9)] transition-all hover:-translate-y-0.5 hover:bg-[#244bd4]">
                  Open the workspace <ArrowRight className="h-4 w-4" />
                </a>
                <a href={BOT_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#18352c]/20 bg-[#fffef8]/80 px-6 py-3.5 text-sm font-semibold text-[#18352c] transition-colors hover:bg-[#fffef8]">
                  <MessagesSquare className="h-4 w-4" /> Ask on Telegram
                </a>
              </div>

              <div className="hero-marginal mt-10 flex flex-wrap items-center gap-x-7 gap-y-3 border-t border-[#18352c]/15 pt-5">
                {advantages.map((item) => (
                  <div key={item.title} className="flex items-center gap-2.5">
                    <item.icon className="h-3.5 w-3.5 text-[#2c6b57]" />
                    <span className="text-[11px] font-semibold text-[#344d43]">{item.title}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="hero-sheet relative mx-auto w-full max-w-[560px] lg:mx-0 lg:justify-self-end">
              <div className="landing-tape absolute -top-3 left-14 z-20 h-7 w-24 -rotate-3 rounded-[2px]" />
              <div className="landing-sheet relative rounded-[3px] p-5 pb-24 md:p-7 md:pb-28">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="landing-kicker !tracking-[0.18em]">Question / 01</p>
                    <p className="mt-2 text-[11px] text-[#8b988f]">Sources retrieved from your workspace</p>
                  </div>
                  <span className="landing-stamp flex h-14 w-14 shrink-0 rotate-6 items-center justify-center text-center text-[8px] font-semibold uppercase leading-tight tracking-wider text-[#2c6b57]">
                    Page<br />verified
                  </span>
                </div>

                <p className="landing-serif mt-5 border-b border-[#e2ddd1] pb-4 text-[23px] leading-snug text-[#18352c]">
                  What does our lab manual say about the figure of merit?
                </p>

                <div className="mt-5 text-[13px] leading-[1.8] text-[#52645c]">
                  It defines the figure of merit as the product of normalised area, power and delay.
                  A lower value means a more efficient design.
                  <span className="ml-1 inline-block h-3.5 w-[2px] animate-pulse rounded-full bg-[#2d59f0] align-middle" />
                </div>

                <div className="mt-4 rounded-lg border border-[#e2ddd1] bg-[#f8f5eb] px-3.5 py-3 font-mono text-[11px] text-[#344d43]">
                  FoM = (area / area₀) · (power / power₀) × (delay / delay₀)
                </div>

                <div className="relative z-10 mt-5 flex flex-wrap items-center gap-2">
                  <span className="text-[8px] font-bold uppercase tracking-[0.18em] text-[#8b988f]">Sources</span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[#cbd6ee] bg-[#eef3ff] px-2.5 py-1 text-[10px] font-medium text-[#36538f]"><FileText className="h-2.5 w-2.5" /> VLSI-Lab-Manual.pdf · p.41</span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[#d7e8df] bg-[#eff8f4] px-2.5 py-1 text-[10px] font-medium text-[#2c6b57]"><FileText className="h-2.5 w-2.5" /> Lecture-Notes-4.pdf · p.7</span>
                </div>
              </div>

              <div className="hero-marginal landing-sheet absolute -bottom-14 -left-4 w-[230px] rotate-[-2deg] rounded-[3px] p-4 sm:-left-8">
                <p className="text-[8px] font-bold uppercase tracking-[0.18em] text-[#8b988f]">Subscription allowance</p>
                <div className="mt-2 flex items-end justify-between">
                  <p className="landing-display text-2xl font-semibold text-[#18352c]">48<span className="text-sm font-normal text-[#8b988f]"> / 100</span></p>
                  <span className="rounded-full bg-[#edf4d8] px-2 py-0.5 text-[9px] font-semibold text-[#45652e]">Today</span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#e8e4d8]"><div className="h-full w-1/2 rounded-full bg-[#2c6b57]" /></div>
              </div>

              <div className="hero-marginal absolute -right-2 top-1/3 hidden rotate-90 text-[8px] font-semibold uppercase tracking-[0.22em] text-[#8b988f] md:block">
                Traceable · Private · Current
              </div>
            </div>
          </div>
        </section>

        <section id="method" data-scene className="order-3 border-y border-[#e2ddd1] bg-[#fffdf7] px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto max-w-[1240px]">
            <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
              <div data-rise>
                <SectionLabel>How it works</SectionLabel>
                <h2 className="landing-display mt-5 max-w-[430px] text-[36px] font-semibold leading-[1.02] text-[#18352c] md:text-[48px]">
                  The path from a document to a
                  <span className="landing-serif italic text-[#2d59f0]"> defensible answer.</span>
                </h2>
              </div>
              <p data-rise className="max-w-[560px] text-[15px] leading-[1.85] text-[#68776f] lg:justify-self-end">
                Not a black box. Each stage is visible to the people running the platform, from the moment a document is embedded to the passage behind an answer.
              </p>
            </div>

            <div data-draw-line className="mt-14 h-px origin-left bg-[#18352c]/30" />

            <div className="grid gap-10 pt-9 md:grid-cols-3 md:gap-0">
              {steps.map((step, index) => (
                <article key={step.index} data-rise className={`relative md:px-7 ${index === 0 ? 'md:pl-0' : ''} ${index < steps.length - 1 ? 'md:border-r md:border-[#e2ddd1]' : 'md:pr-0'}`}>
                  <div className="flex items-center justify-between gap-4">
                    <span className="landing-display text-[46px] font-semibold leading-none text-[#d8d2c3]">{step.index}</span>
                    <span className="flex h-10 w-10 items-center justify-center rounded-full border border-[#18352c]/15 bg-[#f6f2e7] text-[#2c6b57]"><step.icon className="h-[18px] w-[18px]" /></span>
                  </div>
                  <p className="mt-6 text-[9px] font-bold uppercase tracking-[0.2em] text-[#2d59f0]">{step.label}</p>
                  <h3 className="landing-display mt-2 text-[21px] font-semibold text-[#18352c]">{step.title}</h3>
                  <p className="mt-3 text-[14px] leading-[1.85] text-[#5f7067]">{step.text}</p>
                  <p className="mt-5 border-t border-dashed border-[#cfc9ba] pt-3 font-mono text-[10px] uppercase tracking-[0.1em] text-[#7b8981]">{step.footnote}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="what" data-scene className="order-2 relative overflow-hidden px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto grid max-w-[1240px] gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
            <div>
              <div data-rise><SectionLabel>What Vidhya AI is</SectionLabel></div>
              <h2 data-rise className="landing-display mt-5 max-w-[660px] text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[54px]">
                An AI knowledge system,
                <span className="landing-serif italic text-[#2d59f0]"> not another chatbot.</span>
              </h2>
              <div className="mt-7 max-w-[620px] space-y-5 text-[15px] leading-[1.9] text-[#5c6d64] md:text-base">
                <p data-rise>
                  Vidhya turns the knowledge an organisation already owns into reliable answers for
                  its people. Publish curricula, machine manuals, clinical protocols, policy
                  libraries, legal notes or support guides — the system embeds the material,
                  retrieves the right passage and explains it in plain language.
                </p>
                <p data-rise>
                  It is not a thin wrapper around a model. Accounts, memory, owner-defined
                  subscriptions, provider management, audit and both delivery channels are part of
                  the system, so the same foundation can serve a school, a factory, a hospital, a law
                  firm or a global support team.
                </p>
              </div>

              <blockquote data-rise className="mt-9 border-l-2 border-[#2c6b57] pl-5">
                <p className="landing-serif text-[25px] leading-tight text-[#2c4b3e] md:text-[30px]">
                  “Every industry has knowledge worth asking. Vidhya makes it answerable.”
                </p>
              </blockquote>
            </div>

            <div className="border-t border-[#18352c]/20">
              {[
                { number: '01', icon: Layers, title: 'Owned corpus', text: 'Your documents, classifications and retention rules. Nothing is shared with another tenant.' },
                { number: '02', icon: FileText, title: 'Cited answers', text: 'Replies can identify the document and page used, so people verify instead of simply trusting.' },
                { number: '03', icon: MessagesSquare, title: 'Two surfaces', text: 'A full web workspace and Telegram over the same account, history and allowances.' },
                { number: '04', icon: Wallet, title: 'Your commercial rules', text: 'Platform owners define subscription pricing, duration and allowances, or switch billing off for open access.' },
              ].map((item) => (
                <div key={item.number} data-slide className="group grid grid-cols-[42px_1fr_auto] items-start gap-4 border-b border-[#18352c]/15 py-5">
                  <span className="font-mono text-[10px] text-[#8b988f]">{item.number}</span>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <item.icon className="h-4 w-4 text-[#2c6b57]" />
                      <h3 className="text-[15px] font-semibold text-[#18352c]">{item.title}</h3>
                    </div>
                    <p className="mt-1.5 text-[13.5px] leading-[1.8] text-[#63736b]">{item.text}</p>
                  </div>
                  <ArrowUpRight className="mt-1 h-4 w-4 text-[#c4c9c2] transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[#2d59f0]" />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="beyond-rag" data-scene className="order-4 border-y border-[#e2ddd1] bg-[#fffdf7] px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto grid max-w-[1240px] gap-12 lg:grid-cols-[0.7fr_1.3fr] lg:gap-16">
            <div className="lg:sticky lg:top-28 lg:self-start" data-rise>
              <SectionLabel>The difference</SectionLabel>
              <h2 className="landing-display mt-5 text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[50px]">
                Retrieval is the
                <span className="landing-serif italic text-[#2d59f0]"> easy part.</span>
              </h2>
              <p className="mt-5 max-w-[410px] text-[15px] leading-[1.85] text-[#68776f]">
                A vector search and a prompt answer a question once. Running an organisation’s
                assistant means budgets, identity, memory, freshness, governance and commerce.
              </p>
              <div className="mt-8 inline-flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-[#e2ddd1] px-3 py-1.5 text-[10px] font-medium text-[#8b988f] line-through">Generic RAG demo</span>
                <ChevronRight className="h-3.5 w-3.5 text-[#8b988f]" />
                <span className="rounded-full bg-[#d9f27c]/70 px-3 py-1.5 text-[10px] font-semibold text-[#344d24]">Working platform</span>
              </div>
            </div>

            <div>
              <div className="hidden grid-cols-[1fr_1fr_1fr] gap-4 border-b border-[#18352c]/20 pb-3 md:grid">
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#8b988f]">Concern</span>
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#8b988f]">Usual answer</span>
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#2c6b57]">Vidhya AI</span>
              </div>
              {comparison.map((row, index) => (
                <div key={row.point} data-rise className="grid gap-2 border-b border-[#e2ddd1] py-5 md:grid-cols-[1fr_1fr_1fr] md:gap-4">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 font-mono text-[9px] text-[#a0aaa2]">{String(index + 1).padStart(2, '0')}</span>
                    <p className="text-[14px] font-semibold text-[#18352c]">{row.point}</p>
                  </div>
                  <p className="text-[13px] leading-[1.75] text-[#8b988f] md:line-through md:decoration-[#cfd4ce]">{row.rag}</p>
                  <p className="flex items-start gap-2 text-[13px] leading-[1.75] text-[#3c5148]">
                    <span className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#e3f1e9] text-[#2c6b57]"><Check className="h-2.5 w-2.5" /></span>
                    {row.vidhya}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="features" data-scene className="order-5 px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto max-w-[1240px]">
            <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
              <div data-rise>
                <SectionLabel>Capabilities</SectionLabel>
                <h2 className="landing-display mt-5 max-w-[620px] text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[54px]">
                  One system, composed
                  <span className="landing-serif italic text-[#2d59f0]"> end to end.</span>
                </h2>
              </div>
              <p data-rise className="max-w-[360px] text-[15px] leading-[1.85] text-[#68776f] md:text-right">
                Ingest. Answer. Remember. Limit. Bill. Observe. The operational pieces are already connected.
              </p>
            </div>

            <div className="mt-12 grid gap-3 lg:grid-cols-12">
              {features.map((feature) => (
                <article
                  key={feature.title}
                  data-rise
                  className={`group relative overflow-hidden rounded-[18px] border border-[#ded9cc] p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_42px_-32px_rgba(24,53,44,0.45)] md:p-6 ${feature.span} ${feature.tone}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#18352c]/10 bg-[#fffef8]/80 text-[#2c6b57] transition-transform duration-300 group-hover:rotate-3">
                      <feature.icon className="h-[17px] w-[17px]" />
                    </span>
                    {feature.marker && <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#89968e]">{feature.marker}</span>}
                  </div>
                  <h3 className="landing-display mt-5 text-[19px] font-semibold text-[#18352c]">{feature.title}</h3>
                  <p className="mt-2 max-w-[540px] text-[13.5px] leading-[1.8] text-[#63736b]">{feature.text}</p>

                  {feature.title === 'Knowledge with visible status' && (
                    <div className="mt-5 flex items-center gap-2">
                      {[72, 100, 88, 100, 64].map((width, index) => (
                        <div key={index} className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#18352c]/10">
                          <div className="h-full rounded-full bg-[#2c6b57]" style={{ width: `${width}%` }} />
                        </div>
                      ))}
                      <span className="ml-2 font-mono text-[8px] text-[#8b988f]">READY</span>
                    </div>
                  )}
                  {feature.title === 'Streaming web workspace' && (
                    <div className="mt-5 rounded-lg border border-[#d6ddec] bg-white/60 p-2.5 font-mono text-[9px] text-[#5c6d64]">
                      “...the final passage explains why the lower value...”
                      <span className="ml-1 inline-block h-2.5 w-[2px] animate-pulse bg-[#2d59f0] align-middle" />
                    </div>
                  )}
                  {feature.title === 'Telegram bot' && (
                    <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-[#ebd9c8] bg-white/60 px-3 py-1.5 font-mono text-[9px] text-[#7a624d]">
                      <MessagesSquare className="h-3 w-3" /> /login vdk_••••••
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="models" data-scene className="order-6 border-y border-[#d7dfe9] bg-[#eef3fb] px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto grid max-w-[1240px] gap-12 lg:grid-cols-[0.82fr_1.18fr] lg:items-center lg:gap-20">
            <div data-rise>
              <SectionLabel>Commercial model</SectionLabel>
              <h2 className="landing-display mt-5 text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[52px]">
                You define
                <span className="landing-serif italic text-[#2d59f0]"> how access works.</span>
              </h2>
              <p className="mt-5 max-w-[470px] text-[15px] leading-[1.85] text-[#5c6d64]">
                Platform owners shape the commercial model themselves: subscription price, access duration and usage allowances. Or disable billing completely and provide open access.
              </p>

              <div className="mt-7 inline-flex rounded-xl border border-[#d3dbea] bg-[#fffef8]/70 p-1">
                <button
                  onClick={() => setCommercialMode('subscription')}
                  className={`rounded-lg px-4 py-2 text-[12px] font-semibold transition-colors ${commercialMode === 'subscription' ? 'bg-[#2d59f0] text-white' : 'text-[#68776f] hover:text-[#18352c]'}`}
                >
                  Subscription access
                </button>
                <button
                  onClick={() => setCommercialMode('open')}
                  className={`rounded-lg px-4 py-2 text-[12px] font-semibold transition-colors ${commercialMode === 'open' ? 'bg-[#2d59f0] text-white' : 'text-[#68776f] hover:text-[#18352c]'}`}
                >
                  Open access
                </button>
              </div>

              <p className="mt-4 max-w-[450px] text-[12px] leading-relaxed text-[#7b8981]">
                {commercialMode === 'subscription'
                  ? 'Checkout, subscriptions and owner-defined entitlements operate inside the platform.'
                  : 'Checkout and subscription assignment are disabled server-side, not just hidden in the interface.'}
              </p>
            </div>

            <div className="commercial-sheet landing-ticket relative mx-auto w-full max-w-[610px] px-7 py-7 md:px-10 md:py-9">
              <div className="flex items-start justify-between gap-4 border-b border-dashed border-[#d8d2c5] pb-5">
                <div>
                  <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-[#8b988f]">Owner configuration / {commercialMode === 'subscription' ? '01' : '02'}</p>
                  <h3 className="landing-display mt-2 text-2xl font-semibold text-[#18352c]">
                    {commercialMode === 'subscription' ? 'Subscription access' : 'Open access'}
                  </h3>
                </div>
                <span className={`rounded-full px-3 py-1.5 text-[9px] font-bold uppercase tracking-[0.12em] ${commercialMode === 'subscription' ? 'bg-[#d9f27c] text-[#3c4d25]' : 'bg-[#e4eee7] text-[#2c6b57]'}`}>
                  {commercialMode === 'subscription' ? 'Billing on' : 'Billing off'}
                </span>
              </div>

              <div className="grid gap-x-8 gap-y-0 pt-3 sm:grid-cols-2">
                {(commercialMode === 'subscription'
                  ? [
                      ['Subscription price', 'Defined by owner'],
                      ['Access duration', 'Owner-defined days'],
                      ['Daily messages', 'Per-tier allowance'],
                      ['Monthly messages', 'Per-tier allowance'],
                      ['Saved conversations', 'Per-tier ceiling'],
                      ['Context & reply budget', 'Model-aware limits'],
                    ]
                  : [
                      ['Price for every account', '₹0'],
                      ['Access window', 'Continuous'],
                      ['Daily messages', 'Free-tier allowance'],
                      ['Monthly messages', 'Free-tier allowance'],
                      ['Saved conversations', 'Free-tier ceiling'],
                      ['Checkout & assignment', 'Disabled'],
                    ]
                ).map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-3 border-b border-[#e7e2d7] py-3">
                    <span className="text-[11.5px] text-[#68776f]">{label}</span>
                    <span className="text-[12.5px] font-semibold text-[#18352c]">{value}</span>
                  </div>
                ))}
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-[10px] text-[#7b8981]">
                  <ShieldCheck className="h-3.5 w-3.5 text-[#2c6b57]" />
                  {commercialMode === 'subscription' ? 'Enforced per account, server-side' : 'Server-side entitlement lock'}
                </div>
                <span className="landing-display text-lg font-semibold text-[#2d59f0]">
                  {commercialMode === 'subscription' ? 'Your rules' : 'Everyone in'}
                </span>
              </div>

              <div className="absolute -right-1 top-1/2 hidden -translate-y-1/2 rotate-90 font-mono text-[8px] uppercase tracking-[0.2em] text-[#a1aba4] md:block">
                Owner console · vidhya
              </div>
            </div>
          </div>
        </section>

        <section id="use-cases" data-scene className="order-7 px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto max-w-[1240px]">
            <div className="grid gap-8 lg:grid-cols-[1fr_0.8fr] lg:items-end">
              <div data-rise>
                <SectionLabel>Field index</SectionLabel>
                <h2 className="landing-display mt-5 max-w-[720px] text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[54px]">
                  Every place people look
                  <span className="landing-serif italic text-[#2d59f0]"> something up.</span>
                </h2>
              </div>
              <p data-rise className="max-w-[450px] text-[15px] leading-[1.85] text-[#68776f] lg:justify-self-end">
                The corpus changes. The shape of the problem does not: documents in, trustworthy answers out, with ownership and limits in between.
              </p>
            </div>

            <div className="mt-12 grid border-t border-[#18352c]/20 md:grid-cols-2">
              {audiences.map((audience, index) => (
                <div
                  key={audience.title}
                  data-slide
                  className={`group flex items-start gap-4 border-b border-[#18352c]/15 py-5 md:py-6 ${index % 2 === 0 ? 'md:pr-8' : 'md:border-l md:border-[#18352c]/15 md:pl-8'}`}
                >
                  <span className="mt-1 w-7 shrink-0 font-mono text-[9px] text-[#9aa59d]">{String(index + 1).padStart(2, '0')}</span>
                  <audience.icon className="mt-0.5 h-[17px] w-[17px] shrink-0 text-[#2c6b57]" />
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[15px] font-semibold text-[#18352c]">{audience.title}</h3>
                    <p className="mt-1.5 text-[13px] leading-[1.75] text-[#68776f]">{audience.text}</p>
                  </div>
                  <ArrowUpRight className="mt-1 h-3.5 w-3.5 shrink-0 text-[#c7ccc7] transition-all group-hover:translate-x-0.5 group-hover:text-[#2d59f0]" />
                </div>
              ))}
            </div>

            <div className="mt-7 flex flex-col justify-between gap-3 text-[11px] text-[#7b8981] sm:flex-row sm:items-center">
              <p>Also libraries, archives, public desks, franchises and internal help desks.</p>
              <p className="font-mono text-[9px] uppercase tracking-[0.16em]">If people search folders, replace the folder.</p>
            </div>
          </div>
        </section>

        <section id="why" data-scene className="order-8 border-y border-[#dfe4cf] bg-[#f1f6dd] px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto grid max-w-[1240px] gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-20">
            <div data-rise>
              <SectionLabel>The principles</SectionLabel>
              <h2 className="landing-display mt-5 max-w-[520px] text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[54px]">
                The boring parts are
                <span className="landing-serif italic text-[#2d59f0]"> already solved.</span>
              </h2>
              <p className="mt-5 max-w-[480px] text-[15px] leading-[1.85] text-[#5c6d64]">
                Most assistants stop at the prompt. Vidhya ships with the accounts, usage controls, storage, vendor management, payment rails and observability that decide whether it survives its first busy week.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="/login" className="inline-flex items-center gap-2 rounded-xl bg-[#2d59f0] px-5 py-3 text-[12px] font-semibold text-white transition-all hover:-translate-y-0.5 hover:bg-[#244bd4]">
                  Open the workspace <ArrowRight className="h-3.5 w-3.5" />
                </a>
                <a href={BOT_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-xl border border-[#18352c]/20 px-5 py-3 text-[12px] font-semibold text-[#18352c] hover:bg-white/40">
                  <MessagesSquare className="h-3.5 w-3.5" /> Try the bot
                </a>
              </div>
            </div>

            <div className="border-t border-[#18352c]/25">
              {reasons.map((reason, index) => (
                <div key={reason} data-rise className="flex items-start gap-4 border-b border-[#18352c]/15 py-4">
                  <span className="w-6 shrink-0 font-mono text-[9px] text-[#88947e]">{String(index + 1).padStart(2, '0')}</span>
                  <span className="flex-1 text-[14px] leading-[1.75] text-[#3c5148]">{reason}</span>
                  <BadgeCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#2c6b57]" />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" data-scene className="order-9 px-4 py-20 md:px-8 md:py-28">
          <div className="mx-auto grid max-w-[1100px] gap-12 lg:grid-cols-[0.7fr_1.3fr] lg:gap-18">
            <div data-rise>
              <SectionLabel>Questions</SectionLabel>
              <h2 className="landing-display mt-5 text-[38px] font-semibold leading-[1.02] text-[#18352c] md:text-[48px]">
                Before you hand it
                <span className="landing-serif italic text-[#2d59f0]"> the keys.</span>
              </h2>
              <p className="mt-4 max-w-[320px] text-[13.5px] leading-[1.85] text-[#68776f]">
                Clear answers about grounding, ownership, running costs and how access is controlled.
              </p>
            </div>

            <div className="border-t border-[#18352c]/20">
              {faqs.map((faq, index) => (
                <details key={faq.q} className="group border-b border-[#18352c]/15">
                  <summary className="flex cursor-pointer list-none items-start gap-4 py-5">
                    <span className="mt-1 w-6 shrink-0 font-mono text-[9px] text-[#9aa59d]">{String(index + 1).padStart(2, '0')}</span>
                    <span className="flex-1 text-[15.5px] font-semibold leading-snug text-[#18352c]">{faq.q}</span>
                    <span className="relative mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#18352c]/15 text-[#52645c] transition-colors group-open:border-[#2d59f0]/30 group-open:bg-[#edf2ff] group-open:text-[#2d59f0]">
                      <Plus className="h-3.5 w-3.5 group-open:hidden" />
                      <Minus className="hidden h-3.5 w-3.5 group-open:block" />
                    </span>
                  </summary>
                  <p className="max-w-[620px] pb-5 pl-10 pr-10 text-[14px] leading-[1.9] text-[#5f7067]">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="order-10 px-4 pb-20 md:px-8 md:pb-24">
          <div className="relative mx-auto max-w-[1240px] overflow-hidden rounded-[28px] border border-[#d8dcc6] bg-[#fffdf7] px-6 py-14 md:px-12 md:py-20">
            <div className="landing-dot-grid pointer-events-none absolute inset-0 opacity-45" />
            <div className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-[#d9f27c]/45 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-32 left-1/4 h-72 w-72 rounded-full bg-[#dce6ff] blur-3xl" />
            <div className="relative mx-auto max-w-[760px] text-center">
              <span className="landing-kicker mx-auto"><BookOpen className="h-3 w-3" /> The next question</span>
              <h2 className="landing-display mt-5 text-[38px] font-semibold leading-[0.98] text-[#18352c] md:text-[62px]">
                Ask your own documents
                <span className="landing-serif block text-[#2d59f0] italic">something difficult.</span>
              </h2>
              <p className="mx-auto mt-5 max-w-[540px] text-[15px] leading-[1.85] text-[#68776f]">
                Enter the web workspace, connect Telegram, or publish one document and start with a real question.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <a href="/login" className="inline-flex items-center gap-2 rounded-xl bg-[#2d59f0] px-6 py-3.5 text-sm font-semibold text-white shadow-[0_16px_34px_-22px_rgba(45,89,240,0.9)] transition-transform hover:-translate-y-0.5">
                  Open the workspace <ArrowRight className="h-4 w-4" />
                </a>
                <a href={BOT_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-xl border border-[#18352c]/20 bg-[#fffef8]/70 px-6 py-3.5 text-sm font-semibold text-[#18352c] hover:bg-white">
                  <MessagesSquare className="h-4 w-4" /> Ask on Telegram
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#dcd7ca] bg-[#f3efe4]">
        <div className="mx-auto grid max-w-[1240px] gap-8 px-4 py-12 md:grid-cols-[1fr_auto] md:items-end md:px-8">
          <div>
            <LogoFull height={34} />
            <p className="mt-3 max-w-[360px] text-[11px] leading-[1.8] text-[#7b8981]">
              A self-hosted AI knowledge system for every industry. Your documents remain under your control.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            {navLinks.map((link) => (
              <a key={link.href} href={link.href} className="text-[11px] font-medium text-[#68776f] hover:text-[#18352c]">{link.label}</a>
            ))}
            <a href="/login" className="text-[11px] font-semibold text-[#2d59f0]">Sign in</a>
          </div>
        </div>
        <div className="border-t border-[#dcd7ca] px-4 py-5 md:px-8">
          <div className="mx-auto flex max-w-[1240px] flex-col justify-between gap-2 text-[10px] text-[#8b988f] sm:flex-row">
            <span>© {new Date().getFullYear()} Vidhya AI</span>
            <span className="font-mono uppercase tracking-[0.14em]">Source-grounded · Self-hosted · Owner-controlled</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function SectionLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span className={`landing-kicker ${className}`}>
      <span className="h-px w-7 bg-[#2c6b57]/50" />
      {children}
    </span>
  );
}
