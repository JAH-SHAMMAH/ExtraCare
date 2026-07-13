"use client";

import { Newspaper } from "lucide-react";
import { NewsFeed } from "@/components/feed/NewsFeed";

export default function NewsFeedPage() {
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-slate-50">
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        <header className="flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-indigo-600" />
          <h1 className="text-lg font-semibold text-slate-800">News Feed</h1>
        </header>

        <NewsFeed limit={30} />
      </div>
    </div>
  );
}
