from dash import Dash, html, dcc,no_update
from dash.dependencies import Input, Output, State
import datetime
from dash_leaflet import Map, TileLayer, Marker
import random
import psycopg2
from dash_leaflet import Polyline

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Geolocation App", style={"textAlign": "center", "fontSize": "24px", "marginBottom": "20px"}),
    html.Button("Get Location", id="get-location-btn", style={
        "display": "block",
        "margin": "0 auto",
        "padding": "10px 20px",
        "fontSize": "16px"
    }),
    html.Div(id="location-output", style={
        "marginTop": "20px",
        "textAlign": "center",
        "fontSize": "16px",
        "wordWrap": "break-word"
    }),
    dcc.Store(id="location-data"),
    dcc.Store(id="interval-enabled", data=False)
], style={
    "maxWidth": "500px",
    "margin": "0 auto",
    "padding": "10px",
    "boxSizing": "border-box"
})

app.layout.children.append(
    dcc.Interval(id="location-interval", interval=5000, n_intervals=0, disabled=True)
)
@app.callback(
    [Output("location-interval", "disabled"), Output("location-interval", "n_intervals")],
    Input("get-location-btn", "n_clicks"),
    prevent_initial_call=True
)
def enable_interval(n_clicks):
    if n_clicks > 0:
        return False, 1
    return True, 0

app.clientside_callback(
    """
    function(n_intervals) {
        if (n_intervals > 0) {
            return new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    position => {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;

                        // Add Gaussian noise
                        const addGaussianNoise = (value, stdDev) => {
                            const rand = Math.random() * 2 - 1 + Math.random() * 2 - 1 + Math.random() * 2 - 1;
                            return value + rand * stdDev;
                        };

                        resolve({
                            lat: addGaussianNoise(lat, 0.01),
                            lon: addGaussianNoise(lon, 0.01)
                        });
                    },
                    error => {
                        reject("Geolocation not available or permission denied.");
                    }
                );
            });
        }
        return null;
    }
    """,
    Output("location-data", "data"),
    Input("location-interval", "n_intervals")
)
location_history = []

@app.callback(
    Output("location-output", "children"),
    Input("location-data", "data")
)


def display_location(location_data):
    if location_data:
        timestamp = datetime.datetime.now().isoformat()
        location_entry = {
            "timestamp": timestamp,
            "latitude": location_data['lat'],
            "longitude": location_data['lon']
        }
        location_history.append(location_entry)
        print(location_history)
        return f"Latitude: {location_data['lat']}, Longitude: {location_data['lon']} (Recorded at {timestamp})"
    return "Waiting for location updates..."

@app.callback(
    Output("location-map", "children"),
    Input("location-data", "data")
)
def update_map(location_data):
    if location_data:
        if len(location_history) == 1:
            return Map(
                center=[location_data["lat"], location_data["lon"]],
                zoom=12,
                children=[
                    TileLayer(),
                    Marker(position=[location_data["lat"], location_data["lon"]])
                ],
                style={"height": "500px", "width": "100%"}
            )
        elif len(location_history) >= 2:
            coordinates = [[entry["latitude"], entry["longitude"]] for entry in location_history]
            return Map(
                center=coordinates[-1],
                zoom=12,
                children=[
                    TileLayer(),
                    Polyline(positions=coordinates, color="blue", weight=3)
                ],
                style={"height": "500px", "width": "100%"}
            )
    return no_update
# Add a button to save the location history
app.layout.children.append(
    html.Button("Save Location History", id="save-location-btn", style={
        "display": "block",
        "margin": "20px auto",
        "padding": "10px 20px",
        "fontSize": "16px"
    })
)

@app.callback(
    [Output("location-output", "children",allow_duplicate=True),
     Output("location-interval", "disabled",allow_duplicate=True)],
    Input("save-location-btn", "n_clicks"),
    prevent_initial_call=True
)
def save_location_history(n_clicks):
    if location_history:
        # Prepare data for saving
        start_timestamp = location_history[0]["timestamp"]
        end_timestamp = location_history[-1]["timestamp"]
        coordinates = [(entry["longitude"], entry["latitude"]) for entry in location_history]

        # Connect to the PostgreSQL database
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="--------------",
            host="cityflowlimpia.cmpmegoiaext.us-east-1.rds.amazonaws.com",
            port="5432"
        )
        cursor = conn.cursor()

        # Insert the location history as a LineString
        cursor.execute("""
            INSERT INTO geoTracker (start_timestamp, end_timestamp, geometry)
            VALUES (%s, %s, ST_MakeLine(ARRAY[%s]::geometry[]))
        """, (start_timestamp, end_timestamp, ','.join([f"ST_MakePoint({lon}, {lat})" for lon, lat in coordinates])))

        conn.commit()
        cursor.close()
        conn.close()
        print(location_history)
        return f"Location history saved from {start_timestamp} to {end_timestamp}.",True
    return "No location history to save.", no_update

app.layout.children.append(html.Div(id="location-map", style={"marginTop": "20px"}))

if __name__ == "__main__":
    app.run(debug=True)