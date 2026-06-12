"use client";

import Link from "next/link";
import { useJournals } from "@/hooks/useSchoolExperience";
import { WidgetCard } from "./WidgetCard";
import { Camera, Image as ImageIcon } from "lucide-react";
import type { PhotoJournal } from "@/types";

export function JournalsWidget() {
  const { data, isLoading } = useJournals({ page: 1, page_size: 6 });
  const journals = data?.items as PhotoJournal[] | undefined;

  return (
    <WidgetCard
      title="Recent Journals"
      icon={Camera}
      iconClass="bg-pink-50 text-pink-600"
      href="/dashboard/modules/school/journals"
      loading={isLoading}
      skeleton="grid"
      empty={!journals || journals.length === 0}
      emptyText="No photos posted yet."
    >
      <div className="grid grid-cols-3 gap-1.5">
        {journals?.slice(0, 6).map((j) => (
          <Link
            key={j.id}
            href="/dashboard/modules/school/journals"
            className="aspect-square rounded-lg bg-slate-100 overflow-hidden block group"
            title={j.title}
          >
            {j.photo_url ? (
              <img
                src={j.photo_url}
                alt={j.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ImageIcon size={16} className="text-slate-300" />
              </div>
            )}
          </Link>
        ))}
      </div>
    </WidgetCard>
  );
}
