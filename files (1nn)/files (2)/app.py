import streamlit as st
import pandas as pd
import sqlite3
import os
import json
import re
import hashlib
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from collections import defaultdict, Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CommentIQ",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── GLOBAL CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap');

:root {
    --bg:        #0d0f14;
    --surface:   #151820;
    --border:    #1e2330;
    --accent1:   #6ee7b7;
    --accent2:   #818cf8;
    --accent3:   #f472b6;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --card-bg:   #161b27;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Syne', sans-serif !important;
}

[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * { font-family: 'Space Mono', monospace !important; }

.block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }

h1, h2, h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }
h1 { font-size: 2.4rem !important; letter-spacing: -1px !important; }
h2 { font-size: 1.5rem !important; color: var(--accent1) !important; }
h3 { font-size: 1.15rem !important; color: var(--accent2) !important; }

/* Stmetric cards */
[data-testid="stMetric"] {
    background: var(--card-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
}
[data-testid="stMetricValue"] { color: var(--accent1) !important; font-family: 'Space Mono', monospace !important; }
[data-testid="stMetricLabel"] { color: var(--muted) !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--accent1), var(--accent2)) !important;
    color: #0d0f14 !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.05em !important;
    padding: 0.5rem 1.2rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* Inputs / selects */
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: 'Space Mono', monospace !important;
}

/* Code / SQL blocks */
.sql-block {
    background: #0a0c12;
    border: 1px solid var(--accent1);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.82rem;
    color: var(--accent1);
    margin: 0.5rem 0 1rem 0;
    white-space: pre-wrap;
    word-break: break-all;
}

/* Comment cards */
.comment-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent1);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    margin: 0.5rem 0;
    font-size: 0.9rem;
    line-height: 1.6;
}
.comment-card.graph { border-left-color: var(--accent2); }
.comment-card.semantic { border-left-color: var(--accent3); }

.score-badge {
    display: inline-block;
    background: var(--accent3);
    color: #0d0f14;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'Space Mono', monospace;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 8px;
}

/* Module header banner */
.mod-banner {
    background: linear-gradient(135deg, var(--surface), #1a1f2e);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.2rem 1.6rem;
    margin-bottom: 1.5rem;
    border-top: 2px solid var(--accent1);
}

/* Tabs */
[data-baseweb="tab-list"] { background: var(--surface) !important; border-radius: 10px !important; }
[data-baseweb="tab"] { color: var(--muted) !important; font-family: 'Space Mono', monospace !important; font-size: 0.8rem !important; }
[aria-selected="true"][data-baseweb="tab"] { color: var(--accent1) !important; border-bottom: 2px solid var(--accent1) !important; }

/* Expander */
[data-testid="stExpander"] {
    background: var(--card-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}

/* DataFrame */
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 10px !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: var(--surface) !important;
    border: 2px dashed var(--border) !important;
    border-radius: 12px !important;
}

.stAlert { border-radius: 10px !important; }

.divider { height: 1px; background: var(--border); margin: 1.5rem 0; }

.tag {
    display: inline-block;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--accent2);
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    padding: 2px 9px;
    border-radius: 20px;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)

# ─── DB HELPERS ─────────────────────────────────────────────────────────────
DB_PATH = "/tmp/commentiq.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def sanitize_col(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(name).strip()).lower()

def excel_to_db(df: pd.DataFrame, table_name: str = "data") -> list[str]:
    """Store dataframe in SQLite, return sanitized column names."""
    cols_original = list(df.columns)
    cols_sanitized = [sanitize_col(c) for c in cols_original]
    # deduplicate
    seen = {}
    final_cols = []
    for c in cols_sanitized:
        if c in seen:
            seen[c] += 1
            final_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            final_cols.append(c)
    df.columns = final_cols
    conn = get_conn()
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    # store mapping
    st.session_state["col_mapping"] = dict(zip(cols_original, final_cols))
    st.session_state["col_mapping_inv"] = dict(zip(final_cols, cols_original))
    return final_cols

def query_db(sql: str) -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df

def build_sql_query(table: str, filters: dict, comment_col: str) -> str:
    """Build a SELECT query for comments with WHERE clauses from filters."""
    where_clauses = []
    for col, values in filters.items():
        if values:
            escaped = [v.replace("'", "''") for v in values]
            in_list = ", ".join(f"'{v}'" for v in escaped)
            where_clauses.append(f'"{col}" IN ({in_list})')
    base = f'SELECT "{comment_col}"\nFROM "{table}"'
    if where_clauses:
        base += "\nWHERE " + "\n  AND ".join(where_clauses)
    base += "\nORDER BY rowid"
    return base

# ─── GRAPH RAG HELPERS ──────────────────────────────────────────────────────

STOPWORDS = set([
    "the","a","an","is","it","in","on","at","to","of","and","or","but","for",
    "with","was","are","be","this","that","by","from","as","have","has","had",
    "not","we","i","you","they","he","she","our","us","my","his","her","their",
    "its","will","would","could","should","been","do","did","does","so","if",
    "about","more","also","just","can","all","no","up","out","than","when",
    "what","which","there","then","these","those","your","very","some","any",
    "how","am","me","into","through","each","after","before","over","under",
])

def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    words = [w for w in words if w not in STOPWORDS]
    freq = Counter(words)
    return [w for w, _ in freq.most_common(top_n)]

def build_knowledge_graph(comments: list[str]) -> nx.Graph:
    G = nx.Graph()
    all_keywords = []
    doc_keywords = []
    for c in comments:
        kws = extract_keywords(c, top_n=6)
        doc_keywords.append(kws)
        all_keywords.extend(kws)
    # top keywords become nodes
    top = [w for w, _ in Counter(all_keywords).most_common(40)]
    G.add_nodes_from(top)
    # co-occurrence edges
    edge_count = defaultdict(int)
    for kws in doc_keywords:
        kws_f = [k for k in kws if k in top]
        for i in range(len(kws_f)):
            for j in range(i+1, len(kws_f)):
                pair = tuple(sorted([kws_f[i], kws_f[j]]))
                edge_count[pair] += 1
    for (a, b), w in edge_count.items():
        if w >= 1:
            G.add_edge(a, b, weight=w)
    return G, doc_keywords

def graph_rag_query(query: str, comments: list[str], G: nx.Graph, doc_keywords: list[str], top_k: int = 5):
    """Find comments related to query by traversing knowledge graph."""
    q_kws = set(extract_keywords(query, top_n=10))
    # find graph nodes matching query
    matched_nodes = set()
    for node in G.nodes():
        if node in q_kws or any(node in qk or qk in node for qk in q_kws):
            matched_nodes.add(node)
            # 1-hop neighbors
            for nb in G.neighbors(node):
                matched_nodes.add(nb)
    if not matched_nodes:
        matched_nodes = q_kws & set(G.nodes())
    # score comments by overlap with matched nodes
    scored = []
    for i, (c, kws) in enumerate(zip(comments, doc_keywords)):
        overlap = len(set(kws) & matched_nodes)
        if overlap > 0:
            scored.append((overlap, i, c))
    scored.sort(reverse=True)
    results = []
    for score, idx, comment in scored[:top_k]:
        kws = doc_keywords[idx]
        rel_nodes = [k for k in kws if k in matched_nodes]
        results.append({"comment": comment, "score": score, "keywords": rel_nodes})
    return results

def plot_knowledge_graph(G: nx.Graph, highlight_nodes: list[str] = None):
    pos = nx.spring_layout(G, seed=42, k=2.5)
    edge_x, edge_y = [], []
    for e in G.edges():
        x0, y0 = pos[e[0]]
        x1, y1 = pos[e[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_text = list(G.nodes())
    node_colors = []
    for n in G.nodes():
        if highlight_nodes and n in highlight_nodes:
            node_colors.append("#f472b6")
        else:
            node_colors.append("#818cf8")
    node_sizes = []
    for n in G.nodes():
        deg = G.degree(n)
        node_sizes.append(max(12, min(40, 8 + deg * 3)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
        line=dict(color="#1e2330", width=1.5), hoverinfo="none"))
    fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text",
        marker=dict(size=node_sizes, color=node_colors, line=dict(color="#0d0f14", width=2)),
        text=node_text, textposition="top center",
        textfont=dict(family="Space Mono", size=10, color="#e2e8f0"),
        hovertemplate="%{text}<extra></extra>"))
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="#0d0f14",
        plot_bgcolor="#0d0f14",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=430,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig

# ─── SEMANTIC MEMORY HELPERS ────────────────────────────────────────────────

def build_tfidf_index(comments: list[str]):
    vec = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        stop_words="english",
    )
    matrix = vec.fit_transform(comments)
    return vec, matrix

def semantic_search(query: str, vectorizer, matrix, comments: list[str], top_k: int = 6):
    q_vec = vectorizer.transform([query])
    sims = cosine_similarity(q_vec, matrix).flatten()
    top_idx = np.argsort(sims)[::-1][:top_k]
    results = []
    for idx in top_idx:
        if sims[idx] > 0.01:
            results.append({"comment": comments[idx], "score": float(sims[idx]), "idx": int(idx)})
    return results

def cluster_comments(comments: list[str], n_clusters: int = 5):
    from sklearn.cluster import KMeans
    vec = TfidfVectorizer(max_features=500, stop_words="english", sublinear_tf=True)
    X = vec.fit_transform(comments)
    n = min(n_clusters, len(comments))
    km = KMeans(n_clusters=n, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    # top terms per cluster
    terms = vec.get_feature_names_out()
    cluster_terms = {}
    for i in range(n):
        center = km.cluster_centers_[i]
        top_t = [terms[j] for j in np.argsort(center)[::-1][:5]]
        cluster_terms[i] = top_t
    return labels, cluster_terms

def plot_semantic_scores(results):
    if not results:
        return None
    labels = [f"#{i+1}" for i in range(len(results))]
    scores = [r["score"] for r in results]
    fig = go.Figure(go.Bar(
        x=scores, y=labels, orientation="h",
        marker=dict(
            color=scores,
            colorscale=[[0, "#1e2330"], [0.5, "#818cf8"], [1.0, "#f472b6"]],
            showscale=False,
        ),
        text=[f"{s:.3f}" for s in scores],
        textposition="outside",
        textfont=dict(family="Space Mono", size=10, color="#e2e8f0"),
    ))
    fig.update_layout(
        paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
        font=dict(color="#e2e8f0", family="Space Mono"),
        xaxis=dict(showgrid=False, zeroline=False, color="#64748b", range=[0, max(scores)*1.25]),
        yaxis=dict(showgrid=False, color="#64748b"),
        margin=dict(l=10, r=60, t=10, b=10),
        height=200,
    )
    return fig

# ─── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💬 CommentIQ")
    st.markdown("<div style='font-size:0.72rem;color:#64748b;font-family:Space Mono,monospace'>Historical Comment Recommender</div>", unsafe_allow_html=True)
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    module = st.radio(
        "MODULE",
        ["📊 SQL + Excel Filter", "🕸️ Graph RAG Explorer", "🧠 Semantic Memory"],
        label_visibility="visible",
    )
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.72rem;color:#64748b;font-family:Space Mono,monospace'>Upload Excel once, use all modules</div>", unsafe_allow_html=True)

# ─── SHARED DATA UPLOAD (sidebar) ───────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📁 Data Source")
    uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx", "xls"])
    if uploaded:
        file_hash = hashlib.md5(uploaded.getvalue()).hexdigest()
        if st.session_state.get("file_hash") != file_hash:
            df_raw = pd.read_excel(uploaded)
            cols = excel_to_db(df_raw, table_name="data")
            st.session_state["file_hash"] = file_hash
            st.session_state["columns"] = cols
            st.session_state["df_preview"] = df_raw.head(5)
            st.session_state["total_rows"] = len(df_raw)
            # clear caches
            for k in ["graph", "doc_keywords", "tfidf_vec", "tfidf_mat", "all_comments"]:
                st.session_state.pop(k, None)
            st.success(f"✓ Loaded {len(df_raw):,} rows, {len(cols)} columns")

    if "columns" in st.session_state:
        st.markdown(f"<div style='font-size:0.72rem;color:#6ee7b7;font-family:Space Mono,monospace'>● {st.session_state['total_rows']:,} rows · {len(st.session_state['columns'])} cols</div>", unsafe_allow_html=True)
        inv = st.session_state.get("col_mapping_inv", {})
        comment_candidates = [c for c in st.session_state["columns"]
                              if any(k in c.lower() for k in ["comment","note","remark","description","text","feedback","review"])]
        display_candidates = [inv.get(c, c) for c in comment_candidates] if comment_candidates else [inv.get(c, c) for c in st.session_state["columns"]]
        san_candidates = comment_candidates if comment_candidates else st.session_state["columns"]
        selected_display = st.selectbox("Comments column", display_candidates)
        # map back to sanitized
        mapping = st.session_state.get("col_mapping", {})
        selected_san = mapping.get(selected_display, sanitize_col(selected_display))
        st.session_state["comment_col"] = selected_san
        st.session_state["comment_col_display"] = selected_display

# ─── MODULE 1: SQL + EXCEL ──────────────────────────────────────────────────
if module == "📊 SQL + Excel Filter":
    st.markdown("## 📊 SQL-Backed Excel Filter")
    st.markdown("""
    <div class='mod-banner'>
        Upload an Excel file → all columns are parsed and stored in SQLite.
        Use the auto-filters to narrow down rows → get the exact SQL query → retrieve all matching comments.
    </div>
    """, unsafe_allow_html=True)

    if "columns" not in st.session_state:
        st.info("⬅️ Upload an Excel file from the sidebar to get started.")
        st.stop()

    cols = st.session_state["columns"]
    inv = st.session_state.get("col_mapping_inv", {})
    comment_col = st.session_state.get("comment_col", cols[0])

    # ── metrics row
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rows", f"{st.session_state['total_rows']:,}")
    c2.metric("Columns", len(cols))
    c3.metric("Comments Column", inv.get(comment_col, comment_col))

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # ── preview
    with st.expander("🔍 Data Preview (first 5 rows)"):
        st.dataframe(st.session_state["df_preview"], use_container_width=True)

    st.markdown("### 🎛️ Column Filters")
    st.markdown("<div style='font-size:0.82rem;color:#64748b'>Select values to filter. Leave blank = no filter for that column.</div>", unsafe_allow_html=True)

    filter_cols = [c for c in cols if c != comment_col]
    filters = {}

    # auto-determine which cols are filterable (low cardinality or numeric)
    conn = get_conn()
    filter_grid = st.columns(min(3, len(filter_cols))) if filter_cols else []
    for i, col in enumerate(filter_cols):
        try:
            distinct = pd.read_sql_query(f'SELECT DISTINCT "{col}" FROM "data" WHERE "{col}" IS NOT NULL LIMIT 100', conn)
            vals = [str(v) for v in distinct[col].tolist()]
            display_label = inv.get(col, col)
            with filter_grid[i % len(filter_grid)]:
                selected = st.multiselect(f"**{display_label}**", vals, key=f"filt_{col}", placeholder=f"All {display_label}")
                if selected:
                    filters[col] = selected
        except Exception:
            pass
    conn.close()

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # ── build & show SQL
    sql = build_sql_query("data", filters, comment_col)
    st.markdown("### 🗄️ Generated SQL Query")
    st.markdown(f"<div class='sql-block'>{sql}</div>", unsafe_allow_html=True)

    col_run, col_copy = st.columns([1, 4])
    with col_run:
        run = st.button("▶ Run Query")

    if run or st.session_state.get("last_sql") == sql:
        st.session_state["last_sql"] = sql
        try:
            result_df = query_db(sql)
            st.markdown(f"### 💬 Comments Retrieved &nbsp;<span style='font-size:0.82rem;color:#64748b'>({len(result_df):,} rows)</span>", unsafe_allow_html=True)
            if result_df.empty:
                st.warning("No comments matched your filters.")
            else:
                # store for other modules
                comments_list = result_df[comment_col].dropna().astype(str).tolist()
                st.session_state["filtered_comments"] = comments_list
                for c in comments_list[:50]:
                    st.markdown(f"<div class='comment-card'>{c}</div>", unsafe_allow_html=True)
                if len(comments_list) > 50:
                    st.info(f"Showing first 50 of {len(comments_list):,} comments.")
                st.download_button("⬇ Export as CSV", result_df.to_csv(index=False), "comments.csv", "text/csv")
        except Exception as e:
            st.error(f"SQL Error: {e}")

# ─── MODULE 2: GRAPH RAG ────────────────────────────────────────────────────
elif module == "🕸️ Graph RAG Explorer":
    st.markdown("## 🕸️ Graph RAG Explorer")
    st.markdown("""
    <div class='mod-banner'>
        Comments are parsed into a <b>knowledge graph</b> where nodes are topics/keywords and edges represent
        co-occurrence relationships. Query in natural language — the system traverses the graph to surface
        the most relevant historical comments.
    </div>
    """, unsafe_allow_html=True)

    if "columns" not in st.session_state:
        st.info("⬅️ Upload an Excel file from the sidebar to get started.")
        st.stop()

    # load all comments
    comment_col = st.session_state.get("comment_col", st.session_state["columns"][0])
    if "all_comments" not in st.session_state:
        try:
            df_c = query_db(f'SELECT "{comment_col}" FROM "data" WHERE "{comment_col}" IS NOT NULL')
            st.session_state["all_comments"] = df_c[comment_col].astype(str).tolist()
        except Exception as e:
            st.error(f"Error loading comments: {e}")
            st.stop()

    all_comments = st.session_state["all_comments"]

    if not all_comments:
        st.warning("No comments found.")
        st.stop()

    # build graph (cached)
    if "graph" not in st.session_state:
        with st.spinner("Building knowledge graph…"):
            G, doc_kws = build_knowledge_graph(all_comments)
            st.session_state["graph"] = G
            st.session_state["doc_keywords"] = doc_kws

    G = st.session_state["graph"]
    doc_kws = st.session_state["doc_keywords"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Comments", f"{len(all_comments):,}")
    c2.metric("Graph Nodes (topics)", G.number_of_nodes())
    c3.metric("Graph Edges (co-occur)", G.number_of_edges())

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔍 Query Graph", "🗺️ Full Graph View"])

    with tab1:
        st.markdown("### Ask a question or enter a topic")
        query = st.text_input("", placeholder="e.g.  delivery delay  /  payment issue  /  customer unhappy", key="graph_query")
        top_k = st.slider("Max results", 3, 15, 6, key="grag_k")

        if query:
            results = graph_rag_query(query, all_comments, G, doc_kws, top_k=top_k)
            q_kws = extract_keywords(query)
            highlight = []
            for n in G.nodes():
                if any(n in qk or qk in n for qk in q_kws) or n in q_kws:
                    highlight.append(n)
                    for nb in G.neighbors(n):
                        highlight.append(nb)

            col_g, col_r = st.columns([1.2, 1])
            with col_g:
                st.markdown("**Traversal graph** (pink = matched nodes)")
                sub_nodes = set(highlight[:30])
                if sub_nodes:
                    Gsub = G.subgraph(sub_nodes)
                    st.plotly_chart(plot_knowledge_graph(Gsub, highlight), use_container_width=True)
                else:
                    st.plotly_chart(plot_knowledge_graph(G, []), use_container_width=True)

            with col_r:
                st.markdown(f"**{len(results)} relevant comments found**")
                if not results:
                    st.info("No matching comments. Try different keywords.")
                for r in results:
                    tags_html = " ".join(f"<span class='tag'>{k}</span>" for k in r["keywords"])
                    st.markdown(f"""
                    <div class='comment-card graph'>
                        {r['comment']}<br>
                        <div style='margin-top:6px'>{tags_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab2:
        st.markdown("### Full Knowledge Graph")
        st.markdown("<div style='font-size:0.82rem;color:#64748b'>Node size = degree (connections). Hover to see topic labels.</div>", unsafe_allow_html=True)
        st.plotly_chart(plot_knowledge_graph(G), use_container_width=True)
        with st.expander("Top connected topics"):
            top_nodes = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:15]
            for n, d in top_nodes:
                st.markdown(f"<span class='tag'>{n}</span> <span style='color:#64748b;font-size:0.75rem;font-family:Space Mono'>{d} connections</span>", unsafe_allow_html=True)

# ─── MODULE 3: SEMANTIC MEMORY ──────────────────────────────────────────────
elif module == "🧠 Semantic Memory":
    st.markdown("## 🧠 Semantic Memory")
    st.markdown("""
    <div class='mod-banner'>
        TF-IDF vector space indexes every comment. Type any new comment or fragment — the engine
        instantly surfaces the <b>most semantically similar historical comments</b>, ranked by cosine similarity.
        Also clusters all comments into topic groups automatically.
    </div>
    """, unsafe_allow_html=True)

    if "columns" not in st.session_state:
        st.info("⬅️ Upload an Excel file from the sidebar to get started.")
        st.stop()

    comment_col = st.session_state.get("comment_col", st.session_state["columns"][0])
    if "all_comments" not in st.session_state:
        try:
            df_c = query_db(f'SELECT "{comment_col}" FROM "data" WHERE "{comment_col}" IS NOT NULL')
            st.session_state["all_comments"] = df_c[comment_col].astype(str).tolist()
        except Exception as e:
            st.error(f"Error loading comments: {e}")
            st.stop()

    all_comments = st.session_state["all_comments"]
    if not all_comments:
        st.warning("No comments found.")
        st.stop()

    if "tfidf_vec" not in st.session_state:
        with st.spinner("Building semantic index…"):
            vec, mat = build_tfidf_index(all_comments)
            st.session_state["tfidf_vec"] = vec
            st.session_state["tfidf_mat"] = mat

    vec = st.session_state["tfidf_vec"]
    mat = st.session_state["tfidf_mat"]

    tab_search, tab_cluster = st.tabs(["🔎 Similarity Search", "🗂️ Auto Clustering"])

    with tab_search:
        st.markdown("### Enter a comment to find similar historical comments")
        query_text = st.text_area("", height=100,
            placeholder="Paste or type a new comment here… e.g. 'The product arrived damaged and customer service was unhelpful'",
            key="sem_query")
        top_n = st.slider("Top-N results", 3, 20, 8, key="sem_k")

        if query_text.strip():
            results = semantic_search(query_text, vec, mat, all_comments, top_k=top_n)

            if not results:
                st.info("No similar comments found. Try a different query.")
            else:
                st.markdown(f"### 🎯 Top {len(results)} Similar Comments")
                score_fig = plot_semantic_scores(results)
                if score_fig:
                    st.plotly_chart(score_fig, use_container_width=True)

                for i, r in enumerate(results):
                    score_pct = int(r["score"] * 100)
                    st.markdown(f"""
                    <div class='comment-card semantic'>
                        <span style='color:#64748b;font-family:Space Mono;font-size:0.72rem'>#{i+1}</span>
                        <span class='score-badge'>{score_pct}% match</span><br><br>
                        {r['comment']}
                    </div>
                    """, unsafe_allow_html=True)

    with tab_cluster:
        st.markdown("### Auto-Cluster Comments by Topic")
        n_clust = st.slider("Number of clusters", 2, 10, 5, key="n_clust")
        if st.button("🔄 Run Clustering"):
            with st.spinner("Clustering…"):
                try:
                    labels, cluster_terms = cluster_comments(all_comments, n_clusters=n_clust)
                    cluster_df = pd.DataFrame({"comment": all_comments, "cluster": labels})

                    # cluster size chart
                    counts = cluster_df["cluster"].value_counts().sort_index()
                    cluster_names = {i: " · ".join(t[:3]) for i, t in cluster_terms.items()}
                    fig = go.Figure(go.Bar(
                        x=[cluster_names.get(i, f"Cluster {i}") for i in counts.index],
                        y=counts.values,
                        marker=dict(
                            color=counts.values,
                            colorscale=[[0,"#818cf8"],[0.5,"#6ee7b7"],[1.0,"#f472b6"]],
                            showscale=False,
                        ),
                        text=counts.values,
                        textposition="outside",
                    ))
                    fig.update_layout(
                        paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                        font=dict(color="#e2e8f0", family="Space Mono", size=10),
                        xaxis=dict(showgrid=False, color="#64748b"),
                        yaxis=dict(showgrid=False, color="#64748b"),
                        margin=dict(l=10, r=10, t=10, b=60),
                        height=280,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    for ci in range(n_clust):
                        terms_str = " · ".join(cluster_terms.get(ci, []))
                        cluster_comments_list = cluster_df[cluster_df["cluster"] == ci]["comment"].tolist()
                        with st.expander(f"**Cluster {ci+1}** — {terms_str}  ({len(cluster_comments_list)} comments)"):
                            for c in cluster_comments_list[:10]:
                                st.markdown(f"<div class='comment-card semantic'>{c}</div>", unsafe_allow_html=True)
                            if len(cluster_comments_list) > 10:
                                st.info(f"… {len(cluster_comments_list)-10} more in this cluster.")
                except Exception as e:
                    st.error(f"Clustering error: {e}")
        else:
            st.markdown("<div style='color:#64748b;font-size:0.85rem'>Click 'Run Clustering' to group all comments by semantic topic automatically.</div>", unsafe_allow_html=True)
