"use client";

import { useState } from "react";
import {
  useTuckshopProducts,
  useCreateTuckshopProduct,
  useUpdateTuckshopProduct,
  useDeleteTuckshopProduct,
  useTuckshopPurchases,
  useRecordPurchase,
} from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  ShoppingCart, Plus, X, Loader2, Edit2, Trash2, MoreVertical,
  Package, Receipt, AlertTriangle,
} from "lucide-react";
import type { TuckshopProduct, TuckshopPurchase } from "@/types";

export default function TuckshopPage() {
  const canWrite = useHasPermission("school:write");
  const [tab, setTab] = useState<"products" | "sales">("products");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<TuckshopProduct | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [selling, setSelling] = useState<TuckshopProduct | null>(null);
  const [lowStockOnly, setLowStockOnly] = useState(false);

  const { data: productsData, isLoading: loadingProducts } = useTuckshopProducts({
    low_stock: lowStockOnly || undefined,
    page: 1,
    page_size: 50,
  });
  const { data: salesData, isLoading: loadingSales } = useTuckshopPurchases({
    page: 1,
    page_size: 50,
  });

  const createProduct = useCreateTuckshopProduct();
  const updateProduct = useUpdateTuckshopProduct();
  const deleteProduct = useDeleteTuckshopProduct();
  const recordPurchase = useRecordPurchase();

  const [form, setForm] = useState({
    name: "",
    description: "",
    price: 0,
    stock: 0,
    image_url: "",
    category: "",
    is_active: true,
  });

  const [saleForm, setSaleForm] = useState({
    student_id: "",
    quantity: 1,
  });

  const resetForm = () => {
    setForm({ name: "", description: "", price: 0, stock: 0, image_url: "", category: "", is_active: true });
    setEditing(null);
    setShowForm(false);
  };

  const resetSale = () => {
    setSaleForm({ student_id: "", quantity: 1 });
    setSelling(null);
  };

  const handleSubmit = () => {
    const payload = {
      ...form,
      description: form.description || null,
      image_url: form.image_url || null,
      category: form.category || null,
    };
    if (editing) {
      updateProduct.mutate({ id: editing.id, data: payload }, { onSuccess: resetForm });
    } else {
      createProduct.mutate(payload, { onSuccess: resetForm });
    }
  };

  const handleEdit = (p: TuckshopProduct) => {
    setForm({
      name: p.name,
      description: p.description || "",
      price: p.price,
      stock: p.stock,
      image_url: p.image_url || "",
      category: p.category || "",
      is_active: p.is_active,
    });
    setEditing(p);
    setShowForm(true);
    setMenuOpen(null);
  };

  const handleDelete = (id: string) => {
    if (confirm("Delete this product?")) deleteProduct.mutate(id);
    setMenuOpen(null);
  };

  const handleSale = () => {
    if (!selling) return;
    recordPurchase.mutate(
      {
        product_id: selling.id,
        student_id: saleForm.student_id,
        quantity: saleForm.quantity,
      },
      { onSuccess: resetSale },
    );
  };

  const products = productsData?.items as TuckshopProduct[] | undefined;
  const sales = salesData?.items as TuckshopPurchase[] | undefined;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Tuckshop</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Tuckshop</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Manage products, stock levels, and student purchases.
          </p>
        </div>
        {canWrite && tab === "products" && (
          <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2">
            <Plus size={15} />
            New Product
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Products", value: productsData?.total ?? "—" },
          { label: "Active", value: products?.filter((p) => p.is_active).length ?? "—" },
          { label: "Out of Stock", value: products?.filter((p) => p.stock === 0).length ?? "—" },
          { label: "Sales (page)", value: sales?.length ?? "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      <div className="flex bg-white rounded-xl border border-slate-200 p-1 mb-6 max-w-sm">
        <button
          onClick={() => setTab("products")}
          className={cn(
            "flex-1 px-4 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-2",
            tab === "products" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-50",
          )}
        >
          <Package size={14} /> Products
        </button>
        <button
          onClick={() => setTab("sales")}
          className={cn(
            "flex-1 px-4 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-2",
            tab === "sales" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-50",
          )}
        >
          <Receipt size={14} /> Sales
        </button>
      </div>

      {showForm && canWrite && tab === "products" && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Product" : "New Product"}</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Name *</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Price *</label>
              <input type="number" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} className="input" />
            </div>
            <div>
              <label className="label">Stock *</label>
              <input type="number" value={form.stock} onChange={(e) => setForm({ ...form, stock: Number(e.target.value) })} className="input" />
            </div>
            <div>
              <label className="label">Category</label>
              <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input" placeholder="snacks, drinks..." />
            </div>
            <div>
              <label className="label">Image URL</label>
              <input value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} className="input" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} />
            </div>
            <div className="md:col-span-2 flex items-center gap-2">
              <input id="active-prod" type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="active-prod" className="text-xs font-medium text-slate-700">Active (available for sale)</label>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createProduct.isPending || updateProduct.isPending} className="btn-primary gap-2">
              {(createProduct.isPending || updateProduct.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      )}

      {selling && canWrite && (
        <div className="bg-white rounded-xl border border-brand-200 p-6 mb-6 ring-2 ring-brand-100">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">Record Sale: {selling.name}</h2>
            <button onClick={resetSale} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Student ID *</label>
              <input value={saleForm.student_id} onChange={(e) => setSaleForm({ ...saleForm, student_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Quantity (max {selling.stock})</label>
              <input
                type="number"
                min={1}
                max={selling.stock}
                value={saleForm.quantity}
                onChange={(e) => setSaleForm({ ...saleForm, quantity: Number(e.target.value) })}
                className="input"
              />
            </div>
            <div className="md:col-span-2 bg-slate-50 rounded-lg p-3 flex items-center justify-between">
              <span className="text-xs text-slate-500">Total</span>
              <span className="text-lg font-black text-slate-900">
                {(selling.price * saleForm.quantity).toFixed(2)}
              </span>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetSale} className="btn-secondary">Cancel</button>
            <button
              onClick={handleSale}
              disabled={recordPurchase.isPending || !saleForm.student_id || saleForm.quantity < 1}
              className="btn-primary gap-2"
            >
              {recordPurchase.isPending && <Loader2 size={15} className="animate-spin" />}
              Record Sale
            </button>
          </div>
        </div>
      )}

      {tab === "products" && (
        <>
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
              <input type="checkbox" checked={lowStockOnly} onChange={(e) => setLowStockOnly(e.target.checked)} />
              Show low stock only (≤5)
            </label>
          </div>
          {loadingProducts ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-48 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : products && products.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {products.map((p) => (
                <div key={p.id} className={cn(
                  "bg-white rounded-xl border p-5 hover:shadow-md transition-shadow",
                  p.stock === 0 ? "border-rose-200" : p.stock <= 5 ? "border-amber-200" : "border-slate-200",
                )}>
                  <div className="flex items-start justify-between mb-3">
                    {p.image_url ? (
                      <img src={p.image_url} alt={p.name} className="w-12 h-12 rounded-lg object-cover" />
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-orange-50 border border-orange-100 flex items-center justify-center">
                        <ShoppingCart size={20} className="text-orange-600" />
                      </div>
                    )}
                    {canWrite && (
                      <div className="relative">
                        <button onClick={() => setMenuOpen(menuOpen === p.id ? null : p.id)} className="p-1 rounded hover:bg-slate-100">
                          <MoreVertical size={14} className="text-slate-400" />
                        </button>
                        {menuOpen === p.id && (
                          <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                            <button onClick={() => handleEdit(p)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                              <Edit2 size={13} /> Edit
                            </button>
                            <button onClick={() => handleDelete(p.id)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                              <Trash2 size={13} /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{p.name}</h3>
                  {p.category && <p className="text-[10px] uppercase tracking-widest text-slate-400 mt-0.5">{p.category}</p>}
                  {p.description && <p className="text-xs text-slate-500 line-clamp-2 mt-2">{p.description}</p>}
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
                    <span className="text-lg font-black text-slate-900">{p.price.toFixed(2)}</span>
                    <span className={cn(
                      "text-xs font-semibold flex items-center gap-1",
                      p.stock === 0 ? "text-rose-600" : p.stock <= 5 ? "text-amber-600" : "text-slate-500",
                    )}>
                      {p.stock <= 5 && <AlertTriangle size={11} />}
                      Stock: {p.stock}
                    </span>
                  </div>
                  {canWrite && p.is_active && p.stock > 0 && (
                    <button
                      onClick={() => { setSelling(p); setSaleForm({ student_id: "", quantity: 1 }); }}
                      className="w-full mt-3 text-xs font-semibold bg-brand-50 hover:bg-brand-100 text-brand-700 rounded-lg py-2"
                    >
                      Record Sale
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
              <ShoppingCart size={36} className="mb-3 opacity-40" />
              <p className="font-semibold">No products yet</p>
            </div>
          )}
        </>
      )}

      {tab === "sales" && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["Student", "Product", "Qty", "Unit", "Total", "Date"].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {loadingSales ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>
                  ))}</tr>
                ))
              ) : sales && sales.length > 0 ? (
                sales.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-4"><span className="text-xs font-mono text-slate-600">{s.student_id.slice(0, 8)}</span></td>
                    <td className="px-5 py-4"><span className="text-xs font-mono text-slate-600">{s.product_id.slice(0, 8)}</span></td>
                    <td className="px-5 py-4"><span className="text-sm text-slate-700">{s.quantity}</span></td>
                    <td className="px-5 py-4"><span className="text-sm text-slate-600">{s.unit_price.toFixed(2)}</span></td>
                    <td className="px-5 py-4"><span className="text-sm font-bold text-slate-900">{s.total_price.toFixed(2)}</span></td>
                    <td className="px-5 py-4"><span className="text-xs text-slate-500">{formatDate(s.created_at)}</span></td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={6} className="py-12 text-center text-slate-400 text-sm">No sales recorded yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
