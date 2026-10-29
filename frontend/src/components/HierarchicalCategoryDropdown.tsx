import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  ChevronRight,
  ChevronDown,
  FolderTree,
  Folder,
  FolderOpen,
  Tag,
  Check,
  X,
  Search,
  Layers
} from "lucide-react";

export interface CategoryNode {
  name: string;
  fullPath: string;
  depth: number;
  children: CategoryNode[];
}

/**
 * Builds a clean hierarchical category tree from a list of category paths.
 * Supports delimiters like " >> " and " > ".
 * Preserves canonical category fullPaths for accurate database filtering.
 */
export function buildCategoryTree(categoryPaths: string[]): CategoryNode[] {
  const rootNodes: CategoryNode[] = [];
  const nodeMap = new Map<string, CategoryNode>();

  const uniquePaths = Array.from(
    new Set(categoryPaths.map((p) => p.trim()).filter(Boolean))
  );

  for (const rawPath of uniquePaths) {
    const segments = rawPath
      .replace(/\s*>\s*/g, " >> ")
      .split(/\s*>>\s*/)
      .map((s) => s.trim())
      .filter(Boolean);

    if (segments.length === 0) continue;

    let parentPath = "";
    for (let depth = 0; depth < segments.length; depth++) {
      const segmentName = segments[depth];
      const currentPath = parentPath
        ? `${parentPath} >> ${segmentName}`
        : segmentName;

      let node = nodeMap.get(currentPath);
      if (!node) {
        node = {
          name: segmentName,
          fullPath: currentPath,
          depth,
          children: [],
        };
        nodeMap.set(currentPath, node);

        if (depth === 0) {
          rootNodes.push(node);
        } else {
          const parentNode = nodeMap.get(parentPath);
          if (parentNode && !parentNode.children.some((c) => c.name === segmentName)) {
            parentNode.children.push(node);
          }
        }
      }

      parentPath = currentPath;
    }
  }

  function sortTree(nodes: CategoryNode[]): CategoryNode[] {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const node of nodes) {
      if (node.children.length > 0) {
        sortTree(node.children);
      }
    }
    return nodes;
  }

  return sortTree(rootNodes);
}

interface HierarchicalCategoryDropdownProps {
  categories: string[];
  selectedCategory: string;
  onSelectCategory: (category: string) => void;
  className?: string;
  placeholder?: string;
}

export const HierarchicalCategoryDropdown: React.FC<HierarchicalCategoryDropdownProps> = ({
  categories,
  selectedCategory,
  onSelectCategory,
  className = "",
  placeholder = "Browse All Categories",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Build the hierarchical tree from active catalogue categories
  const categoryTree = useMemo(() => {
    return buildCategoryTree(categories);
  }, [categories]);

  // Auto-expand path leading to currently selected category
  useEffect(() => {
    if (selectedCategory) {
      const parts = selectedCategory
        .replace(/\s*>\s*/g, " >> ")
        .split(/\s*>>\s*/)
        .map((s) => s.trim());
      const toExpand = new Set(expandedPaths);
      let curr = "";
      for (const p of parts) {
        curr = curr ? `${curr} >> ${p}` : p;
        toExpand.add(curr);
      }
      setExpandedPaths(toExpand);
    }
  }, [selectedCategory]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const toggleExpand = (fullPath: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(fullPath)) {
        next.delete(fullPath);
      } else {
        next.add(fullPath);
      }
      return next;
    });
  };

  const handleSelect = (fullPath: string) => {
    onSelectCategory(fullPath);
    setIsOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelectCategory("");
  };

  // Human-readable formatted display label
  const displayLabel = useMemo(() => {
    if (!selectedCategory) return placeholder;
    return selectedCategory
      .replace(/\s*>>\s*/g, " › ")
      .replace(/\s*>\s*/g, " › ");
  }, [selectedCategory, placeholder]);

  // Filter tree when user types a search term
  const filterNode = (node: CategoryNode, query: string): CategoryNode | null => {
    const matchesQuery = node.name.toLowerCase().includes(query.toLowerCase());
    const filteredChildren: CategoryNode[] = [];

    for (const child of node.children) {
      const matchingChild = filterNode(child, query);
      if (matchingChild) {
        filteredChildren.push(matchingChild);
      }
    }

    if (matchesQuery || filteredChildren.length > 0) {
      return {
        ...node,
        children: filteredChildren,
      };
    }
    return null;
  };

  const displayedTree = useMemo(() => {
    const query = searchTerm.trim();
    if (!query) return categoryTree;
    return categoryTree
      .map((n) => filterNode(n, query))
      .filter((n): n is CategoryNode => n !== null);
  }, [categoryTree, searchTerm]);

  // Recursive render item
  const renderCategoryNode = (node: CategoryNode) => {
    const hasChildren = node.children.length > 0;
    const isExpanded = searchTerm.trim() ? true : expandedPaths.has(node.fullPath);
    const isSelected = selectedCategory === node.fullPath;

    return (
      <div key={node.fullPath} className="space-y-0.5">
        <div
          className={`flex items-center space-x-1.5 py-1.5 px-2 rounded-xl text-xs transition-colors group cursor-pointer ${
            isSelected
              ? "bg-indigo-50 text-indigo-900 font-bold border border-indigo-200"
              : "text-slate-700 hover:bg-slate-100"
          }`}
          style={{ paddingLeft: `${node.depth * 18 + 8}px` }}
        >
          {/* Distinct Expand / Collapse Chevron control for parents */}
          {hasChildren ? (
            <button
              type="button"
              onClick={(e) => toggleExpand(node.fullPath, e)}
              className="p-1 rounded-md hover:bg-slate-200/80 text-slate-400 hover:text-slate-700 transition-transform cursor-pointer shrink-0"
              aria-label={isExpanded ? `Collapse ${node.name}` : `Expand ${node.name}`}
            >
              <ChevronRight
                className={`h-3.5 w-3.5 transition-transform ${
                  isExpanded ? "rotate-90 text-indigo-600" : ""
                }`}
              />
            </button>
          ) : (
            <span className="w-5 shrink-0 flex items-center justify-center">
              <span className="h-1 w-1 rounded-full bg-slate-300 group-hover:bg-indigo-400" />
            </span>
          )}

          {/* Category selection button */}
          <button
            type="button"
            onClick={() => handleSelect(node.fullPath)}
            className="flex-1 flex items-center space-x-2 text-left truncate cursor-pointer py-0.5"
            title={node.fullPath}
          >
            {hasChildren ? (
              isExpanded ? (
                <FolderOpen className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
              ) : (
                <Folder className="h-3.5 w-3.5 text-slate-400 shrink-0" />
              )
            ) : (
              <Tag className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            )}
            <span className="truncate flex-1">{node.name}</span>
          </button>

          {/* Active selection checkmark */}
          {isSelected && (
            <Check className="h-3.5 w-3.5 text-indigo-600 shrink-0 ml-1" />
          )}
        </div>

        {/* Child Subcategories */}
        {hasChildren && isExpanded && (
          <div className="space-y-0.5 animate-fade-in">
            {node.children.map((child) => renderCategoryNode(child))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`relative inline-block ${className}`} ref={dropdownRef}>
      {/* Selector Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center space-x-2 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer select-none shadow-2xs ${
          selectedCategory
            ? "bg-indigo-50/90 border-indigo-300 text-indigo-800 ring-2 ring-indigo-500/10"
            : "bg-white border-slate-300 text-slate-700 hover:bg-slate-50 hover:border-slate-400"
        }`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <FolderTree className={`h-3.5 w-3.5 ${selectedCategory ? "text-indigo-600" : "text-slate-500"}`} />
        <span className="truncate max-w-[200px] sm:max-w-[280px]">
          {displayLabel}
        </span>

        {/* Clear filter button directly in trigger */}
        {selectedCategory && (
          <span
            onClick={handleClear}
            className="ml-1 p-0.5 rounded-full hover:bg-indigo-200/80 text-indigo-600 hover:text-indigo-900 cursor-pointer transition-colors"
            title="Clear category filter"
            aria-label="Clear category filter"
          >
            <X className="h-3 w-3" />
          </span>
        )}

        <ChevronDown
          className={`h-3.5 w-3.5 text-slate-400 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Hierarchical Dropdown Menu */}
      {isOpen && (
        <div
          className="absolute left-0 mt-2 w-72 sm:w-80 max-h-[380px] bg-white rounded-2xl border border-slate-200 shadow-xl z-50 flex flex-col animate-fade-in overflow-hidden"
          role="listbox"
        >
          {/* Header Bar */}
          <div className="p-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
            <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider flex items-center space-x-1.5">
              <FolderTree className="h-3.5 w-3.5 text-indigo-600" />
              <span>Hierarchical Categories</span>
            </span>
            {selectedCategory && (
              <button
                type="button"
                onClick={() => {
                  onSelectCategory("");
                  setIsOpen(false);
                }}
                className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer"
              >
                Reset Filter
              </button>
            )}
          </div>

          {/* Quick Search Input */}
          <div className="px-3 pt-2.5 pb-2 border-b border-slate-100">
            <div className="relative">
              <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search category or subcategory..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm("")}
                  className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          {/* Category Tree Body */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {/* All Categories Root Option */}
            <button
              type="button"
              onClick={() => {
                onSelectCategory("");
                setIsOpen(false);
              }}
              className={`w-full flex items-center space-x-2 px-2.5 py-2 rounded-xl text-xs font-semibold text-left transition-colors cursor-pointer ${
                !selectedCategory
                  ? "bg-indigo-600 text-white shadow-2xs"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <Layers className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 truncate">All Categories (Full Catalogue)</span>
              {!selectedCategory && <Check className="h-3.5 w-3.5 shrink-0" />}
            </button>

            <div className="pt-1 border-t border-slate-100 space-y-0.5">
              {displayedTree.length > 0 ? (
                displayedTree.map((node) => renderCategoryNode(node))
              ) : (
                <div className="py-6 text-center text-xs text-slate-400">
                  No matching categories found
                </div>
              )}
            </div>
          </div>

          {/* Footer note */}
          <div className="p-2 border-t border-slate-100 bg-slate-50 text-[10px] text-slate-400 text-center">
            Click chevron to expand • Click category name to filter
          </div>
        </div>
      )}
    </div>
  );
};
