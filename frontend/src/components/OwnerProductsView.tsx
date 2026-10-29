import React, { useState, useEffect } from "react";
import { Search, X, Layers, Save, Sparkles, PlusCircle } from "lucide-react";
import {
  fetchDemoProducts,
  simulateDemoProductUpdate,
  simulateDemoProductAdd,
  simulateDemoProductArchive,
  isDemoSession
} from "../services/demoService";
import { addProduct } from "../services/api";
import { fetchProducts, updateProductVerified, archiveProduct } from "../services/api";
import type { ProductItem } from "../types";
import { HierarchicalCategoryDropdown } from "./HierarchicalCategoryDropdown";

interface OwnerProductsViewProps {
  isDemo?: boolean;
}

export const OwnerProductsView: React.FC<OwnerProductsViewProps> = ({ isDemo: propIsDemo }) => {
  const isDemo = Boolean(propIsDemo ?? isDemoSession());
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [inStockOnly, setInStockOnly] = useState<boolean>(false);
  const [search, setSearch] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);
  const [editForm, setEditForm] = useState<Partial<ProductItem>>({});
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [addForm, setAddForm] = useState<{
    product_id: string;
    title: string;
    description: string;
    category: string;
    price: string;
    stock_status: string;
  }>({
    product_id: "",
    title: "",
    description: "",
    category: "Electronics",
    price: "",
    stock_status: "In Stock",
  });
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProducts();
  }, [selectedCategory, inStockOnly, isDemo]);

  const loadProducts = async () => {
    setIsLoading(true);
    try {
      const resp = isDemo
        ? await fetchDemoProducts({
            category: selectedCategory || undefined,
            in_stock_only: inStockOnly,
            search: search.trim() || undefined,
            limit: 100,
          })
        : await fetchProducts({
            category: selectedCategory || undefined,
            in_stock_only: inStockOnly,
            search: search.trim() || undefined,
            limit: 100,
          });
      setProducts(resp.products);
      if (resp.categories) setCategories(resp.categories);
    } catch (err: any) {
      setError(err.message || "Failed to load products");
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartEdit = (prod: ProductItem) => {
    setEditingProduct(prod);
    setEditForm({
      title: prod.title,
      description: prod.description,
      category: prod.category,
      price: prod.price,
      stock_status: prod.stock_status,
      attributes: { ...(prod.attributes || {}) }
    });
    setStatusMsg(null);
    setError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingProduct) return;
    setStatusMsg(null);
    setError(null);

    try {
      if (isDemo) {
        await simulateDemoProductUpdate(editingProduct.product_id, editForm);
        setStatusMsg(`[Demo Sandbox Mode] Demo product ${editingProduct.product_id} updated in sandbox memory. Production database is untouched.`);
        setEditingProduct(null);
        await loadProducts();
        return;
      }
      await updateProductVerified(editingProduct.product_id, editForm);
      setStatusMsg(`Product ${editingProduct.product_id} verified and updated. Knowledge base index refreshed!`);
      setEditingProduct(null);
      await loadProducts();
    } catch (err: any) {
      setError(err.message || "Failed to update product.");
    }
  };

  const handleArchive = async (prodId: string) => {
    if (!window.confirm(`Are you sure you want to deactivate/archive product ${prodId}?`)) return;
    try {
      if (isDemo) {
        await simulateDemoProductArchive(prodId);
        setStatusMsg(`[Demo Sandbox Mode] Product ${prodId} removed from demo view. Production database is untouched.`);
        await loadProducts();
        return;
      }
      await archiveProduct(prodId);
      setStatusMsg(`Product ${prodId} archived successfully.`);
      await loadProducts();
    } catch (err: any) {
      setError(err.message || "Failed to archive product.");
    }
  };

  const handleAddProductSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addForm.product_id.trim() || !addForm.title.trim()) {
      setError("Product ID and Title are required.");
      return;
    }
    setError(null);
    setStatusMsg(null);

    const priceNum = parseFloat(addForm.price) || 0;
    const newProdData = {
      product_id: addForm.product_id.trim(),
      title: addForm.title.trim(),
      description: addForm.description.trim(),
      category: addForm.category.trim(),
      price: priceNum,
      stock_status: addForm.stock_status,
      rating: 4.8,
      attributes: {
        brand: "Store Brand",
        status: "Verified",
      },
    };

    try {
      if (isDemo) {
        await simulateDemoProductAdd(newProdData);
        setStatusMsg(`[Demo Sandbox Mode] Sample product '${newProdData.product_id}' added to demo sandbox. Production database is untouched.`);
        setIsAddModalOpen(false);
        setAddForm({
          product_id: "",
          title: "",
          description: "",
          category: "Electronics",
          price: "",
          stock_status: "In Stock",
        });
        await loadProducts();
        return;
      }

      await addProduct(newProdData);
      setStatusMsg(`Product '${newProdData.product_id}' successfully added to official catalogue!`);
      setIsAddModalOpen(false);
      setAddForm({
        product_id: "",
        title: "",
        description: "",
        category: "Electronics",
        price: "",
        stock_status: "In Stock",
      });
      await loadProducts();
    } catch (err: any) {
      setError(err.message || "Failed to add product.");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-in">
      {isDemo && (
        <div className="bg-purple-50 border border-purple-200 rounded-2xl p-4 flex items-center justify-between shadow-2xs">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-100 rounded-xl text-purple-700 shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-purple-900">Demo Portal: 16 Predefined Sample Products</h4>
              <p className="text-[11px] text-purple-700">
                Displaying isolated demo product catalog. Real store owner projects and modifications remain completely segregated.
              </p>
            </div>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-purple-200 text-purple-900 border border-purple-300 shrink-0">
            Isolated Demo Sandbox
          </span>
        </div>
      )}

      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <Layers className="h-6 w-6 text-indigo-600" />
            <span>{isDemo ? "Predefined Demo Product Catalog" : "Product Catalog & Official Corrections"}</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {isDemo
              ? "Explore sample product catalog management in sandbox mode. Changes are isolated to demo memory."
              : "Store Owner interface for audited product modifications. Any edit updates the ground-truth database."}
          </p>
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-purple-700 text-white font-semibold text-xs hover:bg-purple-800 transition-colors shadow-2xs cursor-pointer shrink-0"
          >
            <PlusCircle className="h-4 w-4" />
            <span>Add Product</span>
          </button>
          <div className="relative flex-1 md:w-64">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadProducts()}
              placeholder="Search title, SKU, or category..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            />
          </div>
          <button
            onClick={loadProducts}
            className="px-3.5 py-2 rounded-xl bg-indigo-600 text-white font-semibold text-xs hover:bg-indigo-700 transition-colors cursor-pointer shrink-0"
          >
            Filter
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-slate-100 text-xs w-full">
          <div className="flex items-center space-x-2">
            <span className="text-slate-500 font-semibold">Category:</span>
            <HierarchicalCategoryDropdown
              categories={categories}
              selectedCategory={selectedCategory}
              onSelectCategory={setSelectedCategory}
              placeholder="All Categories"
            />
          </div>

          {selectedCategory && (
            <div className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 font-semibold text-xs animate-fade-in shadow-2xs">
              <span className="text-slate-500 font-normal">Filtered:</span>
              <span className="font-bold truncate max-w-xs">
                {selectedCategory.replace(/\s*>>\s*/g, " • ").replace(/\s*>\s*/g, " • ")}
              </span>
              <button
                type="button"
                onClick={() => setSelectedCategory("")}
                className="ml-1 p-0.5 rounded-full hover:bg-purple-200 text-purple-500 hover:text-purple-800 cursor-pointer transition-colors"
                title="Clear category filter"
                aria-label="Clear category filter"
              >
                ✕
              </button>
            </div>
          )}

          <label className="flex items-center space-x-1.5 font-medium text-slate-700 cursor-pointer select-none ml-auto">
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(e) => setInStockOnly(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
            />
            <span>In Stock Only</span>
          </label>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between animate-fade-in">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg(null)} className="text-emerald-500 hover:text-emerald-700 cursor-pointer">✕</button>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between animate-fade-in">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 cursor-pointer">✕</button>
        </div>
      )}

      {/* Products Table */}
      {isLoading ? (
        <div className="py-20 text-center text-slate-400 text-xs">
          Loading {isDemo ? "predefined demo products..." : "active catalogue products..."}
        </div>
      ) : products.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 text-slate-400 text-xs">
          No products found matching your search.
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold">
                <tr>
                  <th className="py-3 px-4">SKU / ID</th>
                  <th className="py-3 px-4">Product Title</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Price (₹)</th>
                  <th className="py-3 px-4">Stock Status</th>
                  <th className="py-3 px-4">Rating</th>
                  <th className="py-3 px-4 text-right">Owner Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                {products.map((p) => (
                  <tr key={p.product_id} className="hover:bg-slate-50/80">
                    <td className="py-3 px-4 font-mono font-bold text-indigo-700">{p.product_id}</td>
                    <td className="py-3 px-4 max-w-xs truncate font-semibold text-slate-900">{p.title}</td>
                    <td className="py-3 px-4">{p.category}</td>
                    <td className="py-3 px-4 font-bold">₹{Number(p.price).toLocaleString("en-IN")}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        p.stock_status?.toLowerCase().includes("in stock")
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}>
                        {p.stock_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">{p.rating ? `★ ${p.rating}` : "—"}</td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => handleStartEdit(p)}
                        className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-semibold text-[11px] transition-colors cursor-pointer"
                      >
                        Edit / Correct
                      </button>
                      <button
                        onClick={() => handleArchive(p.product_id)}
                        className="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 font-semibold text-[11px] transition-colors cursor-pointer"
                      >
                        Archive
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Edit Product Modal */}
      {editingProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                  {editingProduct.product_id}
                </span>
                <h3 className="font-bold text-slate-900 text-sm">Owner Verified Correction</h3>
              </div>
              <button onClick={() => setEditingProduct(null)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Title</label>
                <input
                  type="text"
                  value={editForm.title || ""}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Price (₹)</label>
                  <input
                    type="number"
                    value={editForm.price !== undefined ? editForm.price : ""}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, price: parseFloat(e.target.value) || 0 }))}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Stock Status</label>
                  <select
                    value={editForm.stock_status || "In Stock"}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, stock_status: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="In Stock">In Stock</option>
                    <option value="Low Stock">Low Stock</option>
                    <option value="Out of Stock">Out of Stock</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={3}
                  value={editForm.description || ""}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-end space-x-2">
              <button
                onClick={() => setEditingProduct(null)}
                className="px-3.5 py-2 rounded-xl border border-slate-300 text-slate-700 font-semibold text-xs hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="flex items-center space-x-1 px-4 py-2 rounded-xl bg-indigo-600 text-white font-semibold text-xs hover:bg-indigo-700 cursor-pointer shadow-2xs"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Save Correction</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add New Product Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <PlusCircle className="h-5 w-5 text-purple-700" />
                <h3 className="font-bold text-slate-900 text-sm">
                  {isDemo ? "Add Demo Sample Product" : "Add Product to Official Catalogue"}
                </h3>
              </div>
              <button onClick={() => setIsAddModalOpen(false)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleAddProductSubmit} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Product ID / SKU *</label>
                  <input
                    type="text"
                    required
                    placeholder={isDemo ? "DEMO-NEW-99" : "SKU-PROD-101"}
                    value={addForm.product_id}
                    onChange={(e) => setAddForm((prev) => ({ ...prev, product_id: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Category *</label>
                  <input
                    type="text"
                    required
                    placeholder="Electronics, Audio, Wearables..."
                    value={addForm.category}
                    onChange={(e) => setAddForm((prev) => ({ ...prev, category: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Product Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. UltraBook Touchscreen 14"
                  value={addForm.title}
                  onChange={(e) => setAddForm((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Price (₹) *</label>
                  <input
                    type="number"
                    required
                    placeholder="4999"
                    value={addForm.price}
                    onChange={(e) => setAddForm((prev) => ({ ...prev, price: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Stock Status</label>
                  <select
                    value={addForm.stock_status}
                    onChange={(e) => setAddForm((prev) => ({ ...prev, stock_status: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="In Stock">In Stock</option>
                    <option value="Low Stock">Low Stock</option>
                    <option value="Out of Stock">Out of Stock</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="Accurate, factual specifications..."
                  value={addForm.description}
                  onChange={(e) => setAddForm((prev) => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-3.5 py-2 rounded-xl border border-slate-300 text-slate-700 font-semibold text-xs hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-purple-700 text-white font-semibold text-xs hover:bg-purple-800 cursor-pointer shadow-2xs"
                >
                  {isDemo ? "Add to Demo Sandbox" : "Add to Official Catalogue"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
