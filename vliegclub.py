import streamlit as st
import folium
from streamlit_folium import st_folium
import math

# --- CONFIGURATIE DIAMOND DA40 TDI ---
AIRCRAFT_EMPTY_WEIGHT = 800  # kg
AIRCRAFT_MTOW = 1150         # kg
FUEL_LITERS_TO_KG = 0.84     # Jet-A1
BASE_RUNWAY_REQUIRED = 650   # meter
CRUISE_SPEED_TAS = 120       # Knopen
FUEL_FLOW_LPH = 20           
RESERVE_FUEL_LITERS = 15     

# DATABASE VAN WAYPOINTS & MODEL-COÖRDINATEN
waypoints = {
    "EHLE": [52.460, 5.527], "GORLO": [52.733, 6.783], "NDO": [54.012, 9.155],
    "HAM": [53.670, 9.980], "ALS": [54.911, 9.991], "DLE": [52.417, 9.383],
    "HMM": [52.190, 7.615], "COA": [51.748, 4.341], "CIV": [50.402, 2.988],
    "EDXW": [54.913, 8.340], "EDHL": [53.805, 10.719], "EKRK": [55.585, 12.131],
    "EDWJ": [53.679, 6.990], "EDVE": [52.319, 10.556], "EDDG": [52.135, 7.684],
    "LFAT": [50.515, 1.621], "EBBR": [50.901, 4.484], "EHRD": [51.957, 4.437],
    "EDWH": [53.501, 7.501], "EDWI": [53.522, 7.491]
}

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
st.title("✈️ Diamond DA40 TDI - Cockpit Dispatcher v12.2 (TAF Timeline Edition)")

# SIDEBAR: 1. Belading
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

# SIDEBAR: 2. Wind & Weer
st.sidebar.header("2. Wind & Weer (Kruishoogte)")
sim_temp = st.sidebar.slider("Buitentemperatuur (°C)", -10, 40, 15)
sim_qnh = st.sidebar.slider("Luchtdruk QNH (hPa)", 950, 1050, 1013)
wind_direction = st.sidebar.selectbox("Windrichting vandaan", ["Noord", "Oost", "Zuid", "West"])
wind_speed = st.sidebar.slider("Windsnelheid (Knopen)", 0, 50, 15)

# --- NEW IN v12.2: DE TAF VERTREKTIJD SCHUIFBALK ---
st.sidebar.header("3. Geplande Vertrektijd (TAF)")
vertrektijd = st.sidebar.select_slider(
    "Selecteer vertrektijd (Vanaf Nu):",
    options=["Nu VFR", "+3 Uur (TAF Blok 1)", "+6 Uur (TAF Blok 2)", "+9 Uur (TAF Blok 3)"]
)

st.sidebar.header("4. Uitje Voorkeuren")
max_landing_fee = st.sidebar.slider("Max. Landingsgeld (€)", 10, 150, 100)

# GEÜPGRADEDE DATABASE MET 11 EUROPESE STRATEGISCHE GA-VELDEN & TAF METEO TRENDS
vliegvelden = {
    "EDXW": {
        "name": "Sylt (DE)", "runway": 1696, "track_from_ehle": 20, "crosses_edr99": True, "jet_a1": True, "landing_fee": 120, "city_dist": "2 km",
        "route_waypoints": ["EHLE", "GORLO", "NDO", "EDXW"], "gps_route": "EHLE DCT GORLO DCT NDO DCT EDXW",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "VFR OK", "+6 Uur (TAF Blok 2)": "⚠️ TAF: MIST / SIGMET ACTIEF", "+9 Uur (TAF Blok 3)": "⚠️ TAF: MIST / SIGMET ACTIEF"}
    },
    "EDHL": {
        "name": "Lübeck (DE)", "runway": 2102, "track_from_ehle": 65, "crosses_edr99": False, "jet_a1": False, "landing_fee": 25, "city_dist": "8 km",
        "route_waypoints": ["EHLE", "GORLO", "HAM", "EDHL"], "gps_route": "EHLE DCT GORLO DCT HAM DCT EDHL",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "VFR OK", "+6 Uur (TAF Blok 2)": "VFR OK", "+9 Uur (TAF Blok 3)": "VFR OK"}
    },
    "EKRK": {
        "name": "Roskilde (DK)", "runway": 1500, "track_from_ehle": 40, "crosses_edr99": True, "jet_a1": True, "landing_fee": 35, "city_dist": "6 km",
        "route_waypoints": ["EHLE", "GORLO", "NDO", "ALS", "EKRK"], "gps_route": "EHLE DCT GORLO DCT NDO DCT ALS DCT EKRK",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "VFR OK", "+6 Uur (TAF Blok 2)": "VFR OK", "+9 Uur (TAF Blok 3)": "⚠️ TAF: ONWEER (TSRA)"}
    },
    "EDWJ": {
        "name": "Juist (DE)", "runway": 700, "track_from_ehle": 15, "crosses_edr99": False, "jet_a1": False, "landing_fee": 18, "city_dist": "0 km",
        "route_waypoints": ["EHLE", "GORLO", "EDWJ"], "gps_route": "EHLE DCT GORLO DCT JUIST",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "⚠️ TAF: HARD WIND (>25KT)", "+6 Uur (TAF Blok 2)": "VFR OK", "+9 Uur (TAF Blok 3)": "VFR OK"}
    },
    "LFAT": {
        "name": "Le Touquet (FR)", "runway": 1850, "track_from_ehle": 220, "crosses_edr99": False, "jet_a1": True, "landing_fee": 40, "city_dist": "3 km",
        "route_waypoints": ["EHLE", "COA", "CIV", "LFAT"], "gps_route": "EHLE DCT COA DCT CIV DCT LFAT",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "VFR OK", "+6 Uur (TAF Blok 2)": "VFR OK", "+9 Uur (TAF Blok 3)": "VFR OK"}
    },
    "EHRD": {
        "name": "Rotterdam (NL)", "runway": 2200, "track_from_ehle": 240, "crosses_edr99": False, "jet_a1": True, "landing_fee": 65, "city_dist": "5 km",
        "route_waypoints": ["EHLE", "COA", "EHRD"], "gps_route": "EHLE DCT COA DCT EHRD",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "VFR OK", "+6 Uur (TAF Blok 2)": "VFR OK", "+9 Uur (TAF Blok 3)": "VFR OK"}
    },
    "EDWI": {
        "name": "Wangerland (DE)", "runway": 800, "track_from_ehle": 30, "crosses_edr99": False, "jet_a1": True, "landing_fee": 15, "city_dist": "1 km",
        "route_waypoints": ["EHLE", "GORLO", "EDWI"], "gps_route": "EHLE DCT GORLO DCT EDWI",
        "taf_weather": {"Nu VFR": "VFR OK", "+3 Uur (TAF Blok 1)": "VFR OK", "+6 Uur (TAF Blok 2)": "VFR OK", "+9 Uur (TAF Blok 3)": "VFR OK"}
    }
}

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

st.subheader("Strategisch Overzicht - Inclusief Dynamische TAF-Tijdlijn")

m = folium.Map(location=[52.5, 6.5], zoom_start=6)
folium.Marker(waypoints["EHLE"], popup="Vertrek: Lelystad", icon=folium.Icon(color="blue", icon="star")).add_to(m)

# DYNAMISCHE LUCHTRUIM-ACTIVATIE OP BASIS VAN DE TAF-TIJDBALK
# Het militaire oefengebied (ED-R 99) is overdag actief (+3 en +6 uur), maar 'Nu' en '+9 uur' (avond) inactief!
edr99_coords = [[53.5, 6.5], [54.2, 6.5], [54.2, 8.0], [53.5, 8.0]]
if vertrektijd in ["+3 Uur (TAF Blok 1)", "+6 Uur (TAF Blok 2)"]:
    edr99_active = True
    edr99_color = "red"
    edr99_status = "ED-R 99 ACTIEF (Militair oefengebied geactiveerd tijdens dit tijdslot!)"
else:
    edr99_active = False
    edr99_color = "gray"
    edr99_status = "ED-R 99 INACTIEF (Luchtruim vrijgegeven voor dit tijdslot)"

folium.Polygon(locations=edr99_coords, color=edr99_color, fill=True, fill_opacity=0.15, popup=edr99_status).add_to(m)

vliegveld_statussen = {}

for icao, data in vliegvelden.items():
    total_route_distance_nm = 0
    route_line_coords = []
    
    for i in range(len(data["route_waypoints"]) - 1):
        wp_start = data["route_waypoints"][i]
        wp_eind = data["route_waypoints"][i+1]
        
        coord_start = waypoints[wp_start]
        coord_eind = waypoints[wp_eind]
        
        if coord_start not in route_line_coords: route_line_coords.append(coord_start)
        route_line_coords.append(coord_eind)
        
          total_route_distance_nm += calculate_distance_nm(coord_start[0], coord_start[1], coord_eind[0], coord_eind[1])

    # Wind berekening
    headwind = 0
    if wind_direction == "Noord" and data["track_from_ehle"] < 90: headwind = wind_speed * 0.7
    elif wind_direction == "Oost" and 45 < data["track_from_ehle"] < 135: headwind = wind_speed
    elif wind_direction == "Zuid" or wind_direction == "West": headwind = -wind_speed * 0.5  

    ground_speed = CRUISE_SPEED_TAS - headwind
    flight_time_hours = total_route_distance_nm / ground_speed
    
    # Strafminuten toepassen als de No-Fly zone actief is én de route erdoorheen loopt
    penalty_text = ""
    if edr99_active and data["crosses_edr99"]:
        flight_time_hours += (15 / 60)
        penalty_text = f"⚠️ +15 min omvliegen wegens actieve {edr99_status.split(' ')[0]}"
        
    fuel_needed = flight_time_hours * FUEL_FLOW_LPH
    
    # Density Altitude Check
    temp_penalty = max(0, sim_temp - 15) * 0.01
    qnh_penalty = max(0, 1013 - sim_qnh) * 0.005
    needed_runway = BASE_RUNWAY_REQUIRED * (1 + temp_penalty + qnh_penalty)
    
    # Haal het voorspelde TAF-weer op voor DIT vliegveld op DIT specifieke tijdstip
    lokaal_taf_weer = data["taf_weather"][vertrektijd]
    
    color = "green"
    reason = "✈️ Haalbaar"
    
    if fuel_needed > usable_fuel:
        color = "red"
        reason = "❌ BEREIK TE KORT"
    elif needed_runway > data["runway"]:
        color = "red"
        reason = "❌ BAAN TE KORT"
    elif data["landing_fee"] > max_landing_fee:
        color = "red"
        reason = "❌ LANDINGSGELD TE DUUR"
    elif "⚠️" in lokaal_taf_weer:
        color = "red"
        reason = f"❌ SLOTS ONMOGELIJK ({lokaal_taf_weer.replace('⚠️ TAF: ', '')})"
    elif not data["jet_a1"]:
        color = "orange"
        reason = "🟠 GÉÉN JET-A1"

    vliegveld_statussen[icao] = {
        "color": color, "reason": reason, "data": data, "time": int(flight_time_hours*60), 
        "fuel": int(fuel_needed), "gs": int(ground_speed), "dist": int(total_route_distance_nm), "weer": lokaal_taf_weer
    }

    # Plot de knikkende route en waypoints
    folium.PolyLine(route_line_coords, color=color, weight=3, opacity=0.85).add_to(m)
    for wp_name in data["route_waypoints"][1:-1]:
        folium.CircleMarker(waypoints[wp_name], radius=4, color="purple", fill=True, popup=f"Waypoint: {wp_name}").add_to(m)
    folium.Marker(waypoints[icao], popup=data["name"], icon=folium.Icon(color=color, icon="plane")).add_to(m)

st_folium(m, width=1100, height=400)

# Dashboard details
st.markdown("### 📋 Resultaten, TAF Weeromslag & GPS Routes")
for icao, status in vliegveld_statussen.items():
    with st.expander(f"✈️ {icao} - {status['data']['name']} ({status['reason']})"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"📏 **Echte GPS Afstand:** {status['dist']} NM")
            st.write(f"⏱️ **Vliegtijd total:** {status['time']} min ({status['gs']} kt GS)")
            st.write(f"⛽ **Verbruik:** {status['fuel']} Liter")
            st.write(f"💰 **Landingsgeld:** €{status['data']['landing_fee']}")
        with col2:
            # Toon de actieve TAF status van dit specifieke uur!
            if "⚠️" in status['weer']:
                st.error(f"🌦️ **Actuele TAF Prognose:** {status['weer']}")
            else:
                st.success(f"🌦️ **Actuele TAF Prognose:** {status['weer']}")
                
            st.info(f"📍 **Garmin G1000 GPS Route:**")
            st.code(status['data']['gps_route'], language="text")
            st.write(f"🏙️ **Logistiek:** {status['data']['city_dist']}")

# Smart Alternate Advisor
st.markdown("---")
st.header("💡 Smart Alternate Advisor")
rode_velden = {k: v for k, v in vliegveld_statussen.items() if v["color"] == "red"}
groene_velden = {k: v for k, v in vliegveld_statussen.items() if v["color"] == "green"}

if rode_velden:
    for icao, status in rode_velden.items():
        st.error(f"⚠️ **{status['data']['name']} ({icao})** is onbereikbaar tijdens dit tijdslot. Reden: {status['reason']}.")
        if groene_velden:
            st.info("🔮 **Voorgestelde Uitwijk-bestemmingen voor dit tijdstip:**")
            for g_icao, g_status in groene_velden.items():
                st.success(f"👉 Wijzig vertrektijd of koers naar **{g_status['data']['name']} ({g_icao})** (Operationeel Groen). GPS Route: `{g_status['data']['gps_route']}`")
else:
    st.success("🎉 Alle beschikbare vliegvelden zijn in dit tijdslot groen licht!")
