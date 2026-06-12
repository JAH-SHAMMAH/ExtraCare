import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

export interface LandingFeature {
  title: string;
  body: string;
}

export interface LandingModule {
  label: string;
  detail: string;
}

export interface LandingFaq {
  question: string;
  answer: string;
}

export interface IndustryLandingProps {
  eyebrow: string;
  title: string;
  description: string;
  primaryCta: string;
  accent: "indigo" | "emerald" | "rose";
  modules: LandingModule[];
  features: LandingFeature[];
  outcomes: string[];
  faqs: LandingFaq[];
  previewMetrics: Array<{ label: string; value: string }>;
  schema: unknown[];
}

const accentClasses = {
  indigo: {
    text: "text-indigo-700",
    muted: "text-indigo-300",
    bg: "bg-indigo-600",
    soft: "bg-indigo-50 text-indigo-700",
    border: "border-indigo-200",
  },
  emerald: {
    text: "text-emerald-700",
    muted: "text-emerald-300",
    bg: "bg-emerald-600",
    soft: "bg-emerald-50 text-emerald-700",
    border: "border-emerald-200",
  },
  rose: {
    text: "text-rose-700",
    muted: "text-rose-300",
    bg: "bg-rose-600",
    soft: "bg-rose-50 text-rose-700",
    border: "border-rose-200",
  },
};

const capabilityIcons: LucideIcon[] = [ShieldCheck, LockKeyhole, ClipboardList, BarChart3];

export function IndustryLanding({
  eyebrow,
  title,
  description,
  primaryCta,
  accent,
  modules,
  features,
  outcomes,
  faqs,
  previewMetrics,
  schema,
}: IndustryLandingProps) {
  const tone = accentClasses[accent];

  return (
    <main className="min-h-screen bg-white text-slate-950">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />

      <section className="relative isolate overflow-hidden bg-slate-950 text-white">
        <WorkspacePreview metrics={previewMetrics} accent={accent} />
        <div className="relative mx-auto flex min-h-[76vh] max-w-6xl flex-col justify-center px-6 py-20 sm:py-24 lg:px-8">
          <p className={`mb-4 text-sm font-bold uppercase tracking-widest ${tone.muted}`}>
            {eyebrow}
          </p>
          <h1 className="max-w-4xl text-4xl font-black tracking-normal sm:text-6xl">
            {title}
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-200">
            {description}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/register"
              className={`inline-flex items-center gap-2 rounded-lg px-5 py-3 text-sm font-bold text-white ${tone.bg} hover:brightness-95`}
            >
              {primaryCta}
              <ArrowRight size={16} />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-5 py-3 text-sm font-bold text-white hover:bg-white/10"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-200 bg-slate-50">
        <div className="mx-auto grid max-w-6xl gap-4 px-6 py-10 sm:grid-cols-2 lg:grid-cols-4 lg:px-8">
          {features.map((feature, index) => {
            const Icon = capabilityIcons[index % capabilityIcons.length];
            return (
              <article key={feature.title} className="rounded-lg border border-slate-200 bg-white p-5">
                <div className={`mb-4 flex h-9 w-9 items-center justify-center rounded-lg ${tone.soft}`}>
                  <Icon size={18} />
                </div>
                <h2 className="text-base font-black text-slate-950">{feature.title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">{feature.body}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-10 px-6 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
        <div>
          <p className={`text-xs font-bold uppercase tracking-widest ${tone.text}`}>One secure portal</p>
          <h2 className="mt-3 text-3xl font-black tracking-normal text-slate-950">
            Modules stay in their lane.
          </h2>
          <p className="mt-4 text-base leading-7 text-slate-600">
            The Fairview School Portal keeps authentication, notifications, reporting, and administration in one secure place, with every module built around how the school actually runs day to day.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {modules.map((module) => (
            <article key={module.label} className="rounded-lg border border-slate-200 bg-white p-5">
              <h3 className="font-black text-slate-950">{module.label}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{module.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="bg-slate-950 text-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 lg:grid-cols-[1fr_1fr] lg:px-8">
          <div>
            <p className={`text-xs font-bold uppercase tracking-widest ${tone.muted}`}>
              Measurable operations
            </p>
            <h2 className="mt-3 text-3xl font-black tracking-normal">
              Built for records leaders can trust.
            </h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {outcomes.map((outcome) => (
              <div key={outcome} className="flex gap-3 rounded-lg border border-white/10 bg-white/[0.04] p-4">
                <CheckCircle2 size={18} className={tone.muted} />
                <p className="text-sm leading-6 text-slate-200">{outcome}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-16 lg:px-8">
        <div className="mb-8 text-center">
          <p className={`text-xs font-bold uppercase tracking-widest ${tone.text}`}>FAQ</p>
          <h2 className="mt-3 text-3xl font-black tracking-normal text-slate-950">
            Questions teams ask before switching.
          </h2>
        </div>
        <div className="space-y-3">
          {faqs.map((faq) => (
            <details key={faq.question} className="rounded-lg border border-slate-200 bg-white p-5">
              <summary className="cursor-pointer text-base font-black text-slate-950">
                {faq.question}
              </summary>
              <p className="mt-3 text-sm leading-6 text-slate-600">{faq.answer}</p>
            </details>
          ))}
        </div>
      </section>

<section className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-12 sm:flex-row sm:items-center sm:justify-between lg:px-8">
          <div>
            <p className="text-sm font-bold text-slate-500">Fairview School Portal</p>
            <h2 className="mt-1 text-2xl font-black tracking-normal text-slate-950">
              Everything your school needs, in one secure portal.
            </h2>
          </div>
          <Link
            href="/login"
            className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-bold text-white ${tone.bg} hover:brightness-95`}
          >
            Sign in
            <Sparkles size={16} />
          </Link>
        </div>
      </section>
    </main>
  );
}

function WorkspacePreview({
  metrics,
  accent,
}: {
  metrics: Array<{ label: string; value: string }>;
  accent: "indigo" | "emerald" | "rose";
}) {
  const tone = accentClasses[accent];

  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden opacity-45">
      <div className="absolute left-1/2 top-10 w-[900px] -translate-x-1/2 rounded-lg border border-white/10 bg-white/[0.05] p-5 shadow-2xl">
        <div className="mb-5 flex items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${tone.bg}`} />
          <span className="h-3 w-28 rounded-full bg-white/25" />
          <span className="h-3 w-20 rounded-full bg-white/15" />
        </div>
        <div className="grid grid-cols-4 gap-4">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-lg border border-white/10 bg-slate-900/80 p-4">
              <span className="block h-2 w-16 rounded-full bg-white/15" />
              <span className="mt-4 block text-2xl font-black text-white">{metric.value}</span>
              <span className="mt-2 block text-xs font-bold uppercase tracking-widest text-white/50">
                {metric.label}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-[1.2fr_0.8fr] gap-4">
          <div className="h-48 rounded-lg border border-white/10 bg-slate-900/80 p-4">
            <span className="block h-3 w-32 rounded-full bg-white/20" />
            <div className="mt-6 flex h-28 items-end gap-3">
              {[36, 54, 42, 70, 58, 84, 66].map((height, index) => (
                <span
                  key={index}
                  className={`w-10 rounded-t-lg ${tone.bg}`}
                  style={{ height }}
                />
              ))}
            </div>
          </div>
          <div className="h-48 rounded-lg border border-white/10 bg-slate-900/80 p-4">
            <span className="block h-3 w-24 rounded-full bg-white/20" />
            <div className="mt-6 space-y-3">
              {[0, 1, 2, 3].map((item) => (
                <span key={item} className="block h-3 rounded-full bg-white/15" />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
