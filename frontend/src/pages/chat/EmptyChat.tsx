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
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200/80 bg-indigo-50/70 px-3.5 py-1.5 text-xs font-medium text-indigo-700 shadow-xs backdrop-blur-xs dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300">
            <span className="relative flex size-2">
              <span className="pulse-radar absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
            </span>
            <span className="font-semibold tracking-wide uppercase text-[10px]">Enterprise RAG System</span>
            <span className="text-indigo-400 dark:text-indigo-500">|</span>
            <span className="text-zinc-600 dark:text-zinc-300">Zero Hallucination Guarantee</span>
          </div>

          <div className="mx-auto mt-6 grid size-16 place-items-center rounded-2xl bg-linear-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-500/25">
            <Icon name="upload" className="size-8" />
          </div>

          <h2 className="mt-6 text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl dark:text-white">
            Connect your knowledge base
          </h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            Upload your PDF, DOCX, or TXT documents. Our structure-aware parser will chunk, vectorize, and index them in your private vector space.
          </p>

          <div className="mt-8">
            <Link
              to="/documents"
              className={`${button("primary", "lg")} shadow-md shadow-indigo-600/20`}
            >
              <Icon name="upload" className="size-4" /> Upload documents to get started
            </Link>
          </div>

          {/* Feature checklist */}
          <div className="mt-10 grid grid-cols-1 gap-3 text-left sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/40">
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                <span className="text-emerald-500">✓</span> 100% Grounded
              </div>
              <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                Answers cite exact paragraphs and pages.
              </p>
            </div>
            <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/40">
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                <span className="text-emerald-500">✓</span> BGE-M3 Reranking
              </div>
              <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                Cross-encoder filters out off-topic noise.
              </p>
            </div>
            <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/40">
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                <span className="text-emerald-500">✓</span> Guardrails
              </div>
              <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
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
      badgeColor: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
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
      badgeColor: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
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
        <div className="inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-zinc-200/90 bg-white/80 px-4 py-1.5 shadow-xs backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/80">
          <span className="relative flex size-2">
            <span className="pulse-radar absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
          </span>
          <span className="bg-linear-to-r from-indigo-600 to-violet-600 bg-clip-text text-[11px] font-bold uppercase tracking-wider text-transparent dark:from-indigo-400 dark:to-violet-400">
            Verified RAG Engine
          </span>
          <span className="text-zinc-300 dark:text-zinc-700">•</span>
          <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300">
            Strict Source Citations & Zero Hallucination
          </span>
        </div>

        {/* Hero Branding & Headline */}
        <div className="mt-6 flex items-center justify-center gap-3">
          <Logo size="lg" />
        </div>

        <h1 className="mt-5 text-3xl font-extrabold tracking-tight text-zinc-900 sm:text-4xl dark:text-white">
          Intelligent Answers Grounded in{" "}
          <span className="bg-linear-to-r from-indigo-600 via-indigo-500 to-violet-600 bg-clip-text text-transparent dark:from-indigo-400 dark:to-violet-400">
            Your Documents
          </span>
        </h1>

        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Ask questions naturally. Every response is verified through hybrid vector search and cross-encoder reranking, citing the exact passages used.
        </p>

        {/* Live Knowledge Base Indexing Stats */}
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50/80 px-2.5 py-1 text-xs font-medium text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
            <Icon name="doc" className="size-3.5 text-indigo-500" />
            {plural(documents.length, "Document")} Connected
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50/80 px-2.5 py-1 text-xs font-medium text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
            <Icon name="layers" className="size-3.5 text-violet-500" />
            {plural(totalPassages, "Vector Passage")} Ready
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50/80 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Active & Synchronized
          </span>
        </div>

        {/* Categorized Prompt Suggestions */}
        <div className="mt-8 text-left">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            Suggested Investigations
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {suggestions.map((card, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onAsk(card.prompt)}
                className="group relative flex flex-col justify-between rounded-xl border border-zinc-200/90 bg-white p-4 text-left shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-indigo-500/40"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${card.badgeColor}`}>
                      <Icon name={card.icon} className="size-3" />
                      {card.category}
                    </span>
                    <Icon
                      name="chevron"
                      className="size-4 text-zinc-400 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-indigo-600 dark:group-hover:text-indigo-400"
                    />
                  </div>
                  <h3 className="mt-2 text-sm font-semibold text-zinc-900 group-hover:text-indigo-600 dark:text-zinc-100 dark:group-hover:text-indigo-300">
                    {card.title}
                  </h3>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                    "{card.prompt}"
                  </p>
                </div>

                {card.fileName && (
                  <div className="mt-3 flex items-center gap-1.5 border-t border-zinc-100 pt-2 text-[11px] text-zinc-400 dark:border-zinc-800/70">
                    <Icon name="doc" className="size-3 text-zinc-400" />
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
