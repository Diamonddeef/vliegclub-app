import streamlit as st
import folium
from streamlit_folium import st_folium
import math

# --- CONFIGURATIE DIAMOND DA40 TDI ---
AIRCRAFT_EMPTY_WEIGHT = 800  # kg
AIRCRAFT_MTOW = 1150         # kg
FUEL_LITERS_TO_KG = 0.84     # Jet-A1
BASE_RUNWAY_REQUIRED = 650   # meter
CRUISE_SPEED_TAS = 120       # Knopen (True Airspeed)
FUEL_FLOW_LPH = 20           
RESERVE_FUEL_LITERS = 15     

EHLE_LAT, EHLE_LON = 52.460, 5.527  # Lelystad

st.set_page_config(layout="wide")

# ==================================================
# STAP 1: HET INLOGSCHERM (BEVEILIGING)
# ==================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Diamond DA40 Dispatcher - Beveiligde Toegang")
    st.write("Voer het clubwachtwoord in om toegang te krijgen tot de strategische planner.")
    
    wachtwoord_input = st.text_input("Wachtwoord", type="password")
    
    if st.button("Inloggen"):
        if wachtwoord_input == "Hestknappen":
            st.session_state["authenticated"] = True
            st.success("Wachtwoord correct! Applicatie wordt geladen...")
            st.rerun()
        else:
            st.error("Onjuist wachtwoord. Toegang geweigerd.")
    st.stop() # Stopt de code hier zodat de rest onzichtbaar blijft!

# ==================================================
# DE APPLICATIE (Wordt pas uitgevoerd na succesvol inloggen)
# ==================================================
st.title("✈️ Diamond DA40 TDI - Cockpit Dispatcher v7")

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

# SIDEBAR: 3. Budget Filter
st.sidebar.header("3. Uitje Voorkeuren")
max_landing_fee = st.sidebar.slider("Max. Landingsgeld (€)", 10, 150, 100)

# DATABASE
vliegvelden = {
    "EDXW": {
        "name": "Sylt", "lat": 54.913, "lon": 8.340, "runway": 1696, "track_from_ehle": 20,
        "jet_a1": True, "landing_fee": 120, "opening_hours": "06:00 - 22:00 LT",
        "city_dist": "2 km (5 min met taxi tot Westerland centrum)", "info": "PPR verplicht in het weekend!"
    },
    "EDHL": {
        "name": "Lübeck", "lat": 53.805, "lon": 10.719, "runway": 2102, "track_from_ehle": 65,
        "jet_a1": False, "landing_fee": 25, "opening_hours": "06:00 - 22:00 LT",
        "city_dist": "8 km (10 min met de trein vanaf het vliegveldveld-station)", "info": "Treinstation ligt direct naast de terminal."
    },
    "EKRK": {
        "name": "Roskilde", "lat": 55.585, "lon": 12.131, "runway": 1500, "track_from_ehle": 40,
        "jet_a1": True, "landing_fee": 35, "opening_hours": "07:00 - 22:00 LT",
        "city_dist": "6 km (40 min met OV / 15 min met taxi tot Kopenhagen centrum)", "info": "Uitstekend alternatief voor Kopenhagen Kastrup."
    }
}

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return (R * c) * 0.539957

if allowed_to_fly:
    st.subheader("Strategisch Overzicht van de Weekend-Opties vanaf Lelystad")
    
    m = folium.Map(location=[54.0, 9.0], zoom_start=7)
    folium.Marker([EHLE_LAT, EHLE_LON], popup="Vertrek: Lelystad", icon=folium.Icon(color="blue", icon="star")).add_to(m)

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

        # Kaart markers
        popup_text = f"<b>{data['name']} ({icao})</b><br>Landingsgeld: €{data['landing_fee']}<br>Vliegtijd: {int(flight_time_hours*60)} min"
        folium.Marker([data["lat"], data["lon"]], popup=popup_text, icon=folium.Icon(color=color, icon="plane")).add_to(m)
        folium.PolyLine([[EHLE_LAT, EHLE_LON], [data["lat"], data["lon"]]], color=color, weight=2).add_to(m)
        
        # Informatieblokken
        with st.expander(f"{icao} - {data['name']} ({reason})"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Vliegtijd", f"{int(flight_time_hours*60)} min", f"{int(ground_speed)} kt GS")
                st.metric("Brandstof", f"{int(fuel_needed)} Liter", f"{int(usable_fuel - fuel_needed)}L marge")
            with col2:
                st.metric("Landingsgeld", f"€{data['landing_fee']}")
                st.write(f"⏰ **Openingstijden:** {data['opening_hours']}")
            with col3:
                st.write(f"🏙️ **Stadscentrum:** {data['city_dist']}")
                st.write(f"ℹ️ **Opmerking:** {data['info']}")
                
    st_folium(m, width=1100, height=400)

    # Export sectie
    st.markdown("---")
    st.subheader("📋 Genereer Cockpit Briefing Sheet")
    
    if export_opties:
        gekozen_veld = st.selectbox("Selecteer je goedgekeurde bestemming voor export:", [f"{o[0]} - {o[1]}" for o in export_opties])
        sel = [o for o in export_opties if f"{o[0]} - {o[1]}" == gekozen_veld][0]
        
        briefing_text = f"""==================================================
         PRE-FLIGHT BRIEFING SHEET (DA40 TDI)
==================================================
VERTREK: Lelystad Airport (EHLE)
BESTEMMING: {sel[1]} ({sel[0]})
--------------------------------------------------
GEWICHT & BALANS:
- Vliegtuig Leeggewicht: {AIRCRAFT_EMPTY_WEIGHT} kg
- Inzittenden ({pax_count} pax): {pax_weight} kg
- Brandstof aan boord ({fuel_liters}L Jet-A1): {int(fuel_weight)} kg
- TOTAAL STARTGEWICHT: {int(totaal_gewicht)} kg (Max: {AIRCRAFT_MTOW} kg)
--------------------------------------------------
NAVIGATIE & PRESTATIES (SIMULATIE):
- Afstand: {int(sel[2])} NM
- Verwachte Snelheid over de grond (GS): {int(sel[5])} knopen
- GESCHATTE VLIEGTIJD: {int(sel[3]*60)} minuten
- BENODIGDE BRANDSTOF: {int(sel[4])} liter Jet-A1
- OVERIG NA LANDING: {int(fuel_liters - sel[4])} liter (Reserve: {RESERVE_FUEL_LITERS}L)
- BENODIGDE STARTBAAN (EHLE): {int(sel[6])} meter (bij {sim_temp}°C / {sim_qnh} hPa)
--------------------------------------------------
BESTEMMINGSINFORMATIE:
- Landingsgeld: €{sel[7]['landing_fee']}
- Openingstijden: {sel[7]['opening_hours']}
- Jet-A1 Beschikbaar: {'JA' if sel[7]['jet_a1'] else 'NEE (LET OP!)'}
- Logistiek: {sel[7]['city_dist']}
- Extra info: {sel[7]['info']}
=================================================="""

        st.download_button(
            label="📥 Download Briefing Sheet (.txt)",
            data=briefing_text,
            file_name=f"briefing_{sel[0]}.txt",
            mime="text/plain"
        )
        st.code(briefing_text, language="text")
    else:
        st.warning("Er zijn op dit moment geen haalbare vliegvelden om te exporteren met de huidige instellingen.")
else:
    st.warning("Pas de parameters aan om de gewichtsstatus te corrigeren.")
