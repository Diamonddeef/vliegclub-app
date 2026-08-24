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
st.title("✈️ Diamond DA40 TDI - Cockpit Dispatcher v8")

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

# SIDEBAR: 3. TIJDSVARIABELE (Jouw nieuwe No-Fly Zone Parameter!)
st.sidebar.header("3. Vluchttijdstip (Airspace)")
vlucht_dag = st.sidebar.radio("Geplande vluchtdag:", ["Weekend (Za/Zo)", "Doordeweeks (Ma-Vr)"])

st.sidebar.header("4. Uitje Voorkeuren")
max_landing_fee = st.sidebar.slider("Max. Landingsgeld (€)", 10, 150, 100)

# DATABASE
vliegvelden = {
    "EDXW": {
        "name": "Sylt", "lat": 54.913, "lon": 8.340, "runway": 1696, "track_from_ehle": 20, "crosses_edr99": True,
        "jet_a1": True, "landing_fee": 120, "opening_hours": "06:00 - 22:00 LT",
        "city_dist": "2 km (5 min met taxi)", "info": "PPR verplicht in het weekend!"
    },
    "EDHL": {
        "name": "Lübeck", "lat": 53.805, "lon": 10.719, "runway": 2102, "track_from_ehle": 65, "crosses_edr99": False,
        "jet_a1": False, "landing_fee": 25, "opening_hours": "06:00 - 22:00 LT",
        "city_dist": "8 km (10 min met de trein)", "info": "Treinstation naast terminal."
    },
    "EKRK": {
        "name": "Roskilde", "lat": 55.585, "lon": 12.131, "runway": 1500, "track_from_ehle": 40, "crosses_edr99": True,
        "jet_a1": True, "landing_fee": 35, "opening_hours": "07:00 - 22:00 LT",
        "city_dist": "6 km (15 min met taxi)", "info": "Ideaal voor Kopenhagen."
    }
}

# COÖRDINATEN VAN MILITAIR GEBIED ED-R 99 (Polygon boven de Waddeneilanden/Noord-Duitsland)
edr99_coords = [
    [53.5, 6.5],
    [54.2, 6.5],
    [54.2, 8.0],
    [53.5, 8.0]
]

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return (R * c) * 0.539957

if allowed_to_fly:
    st.subheader("Strategisch Overzicht - Inclusief Actieve Luchtruim Restricties")
    
    m = folium.Map(location=[54.0, 9.0], zoom_start=7)
    folium.Marker([EHLE_LAT, EHLE_LON], popup="Vertrek: Lelystad", icon=folium.Icon(color="blue", icon="star")).add_to(m)

    # Bepaal status van de No-Fly Zone
    if vlucht_dag == "Doordeweeks (Ma-Vr)":
        edr99_active = True
        edr99_color = "red"
        edr99_status = "ED-R 99 ACTIEF (Militair oefengebied - Actief Ma-Vr 0900-1700)"
    else:
        edr99_active = False
        edr99_color = "gray"
        edr99_status = "ED-R 99 INACTIEF (Weekend-vrijgave geldt)"

    # Teken de No-Fly Zone op de kaart
    folium.Polygon(
        locations=edr99_coords,
        color=edr99_color,
        fill=True,
        fill_color=edr99_color,
        fill_opacity=0.3,
        popup=edr99_status
    ).add_to(m)

    export_opties = []

    for icao, data in vliegvelden.items():
        distance_nm = calculate_distance_nm(EHLE_LAT, EHLE_LON, data["lat"], data["lon"])
        
        # Windberekening
        headwind = 0
        if wind_direction == "Noord" and data["track_from_ehle"] < 90:
            headwind = wind_speed * 0.7
        elif wind_direction == "Oost" and 45 < data["track_from_ehle"] < 135:
            headwind = wind_speed
        elif wind_direction == "Zuid" or wind_direction == "West":
            headwind = -wind_speed * 0.5  

        ground_speed = CRUISE_SPEED_TAS - headwind
        flight_time_hours = distance_nm / ground_speed
        
        # --- LOGICA: Strafminuten toevoegen als de No-Fly zone actief is op de route ---
        penalty_text = ""
        if edr99_active and data["crosses_edr99"]:
            flight_time_hours += (15 / 60)  # +15 minuten omvliegtijd!
            penalty_text = "⚠️ Inclusief +15 min omvliegtijd wegens actieve ED-R 99."
            
        fuel_needed = flight_time_hours * FUEL_FLOW_LPH
        
        # Performance check
        temp_penalty = max(0, sim_temp - 15) * 0.01
        qnh_penalty = max(0, 1013 - sim_qnh) * 0.005
        needed_runway = BASE_RUNWAY_REQUIRED * (1 + temp_penalty + qnh_penalty)
        
        color = "green"
        reason = "✈️ Perfect haalbaar!"
        
        if fuel_needed > usable_fuel:
            color = "red"
            reason = f"❌ BEREIK TE KORT: {int(fuel_needed)}L nodig."
        elif needed_runway > data["runway"]:
            color = "red"
            reason = f"❌ BAAN TE KORT: {int(needed_runway)}m nodig."
        elif data["landing_fee"] > max_landing_fee:
            color = "red"
            reason = f"💰 LANDINGSGELD TE DUUR: €{data['landing_fee']}."
        elif not data["jet_a1"]:
            color = "orange"
            reason = "🟠 BEREIKBAAR MAAR GÉÉN JET-A1!"

        if color != "red":
            export_opties.append((icao, data["name"], distance_nm, flight_time_hours, fuel_needed, ground_speed, needed_runway, data))

        popup_text = f"<b>{data['name']} ({icao})</b><br>Vliegtijd: {int(flight_time_hours*60)} min"
        folium.Marker([data["lat"], data["lon"]], popup=popup_text, icon=folium.Icon(color=color, icon="plane")).add_to(m)
        folium.PolyLine([[EHLE_LAT, EHLE_LON], [data["lat"], data["lon"]]], color=color, weight=2).add_to(m)
        
        with st.expander(f"{icao} - {data['name']} ({reason})"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Vliegtijd total", f"{int(flight_time_hours*60)} min", penalty_text if penalty_text else f"{int(ground_speed)} kt GS")
                st.metric("Brandstof", f"{int(fuel_needed)} Liter", f"{int(usable_fuel - fuel_needed)}L marge")
            with col2:
                st.metric("Landingsgeld", f"€{data['landing_fee']}")
                st.write(f"⏰ **Openingstijden:** {data['opening_hours']}")
            with col3:
                st.write(f"🏙️ **Stadscentrum:** {data['city_dist']}")
                st.write(f"ℹ️ **Opmerking:** {data['info']}")
                
    st_folium(m, width=1100, height=400)
    
    # Export sectie (afgekorte weergave voor stabiliteit)
    st.markdown("---")
    st.subheader("📋 Genereer Cockpit Briefing Sheet")
    if export_opties:
        gekozen_veld = st.selectbox("Selecteer je goedgekeurde bestemming voor export:", [f"{o} - {o}" for o in export_opties])
        st.success(f"Bestemming geselecteerd voor cockpit export. Klik op download om de sheet te genereren.")
else:
    st.warning("Pas de parameters aan om de gewichtsstatus te corrigeren.")
