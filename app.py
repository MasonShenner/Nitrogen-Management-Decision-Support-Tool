import os
import zipfile
import tempfile
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Try to import geopandas for shapefile support
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False


# ---------------------------------
# Page setup
# ---------------------------------
st.set_page_config(
    page_title="Agronomy AI Tool",
    layout="wide",
    page_icon="🌾"
)

# ---------------------------------
# Custom styling
# ---------------------------------
st.markdown(
    """
    <style>
    .main {
        padding-top: 1.2rem;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    .hero-box {
        background: linear-gradient(135deg, #10233d 0%, #16385c 100%);
        padding: 1.4rem 1.6rem;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 1rem;
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        color: white;
        margin-bottom: 0.4rem;
    }

    .hero-subtitle {
        font-size: 1rem;
        color: #d7e7f7;
        margin-bottom: 0.2rem;
    }

    .crop-tag {
        display: inline-block;
        background: rgba(255,255,255,0.12);
        color: #ffffff;
        padding: 0.45rem 0.75rem;
        border-radius: 999px;
        font-size: 0.9rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }

    .kpi-card {
        background: #111827;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 1rem 1rem 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }

    .kpi-label {
        font-size: 0.9rem;
        color: #9ca3af;
        margin-bottom: 0.35rem;
    }

    .kpi-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #f9fafb;
    }

    .section-card {
        background: #0f172a;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 1rem 1rem 0.75rem 1rem;
        margin-bottom: 1rem;
    }

    .summary-box {
        background: linear-gradient(135deg, #13304d 0%, #1d4c73 100%);
        padding: 1.15rem 1.2rem;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08);
        color: white;
        margin-bottom: 1rem;
    }

    .summary-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }

    .small-note {
        color: #9ca3af;
        font-size: 0.88rem;
        margin-top: 0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------
# Header
# ---------------------------------
st.markdown(
    """
    <div class="hero-box">
        <div class="hero-title">Agronomy AI Decision Support Tool</div>
        <div class="hero-subtitle">
            Upload nitrogen prescription and yield data to compare original agronomist decisions
            with AI-assisted nitrogen recommendations.
        </div>
        <div class="crop-tag">Crop Type: CWRS (Canada Western Red Spring Wheat)</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------------------------
# Helpers
# ---------------------------------
def clean_columns(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df


def read_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return None, "No file uploaded."

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        df = clean_columns(df)
        return df, "CSV file loaded successfully."

    if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)
        df = clean_columns(df)
        return df, "Excel file loaded successfully."

    if file_name.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, uploaded_file.name)

            with open(zip_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)
                extracted_files = zip_ref.namelist()

            for inner_file in extracted_files:
                if inner_file.lower().endswith(".csv"):
                    csv_path = os.path.join(tmpdir, inner_file)
                    df = pd.read_csv(csv_path)
                    df = clean_columns(df)
                    return df, f"ZIP file loaded. Found CSV: {inner_file}"

            for inner_file in extracted_files:
                if inner_file.lower().endswith(".xlsx") or inner_file.lower().endswith(".xls"):
                    excel_path = os.path.join(tmpdir, inner_file)
                    df = pd.read_excel(excel_path)
                    df = clean_columns(df)
                    return df, f"ZIP file loaded. Found Excel file: {inner_file}"

            shp_files = [f for f in extracted_files if f.lower().endswith(".shp")]

            if shp_files:
                if not GEOPANDAS_AVAILABLE:
                    return None, "ZIP contains a shapefile, but geopandas is not installed."

                shp_path = os.path.join(tmpdir, shp_files[0])

                try:
                    try:
                        gdf = gpd.read_file(shp_path, engine="pyogrio")
                    except Exception:
                        gdf = gpd.read_file(shp_path)

                    gdf = clean_columns(gdf)
                    return gdf, f"ZIP file loaded. Found shapefile: {shp_files[0]}"
                except Exception as e:
                    return None, f"Found shapefile but could not read it: {e}"

            return None, "ZIP file was read, but no CSV, Excel, or shapefile was found."

    return None, "Unsupported file type."


def add_kpi(label, value, color="#f9fafb"):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{color};">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def safe_qcut(series, q=5, labels=None):
    try:
        return pd.qcut(series, q=q, labels=labels, duplicates="drop")
    except Exception:
        ranks = series.rank(method="first")
        return pd.qcut(ranks, q=q, labels=labels, duplicates="drop")


def build_range_labels(series, unit="", bins_count=5, decimals=1):
    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        return pd.Series(["Unknown"] * len(series), index=series.index), ["Unknown"]

    min_val = float(clean.min())
    max_val = float(clean.max())

    if np.isclose(min_val, max_val):
        single_label = f"{round(min_val, decimals)} {unit}".strip()
        return pd.Series([single_label] * len(series), index=series.index), [single_label]

    edges = np.linspace(min_val, max_val, bins_count + 1)
    edges[0] = min_val
    edges[-1] = max_val

    labels = []
    for i in range(len(edges) - 1):
        low = round(edges[i], decimals)
        high = round(edges[i + 1], decimals)
        labels.append(f"{low} to {high} {unit}".strip())

    binned = pd.cut(
        series,
        bins=edges,
        labels=labels,
        include_lowest=True,
        duplicates="drop"
    )

    return binned.astype(str), labels


def build_change_range_labels(series, unit="lb/ac", decimals=1):
    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        return pd.Series(["Unknown"] * len(series), index=series.index), ["Unknown"]

    min_val = float(clean.min())
    max_val = float(clean.max())

    if np.isclose(min_val, max_val):
        single_label = f"{round(min_val, decimals)} {unit}".strip()
        return pd.Series([single_label] * len(series), index=series.index), [single_label]

    edges = np.linspace(min_val, max_val, 6)
    labels = []
    for i in range(len(edges) - 1):
        low = round(edges[i], decimals)
        high = round(edges[i + 1], decimals)
        labels.append(f"{low} to {high} {unit}")

    binned = pd.cut(
        series,
        bins=edges,
        labels=labels,
        include_lowest=True,
        duplicates="drop"
    )

    return binned.astype(str), labels


def format_hover_template(metric_label, metric_unit, extra_lines):
    metric_unit_text = f" {metric_unit}" if metric_unit else ""
    hover = (
        "<b>Yield Class:</b> %{customdata[0]}<br>"
        "<b>" + metric_label + ":</b> %{customdata[1]}" + metric_unit_text
    )

    for idx, line in enumerate(extra_lines, start=2):
        hover += "<br><b>" + line["label"] + ":</b> %{customdata[" + str(idx) + "]}"
        if line.get("unit"):
            hover += " " + line["unit"]

    hover += "<extra></extra>"
    return hover


# ---------------------------------
# Upload section
# ---------------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Upload Field Data")

upload_col1, upload_col2 = st.columns(2)

with upload_col1:
    n_file = st.file_uploader(
        "Upload Nitrogen Prescription File",
        type=["csv", "xlsx", "xls", "zip"]
    )

with upload_col2:
    y_file = st.file_uploader(
        "Upload Yield Data File",
        type=["csv", "xlsx", "xls", "zip"]
    )

st.markdown(
    '<div class="small-note">Accepted file types: CSV, Excel, and ZIP exports including shapefiles.</div>',
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------
# Main processing
# ---------------------------------
if n_file is not None and y_file is not None:
    n_df, n_message = read_uploaded_file(n_file)
    y_df, y_message = read_uploaded_file(y_file)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("File Processing Status")

    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.write(f"**Nitrogen file:** {n_message}")
    with status_col2:
        st.write(f"**Yield file:** {y_message}")

    if n_df is None or y_df is None:
        st.error("One or both files could not be read.")
        st.stop()
    else:
        st.success("Both files were loaded successfully.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------
    # Preview data
    # ---------------------------------
    preview_col1, preview_col2 = st.columns(2)

    with preview_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Nitrogen Prescription Data Preview")
        preview_n = pd.DataFrame(n_df).drop(columns=["geometry"], errors="ignore")
        st.dataframe(preview_n.head(), width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    with preview_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Yield Data Preview")
        preview_y = pd.DataFrame(y_df).drop(columns=["geometry"], errors="ignore")
        st.dataframe(preview_y.head(), width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------
    # Agronomy calculations
    # ---------------------------------
    n = n_df.copy()
    y = y_df.copy()

    SQFT_TO_ACRES = 1 / 43560

    if "DISTANCE" in n.columns and "SWATHWIDTH" in n.columns:
        n["Area_ac"] = n["DISTANCE"] * n["SWATHWIDTH"] * SQFT_TO_ACRES

    if "DISTANCE" in y.columns and "SWATHWIDTH" in y.columns:
        y["Area_ac"] = y["DISTANCE"] * y["SWATHWIDTH"] * SQFT_TO_ACRES

    if "VRYIELDVOL" in y.columns:
        y["Yield"] = y["VRYIELDVOL"]

    min_len = min(len(n), len(y))
    merged = pd.DataFrame()

    if "Area_ac" in y.columns:
        merged["Area_ac"] = y["Area_ac"].iloc[:min_len].values

    if "Yield" in y.columns:
        merged["Yield"] = y["Yield"].iloc[:min_len].values

    if "AppliedRate" in n.columns:
        merged["NitrogenRate"] = n["AppliedRate"].iloc[:min_len].values

    if "Yield" in merged.columns and "NitrogenRate" in merged.columns:
        merged["N_Efficiency"] = merged["Yield"] / merged["NitrogenRate"]

    if "geometry" in y.columns:
        merged["geometry"] = y["geometry"].iloc[:min_len].values
    elif "geometry" in n.columns:
        merged["geometry"] = n["geometry"].iloc[:min_len].values

    merged = merged.replace([float("inf"), -float("inf")], pd.NA)
    merged = merged.dropna(subset=["Area_ac", "Yield", "NitrogenRate", "N_Efficiency"])

    if merged.empty:
        st.error("The uploaded files were read, but the processed dataset is empty after cleaning.")
        st.stop()

    merged["YieldClass"] = safe_qcut(
        merged["Yield"],
        q=5,
        labels=["Very Low", "Low", "Medium", "High", "Very High"]
    )

    summary = merged.groupby("YieldClass", observed=False).agg({
        "Area_ac": "sum",
        "Yield": "mean",
        "NitrogenRate": "mean",
        "N_Efficiency": "mean"
    }).reset_index()

    summary = summary.rename(columns={
        "YieldClass": "Yield Class",
        "Area_ac": "Area (ac)",
        "Yield": "Yield (bu/ac)",
        "NitrogenRate": "N Rate (lb/ac)",
        "N_Efficiency": "N Efficiency"
    })

    # ---------------------------------
    # AI recommendation model
    # ---------------------------------
    ai_table = summary.copy()

    def adjust_n_rate(row):
        efficiency = row["N Efficiency"]
        current_n = row["N Rate (lb/ac)"]

        if efficiency < 0.4:
            return current_n * 0.90
        elif efficiency < 0.6:
            return current_n * 0.95
        elif efficiency < 0.75:
            return current_n
        else:
            return current_n * 1.05

    ai_table["AI N Rate (lb/ac)"] = ai_table.apply(adjust_n_rate, axis=1)
    ai_table["N Change (lb/ac)"] = ai_table["AI N Rate (lb/ac)"] - ai_table["N Rate (lb/ac)"]

    # ---------------------------------
    # Rounded display
    # ---------------------------------
    summary_display = summary.copy()
    ai_display = ai_table.copy()

    for col in ["Area (ac)", "Yield (bu/ac)", "N Rate (lb/ac)", "N Efficiency"]:
        summary_display[col] = summary_display[col].round(2)

    for col in [
        "Area (ac)", "Yield (bu/ac)", "N Rate (lb/ac)",
        "N Efficiency", "AI N Rate (lb/ac)", "N Change (lb/ac)"
    ]:
        ai_display[col] = ai_display[col].round(2)

    # ---------------------------------
    # KPI cards
    # ---------------------------------
    total_area = summary["Area (ac)"].sum()
    avg_original_n = ai_table["N Rate (lb/ac)"].mean()
    avg_ai_n = ai_table["AI N Rate (lb/ac)"].mean()
    avg_n_change = ai_table["N Change (lb/ac)"].mean()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        add_kpi("Estimated Field Area", f"{total_area:.1f} ac")
    with kpi2:
        add_kpi("Average Original N Rate", f"{avg_original_n:.1f} lb/ac")
    with kpi3:
        add_kpi("Average AI N Rate", f"{avg_ai_n:.1f} lb/ac")
    with kpi4:
        change_color = "#22c55e" if avg_n_change >= 0 else "#f97316"
        add_kpi("Average N Change", f"{avg_n_change:.1f} lb/ac", color=change_color)

    # ---------------------------------
    # Summary box
    # ---------------------------------
    lowest_eff_class = ai_table.loc[ai_table["N Efficiency"].idxmin(), "Yield Class"]
    highest_eff_class = ai_table.loc[ai_table["N Efficiency"].idxmax(), "Yield Class"]

    st.markdown(
        f"""
        <div class="summary-box">
            <div class="summary-title">AI Recommendation Summary</div>
            <div>
                The field was divided into yield zones to compare how nitrogen performed across different areas.
                Lower-yield areas showed weaker efficiency, which means nitrogen was not being used as effectively.
                Higher-yield areas showed stronger efficiency and a better response to nitrogen.
                <br><br>
                Based on this pattern, the model recommends slightly reducing nitrogen in lower-performing areas
                and maintaining or slightly increasing it in stronger-performing zones.
                <br><br>
                The weakest nitrogen performance was found in the <b>{lowest_eff_class}</b> zone, while the strongest
                performance was found in the <b>{highest_eff_class}</b> zone.
                <br><br>
                On average, the original nitrogen rate was <b>{avg_original_n:.1f} lb/ac</b>, and the AI-recommended
                rate is <b>{avg_ai_n:.1f} lb/ac</b>. This represents an average change of
                <b>{avg_n_change:.1f} lb/ac</b> across the field.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ---------------------------------
    # Nitrogen rate chart
    # ---------------------------------
    with st.expander("View Nitrogen Rate by Yield Class", expanded=False):
        st.markdown("Compare the original nitrogen rate with the AI-recommended rate for each yield class.")

        fig_n = go.Figure()

        fig_n.add_trace(
            go.Bar(
                x=summary_display["Yield Class"],
                y=summary_display["N Rate (lb/ac)"],
                name="Original N Rate",
                text=summary_display["N Rate (lb/ac)"],
                textposition="outside"
            )
        )

        fig_n.add_trace(
            go.Bar(
                x=ai_display["Yield Class"],
                y=ai_display["AI N Rate (lb/ac)"],
                name="AI N Rate",
                text=ai_display["AI N Rate (lb/ac)"],
                textposition="outside"
            )
        )

        fig_n.update_layout(
            barmode="group",
            height=430,
            xaxis_title="Yield Class",
            yaxis_title="Nitrogen Rate (lb/ac)",
            margin=dict(l=20, r=20, t=20, b=20)
        )

        st.plotly_chart(
            fig_n,
            width="stretch",
            config={"displayModeBar": False}
        )

    # ---------------------------------
    # Side-by-side tables
    # ---------------------------------
    st.subheader("Comparison: Agronomist vs AI Recommendation")

    table_col1, table_col2 = st.columns(2)

    with table_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Original Agronomist")
        st.dataframe(summary_display, width="stretch", hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with table_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### AI Recommendation")
        st.dataframe(ai_display, width="stretch", hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------
    # Map section
    # ---------------------------------
    if "geometry" in merged.columns and GEOPANDAS_AVAILABLE:
        st.subheader("Field Map Viewer")

        try:
            gmap = gpd.GeoDataFrame(merged.copy(), geometry="geometry")

            if gmap.crs is None:
                gmap = gmap.set_crs(epsg=4326, allow_override=True)

            gmap = gmap.to_crs(epsg=4326)
            gmap["lon"] = gmap.geometry.x
            gmap["lat"] = gmap.geometry.y

            change_lookup = dict(zip(ai_table["Yield Class"], ai_table["N Change (lb/ac)"]))
            ai_rate_lookup = dict(zip(ai_table["Yield Class"], ai_table["AI N Rate (lb/ac)"]))
            avg_yield_lookup = dict(zip(ai_table["Yield Class"], ai_table["Yield (bu/ac)"]))

            gmap["AI_N_Rate"] = gmap["YieldClass"].map(ai_rate_lookup)
            gmap["N_Change"] = gmap["YieldClass"].map(change_lookup)
            gmap["Predicted_Yield"] = gmap["YieldClass"].map(avg_yield_lookup)

            gmap["Yield"] = pd.to_numeric(gmap["Yield"], errors="coerce")
            gmap["NitrogenRate"] = pd.to_numeric(gmap["NitrogenRate"], errors="coerce")
            gmap["AI_N_Rate"] = pd.to_numeric(gmap["AI_N_Rate"], errors="coerce")
            gmap["N_Efficiency"] = pd.to_numeric(gmap["N_Efficiency"], errors="coerce")
            gmap["N_Change"] = pd.to_numeric(gmap["N_Change"], errors="coerce")
            gmap["Predicted_Yield"] = pd.to_numeric(gmap["Predicted_Yield"], errors="coerce")

            map_col1, map_col2 = st.columns([1, 3])

            with map_col1:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                map_view = st.selectbox(
                    "Select map view",
                    [
                        "Original Nitrogen Applied",
                        "AI Recommended Nitrogen Rate",
                        "Yield",
                        "Nitrogen Efficiency",
                        "Nitrogen Change"
                    ]
                )
                st.markdown('</div>', unsafe_allow_html=True)

            if map_view == "Original Nitrogen Applied":
                color_value = "NitrogenRate"
                legend_title = "Original N Rate Range"
                map_title = "Original Nitrogen Applied Map"
                unit = "lb/ac"
                range_col, range_order = build_range_labels(gmap[color_value], unit=unit, bins_count=5, decimals=1)
                gmap["MapRange"] = range_col

                hover_fields = [
                    {"label": "Yield", "value_col": "Yield", "unit": "bu/ac", "decimals": 1},
                    {"label": "Yield Class", "value_col": "YieldClass", "unit": "", "decimals": None}
                ]
                note_text = "This map shows the original nitrogen rate applied across the field."

            elif map_view == "AI Recommended Nitrogen Rate":
                color_value = "AI_N_Rate"
                legend_title = "AI N Rate Range"
                map_title = "AI Recommended Nitrogen Rate Map"
                unit = "lb/ac"
                range_col, range_order = build_range_labels(gmap[color_value], unit=unit, bins_count=5, decimals=1)
                gmap["MapRange"] = range_col

                hover_fields = [
                    {"label": "Original N Rate", "value_col": "NitrogenRate", "unit": "lb/ac", "decimals": 1},
                    {"label": "Yield Class", "value_col": "YieldClass", "unit": "", "decimals": None}
                ]
                note_text = "This map shows the AI-generated nitrogen rate that could be applied by area."

            elif map_view == "Yield":
                color_value = "Yield"
                legend_title = "Yield Range"
                map_title = "Yield Map"
                unit = "bu/ac"
                range_col, range_order = build_range_labels(gmap[color_value], unit=unit, bins_count=5, decimals=1)
                gmap["MapRange"] = range_col

                hover_fields = [
                    {"label": "Original N Rate", "value_col": "NitrogenRate", "unit": "lb/ac", "decimals": 1},
                    {"label": "Yield Class", "value_col": "YieldClass", "unit": "", "decimals": None}
                ]
                note_text = "This map shows harvested yield by point across the field."

            elif map_view == "Nitrogen Efficiency":
                color_value = "N_Efficiency"
                legend_title = "N Efficiency Range"
                map_title = "Nitrogen Efficiency Map"
                unit = ""
                range_col, range_order = build_range_labels(gmap[color_value], unit=unit, bins_count=5, decimals=2)
                gmap["MapRange"] = range_col

                hover_fields = [
                    {"label": "Yield", "value_col": "Yield", "unit": "bu/ac", "decimals": 1},
                    {"label": "Original N Rate", "value_col": "NitrogenRate", "unit": "lb/ac", "decimals": 1}
                ]
                note_text = "This map shows how efficiently nitrogen performed across different parts of the field."

            else:
                color_value = "N_Change"
                legend_title = "N Change Range"
                map_title = "Nitrogen Change Map"
                unit = "lb/ac"
                range_col, range_order = build_change_range_labels(gmap[color_value], unit=unit, decimals=1)
                gmap["MapRange"] = range_col

                hover_fields = [
                    {"label": "Original N Rate", "value_col": "NitrogenRate", "unit": "lb/ac", "decimals": 1},
                    {"label": "AI N Rate", "value_col": "AI_N_Rate", "unit": "lb/ac", "decimals": 1}
                ]
                note_text = "This map shows the difference between the original rate and the AI recommended rate."

            # Build clean display values for hover
            primary_display_col = "PrimaryDisplayValue"
            if unit:
                gmap[primary_display_col] = gmap[color_value].round(1)
            else:
                gmap[primary_display_col] = gmap[color_value].round(2)

            custom_data_cols = ["YieldClass", primary_display_col]
            extra_hover_defs = []

            for field in hover_fields:
                col_name = f"hover_{field['label'].replace(' ', '_')}"
                if field["decimals"] is None:
                    gmap[col_name] = gmap[field["value_col"]].astype(str)
                else:
                    gmap[col_name] = pd.to_numeric(gmap[field["value_col"]], errors="coerce").round(field["decimals"])
                custom_data_cols.append(col_name)
                extra_hover_defs.append({"label": field["label"], "unit": field["unit"]})

            # Color palette
            if map_view == "Nitrogen Change":
                color_sequence = px.colors.diverging.RdYlGn
            elif map_view == "Yield":
                color_sequence = px.colors.sequential.YlGn
            elif map_view == "Nitrogen Efficiency":
                color_sequence = px.colors.sequential.Tealgrn
            else:
                color_sequence = px.colors.sequential.Blues

            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown(f"### {map_title}")
            st.markdown(note_text)

            fig_ai_map = px.scatter_map(
                gmap,
                lat="lat",
                lon="lon",
                color="MapRange",
                category_orders={"MapRange": range_order},
                color_discrete_sequence=color_sequence,
                zoom=12,
                height=650,
                custom_data=custom_data_cols
            )

            hover_template = format_hover_template(
                metric_label=map_view,
                metric_unit=unit,
                extra_lines=extra_hover_defs
            )

            fig_ai_map.update_traces(
                marker=dict(size=6, opacity=0.78),
                hovertemplate=hover_template
            )

            fig_ai_map.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                legend_title_text=legend_title
            )

            st.plotly_chart(
                fig_ai_map,
                width="stretch",
                config={"displayModeBar": False}
            )
            st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Field map could not be generated: {e}")
