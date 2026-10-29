from typing import Optional, Dict, Any, List

class ActiveConstraints:
    """Stores active shopper search constraints across dialogue turns."""

    def __init__(self):
        self.category: Optional[str] = None
        self.max_price: Optional[float] = None
        self.min_price: Optional[float] = None
        self.brand: Optional[str] = None
        self.color: Optional[str] = None
        self.material: Optional[str] = None
        self.stock_required: Optional[bool] = None
        self.selected_product_id: Optional[str] = None
        self.unresolved_clarification: Optional[str] = None
        self.attributes: Dict[str, str] = {}

    def remove_constraints(self, keys: List[str]) -> None:
        """Removes specific constraints or clears all filters."""
        if "all" in keys:
            self.clear()
            return
        for k in keys:
            if k in ("budget", "price", "max_price"):
                self.max_price = None
                self.min_price = None
            elif hasattr(self, k):
                setattr(self, k, None)
            if k in self.attributes:
                del self.attributes[k]

    def update(self, updates: Dict[str, Any]) -> None:
        """Selectively updates constraints without blowing away existing untouched filters."""
        if updates.get("has_constraint_removal"):
            self.remove_constraints(updates.get("removed_constraints", []))

        if updates.get("category"):
            if self.category and self.category != updates["category"]:
                self.selected_product_id = None
                self.attributes.clear()
                if not updates.get("brand"):
                    self.brand = None
                if not updates.get("color"):
                    self.color = None
                if not updates.get("material"):
                    self.material = None
            self.category = updates["category"]
        if updates.get("max_price") is not None:
            self.max_price = updates["max_price"]
        if updates.get("min_price") is not None:
            self.min_price = updates["min_price"]
        if updates.get("brand"):
            self.brand = updates["brand"]
        if updates.get("color"):
            self.color = updates["color"]
        if updates.get("material"):
            self.material = updates["material"]
        if updates.get("stock_required") is not None:
            self.stock_required = updates["stock_required"]
        if updates.get("product_id"):
            self.selected_product_id = updates["product_id"]

        # Merge custom attributes
        if updates.get("required_attributes"):
            self.attributes.update(updates["required_attributes"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "max_price": self.max_price,
            "min_price": self.min_price,
            "brand": self.brand,
            "color": self.color,
            "material": self.material,
            "stock_required": self.stock_required,
            "product_id": self.selected_product_id,
            "required_attributes": self.attributes
        }

    def clear(self) -> None:
        self.category = None
        self.max_price = None
        self.min_price = None
        self.brand = None
        self.color = None
        self.material = None
        self.stock_required = None
        self.selected_product_id = None
        self.unresolved_clarification = None
        self.attributes.clear()
