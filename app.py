import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os

# Try to import geopandas for shapefile support
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

# ---------------------------------
# Page setup
# ---------------------------------
st.set_page_config(page_title="Agronomy AI Tool", layout="wide")

st.title("Agronomy AI Decision Support Tool")
st.write(
    "Upload nitrogen prescription and yield data to compare "
    "agronomist recommendations with AI-optimized recommendations."
)

st.markdown("**Crop Type:** CWRS (Canada Western Red Spring Wheat)")

# ---------------------------------
# Helper: clean column names
# ---------------------------------
def clean_columns(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df

# ---------------------------------
# Helper: read CSV / Excel / ZIP / Shapefile
# ---------------------------------
def read_uploaded_file(uploaded_file):
    """
    Reads:
    - CSV
    - Excel
    - ZIP containing CSV
    - ZIP containing shapefile components

    Returns:
    - DataFrame if successful
    - None if not readable
    - message string describing what happened
    """
    if uploaded_file is None:
        return None, "No file uploaded."

    file_name = uploaded_file.name.lower()

    # Direct CSV
    if file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        df = clean_columns(df)
        return df, "CSV file loaded successfully."

    # Direct Excel
    if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)
        df = clean_columns(df)
        return df, "Excel file loaded successfully."

    # ZIP file
    if file_name.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, uploaded_file.name)

            # Save uploaded ZIP temporarily
            with open(zip_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Extract ZIP
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)
                extracted_files = zip_ref.namelist()

            # Look for CSV
            for inner_file in extracted_files:
                if inner_file.lower().endswith(".csv"):
                    csv_path = os.path.join(tmpdir, inner_file)
                    df = pd.read_csv(csv_path)
                    df = clean_columns(df)
                    return df, f"ZIP file loaded. Found CSV: {inner_file}"

            # Look for Excel
            for inner_file in extracted_files:
                if inner_file.lower().endswith(".xlsx") or inner_file.lower().endswith(".xls"):
                    excel_path = os.path.join(tmpdir, inner_file)
                    df = pd.read_excel(excel_path)
                    df = clean_columns(df)
                    return df, f"ZIP file loaded. Found Excel file: {inner_file}"

            # Look for shapefile
            shp_files = [f for f in extracted_files if f.lower().endswith(".shp")]

            if shp_files:
                if not GEOPANDAS_AVAILABLE:
                    return None, (
                        "ZIP contains a shapefile, but geopandas is not installed. "
                        "Run: pip3 install geopandas fiona pyogrio"
                    )

                shp_path = os.path.join(tmpdir, shp_files[0])

                try:
                    gdf = gpd.read_file(shp_path)
                    df = pd.DataFrame(gdf)

                    # Drop geometry column for cleaner table display
                    if "geometry" in df.columns:
                        df = df.drop(columns=["geometry"])

                    df = clean_columns(df)
                    return df, f"ZIP file loaded. Found shapefile: {shp_files[0]}"
                except Exception as e:
                    return None, f"Found shapefile but could not read it: {e}"

            return None, "ZIP file was read, but no CSV, Excel, or shapefile was found."

    return None, "Unsupported file type."

# ---------------------------------
# Upload section
# ---------------------------------
st.header("Upload Field Data")

col1, col2 = st.columns(2)

with col1:
    n_file = st.file_uploader(
        "Upload Nitrogen Prescription File",
        type=["csv", "xlsx", "xls", "zip"]
    )

with col2:
    y_file = st.file_uploader(
        "Upload Yield Data File",
        type=["csv", "xlsx", "xls", "zip"]
    )

# ---------------------------------
# Process files if both uploaded
# ---------------------------------
if n_file is not None and y_file is not None:
    n_df, n_message = read_uploaded_file(n_file)
    y_df, y_message = read_uploaded_file(y_file)

    st.subheader("File Processing Status")
    st.write(f"**Nitrogen file:** {n_message}")
    st.write(f"**Yield file:** {y_message}")

    if n_df is None or y_df is None:
        st.error("One or both files could not be read.")
    else:
        st.success("Both files were loaded successfully.")

        # Show previews
        st.subheader("Nitrogen Prescription Data (Preview)")
        st.dataframe(n_df.head())

        st.subheader("Yield Data (Preview)")
        st.dataframe(y_df.head())

        # ---------------------------------
        # Basic Agronomy Calculations
        # ---------------------------------
        st.header("Processed Agronomy Data")

        # Make copies
        n = n_df.copy()
        y = y_df.copy()

        # Convert area to acres
        # Assumes DISTANCE and SWATHWIDTH are in feet
        SQFT_TO_ACRES = 1 / 43560

        if "DISTANCE" in n.columns and "SWATHWIDTH" in n.columns:
            n["Area_ac"] = n["DISTANCE"] * n["SWATHWIDTH"] * SQFT_TO_ACRES

        if "DISTANCE" in y.columns and "SWATHWIDTH" in y.columns:
            y["Area_ac"] = y["DISTANCE"] * y["SWATHWIDTH"] * SQFT_TO_ACRES

        # Create yield column
        if "VRYIELDVOL" in y.columns:
            y["Yield"] = y["VRYIELDVOL"]

        # Merge datasets using simple row alignment
        min_len = min(len(n), len(y))
        merged = pd.DataFrame()

        if "Area_ac" in y.columns:
            merged["Area_ac"] = y["Area_ac"].iloc[:min_len]

        if "Yield" in y.columns:
            merged["Yield"] = y["Yield"].iloc[:min_len]

        if "AppliedRate" in n.columns:
            merged["NitrogenRate"] = n["AppliedRate"].iloc[:min_len]

        # Calculate nitrogen efficiency
        if "Yield" in merged.columns and "NitrogenRate" in merged.columns:
            merged["N_Efficiency"] = merged["Yield"] / merged["NitrogenRate"]

        # Clean bad values
        merged = merged.replace([float("inf"), -float("inf")], pd.NA)
        merged = merged.dropna()

        # Create yield classes
        merged["YieldClass"] = pd.qcut(
            merged["Yield"],
            5,
            labels=["Very Low", "Low", "Medium", "High", "Very High"]
        )

        # Group results
        summary = merged.groupby("YieldClass").agg({
            "Area_ac": "sum",
            "Yield": "mean",
            "NitrogenRate": "mean",
            "N_Efficiency": "mean"
        }).reset_index()

        # Rename for better display
        summary = summary.rename(columns={
            "YieldClass": "Yield Class",
            "Area_ac": "Area (ac)",
            "Yield": "Yield (bu/ac)",
            "NitrogenRate": "N Rate (lb/ac)",
            "N_Efficiency": "N Efficiency"
        })

        st.subheader("Agronomist Data Summary (by Yield Class)")
        st.dataframe(summary)

        # ---------------------------------
        # AI Recommendation Model
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

        # Round tables for cleaner display
        summary_display = summary.copy()
        ai_display = ai_table.copy()

        numeric_cols_summary = ["Area (ac)", "Yield (bu/ac)", "N Rate (lb/ac)", "N Efficiency"]
        for col in numeric_cols_summary:
            summary_display[col] = summary_display[col].round(2)

        numeric_cols_ai = [
            "Area (ac)",
            "Yield (bu/ac)",
            "N Rate (lb/ac)",
            "N Efficiency",
            "AI N Rate (lb/ac)",
            "N Change (lb/ac)"
        ]
        for col in numeric_cols_ai:
            ai_display[col] = ai_display[col].round(2)

        # ---------------------------------
        # AI Recommendation Summary
        # ---------------------------------
        avg_original_n = ai_table["N Rate (lb/ac)"].mean()
        avg_ai_n = ai_table["AI N Rate (lb/ac)"].mean()
        avg_n_change = ai_table["N Change (lb/ac)"].mean()

        lowest_eff_class = ai_table.loc[ai_table["N Efficiency"].idxmin(), "Yield Class"]
        highest_eff_class = ai_table.loc[ai_table["N Efficiency"].idxmax(), "Yield Class"]

        st.header("AI Recommendation Summary")

        st.info(
            f"""
            The field was divided into yield zones to compare how nitrogen performed across different areas.

            Lower-yield areas showed weaker efficiency, meaning nitrogen was not being used as effectively.
            Higher-yield areas showed stronger efficiency and better response to nitrogen.

            Based on this, the model recommends slightly reducing nitrogen in lower-performing areas
            and maintaining or slightly increasing it in stronger-performing zones.

            The weakest nitrogen performance was found in the **{lowest_eff_class}** zone,
            while the strongest performance was found in the **{highest_eff_class}** zone.

            On average, the original nitrogen rate was **{avg_original_n:.1f} lb/ac**,
            while the AI-recommended rate is **{avg_ai_n:.1f} lb/ac**.

            This represents an average change of **{avg_n_change:.1f} lb/ac** across the field.
            """
        )

        # ---------------------------------
        # Side-by-side comparison tables
        # ---------------------------------
        st.header("Comparison: Agronomist vs AI Recommendation")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Original Agronomist")
            st.dataframe(summary_display, use_container_width=True)

        with col2:
            st.subheader("AI Recommendation")
            st.dataframe(ai_display, use_container_width=True)