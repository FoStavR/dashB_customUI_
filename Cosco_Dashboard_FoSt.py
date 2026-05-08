import streamlit as st
import pandas as pd
import glob
import os
import plotly.express as px 
from PIL import Image
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import matplotlib.colors as mcolors
from folium.plugins import Fullscreen, MarkerCluster
from folium.plugins import MiniMap
import plotly.graph_objects as go
import re 

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config( page_title="COSCO Logistics Dashboard",page_icon="🌐", layout="wide")
logo = Image.open(r"Data/logo.png") 
st.title("COSCO GREECE Logistics Dashboard 📈")


# ============================== 
# DATA LOADING
# ============================== 
# -------------------------------
# Load stored coordinates CSV
# -------------------------------

def load_coordinates():
    return pd.read_csv(r"Data/region_coordinates.csv")  # Make sure CSV has lat, lon, city columns if needed
coords_df = load_coordinates()
    
def load_data(folder_path):
    excel_files = glob.glob(os.path.join(folder_path, "*.xlsx"))

    inbound_list = []
    outbound_list = []

    for file in excel_files:
        try:
            inbound_df = pd.read_excel(file, sheet_name='INBOUND')
            inbound_list.append(inbound_df)
        except:
            pass

        try:
            outbound_df = pd.read_excel(file, sheet_name='OUTBOUND')
            outbound_list.append(outbound_df)
        except:
            pass

    inbound_all = pd.concat(inbound_list, ignore_index=True) if inbound_list else pd.DataFrame()
    outbound_all = pd.concat(outbound_list, ignore_index=True) if outbound_list else pd.DataFrame()

    return inbound_all, outbound_all


st.sidebar.image(logo, width='stretch')
# ============================== 
# FILTER FUNCTION (SMART VERSION + DATE SAFE)
# ============================== 

def apply_filters(df):

    st.sidebar.header("Filters ≡")

    # ------------------------------
    # 🔄 RESET ALL FILTERS BUTTON
    # ------------------------------
    if st.sidebar.button("🔄 Reset All Filters", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("filter_"):
                if "date" in key:
                    st.session_state[key] = None
                else:
                    st.session_state[key] = []
        st.rerun()

    # ------------------------------
    # CLEAN COLUMN NAMES
    # ------------------------------
    df = df.copy()
    df.columns = df.columns.str.strip()

    # ------------------------------
    # HELPER FUNCTIONS
    # ------------------------------
    def clean_series_for_filter(s):
        return (
            s.fillna('')
            .astype(str)
            .str.strip()
            .str.upper()
            .str.replace(r'\s+', ' ', regex=True)
        )

    def clean_series_for_ui(s):
        cleaned = clean_series_for_filter(s)
        return cleaned[cleaned != '']

    def apply_single_filter(dataframe, column, selected_values):
        if selected_values:
            return dataframe[
                clean_series_for_filter(dataframe[column]).isin(selected_values)
            ]
        return dataframe

    # ------------------------------
    # INITIAL FILTERED DF
    # ------------------------------
    filtered_df = df.copy()

    # ==========================================================
    # 📅 DATE FILTER (UNCHANGED)
    # ==========================================================
    date_column = None

    if "W\H/PORT Outbound date" in df.columns:
        date_column = "W\H/PORT Outbound date"

    elif "WH Inbound date" in df.columns:
        date_column = "WH Inbound date"

    if date_column:

        filtered_df[date_column] = pd.to_datetime(
            filtered_df[date_column],
            dayfirst=True,
            errors="coerce"
        )

        today = pd.Timestamp.today().normalize()

        filtered_df = filtered_df[
            filtered_df[date_column] <= today
        ]

        valid_dates = filtered_df[date_column].dropna()

        if not valid_dates.empty:

            min_date = valid_dates.min()
            max_date = valid_dates.max()

            selected_dates = st.sidebar.date_input(
                "Date Range 📅",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="filter_date"
            )

            if selected_dates and len(selected_dates) == 2:

                start_date = pd.to_datetime(selected_dates[0])
                end_date = pd.to_datetime(selected_dates[1])

                filtered_df = filtered_df[
                    (filtered_df[date_column].isna()) |
                    (
                        (filtered_df[date_column] >= start_date) &
                        (filtered_df[date_column] <= end_date)
                    )
                ]

    # ==========================================================
    # FILTER CONFIGURATION
    # ==========================================================
    filter_config = [
        {
            "column": "PROJECT",
            "label": "Project 💾",
            "key": "filter_project"
        },
        {
            "column": "Country",
            "label": "Country 🗺️📍",
            "key": "filter_country"
        },
        {
            "column": "Destination Country",
            "label": "Destination Country 🗺️📍",
            "key": "filter_dest_country"
        },
        {
            "column": "Vendor",
            "label": "Vendor ⛓️",
            "key": "filter_vendor"
        },
        {
            "column": "FDC",
            "label": "DC 🏬🚚",
            "key": "filter_fdc"
        },
        {
            "column": "FDC/PORT",
            "label": "DC 🏬🚚",
            "key": "filter_fdc_port"
        },
        {
            "column": "Description",
            "label": "Description 📝",
            "key": "filter_description"
        }
    ]

    # ==========================================================
    # READ CURRENT SELECTIONS
    # ==========================================================
    current_selections = {}

    for config in filter_config:

        column = config["column"]
        key = config["key"]

        if column in filtered_df.columns:
            current_selections[column] = st.session_state.get(key, [])
        else:
            current_selections[column] = []

    # ==========================================================
    # BUILD DYNAMIC FILTERS
    # ==========================================================
    for config in filter_config:

        column = config["column"]
        label = config["label"]
        key = config["key"]

        if column not in filtered_df.columns:
            continue

        # -----------------------------------
        # Create temp df applying ALL OTHER filters
        # -----------------------------------
        temp_df = filtered_df.copy()

        for other_column, selected_values in current_selections.items():

            if other_column == column:
                continue

            if other_column in temp_df.columns:
                temp_df = apply_single_filter(
                    temp_df,
                    other_column,
                    selected_values
                )

        # -----------------------------------
        # Build options dynamically
        # -----------------------------------
        options = sorted(
            clean_series_for_ui(temp_df[column]).unique()
        )

        # Keep selected values visible
        options = sorted(
            set(options) | set(current_selections[column])
        )

        # -----------------------------------
        # Render multiselect
        # -----------------------------------
        selected = st.sidebar.multiselect(
            label,
            options,
            default=current_selections[column],
            key=key
        )

        current_selections[column] = selected

    # ==========================================================
    # APPLY ALL FILTERS TO FINAL DATAFRAME
    # ==========================================================
    for config in filter_config:

        column = config["column"]

        if column not in filtered_df.columns:
            continue

        selected_values = current_selections[column]

        filtered_df = apply_single_filter(
            filtered_df,
            column,
            selected_values
        )

    return filtered_df
# ==============================
# INBOUND DASHBOARD
# ==============================
def show_inbound_dashboard(df):

    st.header("Inbound Dashboard 🪟")

    if df.empty:
        st.warning("Inbound dataframe is empty.")
        return

    df.columns = df.columns.str.strip()
     
    # Convert numeric safely
    numeric_cols = ['CBM', 'KG', 'Reels', 'Boxes', 'Pallets', 'Cartons','Sku Qty.']
    for col in numeric_cols:
        
        if col in df.columns: 
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # ==============================
    # 🔹 CORE KPIs (Volume Based)
    # ==============================
    st.markdown("""
<style>
/* Card container */
div[data-testid="stMetric"] {
    border: 1px solid #e6e6e6;
    padding: 14px;
    border-radius: 12px;
    background-color: #ffffff;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}

/* Label (small text) */
div[data-testid="stMetricLabel"] {
    font-weight: 600;
    font-size: 13px;
}

/* Value (big number) */
div[data-testid="stMetricValue"] {
    font-weight: 700;
    font-size: 20px;
}
</style>
""", unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Shipments", len(df))
    col2.metric("DC", df["FDC"].nunique())
    col3.metric("Unique Countries", df["Country"].nunique())
    col4.metric("Vendors", df["Vendor"].nunique())
    col5.metric("Containers",len(df["Container Size/type"].dropna()))
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Pallets", int(df['Pallets'].sum()))
    col2.metric("Total SKU", int(df['Sku Qty.'].sum()))
    col3.metric("Total Boxes",int(df['Boxes'].sum()))
    col4.metric("Total Reels",int(df['REELS'].sum()))
    col5.metric("Total CBM", round(df['CBM'].sum(),2)) 
    # ==============================
    # 📈 MONTHLY TREND ANALYSIS
    # ==============================
    # -----------------------------------
    # Detect correct date column
    # -----------------------------------
    date_column = None

    if "WH Inbound date" in df.columns:
        date_column = "WH Inbound date"

    elif "W\\H/PORT Outbound date" in df.columns:
        date_column = "W\\H/PORT Outbound date"

    # -----------------------------------
    # Continue only if date exists
    # -----------------------------------
    if date_column:

        # Convert to datetime safely
        df[date_column] = pd.to_datetime(
            df[date_column],
            errors='coerce'
        )

        # Remove invalid dates
        trend_df = df.dropna(subset=[date_column]).copy()

        # Create month column
        trend_df["Month"] = (
            trend_df[date_column]
            .dt.to_period("M")
            .astype(str)
        )

        # -----------------------------------
        # Build Monthly Aggregation
        # -----------------------------------
        monthly_trend = (
            trend_df.groupby("Month")
            .agg({
                "CBM": "sum",
                "Pallets": "sum",
                "Boxes": "sum"
            })
            .reset_index()
        )

        # Add shipment count
        monthly_trend["Shipments"] = (
            trend_df.groupby("Month")
            .size()
            .values
        )

        # -----------------------------------
        # Optional Metrics Safety
        # -----------------------------------
        if "REELS" in trend_df.columns:
            monthly_trend["Reels"] = (
                trend_df.groupby("Month")["REELS"]
                .sum()
                .values
            )

        if "Sku Qty." in trend_df.columns:
            monthly_trend["SKU"] = (
                trend_df.groupby("Month")["Sku Qty."]
                .sum()
                .values
            )
        
        # -----------------------------------
        # Monthly Trend Table
        # -----------------------------------
        st.subheader("Monthly Summary Table 📋")

        display_table = monthly_trend.copy()
        # ---------------------------------
        # Format numeric columns
        # ---------------------------------
        for col in display_table.columns:

            if col != "CBM" and pd.api.types.is_numeric_dtype(display_table[col]):
                display_table[col] = display_table[col].astype(int)
        # ---------------------------------
        # Styled Table
        # ---------------------------------
        styled_table = (
            display_table.style

            # Hide index
            .hide(axis="index")

            # Body styling
            .set_properties(**{
                'background-color': '#f7f8fa',   # softer body tone
                'color': '#2b2b2b',
                'border-color': '#e2e6ea',
                'text-align': 'left'
            })

            # Header + table styling
            .set_table_styles([

                # Headers
                {
                    'selector': 'th',
                    'props': [
                        ('background-color', '#d2d8e1'),
                        ('color', '#111111'),          # darker header text
                        ('font-weight', 'bold'),
                        ('text-align', 'left'),
                        ('padding', '10px'),
                        ('font-size', '13px'),
                        ('border', '1px solid #c3cad4')
                    ]
                },

                # Body cells
                {
                    'selector': 'td',
                    'props': [
                        ('padding', '8px'),
                        ('font-size', '12px'),
                        ('text-align', 'left'),
                        ('border', '1px solid #e1e5ea')
                    ]
                },

                # Hide row indexes completely
                {
                    'selector': '.row_heading',
                    'props': [
                        ('display', 'none')
                    ]
                },

                # Hide top-left blank cell
                {
                    'selector': '.blank',
                    'props': [
                        ('display', 'none')
                    ]
                },

                # Table styling
                {
                    'selector': 'table',
                    'props': [
                        ('border-collapse', 'collapse'),
                        ('width', '100%'),
                        ('font-family', 'Arial, sans-serif')
                    ]
                }
            ])
        )

        # Display table
        st.write(styled_table)

      
        # -----------------------------------
        # Metric Selector
        # -----------------------------------
        st.subheader("Monthly Trend Analysis 📈")
        available_metrics = [
            "Shipments",
            "CBM",
            "Pallets",
            "Boxes"
        ]

        if "Reels" in monthly_trend.columns:
            available_metrics.append("Reels")

        if "SKU" in monthly_trend.columns:
            available_metrics.append("SKU")

        selected_metric = st.selectbox(
            "Select Monthly KPI",
            available_metrics
        )

        # -----------------------------------
        # Month-over-Month Growth
        # -----------------------------------
        monthly_trend["MoM Growth %"] = (
            monthly_trend[selected_metric]
            .pct_change() * 100
        ).round(2)
    
        # -----------------------------------
        # KPI CARDS
        # -----------------------------------
        latest_value = monthly_trend[selected_metric].iloc[-1]

        if len(monthly_trend) > 1:
            previous_value = monthly_trend[selected_metric].iloc[-2]

            growth = (
                ((latest_value - previous_value) / previous_value) * 100
                if previous_value != 0 else 0
            )
        else:
            growth = 0

        k1, k2, k3 = st.columns(3)

        k1.metric(
            f"Latest {selected_metric}",
            f"{latest_value:,.0f}"
        )

        k2.metric(
            "MoM Growth %",
            f"{growth:.2f}%"
        )

        k3.metric(
            "Total Months",
            len(monthly_trend)
        )

        # -----------------------------------
        # Main Trend Chart
        # -----------------------------------
        fig = px.line(
            monthly_trend,
            x="Month",
            y=selected_metric,
            markers=True,
            text=selected_metric
        )

        fig.update_traces(
            textposition="top center",
            line=dict(width=4)
        )

        fig.update_layout(
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0,0,0,0.05)',
            xaxis_title="Month",
            yaxis_title=selected_metric,
            hovermode="x unified",
            margin=dict(t=40, b=40, l=40, r=40)
        )

        st.plotly_chart(fig, use_container_width=True)

        

        # -----------------------------------
        # Monthly Distribution Bar Chart
        # -----------------------------------
        st.subheader(f"{selected_metric} Distribution by Month 📊")

        bar_fig = px.bar(
            monthly_trend,
            x="Month",
            y=selected_metric,
            text=selected_metric,
            color=selected_metric,
            color_continuous_scale="aggrnyl"
        )

        bar_fig.update_layout(
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0,0,0,0.05)',
            xaxis_title="Month",
            yaxis_title=selected_metric,
            coloraxis_showscale=False,
            margin=dict(t=40, b=40, l=40, r=40)
        )

        st.plotly_chart(bar_fig, use_container_width=True)

        

    else:
        st.warning("No valid date column found for trend analysis.")
    
    ch1, ch2 = st.columns(2)
    with ch1:
    # ==============================
    # 🚢 VENDOR ANALYSIS
    # ==============================  
        if 'Vendor' in df.columns:
            st.subheader("Vendor Shipment Distribution ⛓️🔎")
            
            # Count shipments per vendor
            vendor_counts = df['Vendor'].value_counts().reset_index()
            vendor_counts.columns = ['Vendor', 'Count']
            
            
            # Plot bar chart with different colors for each vendor
            fig = px.bar(
                vendor_counts,
                x='Vendor',
                y='Count',
                color='Vendor',  # assign different color per vendor
                text='Count',    # show count on top of bars
                color_discrete_sequence=px.colors.qualitative.Pastel  # optional color palette
            )
            
            # Make background transparent
            fig.update_layout(
                paper_bgcolor='rgba(255, 255, 255, 1)',
                plot_bgcolor='rgba(0,0,0,0.05)',
                xaxis_title='Vendor',
                yaxis_title='Number of Shipments',
                margin=dict(t=40, b=40, l=40, r=40),
                legend=dict(
                title=dict(text=""))
            )
            
            st.plotly_chart(fig, width="stretch")
    with ch2:
    
    # ==============================
    # 📦 GOODS TYPE
    # ==============================
        
        if 'Goods Type' in df.columns:
            st.subheader("Goods Type Breakdown ⚠️🔎")

            # Map codes to full names
            goods_map = {
                "GC": "GENERAL",
                "DG": "DANGEROUS"
            }

            df['Goods Type'] = df['Goods Type'].replace(goods_map)

            # Count occurrences
            goods_counts = df['Goods Type'].value_counts().reset_index()
            goods_counts.columns = ['Goods Type', 'Count']

            # Plot bar chart
            fig = px.bar(
                goods_counts,
                x='Goods Type',
                y='Count',
                color='Goods Type',
                text='Count',
                color_discrete_sequence=px.colors.qualitative.Safe
            )

            fig.update_layout(
                paper_bgcolor='rgba(255, 255, 255, 1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                xaxis_title='Goods Type',
                yaxis_title='Number of Projects',
                margin=dict(t=40, b=40, l=40, r=40),
                legend=dict(
                title=dict(text=""))
            )

            st.plotly_chart(fig, width="stretch")
    # ==============================
    # 🌍 COUNTRY OF ORIGIN
    # ============================== 
    cl1, cl2 = st.columns(2)
    with cl1:
        if 'Country' in df.columns:
            st.subheader("Country of Origin Distribution 🌍🔎")
            
            # Count projects per country
            country_counts = df['Country'].value_counts().reset_index()
            country_counts.columns = ['Country', 'Count']
            
            # Plot bar chart with different colors
            fig = px.bar(
                country_counts,
                x='Country',
                y='Count',
                color='Country',               # different color per country
                text='Count',                  # show count on top
                color_discrete_sequence=px.colors.qualitative.Vivid_r
            )
            
            # Transparent background
            fig.update_layout(
                paper_bgcolor='rgba(255, 255, 255, 1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                xaxis_title='Country',
                yaxis_title='Number of Projects',
                margin=dict(t=40, b=40, l=40, r=40),
                legend=dict(
                title=dict(text=""))
            )
            
            st.plotly_chart(fig, width="stretch")
    with cl2:
        if 'FDC' in df.columns:
            st.subheader("Total Shipments per DC 🏬🔎")
            
            # Count shipments per FDC
            fdc_counts = df['FDC'].value_counts().reset_index()
            fdc_counts.columns = ['FDC', 'Shipments']
            
            # Plot bar chart
            fig = px.bar(
                fdc_counts,
                x='FDC',
                y='Shipments',
                color='FDC',                   # different color per FDC
                text='Shipments',               # show count on top of bars
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            
            # Make background transparent
            fig.update_layout(
                paper_bgcolor='rgba(255, 255, 255, 1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                xaxis_title='DC',
                yaxis_title='Total Shipments',
                margin=dict(t=40, b=40, l=40, r=40),
                legend=dict(
                title=dict(text=""))
                
            )
            fig.update_xaxes(showticklabels=False)
            st.plotly_chart(fig, width="stretch")
    # ==============================
    # 🚢 TOP VESSELS (INBOUND)
    # ==============================
    if 'Vessel/Voyage' in df.columns:

        st.subheader("Top Vessels🚢🔎")

        # Clean column (optional but recommended)
        vessel_series = (
            df['Vessel/Voyage']
            .dropna()
            .astype(str)
            .str.strip()
        )

        # Count occurrences
        vessel_counts = vessel_series.value_counts().reset_index()
        vessel_counts.columns = ['Vessel', 'Shipments']

        # Toggle view
        view_mode = st.radio(
            "View as:",
            ["Chart", "Table"],
            horizontal=True,
            key="inbound_vessel_toggle"
        )

        if view_mode == "Chart":

            fig = px.bar(
                vessel_counts.head(10),
                y='Vessel',
                x='Shipments',
                orientation='h',
                text='Shipments',
                color='Shipments',
                color_continuous_scale= px.colors.qualitative.Vivid_r
            )

            fig.update_layout(
                yaxis=dict(categoryorder='total ascending'),
                margin=dict(t=40, b=40, l=40, r=40),
                paper_bgcolor='rgba(255, 255, 255, 1)',
                plot_bgcolor='rgba(0, 0, 0,0.05)',
                coloraxis_showscale=False
            )

            

            st.plotly_chart(fig, use_container_width=True)

        else:
        # ------------------------------
        # Prepare data
        # ------------------------------
            top_vessels = vessel_counts.head(10).copy()

            total_shipments = top_vessels["Shipments"].sum()

            top_vessels["Percentage"] = (
                top_vessels["Shipments"] / top_vessels["Shipments"].sum() * 100
            ).round(1)

            # normalize for bar display (0–1 scale)
            max_shipments = top_vessels["Shipments"].max()
            top_vessels["Bar"] = top_vessels["Shipments"] / max_shipments


            # ------------------------------
            # Build Plotly table
            # ------------------------------
            fig = go.Figure(data=[go.Table(

                header=dict(
                    values=[
                        "<b>Rank</b>",
                        "<b>Vessel</b>",
                        "<b>Shipments</b>",
                        "<b>% Share</b>"
                        
                    ],
                    fill_color="#1F2A44",
                    font=dict(color="white", size=13),
                    align="left"
                ),

                cells=dict(
                    values=[
                        list(range(1, len(top_vessels) + 1)),
                        top_vessels["Vessel"],
                        top_vessels["Shipments"],
                        [f"{p}%" for p in top_vessels["Percentage"]],
                    ],

                    fill_color=[
                        "white",
                        "white",
                        "white",
                        "white"
                        
                    ],

                    align=["left", "left", "left", "left"],
                    font=dict(color="black", size=12),
                    height=28
                )
            )])

            fig.update_layout(
                margin=dict(t=20, l=10, r=10, b=10)
            )

            st.plotly_chart(fig, use_container_width=True)

        if 'CUSTOMS FORMALITIES' in df.columns:
            st.subheader("Custom Formalities Breakdown 📑🔎")

            # Count values for the column
            customs_counts = df['CUSTOMS FORMALITIES'].value_counts().reset_index()
            customs_counts.columns = ['Formality', 'Count']

            # Create a Plotly bar chart
            fig = px.bar(
                customs_counts,
                x='Formality',
                y='Count',
                color='Count',
                text='Count',  # shows value on top of bars
                color_continuous_scale='Viridis',  # nice gradient
                labels={'Formality':'Custom Formality', 'Count':''},
                
            )

            fig.update_traces(textposition='outside')  # place text above bars
            fig.update_layout(height=500, xaxis_tickangle=-45,
                              legend=dict(
                title=dict(text="")),
                paper_bgcolor='rgba(255, 255, 255, 1)',
                plot_bgcolor='rgba(0,0,0,0.05)',
                ) 

            st.plotly_chart(fig, use_container_width=True)



    tg1,tg2 = st.columns(2)
    # ------------------------------
    # Pie chart for the percentages
    # ------------------------------    
    with tg1:
        if 'Description' in df.columns:
    
            st.subheader("Top Goods 🏆🔎")
    
            # Count occurrences
            goods_counts = df['Description'].value_counts().reset_index()
            goods_counts.columns = ['Description', 'Count']
    
            # Goods Bar Chart
            fig = px.bar(
                goods_counts,
                x='Description',
                y='Count',
                text='Count',
                color='Description',
                width=700,
                height=500
            )
    
            fig.update_traces(
                textposition='outside'
            )
    
            fig.update_layout(
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(0,0,0,0.05)',
                margin=dict(t=0, b=0, l=0, r=0),
                showlegend=False,
                
            )
    
            st.plotly_chart(fig, use_container_width=False)
    
    
    with tg2:
    
        # ==============================
        # 📁 PROJECT SHIPPING MODE
        # ==============================
        if 'PROJECT' in df.columns and 'Shipping MODE' in df.columns:
    
            st.subheader("Project Shipping Mode 📦🔎")
    
            # Count shipping modes
            shipping_counts = df['Shipping MODE'].value_counts().reset_index()
            shipping_counts.columns = ['Shipping MODE', 'Count']
    
            # Shipping Mode Bar Chart
            fig = px.bar(
                shipping_counts,
                x='Shipping MODE',
                y='Count',
                text='Count',
                color='Shipping MODE',
                width=700,
                height=500,
                color_discrete_sequence=px.colors.qualitative.Safe
            )
    
            fig.update_traces(
                textposition='outside'
            )
    
            fig.update_layout(
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                margin=dict(t=0, b=0, l=0, r=0),
                showlegend=False
            )
    
            st.plotly_chart(fig,use_container_width=False)
# ==============================
# ==============================    
# ==============================
# ==============================
# ==============================
# ==============================
# OUTBOUND DASHBOARD
# ==============================
def show_outbound_dashboard(df):

    st.header("Outbound Dashboard 🪟")

    if df.empty:
        st.warning("Outbound dataframe is empty.")
        return

    df.columns = df.columns.str.strip()

    # Convert numeric safely
    numeric_cols = ['CBM', 'Boxes', 'Cartons', 'Pallets']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # ==============================
    # 🔹 OUTBOUND CORE KPIs
    # ==============================
    st.markdown("""
<style>
/* Card container */
div[data-testid="stMetric"] {
    border: 1px solid #e6e6e6;
    padding: 14px;
    border-radius: 12px;
    background-color: #ffffff;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}

/* Label (small text) */
div[data-testid="stMetricLabel"] {
    font-weight: 600;
    font-size: 13px;
}

/* Value (big number) */
div[data-testid="stMetricValue"] {
    font-weight: 700;
    font-size: 20px;
}
</style>
""", unsafe_allow_html=True)
    

    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

    col1.metric("Total Shipments", len(df))

    with col2:
        # ===============================
        # 📍 Unique Regions Metric
        # ===============================
 
        if 'Region' in df.columns:

            # Extract standardized region value
            def extract_region(value):
                value = str(value).strip()
                parts = [p.strip() for p in value.split(',')]

                if len(parts) == 3: 
                    return parts[1]  # middle value
                else: 
                    return parts[0]  # single value or fallback

            # Apply transformation
            region_series = df['Region'].dropna().apply(extract_region)
 
            # Count unique regions
            unique_regions = region_series.nunique()

            # Display metric
            st.metric("Unique Regions", unique_regions)
            

    col3.metric(
        "Total Vendors",
        df['Vendor'].nunique() if 'Vendor' in df.columns else 0
    )

    col4.metric(
        "Total Containers",
        len(df['Container Size/type'].dropna()) if 'Container Size/type' in df.columns else 0
        
    )

    col5.metric(
        "Total Pallets",
        int(df['Pallets'].sum()) if 'Pallets' in df.columns else 0
    )

    col6.metric(
        "Total Boxes",
        int(df['Boxes'].sum()) if 'Boxes' in df.columns else 0
    )
    col7.metric("Total Reels",int(df['REELS'].sum()))
    col8.metric("Total CBM", round(df['CBM'].sum(),2))
    #######################################################################
    ## ==============================
    ## 🗺 MAP VISUALIZATION 
    ## ==============================
    st.subheader("Outbound Global Shipment Map 🌍🔎")
    if all(col in df.columns for col in ['Region', 'Destination Country', 'PROJECT']):


        # ---------------------------------
        # Aggregate shipments per region + project
        # ---------------------------------
            grouped = (
                df.groupby(['Region', 'Destination Country', 'PROJECT'])
                .size()
                .reset_index(name='Project_Shipments')
            )
 
            region_summary = (
                grouped.groupby(['Region', 'Destination Country'])
                .apply(lambda g: pd.Series({
                    'Shipments': g['Project_Shipments'].sum(),
                    'Project_Shipments_Combined': "<br>".join(
                    f"{proj} ({cnt})"
                    for proj, cnt in zip(g['PROJECT'], g['Project_Shipments'])
                )
                }))
                .reset_index()
            )

            # ---------------------------------
            # Merge coordinates
            # ---------------------------------
            region_summary = region_summary.merge(
                coords_df,
                on=['Region', 'Destination Country'],
                how='left'
            )

            region_summary = region_summary.dropna(subset=['lat', 'lon'])

            # ---------------------------------
            # Country Filter
            # ---------------------------------
            all_countries = sorted(region_summary['Destination Country'].unique())
            selected_countries = st.multiselect(
                "Select Countries:",
                options=all_countries,
                default=all_countries
            )

            if selected_countries:
                region_summary = region_summary[
                    region_summary['Destination Country'].isin(selected_countries)
                ]

            if region_summary.empty:
                st.info("No data available for selected filters.")
            else:

                # ---------------------------------
                # Create Dark Mode Map
                # ---------------------------------
                mean_lat = region_summary['lat'].mean()
                mean_lon = region_summary['lon'].mean()

                m = folium.Map(
                    location=[mean_lat, mean_lon],
                    zoom_start=3,
                    tiles="OpenStreetMap",
                    control_scale=False
                    
                )
                # Marker cluster
                marker_cluster = MarkerCluster().add_to(m)

                # Folium supported colors
                folium_colors = [
                    'red', 'blue', 'green', 'purple', 'orange',
                    'darkred', 'lightred', 'beige', 'darkblue',
                    'darkgreen', 'cadetblue', 'darkpurple',
                    'pink', 'lightblue', 'lightgreen',
                    'gray', 'black', 'lightgray'
                ]

                unique_countries = region_summary['Destination Country'].unique()
                country_color_map = {
                    country: folium_colors[i % len(folium_colors)]
                    for i, country in enumerate(unique_countries)
                }

                # ---------------------------------
                # Add Region Markers
                # ---------------------------------
                for _, row in region_summary.iterrows():

                    color_name = country_color_map[row['Destination Country']]

                    popup_html = f"""
                        <div style="
                            font-family: Arial, sans-serif;
                            width: 260px;
                            background-color: #ffffff;
                            color: #333333;
                            border-radius: 10px;
                            padding: 12px;
                        ">

                            <div style="font-size:16px; font-weight:bold; margin-bottom:4px;">
                                🌍 {row['Region']}
                            </div>

                            <div style="font-size:13px; color:#666666; margin-bottom:8px;">
                                {row['Destination Country']}
                            </div>

                            <div style="
                                background-color:#f5f5f5;
                                padding:8px;
                                border-radius:8px;
                                margin-bottom:10px;
                                text-align:center;
                            ">
                                📦 <span style="font-size:18px; font-weight:bold;">
                                    {row['Shipments']}
                                </span><br>
                                <span style="font-size:11px; color:#777777;">
                                    Total Shipments
                                </span>
                            </div>

                            <div style="font-size:12px; margin-bottom:6px;">
                                📁 <b>Projects (Shipments per project)</b>
                            </div>

                            <div style="
                                font-size:12px;
                                line-height:1.5;
                                background-color:#f5f5f5;
                                padding:8px;
                                border-radius:8px;
                                max-height:100px;
                                overflow-y:auto;
                            ">
                                {row['Project_Shipments_Combined']}
                            </div>

                        </div>
                        """

                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_html, max_width=400),
                        icon=folium.Icon(color=color_name, icon='info-sign')
                    ).add_to(marker_cluster)

                # ---------------------------------
                # 🥚 Easter Egg Marker (Cosco Greece)
                # ---------------------------------
                folium.Marker(
                    location=[37.93672505227739, 23.638263063003365],
                    popup=folium.Popup(
                        "❤️ Hello from Cosco Greece, Piraeus!",
                        max_width=300
                    ),
                    tooltip="Click me 👀",
                    icon=folium.Icon(color="red", icon="heart", prefix="fa")
                ).add_to(m)

                # ---------------------------------
                # Render Map
                # ---------------------------------
                # Fullscreen button
                Fullscreen(
                    position="bottomleft",
                    title="Expand Map",
                    title_cancel="Exit Fullscreen",
                    force_separate_button=True
                ).add_to(m)
                st_folium(m, use_container_width=True, height=400) 
    # ==============================
    # 📈 MONTHLY TREND ANALYSIS
    # ==============================
    # -----------------------------------
    # Detect correct date column
    # -----------------------------------
    date_column = None

    if "WH Inbound date" in df.columns:
        date_column = "WH Inbound date"

    elif "W\\H/PORT Outbound date" in df.columns:
        date_column = "W\\H/PORT Outbound date"

    # -----------------------------------
    # Continue only if date exists
    # -----------------------------------
    if date_column:

        # Convert to datetime safely
        df[date_column] = pd.to_datetime(
            df[date_column],
            errors='coerce'
        )

        # Remove invalid dates
        trend_df = df.dropna(subset=[date_column]).copy()

        # Create month column
        trend_df["Month"] = (
            trend_df[date_column]
            .dt.to_period("M")
            .astype(str)
        )

        # -----------------------------------
        # Build Monthly Aggregation
        # -----------------------------------
        monthly_trend = (
            trend_df.groupby("Month")
            .agg({
                "CBM": "sum",
                "Pallets": "sum",
                "Boxes": "sum"
            })
            .reset_index()
        )

        # Add shipment count
        monthly_trend["Shipments"] = (
            trend_df.groupby("Month")
            .size()
            .values
        )

        # -----------------------------------
        # Optional Metrics Safety
        # -----------------------------------
        if "REELS" in trend_df.columns:
            monthly_trend["Reels"] = (
                trend_df.groupby("Month")["REELS"]
                .sum()
                .values
            )

        if "Sku Qty." in trend_df.columns:
            monthly_trend["SKU"] = (
                trend_df.groupby("Month")["Sku Qty."]
                .sum()
                .values
            )
        
        # -----------------------------------
        # Monthly Trend Table
        # -----------------------------------
        st.subheader("Monthly Summary Table 📋")

        display_table = monthly_trend.copy()
        # ---------------------------------
        # Format numeric columns
        # ---------------------------------
        for col in display_table.columns:

            if col != "CBM" and pd.api.types.is_numeric_dtype(display_table[col]):
                display_table[col] = display_table[col].astype(int)
        # ---------------------------------
        # Styled Table
        # ---------------------------------
        styled_table = (
            display_table.style

            # Hide index
            .hide(axis="index")

            # Body styling
            .set_properties(**{
                'background-color': '#f7f8fa',   # softer body tone
                'color': '#2b2b2b',
                'border-color': '#e2e6ea',
                'text-align': 'left'
            })

            # Header + table styling
            .set_table_styles([

                # Headers
                {
                    'selector': 'th',
                    'props': [
                        ('background-color', '#d2d8e1'),
                        ('color', '#111111'),          # darker header text
                        ('font-weight', 'bold'),
                        ('text-align', 'left'),
                        ('padding', '10px'),
                        ('font-size', '13px'),
                        ('border', '1px solid #c3cad4')
                    ]
                },

                # Body cells
                {
                    'selector': 'td',
                    'props': [
                        ('padding', '8px'),
                        ('font-size', '12px'),
                        ('text-align', 'left'),
                        ('border', '1px solid #e1e5ea')
                    ]
                },

                # Hide row indexes completely
                {
                    'selector': '.row_heading',
                    'props': [
                        ('display', 'none')
                    ]
                },

                # Hide top-left blank cell
                {
                    'selector': '.blank',
                    'props': [
                        ('display', 'none')
                    ]
                },

                # Table styling
                {
                    'selector': 'table',
                    'props': [
                        ('border-collapse', 'collapse'),
                        ('width', '100%'),
                        ('font-family', 'Arial, sans-serif')
                    ]
                }
            ])
        )

        # Display table
        st.write(styled_table)

      
        # -----------------------------------
        # Metric Selector
        # -----------------------------------
        st.subheader("Monthly Trend Analysis 📈")
        available_metrics = [
            "Shipments",
            "CBM",
            "Pallets",
            "Boxes"
        ]

        if "Reels" in monthly_trend.columns:
            available_metrics.append("Reels")

        if "SKU" in monthly_trend.columns:
            available_metrics.append("SKU")

        selected_metric = st.selectbox(
            "Select Monthly KPI",
            available_metrics
        )

        # -----------------------------------
        # Month-over-Month Growth
        # -----------------------------------
        monthly_trend["MoM Growth %"] = (
            monthly_trend[selected_metric]
            .pct_change() * 100
        ).round(2)
    
        # -----------------------------------
        # KPI CARDS
        # -----------------------------------
        latest_value = monthly_trend[selected_metric].iloc[-1]

        if len(monthly_trend) > 1:
            previous_value = monthly_trend[selected_metric].iloc[-2]

            growth = (
                ((latest_value - previous_value) / previous_value) * 100
                if previous_value != 0 else 0
            )
        else:
            growth = 0

        k1, k2, k3 = st.columns(3)

        k1.metric(
            f"Latest {selected_metric}",
            f"{latest_value:,.0f}"
        )

        k2.metric(
            "MoM Growth %",
            f"{growth:.2f}%"
        )

        k3.metric(
            "Total Months",
            len(monthly_trend)
        )

        # -----------------------------------
        # Main Trend Chart
        # -----------------------------------
        fig = px.line(
            monthly_trend,
            x="Month",
            y=selected_metric,
            markers=True,
            text=selected_metric
        )

        fig.update_traces(
            textposition="top center",
            line=dict(width=4)
        )

        fig.update_layout(
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0,0,0,0.05)',
            xaxis_title="Month",
            yaxis_title=selected_metric,
            hovermode="x unified",
            margin=dict(t=40, b=40, l=40, r=40)
        )

        st.plotly_chart(fig, use_container_width=True)

        

        # -----------------------------------
        # Monthly Distribution Bar Chart
        # -----------------------------------
        st.subheader(f"{selected_metric} Distribution by Month 📊")

        bar_fig = px.bar(
            monthly_trend,
            x="Month",
            y=selected_metric,
            text=selected_metric,
            color=selected_metric,
            color_continuous_scale="aggrnyl"
        )

        bar_fig.update_layout(
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0,0,0,0.05)',
            xaxis_title="Month",
            yaxis_title=selected_metric,
            coloraxis_showscale=False,
            margin=dict(t=40, b=40, l=40, r=40)
        )

        st.plotly_chart(bar_fig, use_container_width=True)

        

    else:
        st.warning("No valid date column found for trend analysis.")    
    mpc1,mpc2= st.columns(2)
    with mpc1:
        # ==============================
        # 📝 DESCRIPTION
        # ==============================

        if 'Description' in df.columns:

            st.subheader("Top Descriptions🏆🔎")

                # Aggregate
            desc_counts = (
                    df['Description']
                    .dropna()
                    .value_counts()
                    .head(10)
                    .reset_index()
                )
            desc_counts.columns = ['Description', 'Shipments']


            fig = px.bar(
                        desc_counts,
                        x="Description", 
                        y="Shipments",
                        orientation="v",
                        text="Shipments",
                        color="Description",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )

            fig.update_layout(
                        yaxis=dict(categoryorder="total ascending"),
                        margin=dict(t=40, b=40, l=40, r=40),
                        plot_bgcolor="rgba(0,0,0,0.05)",
                        paper_bgcolor="rgba(255,255,255,1)",
                        coloraxis_showscale=False,
                        legend=dict(
                    title=dict(text=""))
                    )

            

            st.plotly_chart(fig, use_container_width=True)
    with mpc2:
            # ===============================
            # 🌍 Top Destination Countries
            # ===============================

        if 'Destination Country' in df.columns:

            st.subheader("Top Destination Countries 🏆🗺️🔎")

            country_clean = (
                df['Destination Country']
                .dropna()
                .astype(str)
                .str.strip()                  # remove leading/trailing spaces
                .str.upper()                  # normalize case
                .str.replace(r'\s+', ' ', regex=True)  # collapse multiple spaces
            )

            country_counts = (
                country_clean
                .value_counts()
                .head(10)
                .reset_index()
            )

            country_counts.columns = ['Country', 'Shipments']

            fig = px.bar(
                country_counts,
                y='Country',
                x='Shipments',
                orientation='h',
                text='Shipments',
                color='Country',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )

            fig.update_layout(
                paper_bgcolor='rgba(255, 255, 255, 1)',
               plot_bgcolor='rgba(0, 0, 0, 0.05)',
                yaxis=dict(categoryorder='total ascending'),
                margin=dict(t=30, b=30, l=30, r=30),
                showlegend=True,legend=dict(
                    title=dict(text="")),
                legend_bgcolor='rgba(0,0,0,0)'
            )

            

            st.plotly_chart(fig, use_container_width=True)



    
    # ==============================
    # 🗺 TOP REGIONS
    # ==============================

    if 'Region' in df.columns or 'Destination Country' in df.columns:

        dest1, dest2 = st.columns(2)
        
    # ------------------------------
    # Top Greek Regions
    # ------------------------------
    with dest1:
        if 'Destination Country' in df.columns and 'Region' in df.columns:
            st.subheader("Top Regions in Greece 🏆🇬🇷🔎")
            df_greece = df[df['Destination Country'].str.strip().str.upper() == "GREECE"].copy()

            if not df_greece.empty:
                # Extract middle value safely
                df_greece['Middle Region'] = df_greece['Region'].apply(
                    lambda x: str(x).split(',')[1].strip()
                    if pd.notna(x) and ',' in str(x) and len(str(x).split(',')) > 2
                    else (str(x).strip() if pd.notna(x) else None)
                )

                region_counts = (
                    df_greece['Middle Region']
                    .dropna()
                    .value_counts()
                    .head(10)
                    .reset_index()
                )
                region_counts.columns = ['Region', 'Shipments']

                fig = px.bar(
                        region_counts,
                        x='Region',
                        y='Shipments',
                        text='Shipments',
                        color='Region',
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )

                fig.update_layout(
                        paper_bgcolor='rgba(255,255,255,1)',
                        plot_bgcolor='rgba(0, 0, 0, 0.05)',
                        xaxis=dict(tickangle=-45),  # tilt labels
                        margin=dict(t=40, b=40, l=40, r=40),
                        legend=dict(
                    title=dict(text="")),legend_bgcolor='rgba(0,0,0,0)'
                    )

                

                st.plotly_chart(fig, use_container_width=True)

                

            else:
                st.info("No Greek regions found in the filtered data.")
    with dest2:
        if 'Vessel/Voyage' in df.columns:

            st.subheader("Top Vessels 🚢🔎")

            # Clean column (optional but recommended)
            vessel_series = (
                df['Vessel/Voyage']
                .dropna()
                .astype(str)
                .str.strip()
            )

            # Count occurrences
            vessel_counts = vessel_series.value_counts().reset_index()
            vessel_counts.columns = ['Vessel', 'Shipments']

           

            fig = px.bar(
                    vessel_counts.head(10),
                    y='Vessel',
                    x='Shipments',
                    orientation='h',
                    text='Shipments',
                    color='Shipments',
                    color_continuous_scale='oryel'
                )

            fig.update_layout(
                    yaxis=dict(categoryorder='total ascending'),
                    margin=dict(t=30, b=30, l=30, r=30),
                    paper_bgcolor='rgba(255,255,255,1)', 
                    plot_bgcolor='rgba(0, 0, 0, 0.05)',
                    coloraxis_showscale=False,
                    legend_bgcolor='rgba(0,0,0,0)'
                )

            

            st.plotly_chart(fig, use_container_width=True)

            
       
    
    col1,col2 = st.columns(2)
    with col1:
        # ==============================
        # 📑 CUSTOM FORMALITIES
        # ==============================
        if 'CUSTOMS FORMALITIES' in df.columns:
            st.subheader("Custom Formalities📑🔎") 

            customs_counts = df['CUSTOMS FORMALITIES'].value_counts().reset_index()
            customs_counts.columns = ['Formality', 'Count']

            fig = px.bar(
                customs_counts,
                x='Formality',
                y='Count',
                text='Count',
                color='Count',
                color_continuous_scale='Viridis'
            )

            fig.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                xaxis_title="",
                yaxis_title="",legend_bgcolor='rgba(0,0,0,0)'
            )

           

            st.plotly_chart(fig, use_container_width=True)
    with col1:
        # ==============================
        # 📦 CONTAINER SIZE
        # ============================== 
        if 'Container Size/type' in df.columns:
            st.subheader("Container Size 🏗️🔎")

            count_20 = df['Container Size/type'].astype(str).str.count(r"20")
            count_40 = df['Container Size/type'].astype(str).str.count(r"40") 

            container_counts = pd.DataFrame({ 
                "Size": ["20'", "40'"], 
                "Count": [count_20.sum(), count_40.sum()]
            })
 
            fig = px.bar(
                container_counts,
                x='Size',
                y='Count',
                text='Count',
                color='Size'
            )

            fig.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                xaxis_title="",
                yaxis_title="",
                legend=dict(
                title=dict(text="")),
                legend_bgcolor='rgba(0,0,0,0)',
            )

            

            st.plotly_chart(fig, use_container_width=True)
    with col2:
        # ==============================
        # 📦 GOODS TYPE
        # ==============================
        if 'Goods Type' in df.columns:
            st.subheader("Goods Type ⚠️🔎")

            goods_counts = df['Goods Type'].value_counts().reset_index()
            goods_counts.columns = ['Goods Type', 'Count']

            fig = px.bar(
                goods_counts,
                x='Goods Type',
                y='Count',
                text='Count',
                color='Goods Type',
                color_discrete_sequence=px.colors.qualitative.Safe
            )

            fig.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(0,0,0,0.1)',
                xaxis_title="",
                yaxis_title="",
                legend=dict(
                title=dict(text="")),
                legend_bgcolor='rgba(0,0,0,0)'
            )

            fig.update_traces(textposition='outside')

            st.plotly_chart(fig, use_container_width=True)
    with col2:
        # ==============================
        # 🚚 SHIPPING MODE
        # ==============================
        if 'Shipping MODE' in df.columns:
            st.subheader("Shipping Mode 🏬🔎")

            shipping_mode = (
                df['Shipping MODE']
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
            )

            shipping_counts = shipping_mode.value_counts().reset_index()
            shipping_counts.columns = ['Mode', 'Count']

            fig = px.bar(
                shipping_counts,
                x='Mode',
                y='Count',
                text='Count',
                color='Mode',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )

            fig.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(0, 0, 0, 0.05)',
                xaxis_title="",
                yaxis_title="",
                legend=dict(
                title=dict(text="")),
                legend_bgcolor='rgba(0,0,0,0)',
                
            )

            

            st.plotly_chart(fig, use_container_width=True)
# ==============================
# ==============================    
# ==============================
# ==============================
# ==============================
# ==============================
# OVERVIEW DASHBOARD
# ==============================   
def show_overview_dashboard(inbound_df, outbound_df):

    st.header("Overview Analysis Dashboard 📊")

    # -----------------------------------
    # Clean column names
    # -----------------------------------
    inbound_df.columns = inbound_df.columns.str.strip()
    outbound_df.columns = outbound_df.columns.str.strip()

    # -----------------------------------
    # Safe numeric conversion
    # -----------------------------------
    numeric_cols = [
        'CBM',
        'Boxes',
        'Pallets',
        'REELS',
        'Sku Qty.'
    ]

    for col in numeric_cols:

        if col in inbound_df.columns:
            inbound_df[col] = pd.to_numeric(
                inbound_df[col],
                errors='coerce'
            ).fillna(0)

        if col in outbound_df.columns:
            outbound_df[col] = pd.to_numeric(
                outbound_df[col],
                errors='coerce'
            ).fillna(0)

    # =====================================
    # KPI CALCULATIONS
    # =====================================
    inbound_shipments = len(inbound_df)
    outbound_shipments = len(outbound_df)

    total_shipments = (
        inbound_shipments +
        outbound_shipments
    )

    inbound_cbm = inbound_df['CBM'].sum()
    outbound_cbm = outbound_df['CBM'].sum()

    total_cbm = inbound_cbm + outbound_cbm

    inbound_pallets = inbound_df['Pallets'].sum()
    outbound_pallets = outbound_df['Pallets'].sum()

    
 # ==============================
    # 🔹 CORE KPIs (Volume Based)
    # ==============================
    st.markdown("""
<style>
/* Card container */
div[data-testid="stMetric"] {
    border: 1px solid #e6e6e6;
    padding: 14px;
    border-radius: 12px;
    background-color: #ffffff;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}

/* Label (small text) */
div[data-testid="stMetricLabel"] {
    font-weight: 600;
    font-size: 13px;
}

/* Value (big number) */
div[data-testid="stMetricValue"] {
    font-weight: 700;
    font-size: 20px;
}
</style>
""", unsafe_allow_html=True)

    # =====================================
    # EXECUTIVE KPI CARDS
    # =====================================
    inbound_monthly = build_monthly(
    inbound_df,
        "WH Inbound date",
        "Inbound"
    )

    outbound_monthly = build_monthly(
        outbound_df,
        "W\\H/PORT Outbound date",
        "Outbound"
    )
    overview_monthly = pd.merge(
    inbound_monthly,
    outbound_monthly,
    on="Month",
    how="outer"
    ) 

    overview_monthly = (
        overview_monthly
        .sort_values("Month")
        .fillna(0)
    )
    overview_monthly["Total_Shipments"] = (
    overview_monthly["Inbound_Shipments"] +
    overview_monthly["Outbound_Shipments"]
)

    peak_idx = overview_monthly["Total_Shipments"].idxmax()

    peak_month = overview_monthly.loc[peak_idx, "Month"]
    peak_value = overview_monthly.loc[peak_idx, "Total_Shipments"]
    overview_monthly["Total_CBM"] = (
    overview_monthly["Inbound_CBM"] +
    overview_monthly["Outbound_CBM"]
)

    avg_monthly_flow = (
        overview_monthly["Total_CBM"]
        .mean()
    )
    total_cbm = (
    overview_monthly["Inbound_CBM"].sum() +
    overview_monthly["Outbound_CBM"].sum()
)

    

    flow_balance_ratio = (
    inbound_shipments / outbound_shipments
    if outbound_shipments != 0 else 0
)
    
    st.subheader("Operational Overview KPIs 🚀")
    col1, col2, col3 = st.columns(3) 
    col1.metric( "Total Shipments", f"{total_shipments:,}" ) 
    col2.metric( "Inbound Shipments", f"{inbound_shipments:,}" ) 
    col3.metric( "Outbound Shipments", f"{outbound_shipments:,}" ) 
    col4, col5, col6 = st.columns(3) 
    col4.metric( "Total CBM", f"{total_cbm:,.2f}" ) 
    col5.metric( "Inbound CBM", f"{inbound_cbm:,.2f}" ) 
    col6.metric( "Outbound CBM", f"{outbound_cbm:,.2f}" )
    k1, k2, k3 = st.columns(3)

    k1.metric(
        "Peak Operational Month",
        peak_month,
        f"{int(peak_value)} shipments that month"
    )

    k2.metric(
        "Avg Monthly Flow","Total CBM / Month",
        f"{avg_monthly_flow:,.1f} CBM"
    )

    k3.metric(
        "Flow Balance Ratio ⚖️","Total Inbound / Outbound Shipments",
        f"{flow_balance_ratio:,.2f}"
    )
    
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Total Shipment Distribution 📦")
        shipments_df = pd.DataFrame({
    "Type": ["Inbound", "Outbound"],
    "Value": [inbound_shipments, outbound_shipments]
    })

        fig_shipments = px.pie(
            shipments_df,
            names="Type",
            values="Value",
            hole=0.3,
            color="Type",
            color_discrete_map={
                "Inbound": "#1f77b4",
                "Outbound": "#ff7f0e"
            }
        )

        fig_shipments.update_traces(
            textinfo="percent+label"
        )

        fig_shipments.update_layout(
            annotations=[
                dict(
                    text=f"{total_shipments:,}<br>Total",
                    x=0.5,
                    y=0.5,
                    font_size=18,
                    showarrow=False
                )
            ],
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0, 0, 0, 0.05)',
            margin=dict(t=40, b=20, l=20, r=20)
        )

        st.plotly_chart(fig_shipments, use_container_width=True)

    with g2:
        
        stacked_df = overview_monthly[
        [
            "Month",
            "Inbound_Shipments",
            "Outbound_Shipments"
        ]
    ].copy()

        stacked_df = stacked_df.melt(
            id_vars="Month",
            value_vars=[
                "Inbound_Shipments",
                "Outbound_Shipments"
            ],
            var_name="Flow",
            value_name="Shipments"
        )
        stacked_df["Flow"] = stacked_df["Flow"].replace({
            "Inbound_Shipments": "Inbound",
            "Outbound_Shipments": "Outbound"
        })
        st.subheader("Inbound vs Outbound Monthly Flow 📦")

        fig = px.bar(
            stacked_df,
            x="Month",
            y="Shipments",
            color="Flow",
            barmode="stack",
            text="Shipments",
            color_discrete_map={
                "Inbound": "#1f77b4",
                "Outbound": "#ff7f0e"
            }
        )

        fig.update_layout(
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0,0,0,0.05)',
            xaxis_title="Month",
            yaxis_title="Shipments",
            hovermode="x unified",
            margin=dict(t=40, b=40, l=40, r=40),
            legend_title=""
        )

        st.plotly_chart(fig, use_container_width=True)
    
  
  
   
   
    st.subheader("Global Operational Presence 🌍")

    

        # ==========================================================
        # MINIMAL LEGEND
        # ==========================================================

    st.markdown("""
        <div style="
        display:flex;
        gap:18px;
        align-items:center;
        font-size:13px;
        margin-bottom:10px;
        color:#555;
        flex-wrap:wrap;
        ">

        <div style="display:flex;align-items:center;gap:6px;">
        <div style="
        width:12px;
        height:12px;
        background:#1f77b4;
        border-radius:2px;
        "></div>
        <span>Inbound</span>
        </div>

        <div style="display:flex;align-items:center;gap:6px;">
        <div style="
        width:12px;
        height:12px;
        background:#ff7f0e;
        border-radius:2px;
        "></div>
        <span>Outbound</span>
        </div>

        <div style="display:flex;align-items:center;gap:6px;">
        <div style="
        width:12px;
        height:12px;
        background:#9467bd;
        border-radius:2px;
        "></div>
        <span>Both</span>
        </div>

        <div style="display:flex;align-items:center;gap:6px;">
        <div style="
        width:12px;
        height:12px;
        background:#d3d3d3;
        border-radius:2px;
        border:1px solid #c0c0c0;
        "></div>
        <span>No Activity</span>
        </div>

        </div>
        """, unsafe_allow_html=True)


        # ==========================================================
        # CLEAN INBOUND COUNTRIES
        # ==========================================================

    inbound_countries = (
            inbound_df["Country"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .unique()
        )

        # ==========================================================
        # CLEAN OUTBOUND COUNTRIES
        # ==========================================================

    outbound_countries = (
            outbound_df["Destination Country"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .unique()
        )

        # ==========================================================
        # BUILD COUNTRY STATUS
        # ==========================================================

    all_operational_countries = set(inbound_countries).union(
            set(outbound_countries)
        )

    country_status = []

    for country in all_operational_countries:

            in_inbound = country in inbound_countries
            in_outbound = country in outbound_countries

            if in_inbound and in_outbound:
                status = "BOTH"

            elif in_inbound:
                status = "INBOUND"

            elif in_outbound:
                status = "OUTBOUND"

            else:
                status = "NONE"

            country_status.append({
                "Country": country,
                "Status": status
            })

    country_status_df = pd.DataFrame(country_status)

        # ==========================================================
        # COLOR MAPPING
        # ==========================================================

    color_map = {
            "INBOUND": "#1f77b4",
            "OUTBOUND": "#ff7f0e",
            "BOTH": "#9467bd",
            "NONE": "#d3d3d3"
        }

        # ==========================================================
        # CREATE FIGURE
        # ==========================================================

    fig = go.Figure()

        # ==========================================================
        # ADD CHOROPLETH LAYERS
        # ==========================================================

    for status, color in color_map.items():

            temp_df = country_status_df[
                country_status_df["Status"] == status
            ]

            if temp_df.empty:
                continue

            fig.add_trace(go.Choropleth(

                locations=temp_df["Country"],

                locationmode="country names",

                z=[1] * len(temp_df),

                name=status,

                hovertemplate=
                    "<b>%{location}</b><br>" +
                    f"Status: {status}<extra></extra>",

                showscale=False,

                colorscale=[
                    [0, color],
                    [1, color]
                ],

                marker_line_color="white",
                marker_line_width=0.5
            ))

        # ==========================================================
        # 📍 COSCO PIRAEUS MARKER ONLY
        # ==========================================================

    fig.add_trace(go.Scattergeo(

            lon=[23.638263063003365],

            lat=[37.93672505227739],

            text=["COSCO Greece - Piraeus"],

            mode="markers+text",

            textposition="top center",

            marker=dict(
                size=12,
                color="red",
                line=dict(
                    width=1,
                    color="black"
                )
            ),

            name="COSCO Piraeus",

            hovertemplate=
                "<b>%{text}</b><extra></extra>"
        ))

        # ==========================================================
        # LAYOUT
        # ==========================================================

    fig.update_layout(

            geo=dict(

                showframe=False,

                showcoastlines=True,

                coastlinecolor="LightGray",

                projection_type="natural earth",

                bgcolor="rgba(0,0,0,0)",

                showland=True,
    
                landcolor="#efefef",
                projection_scale=1.2 
            ),

            paper_bgcolor='rgba(255,255,255,1)',

            plot_bgcolor='rgba(0, 0, 0, 0.05)',

            height=600,
            
            margin=dict(
                t=40,
                b=20,
                l=20,
                r=20
            ),

            showlegend=False
        )

        # ==========================================================
        # DISPLAY MAP
        # ==========================================================

    st.plotly_chart(
            fig,
            use_container_width=True
        )

    
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Total CBM Distribution 📦")

        cbm_df = pd.DataFrame({
            "Type": ["Inbound", "Outbound"],
            "Value": [inbound_cbm, outbound_cbm]
        })

        fig_cbm = px.pie(
            cbm_df,
            names="Type",
            values="Value",
            hole=0.3,
            color="Type",
            color_discrete_map={
                "Inbound": "#2ca02c",
                "Outbound": "#d62728"
            }
        )

        fig_cbm.update_traces(
            textinfo="percent+label"
        )

        fig_cbm.update_layout(
            annotations=[
                dict(
                    text=f"{total_cbm:,.1f}<br>CBM",
                    x=0.5,
                    y=0.5,
                    font_size=18,
                    showarrow=False
                )
            ],
            paper_bgcolor='rgba(255,255,255,1)',
            plot_bgcolor='rgba(0, 0, 0, 0.05)',
            margin=dict(t=40, b=20, l=20, r=20)
        )

        st.plotly_chart(fig_cbm, use_container_width=True)
    with col2:
        st.subheader("Monthly CBM Comparison 📐")

        st.plotly_chart(
            comparison_chart(
                overview_monthly,
                "Inbound_CBM",
                "Outbound_CBM",
                "Inbound vs Outbound CBM",
                "CBM",
                "#2ca02c",   # green
                "#d62728"    # light green
            ),
            use_container_width=True
        )
     
    
def build_monthly(df, date_col, label):


    temp = df.copy()

    # same logic your dashboards already use
    temp[date_col] = pd.to_datetime(
        temp[date_col],
        errors="coerce"
    )

    temp = temp.dropna(subset=[date_col])
    temp["Containers"] = temp["Container Size/type"].notna().astype(int)
    # remove future dates
    today = pd.Timestamp.today().normalize()

    temp = temp[
        temp[date_col] <= today
    ]

    # create month
    temp["Month"] = (
        temp[date_col]
        .dt.to_period("M")
        .astype(str)
    )

    # aggregate
    monthly = (
        temp.groupby("Month")
        .agg({
            "CBM": "sum",
            "Pallets": "sum",
            "Boxes": "sum",
            "Containers": "sum"
        })
        .reset_index()
    )

    monthly[f"{label}_Shipments"] = (
        temp.groupby("Month")
        .size()
        .values
    )

    # rename metrics
    monthly = monthly.rename(columns={
        "CBM": f"{label}_CBM",
        "Pallets": f"{label}_Pallets",
        "Boxes": f"{label}_Boxes",
        "Containers": f"{label}_Containers"
    })

    return monthly 
def comparison_chart(
    df,
    inbound_col,
    outbound_col,
    title,
    y_title,
    inbound_color,
    outbound_color
):

    fig = go.Figure()

    # Inbound
    fig.add_trace(go.Bar(
        x=df["Month"],
        y=df[inbound_col],
        name="Inbound",
        marker_color=inbound_color
    ))

    # Outbound
    fig.add_trace(go.Bar(
        x=df["Month"],
        y=df[outbound_col],
        name="Outbound",
        marker_color=outbound_color
    )) 

    fig.update_layout(
        title=title,
        barmode="group",
        xaxis_title="Month",
        yaxis_title=y_title,
        paper_bgcolor='rgba(255,255,255,1)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        margin=dict(t=40, b=40, l=40, r=40),
        hovermode="x unified",
        legend=dict(
            title=""
        )
    )

    return fig

# ==============================
# MAIN APP FLOW
# ==============================

folder_path = "Data/"  # Update this path to your folder containing Excel files
inbound_df, outbound_df = load_data(folder_path)

# -----------------------------
# Select Data View in Sidebar
# -----------------------------
st.sidebar.header("Data Selection 📊")
data_choice = st.sidebar.radio(
    "Display: ",
    ["Overview 📊","Inbound ◀️", "Outbound ▶️"]
)

# Apply filters based on selection
if data_choice == "Inbound ◀️":
    if inbound_df.empty:
        st.warning("No Inbound data available.")
    else:
        filtered = apply_filters(inbound_df)
        show_inbound_dashboard(filtered)

elif data_choice == "Outbound ▶️":
    if outbound_df.empty:
        st.warning("No Outbound data available.")
    else:
        filtered = apply_filters(outbound_df)
        show_outbound_dashboard(filtered)
elif data_choice == "Overview 📊":
    if inbound_df.empty and outbound_df.empty:
        st.warning("No data available for overview.")
    else:
        show_overview_dashboard(
            inbound_df,
            outbound_df)
st.sidebar.markdown(
    "<p style='font-size:12px;color:gray'>Use the filters above to refine the dataset. "
    "The dashboard updates automatically based on your selection.</p>",
    unsafe_allow_html=True
)
