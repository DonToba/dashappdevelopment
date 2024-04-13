import dash
from dash import html, dcc, Input, Output, State
import geopandas as gpd
from shapely.geometry import Point, box
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
import io
import base64
import folium
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import requests
from zipfile import ZipFile
from io import BytesIO
import os

# Load shapefiles
# URLs of shapefiles on GitHub
# Set the PROJ_LIB environment variable
# URLs of shapefiles on GitHub
# URLs of GeoJSON files on GitHub
building_footprints_url = 'https://raw.githubusercontent.com/DonToba/Atopcon/main/Building_Footprints_4326.geojson'
poi_url = 'https://raw.githubusercontent.com/DonToba/Atopcon/main/POIs.geojson'
roads_url = 'https://raw.githubusercontent.com/DonToba/Atopcon/main/roads.geojson'

# Function to download and load GeoJSON file into GeoPandas DataFrame
def load_geojson(url):
    response = requests.get(url)
    if response.status_code == 200:
        gdf = gpd.read_file(response.text)
        return gdf
    else:
        print("Failed to download the GeoJSON file.")

# Download and load building footprints
building_footprints = load_geojson(building_footprints_url)

# Download and load POIs
POIs = load_geojson(poi_url)

# Download and load roads
roads = load_geojson(roads_url)

# Default coordinates
default_latitude = 9.0820
default_longitude = 8.6753

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server

# Define layout and style
app.layout = html.Div(style={'backgroundColor': '#000', 'color': '#fff', 'fontFamily': 'Arial, sans-serif'}, children=[
    html.H1("ATOPCON DEMO BY NERVS", style={'textAlign': 'center', 'marginBottom': '20px'}),
    html.Div([
        html.Label("Latitude", style={'fontWeight': 'bold'}),
        dcc.Input(id='input-lat', type='number', value=default_latitude, style={'marginRight': '20px'}),
        html.Label("Longitude", style={'fontWeight': 'bold'}),
        dcc.Input(id='input-lon', type='number', value=default_longitude, style={'marginRight': '20px'}),
        html.Button('Submit', id='submit-val', n_clicks=0, style={'marginTop': '20px', 'backgroundColor': '#007bff', 'color': '#fff', 'border': 'none'}),
    ], style={'textAlign': 'center', 'marginBottom': '20px'}),
    html.Div(id='map-container', style={'textAlign': 'center'}),
    html.Div(id='analysis-container', style={'textAlign': 'center', 'marginTop': '20px'})
])

@app.callback(
    Output('map-container', 'children'),
    [Input('submit-val', 'n_clicks')],
    [State('input-lat', 'value'), State('input-lon', 'value')]
)
def update_map(n_clicks, latitude, longitude):
    # Initialize map with default location
    mymap = folium.Map(location=[default_latitude, default_longitude], zoom_start=15)
    
    # Check if submit button was clicked
    if n_clicks > 0:
        # Validate latitude and longitude
        if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
            return html.Iframe(id='map-iframe', width='100%', height='600'), "Invalid latitude or longitude!"

        # Create marker for inputted location
        folium.Marker(location=[latitude, longitude], popup="Subject Site").add_to(mymap)

        # Create circle with 250m radius
        folium.Circle(location=[latitude, longitude], radius=250, color='blue', fill=True, fill_opacity=0.2).add_to(mymap)

        # Update map zoom to focus on circle and point
        mymap.fit_bounds([[latitude - 0.01, longitude - 0.01], [latitude + 0.01, longitude + 0.01]])

    # Save Folium map to HTML file
    map_html = "mymap.html"
    mymap.save(map_html)

    return html.Iframe(id='map-iframe', srcDoc=open(map_html).read(), width='100%', height='600'), ""

def update_map(latitude, longitude):
    # Create circle geometry
    circle_center = Point(longitude, latitude)
    circle = circle_center.buffer(0.025)

    # Select features within the circle
    buildings_within_radius = building_footprints[building_footprints.geometry.intersects(circle)]

    # Plot map
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw={'projection': ccrs.PlateCarree()})
    buildings_within_radius.plot(ax=ax, color='red')
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS)
    bbox = buildings_within_radius.total_bounds
    ax.set_extent([bbox[0], bbox[2], bbox[1], bbox[3]])
    gl = ax.gridlines(draw_labels=True)
    gl.xlabels_top = gl.ylabels_right = False
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    ax.annotate('N', xy=(0.1, 0.95), xycoords='axes fraction', ha='center', va='center',
                arrowprops=dict(facecolor='black', arrowstyle='->', linewidth=1.5), fontsize=30)
    bbox_polygon = box(bbox[0], bbox[1], bbox[2], bbox[3])
    bbox_patch = ax.add_geometries([bbox_polygon], ccrs.PlateCarree(),
                                    facecolor='none', edgecolor='black', linewidth=1)

    # Convert matplotlib figure to base64 image
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)
    img_base64 = base64.b64encode(img_data.getvalue()).decode('utf-8')

    return html.Img(src='data:image/png;base64,{}'.format(img_base64), style={'height': '500px', 'width': 'auto'})

def generate_report(latitude, longitude):
    # Create circle geometry
    circle_center = Point(longitude, latitude)
    circle = circle_center.buffer(0.025)

    # Select features within the circle
    buildings_within_radius = building_footprints[building_footprints.geometry.intersects(circle)]
    roads_within_radius = roads[roads.geometry.intersects(circle)]
    pois_within_radius = POIs[POIs.geometry.intersects(circle)]

    # Plot charts
    charts = [
        ('Chart showing Use of Buildings within 250m radius', buildings_within_radius["Use"]),
        ('Chart showing Height of Buildings within 250m radius', buildings_within_radius["Height"]),
        ('Chart showing road classes within 250m radius', roads_within_radius["Class"]),
        ('Chart showing condition of roads within 250m radius', roads_within_radius["Condition"])
    ]

    chart_elements = []

    for attribute_name, data in charts:
        plt.figure(figsize=(10, 6))
        ax = data.value_counts().plot(kind='bar')
        for p in ax.patches:
            ax.annotate(str(p.get_height()), (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='center', xytext=(0, 10), textcoords='offset points')
        plt.title('{}'.format(attribute_name))
        plt.xlabel('Building Use' if attribute_name.startswith('Chart showing Use') else 'Road Condition' if attribute_name.startswith('Chart showing condition') else 'Road Class' if attribute_name.startswith('Chart showing road') else 'Number of floors')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.annotate('This report was generated by Nervs', (0.75, 0.05), xycoords='figure fraction', ha='left', fontsize=6.5)
        plt.tight_layout()

        # Convert matplotlib figure to base64 image
        img_data = io.BytesIO()
        plt.savefig(img_data, format='png')
        img_data.seek(0)
        img_base64 = base64.b64encode(img_data.getvalue()).decode('utf-8')

        chart_elements.append(html.Div([
            html.Img(src='data:image/png;base64,{}'.format(img_base64), style={'height': '400px', 'width': 'auto'})
        ]))

    return chart_elements

@app.callback(
    Output('analysis-container', 'children'),
    [Input('submit-val', 'n_clicks')],
    [State('input-lat', 'value'), State('input-lon', 'value')]
)
def run_analysis(n_clicks, latitude, longitude):
    if n_clicks > 0:
        return generate_report(latitude, longitude)

if __name__ == '__main__':
    app.run_server(debug=False)
