"use client";

import {
  useTuckshopProducts,
  useTuckshopSalesSummary,
} from "@/hooks/useSchoolExperience";
import { WidgetCard, WidgetMetric } from "./WidgetCard";
import { ShoppingCart, AlertTriangle } from "lucide-react";
import type { TuckshopProduct } from "@/types";

export function TuckshopWidget() {
  const { data: productsData, isLoading: loadingProducts } = useTuckshopProducts({
    page: 1,
    page_size: 50,
  });
  const { data: summary, isLoading: loadingSummary } = useTuckshopSalesSummary();

  const isLoading = loadingProducts || loadingSummary;
  const products = productsData?.items as TuckshopProduct[] | undefined;

  const lowStock = products?.filter((p) => p.stock > 0 && p.stock <= 5).length ?? 0;
  const outOfStock = products?.filter((p) => p.stock === 0).length ?? 0;

  const todayRevenue = (summary?.total_revenue as number | undefined) ?? 0;

  return (
    <WidgetCard
      title="Tuckshop"
      icon={ShoppingCart}
      iconClass="bg-orange-50 text-orange-600"
      href="/dashboard/modules/school/tuckshop"
      loading={isLoading}
      empty={(!products || products.length === 0) && todayRevenue === 0}
      emptyText="No tuckshop activity."
      tone={outOfStock > 0 ? "danger" : lowStock > 0 ? "warning" : "default"}
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <WidgetMetric label="Today's Revenue" value={todayRevenue.toFixed(2)} tone="positive" />
        <WidgetMetric label="Low Stock" value={lowStock + outOfStock} tone={outOfStock > 0 ? "negative" : "neutral"} />
      </div>
      {(lowStock > 0 || outOfStock > 0) && products && (
        <ul className="space-y-1.5">
          {products
            .filter((p) => p.stock <= 5)
            .slice(0, 3)
            .map((p) => (
              <li key={p.id} className="flex items-center gap-2 text-xs">
                <AlertTriangle size={11} className={p.stock === 0 ? "text-rose-500" : "text-amber-500"} />
                <span className="text-slate-700 truncate flex-1">{p.name}</span>
                <span className="text-slate-400 shrink-0">{p.stock} left</span>
              </li>
            ))}
        </ul>
      )}
    </WidgetCard>
  );
}
