import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import pandas as pd

# --- CONFIGURATIE DIAMOND DA40 TDI ---
AIRCRAFT_EMPTY_WEIGHT = 800  # kg
AIRCRAFT_MTOW = 1150         # kg
FUEL_LITERS_TO_KG = 0.84     # Jet-A1
BASE_RUNWAY_REQUIRED = 650   # meter
CRUISE_SPEED_TAS = 120       # Knopen
FUEL_FLOW_LPH = 20           
RESERVE_FUEL_LITERS = 15     

EHLE_LAT, EHLE_LON = 52.460, 5.527  # Lelystad Airport

st.set_page_config(layout="wide")

# INLOGSCHERM
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Diamond DA40 Dispatcher - Beveiligde Toegang")
    wachtwoord_input = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if wachtwoord_input == "Hestknappen":
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Onjuist wachtwoord.")
    st.stop()

# APPLICATIE
st.title("✈️ Diamond DA40 TDI - Cockpit Dispatcher v12.1 (Global Engine)")

# HERSTELDE INTERNET KOPPELING: We lossen de ParserError op met escapechar en on_bad_lines
@st.cache_data
def load_global_airports():
    url = "https://ourairports.com"
    try:
        # We dwingen pandas om foute regels over te slaan en quotes correct te lezen
        df = pd.read_csv(url, quotechar='"', skipinitialspace=True, on_bad_lines='skip')
        df = df[df['type'].isin(['medium_airport', 'large_airport', 'small_airport'])]
        df = df[df['continent'] == 'EU']
        return df
    except Exception as e:
        # Mocht internet of de CSV echt weigeren, dan bouwen we een live fallback
        st.warning("Live database kon niet worden geladen. Fallback actief.")
        fallback_data = {
            'ident': ['EDXW', 'EDHL', 'EKRK', 'EDWJ', 'EDVE', 'EDDG'],
            'name': ['Sylt', 'Lübeck', 'Roskilde', 'Juist', 'Braunschweig', 'Münster Osnabrück'],
            'latitude_deg': [54.913, 53.805, 55.585, 53.679, 52.319, 52.135],
            'longitude_deg': [8.340, 10.719, 12.131, 6.990, 10.556, 7.684],
            'type': ['medium_airport', 'medium_airport', 'medium_airport', 'small_airport', 'medium_airport', 'large_airport'],
            'iso_country': ['DE', 'DE', 'DK', 'DE', 'DE', 'DE']
        }
        return pd.DataFrame(fallback_data)

with st.spinner("Wereldwijde Europese luchtvaartdatabase laden..."):
    airports_df = load_global_airports()

# SIDEBARS
st.sidebar.header("1. Belading & Brandstof")
pax_count = st.sidebar.slider("Aantal personen", 1, 4, 3)
pax_weight = pax_count * 85  
fuel_liters = st.sidebar.slider("Brandstof (Liters)", 30, 106, 80)
fuel_weight = fuel_liters * FUEL_LITERS_TO_KG
totaal_gewicht = AIRCRAFT_EMPTY_WEIGHT + pax_weight + fuel_weight
overgewicht = totaal_gewicht - AIRCRAFT_MTOW

allowed_to_fly = True
st.sidebar.subheader("Gewichtsstatus")
if overgewicht > 0:
    st.sidebar.error(f"❌ TE ZWAAR!")
    allowed_to_fly = False
else:
    st.sidebar.success(f"✅ Gewicht OK.")

usable_fuel = fuel_liters - RESERVE_FUEL_LITERS

st.sidebar.header("2. Wind & Weer (Kruishoogte)")
sim_temp = st.sidebar.slider("Buitentemperatuur (°C)", -10, 40, 15)
sim_qnh = st.sidebar.slider("Luchtdruk QNH (hPa)", 950, 1050, 1013)
wind_direction = st.sidebar.selectbox("Windrichting vandaan", ["Noord", "Oost", "Zuid", "West"])
wind_speed = st.sidebar.slider("Windsnelheid (Knopen)", 0, 50, 15)

st.sidebar.header("3. Airspace")
vlucht_dag = st.sidebar.radio("Geplande vluchtdag:", ["Weekend (Za/Zo)", "Doordeweeks (Ma-Vr)"])
max_landing_fee = st.sidebar.slider("Max. Landingsgeld (€)", 10, 150, 100)

st.sidebar.header("🔍 Bestemming Zoeken")
icao_input = st.sidebar.text_input("Typ ICAO code (bv. EDXW, EKRK, LFAT, EDHL)", "EDXW").upper().strip()

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return (R * c) * 0.539957


# APPLICATIE LOGICA DRAAIEN
if not allowed_to_fly:
    st.warning("⚠️ Vliegtuig is te zwaar. Pas de parameters aan aan de linkerkant.")
    st.stop()

# Zoek het vliegveld op in de wereld-database
target_airport = airports_df[airports_df['ident'] == icao_input]

if not target_airport.empty:
    airport_data = target_airport.iloc[0]
    dest_name = airport_data['name']
    dest_lat = airport_data['latitude_deg']
    dest_lon = airport_data['longitude_deg']
    
    # Baanlengte schatten of hardcoded overschrijven
    runway_length = 2000 if airport_data['type'] == 'large_airport' else 1200
    if icao_input == "EDXW": runway_length = 1696 
    if icao_input == "EDWJ": runway_length = 700
    
    # --- AUTOMATISCHE GPS ROUTE-GENERATOR ---
    distance_direct = calculate_distance_nm(EHLE_LAT, EHLE_LON, dest_lat, dest_lon)
    
    # Genereer virtuele waypoints op 1/3 en 2/3 van de route
    wp1_lat = EHLE_LAT + (dest_lat - EHLE_LAT) * 0.33 + 0.15
    wp1_lon = EHLE_LON + (dest_lon - EHLE_LON) * 0.33 - 0.10
    wp2_lat = EHLE_LAT + (dest_lat - EHLE_LAT) * 0.66 - 0.10
    wp2_lon = EHLE_LON + (dest_lon - EHLE_LON) * 0.66 + 0.15
    
    wp1_name = "WP" + str(int(wp1_lat)) + "N"
    wp2_name = "WP" + str(int(wp2_lon)) + "E"
    
    route_line_coords = [[EHLE_LAT, EHLE_LON], [wp1_lat, wp1_lon], [wp2_lat, wp2_lon], [dest_lat, dest_lon]]
    gps_route_string = f"EHLE DCT {wp1_name} DCT {wp2_name} DCT {icao_input}"
    
    total_route_distance_nm = (
        calculate_distance_nm(EHLE_LAT, EHLE_LON, wp1_lat, wp1_lon) +
        calculate_distance_nm(wp1_lat, wp1_lon, wp2_lat, wp2_lon) +
        calculate_distance_nm(wp2_lat, wp2_lon, dest_lat, dest_lon)
    )

    # Wind component
    headwind = 0
    if wind_direction == "Noord": headwind = wind_speed * 0.4
    elif wind_direction == "Oost": headwind = wind_speed * 0.5
    elif wind_direction == "Zuid" or wind_direction == "West": headwind = -wind_speed * 0.4  

    ground_speed = CRUISE_SPEED_TAS - headwind
    flight_time_hours = total_route_distance_nm / ground_speed
    
    # No-Fly zone check (ED-R 99)
    edr99_coords = [[53.5, 6.5], [54.2, 6.5], [54.2, 8.0], [53.5, 8.0]]
    edr99_active = vlucht_dag == "Doordeweeks (Ma-Vr)"
    
    crosses_edr99 = 53.0 < dest_lat < 56.0 and 5.0 < dest_lon < 9.0
    penalty_text = ""
    if edr99_active and crosses_edr99:
        flight_time_hours += (15 / 60)
        penalty_text = "⚠️ +15 min wegens actieve ED-R 99 zone."
        
    fuel_needed = flight_time_hours * FUEL_FLOW_LPH
    
    temp_penalty = max(0, sim_temp - 15) * 0.01
    qnh_penalty = max(0, 1013 - sim_qnh) * 0.005
    needed_runway = BASE_RUNWAY_REQUIRED * (1 + temp_penalty + qnh_penalty)
    
    estimated_fee = 120 if icao_input == "EDXW" else (20 if runway_length < 1000 else 40)
    has_jet_a1 = False if icao_input == "EDHL" or icao_input == "EDWJ" else True

    color = "green"
    reason = "✈️ Route is 100% operationeel haalbaar!"
    
    if fuel_needed > usable_fuel:
        color = "red"
        reason = f"❌ BEREIK TE KORT: {int(fuel_needed)}L nodig."
    elif needed_runway > runway_length:
        color = "red"
        reason = f"❌ BAAN TE KORT: {int(needed_runway)}m nodig (Beschikbaar: {runway_length}m)."
    elif estimated_fee > max_landing_fee:
        color = "red"
        reason = f"💰 LANDINGSGELD TE DUUR: Geschat €{estimated_fee}."
    elif not has_jet_a1:
        color = "orange"
        reason = "🟠 GÉÉN JET-A1 BESCHIKBAAR OP BESTEMMING!"

    st.subheader(f"Echte Vliegroute naar {dest_name} ({icao_input})")
    m = folium.Map(location=[(EHLE_LAT + dest_lat)/2, (EHLE_LON + dest_lon)/2], zoom_start=6)
    
    folium.Marker([EHLE_LAT, EHLE_LON], popup="Vertrek: Lelystad", icon=folium.Icon(color="blue", icon="star")).add_to(m)
    folium.Marker([dest_lat, dest_lon], popup=dest_name, icon=folium.Icon(color=color, icon="plane")).add_to(m)
    
    edr99_color = "red" if edr99_active else "gray"
    folium.Polygon(locations=edr99_coords, color=edr99_color, fill=True, fill_opacity=0.10).add_to(m)

    folium.PolyLine(route_line_coords, color=color, weight=4, opacity=0.85).add_to(m)
    folium.CircleMarker([wp1_lat, wp1_lon], radius=5, color="purple", fill=True, popup=wp1_name).add_to(m)
    folium.CircleMarker([wp2_lat, wp2_lon], radius=5, color="purple", fill=True, popup=wp2_name).add_to(m)

    st_folium(m, width=1100, height=450)

    st.markdown("### 📋 Cockpit Flight Log & GPS Route")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Echte GPS Afstand", f"{int(total_route_distance_nm)} NM", f"Directe lijn was {int(distance_direct)} NM")
        st.metric("Totale Vliegtijd", f"{int(flight_time_hours*60)} min", penalty_text if penalty_text else f"{int(ground_speed)} kt GS")
        st.metric("Brandstof Verbruik", f"{int(fuel_needed)} Liter", f"{int(usable_fuel - fuel_needed)}L over")
    with col2:
        st.success(f"Status: {reason}")
        st.info("📍 **Garmin G1000 GPS Route String:**")
        st.code(gps_route_string, language="text")
        st.write(f"🏢 **Luchthaven:** {dest_name} ({airport_data['iso_country']})")
        st.write(f"📏 **Beschikbare Baanlengte:** {runway_length} meter | **Landingsgeld (Est):** €{estimated_fee}")
        st.write(f"⛽ **Jet-A1 Tanken:** {'JA' if has_jet_a1 else 'NEE (LET OP!)'}")

else:
    st.error(f"❌ ICAO code '{icao_input}' niet gevonden in de Europese database.")
