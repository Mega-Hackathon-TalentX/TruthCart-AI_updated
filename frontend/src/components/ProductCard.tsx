import React from "react";
import { Star, Check, X, FileText, MessageSquare, AlertCircle } from "lucide-react";
import type { ProductResult, ProductItem } from "../types";

export type CardProduct = ProductResult | (ProductItem & { citation?: string });

interface ProductCardProps {
  product: CardProduct;
  onViewEvidence?: (citation: string) => void;
  onAskInChat?: (query: string) => void;
  onReportProduct?: (productId: string) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onViewEvidence,
  onAskInChat,
  onReportProduct,
}) => {
  const isInStock = product.stock_status.toLowerCase().includes("in stock") || product.stock_status.toLowerCase() === "available";
  const attrs = Object.entries(product.attributes || {});

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-3">
      {/* Top Header: ID Badge & Citation */}
      <div>
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200">
            {product.product_id}
          </span>

          {product.citation ? (
            <button
              onClick={() => onViewEvidence && onViewEvidence(product.citation!)}
              className="text-[11px] font-mono font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100/70 px-2 py-0.5 rounded-md border border-indigo-100 flex items-center space-x-1 cursor-pointer transition-colors"
              title="Inspect Ground Truth Evidence for this product"
            >
              <FileText className="h-3 w-3" />
              <span>{product.citation}</span>
            </button>
          ) : (
            <span className="text-[11px] font-medium text-slate-500 bg-slate-50 px-2 py-0.5 rounded-md border border-slate-200">
              {product.category}
            </span>
          )}
        </div>

        {/* Title */}
        <h4 className="font-semibold text-slate-900 text-sm leading-snug line-clamp-2">
          {product.title}
        </h4>

        {/* Description snippet if present */}
        {product.description && (
          <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
            {product.description}
          </p>
        )}
      </div>

      {/* Attributes Chips */}
      {attrs.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {attrs.slice(0, 4).map(([key, val]) => (
            <span
              key={key}
              className="text-[11px] px-2 py-0.5 rounded-md bg-slate-50 text-slate-600 border border-slate-200/80 capitalize"
            >
              <strong className="text-slate-700">{key}:</strong>{" "}
              {Array.isArray(val) ? val.join(", ") : String(val)}
            </span>
          ))}
        </div>
      )}

      {/* Pricing & Stock Status */}
      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
        <div>
          <span className="text-xs text-slate-400 block font-medium">Catalogue Price</span>
          <span className="text-base font-bold text-slate-900">
            ₹{product.price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>

        <div className="flex flex-col items-end space-y-1">
          {/* Stock Status Badge */}
          <span
            className={`text-[11px] font-semibold px-2 py-0.5 rounded-full flex items-center space-x-1 ${
              isInStock
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-rose-50 text-rose-700 border border-rose-200"
            }`}
          >
            {isInStock ? (
              <Check className="h-3 w-3 stroke-[2.5]" />
            ) : (
              <X className="h-3 w-3 stroke-[2.5]" />
            )}
            <span>{product.stock_status}</span>
          </span>

          {/* Rating if present */}
          {product.rating !== null && product.rating !== undefined && (
            <div className="flex items-center space-x-1 text-xs text-amber-600 font-semibold">
              <Star className="h-3 w-3 fill-amber-400 stroke-amber-400" />
              <span>{product.rating.toFixed(1)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Action buttons if handlers provided */}
      {(onAskInChat || onReportProduct) && (
        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
          {onAskInChat && (
            <button
              onClick={() => onAskInChat(`Tell me about ${product.title}`)}
              className="text-indigo-600 hover:text-indigo-700 font-medium flex items-center space-x-1 cursor-pointer"
            >
              <MessageSquare className="h-3 w-3" />
              <span>Ask Assistant</span>
            </button>
          )}
          {onReportProduct && (
            <button
              onClick={() => onReportProduct(product.product_id)}
              className="text-slate-400 hover:text-rose-600 font-medium flex items-center space-x-1 cursor-pointer"
            >
              <AlertCircle className="h-3 w-3" />
              <span>Report Issue</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};
