import type { ProductItem, CatalogueVersion, SystemStats, CatalogueStatusResponse, User } from '../types';
import {
  DEMO_CATALOGUE_VERSIONS,
  DEMO_PRODUCTS,
  DEMO_SYSTEM_STATS,
  type DemoProductItem,
  type DemoCatalogueVersion,
} from '../data/demoCatalog';
import { getStoredUser } from './api';

/**
 * Isolated Demo Data Service.
 * Ensures the Demo Portal always consumes predefined sample data without touching,
 * fetching, or leaking real Store Owner production databases.
 */

// In-memory session copies for demo sandbox actions (isolated from database)
let sessionDemoVersions: DemoCatalogueVersion[] = [...DEMO_CATALOGUE_VERSIONS];
let sessionDemoProducts: DemoProductItem[] = [...DEMO_PRODUCTS];

export function isDemoSession(user?: User | null): boolean {
  if (user) return Boolean(user.is_demo);
  const stored = getStoredUser();
  if (stored && Boolean(stored.is_demo)) return true;
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") !== null || params.get("portal") === "demo") {
      return true;
    }
  }
  return false;
}

export function resetDemoSessionData(): void {
  sessionDemoVersions = [...DEMO_CATALOGUE_VERSIONS];
  sessionDemoProducts = [...DEMO_PRODUCTS];
}

export async function fetchDemoCatalogueVersions(): Promise<CatalogueVersion[]> {
  // Predefined catalog entries available immediately without touching database
  return JSON.parse(JSON.stringify(sessionDemoVersions));
}

export async function fetchDemoCatalogueStatus(): Promise<CatalogueStatusResponse> {
  const activeCat = sessionDemoVersions.find((c) => c.is_active) || sessionDemoVersions[0];
  const allCategories = Array.from(new Set(sessionDemoProducts.map((p) => p.category))).sort();
  return {
    status: activeCat.status || "ACTIVE",
    is_ready: true,
    is_official: false,
    is_synthetic_fixture: false,
    records_loaded: sessionDemoProducts.length,
    records_rejected: 0,
    duplicate_records: 0,
    missing_fields_count: 0,
    categories: allCategories,
    total_active_products: sessionDemoProducts.length,
    data_source_path: "predefined_demo_catalog.json (Isolated Sandbox)",
  };
}

export async function fetchDemoProducts(params?: {
  category?: string;
  min_price?: number;
  max_price?: number;
  in_stock_only?: boolean;
  search?: string;
  sort_by?: string;
  limit?: number;
  offset?: number;
}): Promise<{ total: number; categories: string[]; products: ProductItem[] }> {
  let list = [...sessionDemoProducts];

  if (params?.category) {
    const catLower = params.category.trim().toLowerCase();
    list = list.filter((p) => p.category.toLowerCase() === catLower);
  }

  if (params?.min_price !== undefined) {
    list = list.filter((p) => p.price >= params.min_price!);
  }

  if (params?.max_price !== undefined) {
    list = list.filter((p) => p.price <= params.max_price!);
  }

  if (params?.in_stock_only) {
    list = list.filter(
      (p) =>
        p.stock_status.toLowerCase().includes("in stock") ||
        p.stock_status.toLowerCase().includes("low stock")
    );
  }

  if (params?.search) {
    const q = params.search.trim().toLowerCase();
    list = list.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.product_id.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        (p.attributes && Object.values(p.attributes).some((val) => String(val).toLowerCase().includes(q)))
    );
  }

  if (params?.sort_by === "price_asc") {
    list.sort((a, b) => a.price - b.price);
  } else if (params?.sort_by === "price_desc") {
    list.sort((a, b) => b.price - a.price);
  } else if (params?.sort_by === "rating_desc") {
    list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  } else if (params?.sort_by === "title_desc") {
    list.sort((a, b) => b.title.localeCompare(a.title));
  } else {
    list.sort((a, b) => a.title.localeCompare(b.title));
  }

  const allCategories = Array.from(new Set(sessionDemoProducts.map((p) => p.category))).sort();
  const total = list.length;
  const offset = params?.offset || 0;
  const limit = params?.limit || 100;
  const paginated = list.slice(offset, offset + limit);

  return {
    total,
    categories: allCategories,
    products: JSON.parse(JSON.stringify(paginated)),
  };
}

export async function fetchDemoProduct(productId: string): Promise<ProductItem> {
  const found = sessionDemoProducts.find((p) => p.product_id === productId);
  if (!found) {
    throw new Error(`Demo product '${productId}' not found in sample catalogue.`);
  }
  return JSON.parse(JSON.stringify(found));
}

export async function fetchDemoSystemStats(): Promise<SystemStats> {
  return JSON.parse(JSON.stringify(DEMO_SYSTEM_STATS));
}

export async function simulateDemoProductAdd(
  productData: Partial<ProductItem>
): Promise<{ status: string; message: string; product: ProductItem }> {
  const newId = productData.product_id || `DEMO-NEW-${Date.now().toString().slice(-4)}`;
  const created: DemoProductItem = {
    product_id: newId,
    title: productData.title || "Untitled Demo Product",
    description: productData.description || "Demo sample description",
    category: productData.category || "General",
    price: productData.price || 999,
    stock_status: productData.stock_status || "In Stock",
    rating: productData.rating || 4.5,
    is_demo: true,
    isDemo: true,
    created_at: new Date().toISOString(),
    attributes: productData.attributes || {},
  };

  sessionDemoProducts.unshift(created);

  return {
    status: "success",
    message: `Demo product '${newId}' added to sandbox memory (isolated from production database).`,
    product: created,
  };
}

export async function simulateDemoProductUpdate(
  productId: string,
  updates: Partial<ProductItem>
): Promise<{ status: string; message: string; product: ProductItem }> {
  const index = sessionDemoProducts.findIndex((p) => p.product_id === productId);
  if (index === -1) {
    throw new Error(`Demo product '${productId}' not found.`);
  }

  const updated: DemoProductItem = {
    ...sessionDemoProducts[index],
    ...updates,
    updated_at: new Date().toISOString(),
  };

  sessionDemoProducts[index] = updated;

  return {
    status: "success",
    message: `Demo product '${productId}' updated in sandbox (isolated from production).`,
    product: updated,
  };
}

export async function simulateDemoProductArchive(
  productId: string
): Promise<{ status: string; message: string }> {
  sessionDemoProducts = sessionDemoProducts.filter((p) => p.product_id !== productId);
  return {
    status: "success",
    message: `Demo product '${productId}' archived in sandbox memory (isolated from production).`,
  };
}
