import { Link } from "react-router";

import type { DocumentInfo } from "../../api/types";
import { Icon } from "../../components/Icon";
import { Logo } from "../../components/Logo";
import { button } from "../../components/ui";
import { plural } from "../../lib/format";

interface SuggestionCard {
  category: string;
  badgeColor: string;
  icon: "doc" | "list" | "search" | "shield";
  title: string;
  prompt: string;
  fileName?: string;
}

export function EmptyChat({ documents, onAsk }: { documents: DocumentInfo[]; onAsk: (question: string) => void }) {
  const totalPassages = documents.reduce((sum, d) => sum + d.chunk_count, 0);

  if (!documents.length) {
    return (
      <div className="flex h-full items-center justify-center px-4 py-8">
        <div className="fade-in max-w-xl text-center">
          {/* Top System Tag */}
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/80 bg-blue-50/70 px-3.5 py-1.5 text-xs font-medium text-blue-700 shadow-xs backdrop-blur-xs dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-300">
            <span className="relative flex size-2">
              <span className="pulse-radar absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
            </span>
            <span className="font-semibold tracking-wide uppercase text-[10px]">Document intelligence</span>
            <span className="text-blue-400 dark:text-blue-500">|</span>
            <span className="text-slate-600 dark:text-slate-300">Answers with document sources</span>
          </div>

          <div className="mx-auto mt-6 grid size-16 place-items-center rounded-2xl bg-blue-700 text-white shadow-sm shadow-blue-900/15">
            <Icon name="upload" className="size-8" />
          </div>

          <h2 className="mt-6 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            Connect your knowledge base
          </h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            Upload your PDF, DOCX, or TXT documents. Our structure-aware parser will chunk, vectorize, and index them in your private vector space.
          </p>

          <div className="mt-8">
            <Link
              to="/documents"
              className={`${button("primary", "lg")} shadow-md shadow-blue-600/20`}
            >
              <Icon name="upload" className="size-4" /> Upload documents to get started
            </Link>
          </div>

          {/* Feature checklist */}
          <div className="mt-10 grid grid-cols-1 gap-3 text-left sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 dark:border-slate-800 dark:bg-slate-900/40">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 dark:text-slate-100">
                <Icon name="check" className="size-3.5 text-blue-700" /> Answers cite sources
              </div>
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                Answers cite exact paragraphs and pages.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 dark:border-slate-800 dark:bg-slate-900/40">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 dark:text-slate-100">
                <Icon name="check" className="size-3.5 text-blue-700" /> Relevant passages
              </div>
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                Cross-encoder filters out off-topic noise.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 dark:border-slate-800 dark:bg-slate-900/40">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 dark:text-slate-100">
                <Icon name="check" className="size-3.5 text-blue-700" /> Document scoped
              </div>
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                Refuses to fabricate unmentioned facts.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Dynamic suggestions tailored to uploaded documents
  const docA = documents[0];
  const docB = documents[1] || documents[0];

  const suggestions: SuggestionCard[] = [
    {
      category: "Executive Summary",
      badgeColor: "bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
      icon: "doc",
      title: "Synthesize Core Overview",
      prompt: `Provide an executive summary of ${docA.file_name}, highlighting its primary purpose, scope, and key conclusions.`,
      fileName: docA.file_name,
    },
    {
      category: "Data & Deadlines",
      badgeColor: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
      icon: "list",
      title: "Extract Critical Metrics & Dates",
      prompt: `What are the key deadlines, dates, numerical targets, or milestones specified in ${docA.file_name}?`,
      fileName: docA.file_name,
    },
    {
      category: "Policies & Rules",
      badgeColor: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
      icon: "shield",
      title: "Compliance & Requirements",
      prompt: `List the mandatory rules, policy requirements, or compliance guidelines detailed in ${docB.file_name}.`,
      fileName: docB.file_name,
    },
    {
      category: "Deep Analysis",
      badgeColor: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
      icon: "search",
      title: "Risks & Action Items",
      prompt: `What specific risks, recommendations, or operational action items are outlined in ${docB.file_name}?`,
      fileName: docB.file_name,
    },
  ];

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-8 sm:py-12">
      <div className="fade-in w-full max-w-3xl text-center">
        {/* Prominent System Tag on Home Page */}
        <div className="inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-slate-200/90 bg-white/80 px-4 py-1.5 shadow-xs backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/80">
          <span className="relative flex size-2">
            <span className="pulse-radar absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
          </span>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300">
            Your document workspace
          </span>
          <span className="text-slate-300 dark:text-slate-700">•</span>
          <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
            Ask questions and review cited sources
          </span>
        </div>

        {/* Hero Branding & Headline */}
        <div className="mt-6 flex items-center justify-center gap-3">
          <Logo size="lg" />
        </div>

        <h1 className="mt-5 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl dark:text-white">
          Ask your documents a question
        </h1>

        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
          Search your knowledge base in plain language and follow each answer back to its source passages.
        </p>

        {/* Live Knowledge Base Indexing Stats */}
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1 text-xs font-medium text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            <Icon name="doc" className="size-3.5 text-blue-500" />
            {plural(documents.length, "Document")} Connected
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1 text-xs font-medium text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            <Icon name="layers" className="size-3.5 text-sky-500" />
            {plural(totalPassages, "Vector Passage")} Ready
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50/80 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Active & Synchronized
          </span>
        </div>

        {/* Categorized Prompt Suggestions */}
        <div className="mt-8 text-left">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Start with a question
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {suggestions.map((card, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onAsk(card.prompt)}
                className="group relative flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-4 text-left shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-500/40"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${card.badgeColor}`}>
                      <Icon name={card.icon} className="size-3" />
                      {card.category}
                    </span>
                    <Icon
                      name="chevron"
                      className="size-4 text-slate-400 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-blue-600 dark:group-hover:text-blue-400"
                    />
                  </div>
                  <h3 className="mt-2 text-sm font-semibold text-slate-900 group-hover:text-blue-600 dark:text-slate-100 dark:group-hover:text-blue-300">
                    {card.title}
                  </h3>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                    "{card.prompt}"
                  </p>
                </div>

                {card.fileName && (
                  <div className="mt-3 flex items-center gap-1.5 border-t border-slate-100 pt-2 text-[11px] text-slate-400 dark:border-slate-800/70">
                    <Icon name="doc" className="size-3 text-slate-400" />
                    <span className="truncate">{card.fileName}</span>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
