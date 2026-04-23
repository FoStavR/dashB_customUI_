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
from folium.plugins import Fullscreen, MarkerCluster
from folium.plugins import MiniMap
import plotly.graph_objects as go

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config( page_title="Welcome to COSCO Logistics Dashboard",page_icon="🌐", layout="wide")
logo = Image.open("Data/logo.png") 
st.title("COSCO GREECE Logistics Dashboard 📈")


# ============================== 
# DATA LOADING
# ============================== 
# -------------------------------
# Load stored coordinates CSV
# -------------------------------

def load_coordinates():
    return pd.read_csv("Data/region_coordinates.csv")  # Make sure CSV has lat, lon, city columns if needed
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
def clean_series(s):
    """Normalize categorical columns: strip, upper, collapse spaces"""
    return (
        s.dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r'\s+', ' ', regex=True)
    )
def apply_filters(df):

    st.sidebar.header("Filters ≡")

    # ------------------------------
    # 🔄 RESET ALL FILTERS BUTTON
    # ------------------------------
    # Reset all filters automatically
    if st.sidebar.button("🔄 Reset All Filters", use_container_width=True):
        for key in list(st.session_state.keys()):
            # Use empty list for multiselect filters
            if key.startswith("filter_"):
                if "date" in key:
                    st.session_state[key] = None
                else:
                    st.session_state[key] = []
        st.rerun()

    df.columns = df.columns.str.strip()
    filtered_df = df.copy()

    # ------------------------------
    # 📅 DATE FILTER
    # ------------------------------
    date_column = None
    if "W\H/PORT Outbound date" in df.columns:
        date_column = "W\H/PORT Outbound date"
    elif "WH Inbound date" in df.columns:
        date_column = "WH Inbound date"

    if date_column:
        filtered_df[date_column] = pd.to_datetime(
            filtered_df[date_column], errors="coerce"
        )
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
                    ((filtered_df[date_column] >= start_date) &
                     (filtered_df[date_column] <= end_date))
                ]

    # ------------------------------
    # PROJECT FILTER
    # ------------------------------
    if 'PROJECT' in df.columns:
        projects = st.sidebar.multiselect(
            "Project 💾",
            sorted(clean_series(df['PROJECT']).unique()),
            key="filter_project"
        )
        if projects:
            filtered_df = filtered_df[
                clean_series(filtered_df['PROJECT']).isin(projects)
            ]

    # ------------------------------
    # COUNTRY FILTER (Inbound)
    # ------------------------------
    if 'Country' in df.columns:
        countries = st.sidebar.multiselect(
            "Country 🗺️📍",
            sorted(clean_series(df['Country']).unique()),
            key="filter_country"
        )
        if countries:
            filtered_df = filtered_df[
                clean_series(filtered_df['Country']).isin(countries)
            ]

    # ------------------------------
    # DESTINATION COUNTRY FILTER (Outbound)
    # ------------------------------
    if 'Destination Country' in df.columns:
        dest_countries = st.sidebar.multiselect(
            "Destination Country 🗺️📍",
            sorted(clean_series(df['Destination Country']).unique()),
            key="filter_dest_country"
        )
        if dest_countries:
            filtered_df = filtered_df[
                clean_series(filtered_df['Destination Country']).isin(dest_countries)
            ]

    # ------------------------------
    # VENDOR FILTER
    # ------------------------------
    if 'Vendor' in df.columns:
        vendors = st.sidebar.multiselect(
            "Vendor ⛓️",
            sorted(clean_series(df['Vendor']).unique()),
            key="filter_vendor"
        )
        if vendors:
            filtered_df = filtered_df[
                clean_series(filtered_df['Vendor']).isin(vendors)
            ]

    # ------------------------------
    # DC FILTER (Inbound)
    # ------------------------------
    if 'FDC' in df.columns:
        fdc = st.sidebar.multiselect(
            "DC 🏬🚚",
            sorted(clean_series(df['FDC']).unique()),
            key="filter_fdc"
        )
        if fdc:
            filtered_df = filtered_df[
                clean_series(filtered_df['FDC']).isin(fdc)
            ]

    # ------------------------------
    # DC/PORT FILTER (Outbound)
    # ------------------------------
    if 'FDC/PORT' in df.columns:
        fdc_port = st.sidebar.multiselect(
            "DC 🏬🚚",
            sorted(clean_series(df['FDC/PORT']).unique()),
            key="filter_fdc_port"
        )
        if fdc_port:
            filtered_df = filtered_df[
                clean_series(filtered_df['FDC/PORT']).isin(fdc_port)
            ]
    
    if 'Description' in df.columns:
        descriptions = st.sidebar.multiselect(
                "Description 📝",
                sorted(clean_series(df['Description']).unique()),
                key="filter_description" 
            )
        if descriptions:
                filtered_df = filtered_df[
                    clean_series(filtered_df['Description']).isin(descriptions)
                ]    
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
    col4.metric("Total Reels",int(df['Reels'].sum()))
    col5.metric("Total CBM", round(df['CBM'].sum(),2))
  
    
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
                plot_bgcolor='rgba(0, 0, 0, 0.2)',
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
                plot_bgcolor='rgba(0, 0, 0, 0.2)',
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
                plot_bgcolor='rgba(0, 0, 0, 0.2)',
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
                plot_bgcolor='rgba(0, 0, 0, 0.2)',
                xaxis_title='DC',
                yaxis_title='Total Shipments',
                margin=dict(t=40, b=40, l=40, r=40),
                legend=dict(
                title=dict(text=""))
            )
            
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
                plot_bgcolor='rgba(0, 0, 0, 0.1)',
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
                plot_bgcolor='rgba(0,0,0,0.1)',
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

            # Add percentage
            goods_counts['Percentage'] = (
                goods_counts['Count'] / goods_counts['Count'].sum() * 100
            ).round(2)

            fig = px.pie(
                    goods_counts,
                    names='Description',
                    values='Percentage',
                    hole=0,
                    width=350,
                    height=300
                )

            fig.update_layout(
                    paper_bgcolor='rgba(255, 255, 255, 1)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=0, b=0, l=0, r=0)
                )

            st.plotly_chart(fig, width="stretch")
    with tg2:
        # ==============================
        # 📁 PROJECT ALLOCATION
        # ==============================
        if 'PROJECT' in df.columns and 'Shipping MODE' in df.columns:
                st.subheader("Project Shipping Mode 📦🔎")
                
                # Count projects per shipping mode
                shipping_counts = df['Shipping MODE'].value_counts().reset_index()
                shipping_counts.columns = ['Shipping MODE', 'Count']
                
                # Create interactive pie chart
                fig = px.pie(
                    shipping_counts, 
                    names='Shipping MODE', 
                    values='Count',
                    hole=0,  # 0 for full pie, >0 for donut
                    width=350, height=300,
                    color='Shipping MODE',  # gives each mode a different color
                    color_discrete_sequence=px.colors.qualitative.Safe
    
                )
                
                # Make background transparent
                fig.update_layout(
                    paper_bgcolor='rgba(255, 255, 255, 1)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=0, b=0, l=0, r=0)
                )
                
                st.plotly_chart(fig, width="stretch")

        



# ==============================c
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
    col7.metric("Total Reels",int(df['Reels'].sum()))
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
                    'Project_Shipments_Combined': ", ".join(
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
                        plot_bgcolor="rgba(0,0,0,0.1)",
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
               plot_bgcolor='rgba(0, 0, 0, 0.1)',
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
                        plot_bgcolor='rgba(0,0,0,0.1)',
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
                    plot_bgcolor='rgba(0,0,0,0.1)',
                    coloraxis_showscale=False,
                    legend_bgcolor='rgba(0,0,0,0)'
                )

            

            st.plotly_chart(fig, use_container_width=True)

            
       
    
    col1,col2,col3,col4 = st.columns(4)
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
                plot_bgcolor='rgba(0,0,0,0.1)',
                xaxis_title="",
                yaxis_title="",legend_bgcolor='rgba(0,0,0,0)'
            )

           

            st.plotly_chart(fig, use_container_width=True)
    with col2:
        # ==============================
        # 📦 CONTAINER SIZE
        # ============================== 
        if 'Container Size/type' in df.columns:
            st.subheader("Container Size 🏗️🔎")

            count_20 = df['Container Size/type'].astype(str).str.count(r"20'")
            count_40 = df['Container Size/type'].astype(str).str.count(r"40'")

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
                plot_bgcolor='rgba(0,0,0,0.1)',
                xaxis_title="",
                yaxis_title="",
                legend=dict(
                title=dict(text="")),
                legend_bgcolor='rgba(0,0,0,0)',
            )

            

            st.plotly_chart(fig, use_container_width=True)
    with col3:
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
    with col4:
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
                plot_bgcolor='rgba(0,0,0,0.1)',
                xaxis_title="",
                yaxis_title="",
                legend=dict(
                title=dict(text="")),
                legend_bgcolor='rgba(0,0,0,0)'
            )

            

            st.plotly_chart(fig, use_container_width=True)
    
    
    


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
    ["Inbound ◀️", "Outbound ▶️"]
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

st.sidebar.markdown(
    "<p style='font-size:12px;color:gray'>Use the filters above to refine the dataset. "
    "The dashboard updates automatically based on your selection.</p>",
    unsafe_allow_html=True
)
