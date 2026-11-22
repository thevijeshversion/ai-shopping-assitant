"""
agents/search.py
----------------
Search Agent — filters products from the dataset based on user query.

This agent is responsible for:
- Loading the product dataset
- Parsing the user's intent (category, budget, keywords)
- Returning a filtered list of matching products

Students:
- The basic filtering logic is implemented below as a starting point.
- TODO items show you where to extend and improve the logic.
- Do not change the function signatures — other agents depend on them.
"""

import pandas as pd
import os
import re
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


# Path to the product dataset
DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/products.csv")

# Common stop words to ignore during keyword matching
STOP_WORDS = {
    "for", "with", "and", "or", "the", "a", "an", "in", "on", "to",
    "of", "best", "good", "cheap", "affordable", "me", "find", "show", "buy"
}

# TODO 2: Python dictionary mapping search terms to their synonyms
SYNONYMS: dict[str, list[str]] = {
    "moisturiser": ["moisturizer", "hydrating cream", "face cream", "lotion"],
    "moisturizer": ["moisturiser", "hydrating cream", "face cream", "lotion"],
    "under eye cream": ["eye contour serum", "eye cream", "eye gel"],
    "eye contour serum": ["under eye cream", "eye cream", "eye gel"],
    "face wash": ["cleanser", "facial cleanser", "cleansing gel"],
    "cleanser": ["face wash", "facial cleanser", "cleansing gel"],
    "sunscreen": ["sunblock", "spf", "uv protection"],
    "lipstick": ["lip color", "lip colour", "lip tint", "lip stain"],
    "foundation": ["skin tint", "bb cream", "cc cream", "concealer"],
    "shampoo": ["hair cleanser"],
    "earphones": ["earbuds", "headphones", "headset", "tws"],
}


def load_products() -> pd.DataFrame:
    """
    Loads the product dataset from CSV.

    Returns:
        pd.DataFrame: All products, or empty DataFrame on error.
    """
    try:
        return pd.read_csv(DATA_PATH)
    except Exception as e:
        print(f"[load_products] Error loading products: {e}")
        return pd.DataFrame()


def extract_budget(query: str) -> tuple[float | None, str]:
    """
    Extract a maximum budget from natural language phrases in the query
    and returns (extracted_budget, cleaned_query).
    """
    try:
        pattern = r"\b(?:under|below|less\s+than|within|max|upto|up\s+to)\s*(?:rs\.?|inr|₹|\$)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\b"
        match = re.search(pattern, query, flags=re.IGNORECASE)
        
        if match:
            raw_amount = match.group(1).replace(",", "")
            
            budget = float(raw_amount)
            # Remove the matched budget phrase from the query so it doesn't skew keyword search
            cleaned_query = (query[:match.start()] + " " + query[match.end():]).strip()
            return budget, cleaned_query
        return None, query
    except Exception as e:
        print(f"[extract_budget] Error extracting budget: {e}")
        return None, query


def get_expanded_terms(query: str) -> list[str]:
    """
    Expands the query using the SYNONYMS dictionary.
    Includes full phrases, individual keywords, and any matching dictionary synonyms.
    """
    try:
        q_lower = query.lower().strip()
        terms = {q_lower}
        
        # 1. Check if any dictionary key appears in the query (handles multi-word keys like "under eye cream")
        for key, syn_list in SYNONYMS.items():
            if key in q_lower:
                terms.add(key)
                terms.update(syn_list)

        # 2. Add individual words and check if any single word is a key in SYNONYMS
        for word in re.findall(r"[a-z0-9]+", q_lower):
            if word not in STOP_WORDS:
                terms.add(word)
                if word in SYNONYMS:
                    terms.update(SYNONYMS[word])

        return list(terms)
    except Exception as e:
        print(f"[get_expanded_terms] Error expanding terms: {e}")
        return []


def fuzzy_term_in_text(term: str, text: str, text_words: list[str], threshold: int = 82) -> bool:
    """
    Checks if a term matches the product text either directly or via fuzzy matching.
    """
    try:
        if term in text:
            return True
        
        # Fuzzy check against individual words (for single-word typos like 'mosturizer')
        if " " not in term and len(term) >= 4:
            for word in text_words:
                if len(word) < 4:
                    continue
                if HAS_RAPIDFUZZ:
                    if fuzz.ratio(term, word) >= threshold:
                        return True
                else:
                    ratio = SequenceMatcher(None, term, word).ratio() * 100
                    if ratio >= threshold:
                        return True

        # Fuzzy partial check for multi-word phrases
        elif " " in term and HAS_RAPIDFUZZ:
            if fuzz.partial_ratio(term, text) >= threshold:
                return True

        return False
    except Exception as e:
        print(f"[fuzzy_term_in_text] Error matching term '{term}': {e}")
        return False


def search_products(query: str, max_budget: float = None, category: str = None) -> list[dict]:
    """
    Filters products based on a search query, optional budget, and optional category.

    Args:
        query      : Free-text search string from the user (e.g. "moisturiser for dry skin")
        max_budget : Maximum price the user is willing to pay (optional)
        category   : Product category to filter by (optional, e.g. "Skincare", "Electronics")

    Returns:
        List of matching product dicts. Returns empty list if no matches found.

    Example:
        >>> results = search_products("lipstick under 400", max_budget=400, category="Beauty")
    """
    try:
        df = load_products()

        
        # ── Category filter ──────────────────────────────────────────────────────
        if category:
            df = df[df["category"].str.lower() == category.lower()]
        
        # ── Extract budget from query if not explicitly provided ─────────────────
        cleaned_query = query or ""
        if cleaned_query:
            extracted_budget, cleaned_query = extract_budget(cleaned_query)            
            if extracted_budget is not None and (max_budget is None or max_budget==0):
                max_budget = extracted_budget  
        
        # ── Budget filter ────────────────────────────────────────────────────────
        if max_budget is not None:
            df = df[df["price"] <= max_budget]
       
        # ── Keyword filter ───────────────────────────────────────────────────────
        if cleaned_query.strip() and not df.empty:
            search_terms = get_expanded_terms(cleaned_query)            
            search_columns = ["product_name", "brand", "subcategory", "key_specs", "category"]

            def row_matches(row) -> bool:
                try:
                    combined = " ".join(
                        str(row[col]).lower()
                        for col in search_columns
                        if col in row.index and pd.notna(row[col])
                    )
                    words = re.findall(r"[a-z0-9]+", combined)
                    return any(fuzzy_term_in_text(term, combined, words) for term in search_terms)
                except Exception as e:
                    print(f"[search_products] Error in row_matches: {e}")
                    return False

            df = df[df.apply(row_matches, axis=1)]        
        
        # ── Stock filter ─────────────────────────────────────────────────────────
        if not df.empty:
            df = df[df["stock_status"] != "out_of_stock"]

        return df.to_dict(orient="records")

    except Exception as e:
        print(f"[search_products] Error searching products: {e}")
        return []
