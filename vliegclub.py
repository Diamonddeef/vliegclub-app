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

EHLE_LAT, EHLE_LON = 52.460, 5.527  # Lelystad

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
st.title("✈️ Diamond DA40 TDI - Cockpit Dispatcher v10")

# SIDEBAR: 1. Belading
st.sidebar.header("1. Belading & Brandstof")
pax_count = st.sidebar.slider("Aantal personen", 1, 4, 3)
pax_weight = pax_count * 85  
fuel_liters = st.sidebar.slider("Brandstof (Liters)", 30, 106, 80)
fuel_weight = fuel_liters * FUEL_LITERS_TO_KG
totaal_gewicht = AIRCRAFT_EMPTY_WEIGHT + pax_weight + fuel_weight
overgewicht = totaal_gewicht - AIRCRAFT_MTOW

if overgewicht > 0:
    st.sidebar.error(f"❌ TE ZWAAR! {int(totaal_gewicht)} kg.")
    allowed_to_fly = False
else:
    st.sidebar.success(f"✅ Gewicht OK: {int(totaal_gewicht)} kg.")
    allowed_to_fly = True

usable_fuel = fuel_liters - RESERVE_FUEL_LITERS

# SIDEBAR: 2. Weer & Wind
st.sidebar.header("2. Wind & Weer (Kruishoogte)")
sim_temp = st.sidebar.slider("Buitentemperatuur (°C)", -10, 40, 15)
sim_qnh = st.sidebar.slider("Luchtdruk QNH (hPa)", 950, 1050, 1013)

st.sidebar.subheader("Meteo op Kruishoogte")
wind_direction = st.sidebar.selectbox("Windrichting vandaan", ["Noord", "Oost", "Zuid", "West"])
wind_speed = st.sidebar.slider("Windsnelheid (Knopen)", 0, 50, 15)

# SIDEBAR: 3. Vluchttijdstip
st.sidebar.header("3. Vluchttijdstip (Airspace)")
vlucht_dag = st.sidebar.radio("Geplande vluchtdag:", ["Weekend (Za/Zo)", "Doordeweeks (Ma-Vr)"])

st.sidebar.header("4. Uitje Voorkeuren")
max_landing_fee = st.sidebar.slider("Max. Landingsgeld (€)", 10, 150, 100)

# EXTENDED DATABASE v10
vliegvelden = {
    "EDXW": {
        "name": "Sylt", "lat": 54.913, "lon": 8.340, "runway": 1696, "track_from_ehle": 20, "crosses_edr99": True,
        "jet_a1": True, "landing_fee": 120, "opening_hours": "06:00 - 22:00 LT", "city_dist": "2 km (5 min taxi)",
        "gps_route": "EHLE DCT GORLO DCT NDO DCT EDXW", "info": "PPR verplicht in het weekend!"
    },
    "EDHL": {
        "name": "Lübeck", "lat": 53.805, "lon": 10.719, "runway": 2102, "track_from_ehle": 65, "crosses_edr99": False,
        "jet_a1": False, "landing_fee": 25, "opening_hours": "06:00 - 22:00 LT", "city_dist": "8 km (10 min trein)",
        "gps_route": "EHLE DCT GORLO DCT HAM DCT EDHL", "info": "Treinstation naast terminal. Momenteel geen Jet-A1!"
    },
    "EKRK": {
        "name": "Roskilde", "lat": 55.585, "lon": 12.131, "runway": 1500, "track_from_ehle": 40, "crosses_edr99": True,
        "jet_a1": True, "landing_fee": 35, "opening_hours": "07:00 - 22:00 LT", "city_dist": "6 km (15 min taxi)",
        "gps_route": "EHLE DCT GORLO DCT NDO DCT ALS DCT EKRK", "info": "Ideaal alternatief voor Kopenhagen Kastrup."
    },
    "EDWJ": {
        "name": "Juist (Waddeneiland)", "lat": 53.679, "lon": 6.990, "runway": 700, "track_from_ehle": 15, "crosses_edr99": False,
        "jet_a1": False, "landing_fee": 18, "opening_hours": "SR - SS", "city_dist": "0 km (Direct aan strand)",
        "gps_route": "EHLE DCT GORLO DCT JUIST", "info": "Autovrij eiland. Let op de korte baan!"
    },
    "EDVE": {
        "name": "Braunschweig", "lat": 52.319, "lon": 10.556, "runway": 2300, "track_from_ehle": 95, "crosses_edr99": False,
        "jet_a1": True, "landing_fee": 22, "opening_hours": "06:00 - 22:00 LT", "city_dist": "7 km (10 min bus)",
        "gps_route": "EHLE DCT GORLO DCT DLE DCT EDVE", "info": "Grote verharde baan, zeer GA-vriendelijk."
    },
    "EDDG": {
        "name": "Münster Osnabrück", "lat": 52.135, "lon": 7.684, "runway": 2170, "track_from_ehle": 120, "crosses_edr99": False,
        "jet_a1": True, "landing_fee": 45, "opening_hours": "24 HR H24", "city_dist": "25 km (20 min expressbus)",
        "gps_route": "EHLE DCT HMM DCT EDDG", "info": "Internationale luchthaven, Jet-A1 altijd beschikbaar."
    }
}

edr99_coords = [[53.5, 6.5], [54.2, 6.5], [54.2, 8.0], [53.5, 8.0]]

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return (R * c) * 0.539957

if allowed_to_fly:
    st.subheader("Strategisch Overzicht - Luchtruim & GPS Routing")
    
    m = folium.Map(location=[53.5, 8.5], zoom_start=7)
    folium.Marker([EHLE_LAT, EHLE_LON], popup="Vertrek: Lelystad", icon=folium.Icon(color="blue", icon="star")).add_to(m)

    # Airspace Status
    edr99_active = vlucht_dag == "Doordeweeks (Ma-Vr)"
    edr99_color = "red" if edr99_active else "gray"
    folium.Polygon(locations=edr99_coords, color=edr99_color, fill=True, fill_opacity=0.15).add_to(m)

    vliegveld_statussen = {}

    for icao, data in vliegvelden.items():
        distance_nm = calculate_distance_nm(EHLE_LAT, EHLE_LON, data["lat"], data["lon"])
        
        # Wind component
        headwind = 0
        if wind_direction == "Noord" and data["track_from_ehle"] < 90: headwind = wind_speed * 0.7
        elif wind_direction == "Oost" and 45 < data["track_from_ehle"] < 135: headwind = wind_speed
        elif wind_direction == "Zuid" or wind_direction == "West": headwind = -wind_speed * 0.5  

        ground_speed = CRUISE_SPEED_TAS - headwind
        flight_time_hours = distance_nm / ground_speed
        
        penalty_text = ""
        if edr99_active and data["crosses_edr99"]:
            flight_time_hours += (15 / 60)
            penalty_text = "⚠️ +15 min omvliegen wegens actieve ED-R 99."
            
        fuel_needed = flight_time_hours * FUEL_FLOW_LPH
        
        # Density Altitude Check
        temp_penalty = max(0, sim_temp - 15) * 0.01
        qnh_penalty = max(0, 1013 - sim_qnh) * 0.005
        needed_runway = BASE_RUNWAY_REQUIRED * (1 + temp_penalty + qnh_penalty)
        
        color = "green"
        reason = "✈️ Perfect haalbaar!"
        
        if fuel_needed > usable_fuel:
            color = "red"
            reason = "❌ BEREIK TE KORT"
        elif needed_runway > data["runway"]:
            color = "red"
            reason = "❌ BAAN TE KORT"
        elif data["landing_fee"] > max_landing_fee:
            color = "red"
            reason = "❌ LANDINGSGELD TE DUUR"
        elif not data["jet_a1"]:
            color = "orange"
            reason = "🟠 GÉÉN JET-A1"

        vliegveld_statussen[icao] = {"color": color, "reason": reason, "data": data, "time": int(flight_time_hours*60), "fuel": int(fuel_needed), "gs": int(ground_speed)}

        # Markers tekenen
        folium.Marker([data["lat"], data["lon"]], popup=data["name"], icon=folium.Icon(color=color, icon="plane")).add_to(m)
        folium.PolyLine([[EHLE_LAT, EHLE_LON], [data["lat"], data["lon"]]], color=color, weight=2).add_to(m)

    # Toon de kaart op het scherm
    st_folium(m, width=1100, height=400)

    # NIEUWE SCREEN LAYOUT: Overzichtelijke datablokken per vliegveld
    st.markdown("### 📋 Resultaten & Cockpit GPS Routes")
    
    for icao, status in vliegveld_statussen.items():
        with st.expander(f"✈️ {icao} - {status['data']['name']} ({status['reason']})"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.write(f"⏱️ **Vliegtijd:** {status['time']} min ({status['gs']} kt GS)")
                st.write(f"⛽ **Verbruik:** {status['fuel']} Liter")
                st.write(f"💰 **Landingsgeld:** €{status['data']['landing_fee']}")
            with col2:
                # Hier staat de GPS route nu in een prachtig, opvallend code-vak!
                st.info(f"📍 **Garmin G1000 GPS Route:**")
                st.code(status['data']['gps_route'], language="text")
                st.write(f"🏙️ **Logistiek:** {status['data']['city_dist']} | {status['data']['info']}")

    # Smart Alternate Advisor
    st.markdown("---")
    st.header("💡 Smart Alternate Advisor")
    rode_velden = {k: v for k, v in vliegveld_statussen.items() if v["color"] == "red"}
    groene_velden = {k: v for k, v in vliegveld_statussen.items() if v["color"] == "green"}
    
    if rode_velden:
        for icao, status in rode_velden.items():
            st.error(f"⚠️ **{status['data']['name']} ({icao})** is vandaag ROOD. Reden: {status['reason']}.")
            if groene_velden:
                st.info("🔮 **Voorgestelde Uitwijk-bestemmingen:**")
                for g_icao, g_status in groene_velden.items():
                    st.success(f"👉 Koers wijzigen naar **{g_status['data']['name']} ({g_icao})** (Operationeel Groen). GPS Route: `{g_status['data']['gps_route']}`")
    else:
        st.success("🎉 Alle vliegvelden in de database zijn vandaag groen licht!")
        
else:
    st.warning("Pas de parameters aan om de gewichtsstatus te corrigeren.")
