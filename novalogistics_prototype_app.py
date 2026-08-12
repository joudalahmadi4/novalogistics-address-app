
import time
import hashlib
import re

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process

st.set_page_config(page_title="NovaLogistics — Address Review", layout="wide")

GREEN_900 = "#1f3f34"
GREEN_800 = "#2c5f4f"
MINT_100 = "#e6f2ec"
BG = "#f5f6f7"
RED = "#c8553d"
RED_BG = "#fbeae6"
AMBER = "#b8862c"
AMBER_BG = "#fbf1e0"

st.markdown(f"""
<style>
    .stApp {{ background-color: {BG}; }}


    .stApp, .stApp p, .stApp span, .stApp label,
    .stApp h1, .stApp h2, .stApp h3, .stApp div {{
        color: #16211d;
    }}

    .nova-header {{
        display:flex; align-items:center; gap:10px; padding:6px 0 18px 0;
    }}
    .nova-badge {{
        width:34px; height:34px; border-radius:9px; background:{GREEN_800};
        display:flex; align-items:center; justify-content:center; color:white; font-size:16px;
    }}
    .pill {{
        display:inline-block; padding:4px 12px; border-radius:999px;
        font-size:12px; font-weight:700;
    }}
    .pill-approved {{ background:{MINT_100}; color:{GREEN_800} !important; }}
    .pill-review   {{ background:{AMBER_BG}; color:{AMBER} !important; }}
    .pill-flagged  {{ background:{RED_BG};  color:{RED} !important; }}
    .pill-unmatched{{ background:#eee; color:#666 !important; }}
    div[data-testid="stMetric"] {{
        background:white; border-radius:14px; padding:14px 18px;
        box-shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 20px rgba(0,0,0,.05);
    }}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>\
    [data-testid="stFileUploaderFile"],
    [data-testid="stFileUploaderFile"] * {
        color: #f5f6f7 !important;
    }
    [data-testid="stFileUploaderFileName"] {
        color: #f5f6f7 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploaderDropzone"] * {
        color: #77dd77 !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        color: #16211d !important;
        background-color: #f5f6f7 !important;
    }
    [data-testid="stFileUploaderFile"],
    [data-testid="stFileUploaderFile"] * {
        color: #f5f6f7 !important;
    }
</style>
""", unsafe_allow_html=True)
st.markdown("""
<div class="nova-header">
    <div class="nova-badge">📍</div>
    <div><b style="font-size:18px; color:#16211d;">NovaLogistics</b><br>
    <span style="color:#5b6b64; font-size:12px;">AI-Powered Address Validation</span></div>
</div>
""", unsafe_allow_html=True)

DISTRICTS_BY_CITY = {
    "الرياض": ["الملقا", "النرجس", "الياسمين", "الروضة", "العليا", "السليمانية", "الملز",
               "النزهة", "الشفا", "حطين", "الربيع", "قرطبة", "اليرموك", "النخيل"],
    "جدة": ["الروضة", "الحمراء", "السلامة", "النزهة", "الشاطئ", "الصفا", "البوادي",
            "المرجان", "الزهراء", "النعيم", "الفيصلية", "الأندلس"],
    "الدمام": ["الفيصلية", "الشاطئ", "النور", "الجلوية", "الأمانة", "الروضة", "البادية",
               "الضباب", "الفردوس"],
    "الخفجي": ["الروضة", "الفيصلية", "الكورنيش"],
    "جازان": ["الروضة", "الصفا", "الشاطئ"],
    "الطائف": ["الشفا", "الحوية", "شهار", "السداد", "النسيم"],
    "الوجه": ["النور", "النسيم", "السلام"],
    "ضباء": ["الصفا", "النور"],
    "سكاكا": ["السلام", "الفيصلية"],
    "الجبيل": ["الفناتير", "الدفي", "الجبيل البلد", "الحويلات"],
}
ALL_CITIES = list(DISTRICTS_BY_CITY.keys())
CITY_DISTRICT_PAIRS = [(c, d) for c, ds in DISTRICTS_BY_CITY.items() for d in ds]
REFERENCE_STRINGS = [f"{c} {d}" for c, d in CITY_DISTRICT_PAIRS]

FILLERS = ["الله يرضي عليك", "بسرعه لو سمحت", "مستعجل", "ضروري",
           "يعطيك العافيه", "لو تكرمت", "بارك الله فيك", "ياليت توصل بسرعه"]

AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"
DIGIT_MAP = str.maketrans(AR_DIGITS, EN_DIGITS)

ABBREV_MAP = {
    r"\bح\b": "حي", r"\bش\b": "شارع", r"\bط\b": "طريق", r"\bمبني\b": "مبنى",
}


def normalize_arabic(text):
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ي", text)
    text = re.sub(r"[\u064B-\u065F]", "", text)
    text = re.sub(r"ـ", "", text)
    return text


def clean_address(text):
    text = str(text).translate(DIGIT_MAP)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\b05\d{8}\b", "", text)
    text = re.sub(r"[،,.\-_/\\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = normalize_arabic(text)
    for f in FILLERS:
        text = text.replace(normalize_arabic(f), "")
    for pattern, full in ABBREV_MAP.items():
        text = re.sub(pattern, full, text)
    return re.sub(r"\s+", " ", text).strip()


def match_address(cleaned_text):
    normalized_refs = [normalize_arabic(r) for r in REFERENCE_STRINGS]
    best = process.extractOne(cleaned_text, normalized_refs, scorer=fuzz.token_set_ratio)

    if best is None:
        return None, None, 0

    _, score, idx = best
    city, district = CITY_DISTRICT_PAIRS[idx]
    return city, district, round(score)


def status_from_confidence(score):
    if score >= 85:
        return "Approved", "pill-approved"
    elif score >= 60:
        return "Needs Review", "pill-review"
    elif score >= 45:
        return "Flagged", "pill-flagged"
    else:
        return "Unmatched", "pill-unmatched"

def letter_from_name(name):
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return chr(ord("A") + (h % 26))

def derive_short_code(city, district, building_number=None):
    region_code   = letter_from_name(city)
    branch_code   = letter_from_name(city)
    division_code = letter_from_name(district)
    unique_code   = "X"  # can't be derived

    letters = f"{region_code}{branch_code}{division_code}{unique_code}"

    if building_number is None:
        h = int(hashlib.md5(f"{city}{district}".encode("utf-8")).hexdigest(), 16)
        building_number = 1000 + (h % 9000)

    return f"{letters}{building_number:04d}"

st.subheader("Upload address data")
uploaded_file = st.file_uploader(
    "Drop a CSV with a column of messy Arabic addresses",
    type=["csv"],
)

if uploaded_file is not None:
    raw_df = pd.read_csv(uploaded_file)

    address_col = st.selectbox(
        "Which column holds the address text?",
        options=raw_df.columns.tolist(),
        index=0,
    )

    n_rows = st.slider("Rows to process (demo limit)", 5, min(500, len(raw_df)), 20)

    if st.button("Process addresses", type="primary"):

        progress_bar = st.progress(0, text="Starting...")
        results = []

        subset = raw_df.head(n_rows).reset_index(drop=True)

        for i, row in subset.iterrows():
            raw_text = row[address_col]
            cleaned = clean_address(raw_text)
            city, district, score = match_address(cleaned)
            status, css_class = status_from_confidence(score)
            code = derive_short_code(city, district)

            results.append({
                "Original": raw_text,
                "Cleaned": cleaned,
                "Matched City": city,
                "Matched District": district,
                "Confidence %": score,
                "Status": status,
                "_css": css_class,
                "Mock SPL Code": code,
            })

            progress_bar.progress(
                (i + 1) / len(subset),
                text=f"Processing address {i + 1} of {len(subset)}..."
            )
            time.sleep(0.03)

        progress_bar.empty()
        st.success(f"Done — {len(results)} addresses processed.")

        results_df = pd.DataFrame(results)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Approved", (results_df["Status"] == "Approved").sum())
        c2.metric("Needs Review", (results_df["Status"] == "Needs Review").sum())
        c3.metric("Flagged", (results_df["Status"] == "Flagged").sum())
        c4.metric("Unmatched", (results_df["Status"] == "Unmatched").sum())

        st.markdown("### Results")

        # simple, non-technical friendly cards: original address -> national address code
        def render_card(r):
            return f"""
            <div style="
                background:white; border-radius:16px; padding:20px 24px;
                margin-bottom:14px;
                box-shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 20px rgba(0,0,0,.06);
                border-left:5px solid {GREEN_800};
            ">
                <div style="font-size:11px; font-weight:700; color:#5b6b64;
                            letter-spacing:.03em; margin-bottom:6px;">
                    ORIGINAL ADDRESS
                </div>
                <div style="font-size:15px; color:#16211d; direction:rtl;
                            text-align:right; line-height:1.5; margin-bottom:14px;">
                    {r['Original']}
                </div>
                <div style="font-size:11px; font-weight:700; color:#5b6b64;
                            letter-spacing:.03em; margin-bottom:6px;">
                    NATIONAL ADDRESS CODE
                </div>
                <div style="font-size:20px; font-weight:800; color:{GREEN_800};
                            font-family:monospace; letter-spacing:1px;">
                    {r['Mock SPL Code']}
                </div>
            </div>
            """

        for r in results:
            st.markdown(render_card(r), unsafe_allow_html=True)

        csv_out = results_df[["Original", "Mock SPL Code"]].to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download results as CSV", csv_out, "address_review_results.csv", "text/csv")

else:
    st.info("Upload a CSV to begin")
