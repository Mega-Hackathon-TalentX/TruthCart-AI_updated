import re
from typing import Dict, Any, List, Optional, Tuple
from app.retrieval.policy_search import policy_search_engine
from app.ingestion.catalogue_loader import catalogue_loader

PROMPT_INJECTION_PATTERNS = [
    r'(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|safeguards|constraints|guidelines)',
    r'system\s+(?:prompt\s+)?override',
    r'developer\s+mode',
    r'you\s+are\s+now\s+(?:an?\s+)?unrestricted',
    r'override\s+(?:the\s+)?(?:evidence|rules|safeguards?)',
    r'bypass\s+(?:the\s+)?safeguards?',
    r'pretend\s+(?:[a-zA-Z0-9\-\s]+(?:comes with|is free|costs zero|warranty))',
    r'pretend\s+(?:you\s+can\s+invent|everything\s+is\s+free)',
    r'claim\s+that\s+(?:all\s+products\s+are\s+free|inventory\s+is\s+unlimited)',
    r'say\s+yes\s+to\s+everything'
]

class QueryUnderstanding:
    """Deterministic natural-language and code-mixed query parser with structured entity extraction."""

    # Common categories and shopping language synonyms
    KNOWN_CATEGORIES = {
        # Footwear
        "footwear": "Footwear",
        "shoes": "Footwear",
        "shoe": "Footwear",
        "sneakers": "Footwear",
        "sneaker": "Footwear",
        "running shoes": "Footwear",
        "running shoe": "Footwear",
        "hiking shoes": "Footwear",
        "hiking shoe": "Footwear",
        "boots": "Footwear",
        "boot": "Footwear",
        "sandals": "Footwear",
        "sandal": "Footwear",
        "slippers": "Footwear",
        "slipper": "Footwear",
        "flip flops": "Footwear",
        "flip flop": "Footwear",
        "heels": "Footwear",
        "block heels": "Footwear",
        "flats": "Footwear",
        "ballerinas": "Footwear",
        "loafers": "Footwear",
        "loafer": "Footwear",
        "kicks": "Footwear",
        # Multilingual: Telugu / Hindi Footwear
        "joote": "Footwear",
        "joota": "Footwear",
        "jootey": "Footwear",
        "जूते": "Footwear",
        "जूता": "Footwear",
        "cheppulu": "Footwear",
        "cheppu": "Footwear",
        "చెప్పులు": "Footwear",

        # Clothing / Apparel
        # Fashion & Apparel
        "fashion": "Fashion",
        "clothing": "Fashion",
        "clothes": "Fashion",
        "apparel": "Fashion",
        "garments": "Fashion",
        # Multilingual: Telugu / Hindi Apparel
        "kapde": "Fashion",
        "kapda": "Fashion",
        "कपड़े": "Fashion",
        "कपड़ा": "Fashion",
        "batalu": "Fashion",
        "battalu": "Fashion",
        "బట్టలు": "Fashion",
        "saree": "Fashion",
        "sarees": "Fashion",
        "kurti": "Fashion",
        "kurtis": "Fashion",
        "kurta": "Fashion",
        "कुर्ता": "Fashion",
        "साड़ी": "Fashion",
        "shirts": "Fashion",
        "shirt": "Fashion",
        "formal shirts": "Fashion",
        "tshirts": "Fashion",
        "tshirt": "Fashion",
        "t-shirts": "Fashion",
        "t-shirt": "Fashion",
        "tees": "Fashion",
        "tee": "Fashion",
        "tops": "Fashion",
        "casual tops": "Fashion",
        "jeans": "Fashion",
        "denim": "Fashion",
        "denim jeans": "Fashion",
        "trousers": "Fashion",
        "trouser": "Fashion",
        "chinos": "Fashion",
        "chino": "Fashion",
        "jackets": "Fashion",
        "jacket": "Fashion",
        "winter jackets": "Fashion",
        "leggings": "Fashion",
        "jeggings": "Fashion",
        "nightwear": "Fashion",
        "pajamas": "Fashion",
        "pyjamas": "Fashion",
        "kurtas": "Fashion",
        "traditional kurtas": "Fashion",
        "dresses": "Fashion",
        "dress": "Fashion",
        "western dresses": "Fashion",
        "hoodie": "Fashion",
        "hoodies": "Fashion",

        # Electronics
        "electronics": "Electronics",
        "electronic": "Electronics",
        "gadgets": "Electronics",
        "gadget": "Electronics",
        "headphones": "Electronics",
        "headphone": "Electronics",
        "earphones": "Electronics",
        "earphone": "Electronics",
        "earbuds": "Electronics",
        "earbud": "Electronics",
        "audio": "Electronics",
        "wireless speakers": "Electronics",
        "speakers": "Electronics",
        "speaker": "Electronics",
        "keyboards": "Electronics",
        "keyboard": "Electronics",
        "mice": "Electronics",
        "mouse": "Electronics",
        "fast chargers": "Electronics",
        "chargers": "Electronics",
        "charger": "Electronics",
        "power banks": "Electronics",
        "power bank": "Electronics",
        "protective cases": "Electronics",
        "phone cases": "Electronics",
        "phone case": "Electronics",
        "cases": "Electronics",
        "case": "Electronics",
        "pen drives": "Electronics",
        "pen drive": "Electronics",
        "usb drive": "Electronics",
        "smartwatches": "Electronics",
        "smartwatch": "Electronics",
        "smart watch": "Electronics",
        "smart watches": "Electronics",
        "laptop": "Electronics",
        "laptops": "Electronics",

        # Beauty & Personal Care
        "beauty & personal care": "Beauty & Personal Care",
        "beauty and personal care": "Beauty & Personal Care",
        "beauty": "Beauty & Personal Care",
        "personal care": "Beauty & Personal Care",
        "cosmetics": "Beauty & Personal Care",
        "perfumes": "Beauty & Personal Care",
        "perfume": "Beauty & Personal Care",
        "fragrances": "Beauty & Personal Care",
        "fragrance": "Beauty & Personal Care",
        "deodorants": "Beauty & Personal Care",
        "deodorant": "Beauty & Personal Care",
        "shampoos": "Beauty & Personal Care",
        "shampoo": "Beauty & Personal Care",
        "conditioners": "Beauty & Personal Care",
        "conditioner": "Beauty & Personal Care",
        "trimmers": "Beauty & Personal Care",
        "trimmer": "Beauty & Personal Care",
        "shaving": "Beauty & Personal Care",
        "grooming": "Beauty & Personal Care",
        "face creams": "Beauty & Personal Care",
        "face cream": "Beauty & Personal Care",
        "skin care": "Beauty & Personal Care",
        "skincare": "Beauty & Personal Care",

        # Home & Kitchen
        "home & kitchen": "Home & Kitchen",
        "home and kitchen": "Home & Kitchen",
        "home": "Home & Kitchen",
        "kitchen": "Home & Kitchen",
        "bed linen": "Home & Kitchen",
        "bedsheets": "Home & Kitchen",
        "bedsheet": "Home & Kitchen",
        "double bedsheets": "Home & Kitchen",
        "pillows": "Home & Kitchen",
        "pillow": "Home & Kitchen",
        "pillow covers": "Home & Kitchen",
        "cookware": "Home & Kitchen",
        "non-stick pans": "Home & Kitchen",
        "pans": "Home & Kitchen",
        "pan": "Home & Kitchen",
        "pressure cookers": "Home & Kitchen",
        "pressure cooker": "Home & Kitchen",
        "curtains": "Home & Kitchen",
        "curtain": "Home & Kitchen",
        "door curtains": "Home & Kitchen",
        "dinnerware": "Home & Kitchen",
        "plates": "Home & Kitchen",
        "plate": "Home & Kitchen",
        "bowls": "Home & Kitchen",
        "bowl": "Home & Kitchen",
        "showpieces": "Home & Kitchen",
        "showpiece": "Home & Kitchen",
        "wall clocks": "Home & Kitchen",
        "wall clock": "Home & Kitchen",
        "clocks": "Home & Kitchen",
        "clock": "Home & Kitchen",
        "study lamps": "Home & Kitchen",
        "lamps": "Home & Kitchen",
        "lamp": "Home & Kitchen",
        "lighting": "Home & Kitchen",
        "airtight containers": "Home & Kitchen",
        "containers": "Home & Kitchen",
        "container": "Home & Kitchen",
        "storage containers": "Home & Kitchen",
        "flask": "Home & Kitchen",
        "water bottle": "Home & Kitchen",
        "bottle": "Home & Kitchen",

        # Sports & Fitness
        "sports & fitness": "Sports & Fitness",
        "sports and fitness": "Sports & Fitness",
        "sports": "Sports & Fitness",
        "fitness": "Sports & Fitness",
        "gym": "Sports & Fitness",
        "workout": "Sports & Fitness",
        "badminton": "Sports & Fitness",
        "rackets": "Sports & Fitness",
        "racket": "Sports & Fitness",
        "shuttles": "Sports & Fitness",
        "shuttle": "Sports & Fitness",
        "cricket": "Sports & Fitness",
        "cricket bats": "Sports & Fitness",
        "bats": "Sports & Fitness",
        "bat": "Sports & Fitness",
        "cycling": "Sports & Fitness",
        "helmets": "Sports & Fitness",
        "helmet": "Sports & Fitness",
        "dumbbell sets": "Sports & Fitness",
        "dumbbells": "Sports & Fitness",
        "dumbbell": "Sports & Fitness",
        "weights": "Sports & Fitness",
        "yoga mats": "Sports & Fitness",
        "yoga mat": "Sports & Fitness",
        "mats": "Sports & Fitness",
        "mat": "Sports & Fitness",

        # Stationery
        "stationery": "Stationery",
        "hardbound diaries": "Stationery",
        "diaries": "Stationery",
        "diary": "Stationery",
        "notebooks": "Stationery",
        "notebook": "Stationery",
        "security courier bags": "Stationery",
        "courier bags": "Stationery",
        "gel pens": "Stationery",
        "pens": "Stationery",
        "pen": "Stationery",

        # Pet Supplies
        "pet supplies": "Pet Supplies",
        "pets": "Pet Supplies",
        "pet": "Pet Supplies",
        "pet shampoos": "Pet Supplies",
        "pet shampoo": "Pet Supplies",
        "dog shampoo": "Pet Supplies",
        "cat shampoo": "Pet Supplies",

        # Enterprise
        "enterprise": "Enterprise",
    }

    # Product subtypes for verifying specific item availability vs broader category
    KNOWN_SUBTYPES = {
        "slippers": "slippers",
        "slipper": "slippers",
        "flip flops": "flip flops",
        "sandals": "sandals",
        "sandal": "sandals",
        "running shoes": "running shoes",
        "hiking shoes": "hiking shoes",
        "sneakers": "sneakers",
        "boots": "boots",
        "winter boots": "winter boots",
        "block heels": "block heels",
        "heels": "block heels",
        "ballerinas": "ballerinas",
        "flats": "flats",
        "formal leather shoes": "formal leather shoes",
        "leather shoes": "formal leather shoes",
        "loafers": "loafers",
        "casual t-shirts": "casual t-shirts",
        "t-shirts": "casual t-shirts",
        "formal shirts": "formal shirts",
        "denim jeans": "denim jeans",
        "jeans": "denim jeans",
        "trousers": "trousers & chinos",
        "chinos": "trousers & chinos",
        "winter jackets": "winter jackets",
        "casual tops": "casual tops",
        "leggings": "leggings & jeggings",
        "nightwear": "nightwear",
        "traditional kurtas": "traditional kurtas",
        "kurtas": "traditional kurtas",
        "western dresses": "western dresses",
        "dresses": "western dresses",
        "hoodie": "hoodie",
        "jacket": "jacket",
        "shirt": "shirt",
        "headphones": "headphones",
        "wireless speakers": "wireless speakers",
        "speakers": "wireless speakers",
        "keyboards": "keyboards",
        "mice": "mice",
        "fast chargers": "fast chargers",
        "power banks": "power banks",
        "protective cases": "protective cases",
        "pen drives": "pen drives",
        "smartwatch": "smartwatch",
        "smartwatches": "smartwatch",
        "perfumes": "perfumes",
        "fragrances": "perfumes",
        "conditioners": "conditioners",
        "shampoos": "shampoos",
        "trimmers": "trimmers",
        "face creams": "face creams",
        "bedsheets": "double bedsheets",
        "pillows": "pillows & covers",
        "non-stick pans": "non-stick pans",
        "pressure cookers": "pressure cookers",
        "curtains": "eyelet door curtains",
        "plates & bowls": "plates & bowls",
        "showpieces": "showpieces",
        "wall clocks": "wall clocks",
        "study lamps": "study lamps",
        "airtight containers": "airtight containers",
        "rackets & shuttles": "rackets & shuttles",
        "cricket bats": "bats & protection",
        "helmets & gear": "helmets & gear",
        "dumbbell sets": "dumbbell sets",
        "dumbbells": "dumbbell sets",
        "dumbbell": "dumbbell sets",
        "sets": "dumbbell sets",
        "yoga mats": "yoga mats",
        "yoga mat": "yoga mats",
        "hardbound diaries": "hardbound diaries",
        "security courier bags": "security courier bags",
        "gel pens": "gel pens",
        "pet shampoos": "pet shampoos",
    }

    KNOWN_COLORS = ["blue", "sky blue", "navy blue", "navy", "white", "black", "red", "green", "cobalt blue", "grey", "gray", "olive", "charcoal", "pink", "yellow", "purple", "brown", "beige", "maroon"]
    KNOWN_MATERIALS = ["cotton", "linen", "silk", "leather", "polyester", "wool", "denim", "stainless steel", "glass", "wood", "plastic", "metal"]
    KNOWN_BRANDS = ["talentcloth", "aerostep", "aerowarm", "aerotech", "vanguard", "craftsman", "thermashield", "baristacraft", "zensound", "chronos", "mechprecision", "apple", "samsung", "nike", "adidas", "boat", "noise", "fire-boltt", "puma", "reebok", "philips"]


    @staticmethod
    def parse_budget(text: str) -> Tuple[Optional[float], Optional[float]]:
        """Parses price constraints including 'under 2k', 'below 1500', 'between 1000 and 2000'."""
        max_price = None
        min_price = None

        t = text.lower()

        # Remove commas between digits e.g. '2,000' -> '2000'
        t = re.sub(r'(\d+),(\d+)', r'\1\2', t)

        # Handle 'k' multiplier e.g. '2k' -> '2000'
        t = re.sub(r'(\d+)\s*k\b', lambda m: str(int(m.group(1)) * 1000), t)

        # 1. Between X and Y
        between_match = re.search(r'between\s+(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:and|to|-)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)', t)
        if between_match:
            min_price = float(between_match.group(1))
            max_price = float(between_match.group(2))
            return min_price, max_price

        # 2. Under / Below / Less than
        under_match = re.search(r'(?:under|below|less\s+than|budget(?:\s+is)?|max|up\s+to|<=|<)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)', t)
        if under_match:
            max_price = float(under_match.group(1))

        # 2b. Hindi / Telugu 'se kam' / 'lopala' / 'thakkuva' (under/below postposition)
        post_under = re.search(r'(\d+(?:\.\d+)?)\s*(?:₹|rs\.?|inr)?\s*(?:se\s+kam|se\s+neeche|ke\s+andar|lopala|thakkuva|లోపల|తక్కువ|से\s*कम|के\s*अंदर)', t)
        if post_under and max_price is None:
            max_price = float(post_under.group(1))

        # 3. Above / Over / More than
        above_match = re.search(r'(?:above|over|more\s+than|min|at\s+least|>=|>)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)', t)
        if above_match:
            min_price = float(above_match.group(1))

        # 3b. Hindi / Telugu 'se zyada' / 'kante ekkuva' (above/more than postposition)
        post_above = re.search(r'(\d+(?:\.\d+)?)\s*(?:₹|rs\.?|inr)?\s*(?:se\s+zyada|se\s+upar|kante\s+ekkuva|ekkuva|ఎక్కువ|సే\s*ఎక్కువ|से\s*ज्यादा|से\s*अधिक)', t)
        if post_above and min_price is None:
            min_price = float(post_above.group(1))

        # 4. Trailing "under 1000" or plain numbers if preceded by category
        if max_price is None and min_price is None:
            plain_under = re.search(r'\b(?:under|sub)\s*(?:₹|rs\.?|inr)?\s*(\d+)', t)
            if plain_under:
                max_price = float(plain_under.group(1))

        return min_price, max_price

    @staticmethod
    def extract_product_ids(text: str) -> List[str]:
        """Detects all product IDs like TC-DEV-101, P102, TC-101, SKU-1234."""
        pattern = r'\b([A-Za-z]{1,4}(?:-[A-Za-z0-9]+)?-\d+|\b[A-Za-z]{1,3}\d{2,6}\b)'
        matches = re.findall(pattern, text)
        pids = []
        for cand in matches:
            cand_clean = cand.strip().upper()
            if not re.match(r'^\d+[a-zA-Z]+$', cand_clean) and not cand_clean.lower() in ("ram", "ssd", "usb", "ps5", "rtx"):
                pids.append(cand_clean)
        return list(dict.fromkeys(pids)) # preserve order, remove duplicates

    @classmethod
    def detect_constraint_removals(cls, text: str) -> Tuple[bool, List[str]]:
        """Detects requests to clear or remove specific constraints."""
        t_lower = text.lower()
        if any(w in t_lower for w in ["clear filters", "reset filters", "start over", "clear all"]):
            return True, ["all"]

        removals = []
        if any(w in t_lower for w in ["remove budget", "no budget limit", "any price", "remove price", "ignore price", "no price limit"]):
            removals.append("budget")
        if any(w in t_lower for w in ["any color", "no color preference", "remove color", "remove colour"]):
            removals.append("color")
        if any(w in t_lower for w in ["any material", "remove material filter", "remove material"]):
            removals.append("material")
        if any(w in t_lower for w in ["any brand", "remove brand filter", "remove brand"]):
            removals.append("brand")

        return len(removals) > 0, removals

    @classmethod
    def detect_prompt_injection(cls, text: str) -> bool:
        t_lower = text.lower()
        for p in PROMPT_INJECTION_PATTERNS:
            if re.search(p, t_lower):
                return True
        return False

    @classmethod
    def parse(cls, query: str) -> Dict[str, Any]:
        """Extracts search constraints and intent deterministically."""
        cleaned = query.strip()
        q_lower = cleaned.lower()

        # Check prompt injection attempt
        is_injection = cls.detect_prompt_injection(cleaned)

        # Check constraint removals
        has_removal, removed_constraints = cls.detect_constraint_removals(cleaned)

        # Handle code-mixed Telugu/Hindi keywords like 'kavali' (want) or 'chahiye' (want)
        normalized_q = q_lower
        for w in ("kavali", "chahiye", "please", "dikhao", "dikhaye", "chupinchu", "chudali", "batao", "mujhe", "दिखाओ", "चाहिए", "बताओ", "చూపించు", "కావాలి"):
            normalized_q = normalized_q.replace(w, " ")
        normalized_q = " ".join(normalized_q.split())

        all_pids = cls.extract_product_ids(cleaned)
        pid = all_pids[0] if all_pids else None
        min_p, max_p = cls.parse_budget(normalized_q)

        # Detect comparison intent
        is_compare = False
        compare_pids = []
        if any(w in normalized_q for w in ["compare", "comparison", "difference between", " vs ", " versus "]):
            is_compare = True
            if len(all_pids) >= 2:
                compare_pids = all_pids[:2]
            else:
                # Check if product names in catalogue match
                prods = catalogue_loader.get_all_products()
                matched_in_query = []
                for p in prods:
                    p_title_lower = p["title"].lower()
                    if p_title_lower in normalized_q or any(token in normalized_q for token in p_title_lower.split() if len(token) >= 4):
                        if p["product_id"] not in matched_in_query:
                            matched_in_query.append(p["product_id"])
                if len(matched_in_query) >= 2:
                    compare_pids = matched_in_query[:2]

        # Detect product title match (exact full title or full title mentioned in query)
        title_lookup = None
        if not pid and not is_compare:
            cleaned_lower = cleaned.strip().lower()
            best_match = None
            best_len = 0
            for p in catalogue_loader.get_all_products():
                p_title = p.get("title", "").strip()
                p_title_lower = p_title.lower()
                if not p_title_lower:
                    continue
                if cleaned_lower == p_title_lower or normalized_q.strip() == p_title_lower:
                    best_match = p
                    break
                elif len(p_title_lower) >= 8 and p_title_lower in cleaned_lower:
                    if len(p_title_lower) > best_len:
                        best_match = p
                        best_len = len(p_title_lower)
            if best_match:
                pid = best_match["product_id"]
                title_lookup = best_match["title"]

        # Detect category (longest match first)
        category = None
        sorted_cats = sorted(cls.KNOWN_CATEGORIES.items(), key=lambda x: len(x[0]), reverse=True)
        for cat_kw, mapped_cat in sorted_cats:
            if re.search(r'\b' + re.escape(cat_kw) + r'\b', normalized_q):
                category = mapped_cat
                break

        # Detect product subtype (longest match first)
        requested_subtype = None
        sorted_subtypes = sorted(cls.KNOWN_SUBTYPES.items(), key=lambda x: len(x[0]), reverse=True)
        for sub_kw, canon_sub in sorted_subtypes:
            if re.search(r'\b' + re.escape(sub_kw) + r'\b', normalized_q):
                requested_subtype = canon_sub
                break

        # Detect color
        color = None
        for c in cls.KNOWN_COLORS:
            if re.search(r'\b' + re.escape(c) + r'\b', normalized_q):
                color = c.title()
                break

        # Detect material
        material = None
        for m in cls.KNOWN_MATERIALS:
            if re.search(r'\b' + re.escape(m) + r'\b', normalized_q):
                material = m.title()
                break

        # Detect brand
        brand = None
        for b in cls.KNOWN_BRANDS:
            if re.search(r'\b' + re.escape(b) + r'\b', normalized_q):
                brand = b.title()
                break

        # Detect stock requirement (explicit in-stock requests only, not casual 'available' or 'can I buy')
        stock_required = None
        if re.search(r'\b(in[\s-]stock|only\s+in[\s-]stock|currently\s+in[\s-]stock|in\s+stock\s+only|items\s+in\s+stock|products\s+in\s+stock)\b', normalized_q):
            stock_required = True
        elif "which products are in stock" in normalized_q or "only items in stock" in normalized_q:
            stock_required = True

        # Detect policy topic strictly when not a product or budget query
        policy_topic = policy_search_engine.detect_policy_topic(cleaned)
        has_policy_kw = any(w in normalized_q for w in ["policy", "return", "refund", "exchange", "warranty", "shipping", "delivery time", "how to return", "can i return"])
        is_policy = (
            (policy_topic is not None or "policy" in normalized_q or "terms" in normalized_q)
            and not pid
            and max_p is None
            and min_p is None
            and not is_compare
            and (
                has_policy_kw
                or (not category and not any(w in normalized_q for w in ["under", "cost", "price", "budget", "buy", "shoe", "footwear", "laptop", "shirt", "watch"]))
            )
        )

        # Detect specific requested attributes
        requested_attrs = []
        required_attributes = {}

        # Attribute extraction with specific value bounds (e.g. 16 GB RAM)
        ram_val_match = re.search(r'(\d+)\s*(?:gb|mb|tb)?\s+(?:ram|memory)', normalized_q) or re.search(r'(?:ram|memory)\s*(?:of|:)?\s*(\d+)\s*(?:gb|mb|tb)?', normalized_q)
        if ram_val_match:
            required_attributes["ram"] = f"{ram_val_match.group(1)} GB"
            requested_attrs.append("ram")
        elif "ram" in normalized_q or "memory" in normalized_q:
            requested_attrs.append("ram")

        if re.search(r'\b(price|cost|keemat|daam|rate|dhara|vela|कीमत|भाव|ధర)\b', normalized_q):
            requested_attrs.append("price")
        if re.search(r'\b(discount|deal|offer|coupon|markdown)\b', normalized_q):
            requested_attrs.append("discount")
        if re.search(r'\b(waterproof|water-resistant|water resistance)\b', normalized_q):
            requested_attrs.append("waterproof")
        is_storage_item = any(w in normalized_q for w in ["container", "box", "bag", "jar", "bin", "basket", "organiser", "organizer", "tray", "pouch"])
        if ("storage" in normalized_q and not is_storage_item) or "ssd" in normalized_q or "hdd" in normalized_q:
            requested_attrs.append("storage")
        if "battery" in normalized_q:
            requested_attrs.append("battery_life")
        if "material" in normalized_q:
            requested_attrs.append("material")
        if "color" in normalized_q or "colour" in normalized_q or "rang" in normalized_q:
            requested_attrs.append("color")
        if "warranty" in normalized_q or "guarantee" in normalized_q or "वारंटी" in normalized_q or "వారంటీ" in normalized_q:
            requested_attrs.append("warranty")
        if re.search(r'\b(rating|stars?|review)\b', normalized_q):
            requested_attrs.append("rating")

        # Sorting and review count criteria
        sort_by = None
        if any(w in normalized_q for w in ["highest rating", "highest rated", "top-rated", "top rated", "sort by rating", "sort these results by highest rating"]):
            sort_by = "rating_desc"
        elif any(w in normalized_q for w in ["cheapest", "lowest price", "cheapest first", "sort by cheapest"]):
            sort_by = "price_asc"
        elif any(w in normalized_q for w in ["highest price", "most expensive", "priciest"]):
            sort_by = "price_desc"

        min_reviews = None
        m_rev = re.search(r'at\s+least\s+(\d+)\s+reviews', normalized_q) or re.search(r'(\d+)\+\s*reviews', normalized_q) or re.search(r'minimum\s+(\d+)\s+reviews', normalized_q)
        if m_rev:
            try:
                min_reviews = int(m_rev.group(1))
            except ValueError:
                pass

        # Multi-domain Cross-Dataset Intents
        is_review_summary = bool(
            re.search(r'\b(complaints?|negative\s+feedback|issues?|problems?|review\s+summary|customer\s+feedback)\b', normalized_q)
            or ("reviews" in normalized_q and any(w in normalized_q for w in ("summarize", "summary", "complaint", "feedback", "what do users say")))
        )
        is_seller_price_compare = bool(
            re.search(r'\b(sellers?|competitors?|marketplace\s+prices?|compare\s+prices?\s+(?:from|between|across)\s+(?:two|different|all)\s+sellers?)\b', normalized_q)
            or ("compare prices" in normalized_q and any(w in normalized_q for w in ("seller", "sellers", "market", "competitor")))
        )

        intent = "search"
        if is_injection:
            intent = "prompt_injection"
        elif is_seller_price_compare:
            intent = "seller_price_comparison"
        elif is_review_summary:
            intent = "review_summary"
        elif is_compare and len(compare_pids) >= 2:
            intent = "comparison"
        elif is_policy:
            intent = "policy"
        elif pid and requested_attrs:
            intent = "attribute_lookup"
        elif pid:
            intent = "product_lookup"

        return {
            "query": cleaned,
            "intent": intent,
            "product_id": pid,
            "title": title_lookup,
            "compare_product_ids": compare_pids,
            "category": category,
            "requested_subtype": requested_subtype,
            "min_price": min_p,
            "max_price": max_p,
            "color": color,
            "material": material,
            "brand": brand,
            "stock_required": stock_required,
            "policy_topic": policy_topic,
            "is_policy_query": is_policy,
            "sort_by": sort_by,
            "min_reviews": min_reviews,
            "requested_attributes": requested_attrs,
            "required_attributes": required_attributes,
            "has_constraint_removal": has_removal,
            "removed_constraints": removed_constraints,
            "is_prompt_injection": is_injection,
            "has_prompt_injection": is_injection
        }

query_understanding = QueryUnderstanding()
