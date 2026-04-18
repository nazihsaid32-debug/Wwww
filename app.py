import streamlit as st
import pandas as pd
from datetime import datetime, time
import plotly.express as px

# 1. Configuration de la page
st.set_page_config(page_title="AKHFENNIRE 1 - Report Manager", layout="wide")

# 2. Design de l'interface (Bienvenue & Logo)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("https://static.wixstatic.com/media/bbe160_691ccb3c43634bc586a0c7d25b4ad47b~mv2.jpg", width=250)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Bienvenue</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Ajustement des alarmes AKHFENNIRE 1</h3>", unsafe_allow_html=True)

st.markdown("---")

# 3. Barre latérale (Sidebar) - Filtre Date & Cas Spécial
st.sidebar.header("🗓️ Sélection du Jour")
target_date = st.sidebar.date_input("Choisir le jour de travail", datetime.now())

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Cas Spécial")

list_wtg = [f"WTG{str(i).zfill(2)}" for i in range(1, 62)]
selected_wtgs = st.sidebar.multiselect("Turbines impactées", list_wtg)

m_start_time = st.sidebar.time_input("Heure Début", time(0, 0))
m_end_time = st.sidebar.time_input("Heure Fin", time(23, 59))
m_impact_type = st.sidebar.radio("Nature de l'impact", ["Déclenchement", "Bridage"])
m_resp = st.sidebar.selectbox("Responsabilité", ["EEM", "GE", "ONEE", "Autres"])

# 4. Base de données des Alarmes
base_rules = {
    'BackWind': 'EEM', 'AnemCheck': 'WTG', 'HiTemAux1': 'WTG',
    'ManualStop': 'WTG', 'Corrective maintenance': 'WTG', 'Out of Grid': 'ONEE'
}

# 5. Zone de téléchargement
uploaded_file = st.file_uploader("📂 Charger le fichier excel des alarmes", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # تحويل التواريخ
    df['Start'] = pd.to_datetime(df['Start Data and Time'], dayfirst=True)
    df['End'] = pd.to_datetime(df['End Date and Time'], dayfirst=True)
    
    # الفلترة اليومية والقص الزمني (00:00 إلى 23:59)
    day_start = datetime.combine(target_date, time(0, 0, 0))
    day_end = datetime.combine(target_date, time(23, 59, 59))
    
    df = df[(df['Start'] <= day_end) & (df['End'] >= day_start)].copy()
    df['Start'] = df['Start'].clip(lower=day_start)
    df['End'] = df['End'].clip(upper=day_end)
    
    df = df.sort_values(['WTG0', 'Start'])
    
    processed_rows = []

    for wtg, group in df.groupby('WTG0'):
        if group.empty: continue
        
        c_s, c_e, c_a = group.iloc[0]['Start'], group.iloc[0]['End'], group.iloc[0]['Alarm text']
        
        for i in range(1, len(group)):
            row = group.iloc[i]
            if row['Start'] <= c_e:
                c_e = max(c_e, row['End'])
            else:
                resp = base_rules.get(c_a, 'WTG')
                impact = "-"
                if wtg in selected_wtgs:
                    ms, me = datetime.combine(target_date, m_start_time), datetime.combine(target_date, m_end_time)
                    if not (c_e <= ms or c_s >= me):
                        resp, impact = m_resp, m_impact_type

                processed_rows.append([wtg, c_a, c_s, c_e, resp, impact])
                c_s, c_e, c_a = row['Start'], row['End'], row['Alarm text']
        
        processed_rows.append([wtg, c_a, c_s, c_e, base_rules.get(c_a, 'WTG'), "-"])

    result_df = pd.DataFrame(processed_rows, columns=['WTG', 'Alarm', 'Start', 'Fin', 'Responsibility', 'Type Impact'])
    result_df['Duration_Hrs'] = (result_df['Fin'] - result_df['Start']).dt.total_seconds() / 3600

    # عرض جدول البيانات
    st.subheader(f"✅ Analyse des alarmes - {target_date}")
    st.dataframe(result_df)

    st.markdown("---")
    st.header("📊 Rapport Journalier (Visualisation)")

    # --- الجزء الأول: منحنى ساعات التشغيل لكل توربين ---
    # نحسب إجمالي ساعات التوقف لكل توربين وننقصها من 24
    downtime = result_df.groupby('WTG')['Duration_Hrs'].sum().reset_index()
    # التأكد من شمول جميع التوربينات حتى التي لم تتوقف (ساعاتها 24)
    all_wtgs_df = pd.DataFrame({'WTG': list_wtg})
    final_stats = pd.merge(all_wtgs_df, downtime, on='WTG', how='left').fillna(0)
    final_stats['Operating_Hrs'] = 24 - final_stats['Duration_Hrs']
    final_stats['Operating_Hrs'] = final_stats['Operating_Hrs'].clip(lower=0)

    fig_bar = px.bar(final_stats, x='WTG', y='Operating_Hrs', 
                     title="Heures de fonctionnement par Turbine (Max 24h)",
                     labels={'Operating_Hrs': 'Heures de Marche'},
                     color='Operating_Hrs', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar, use_container_width=True)

    # --- الجزء الثاني: دائرة الأعطال الأكثر تكراراً ---
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        alarm_counts = result_df['Alarm'].value_counts().reset_index()
        alarm_counts.columns = ['Alarm', 'Count']
        fig_pie = px.pie(alarm_counts, values='Count', names='Alarm', 
                         title="Répartition des Alarmes par Fréquence (%)",
                         hole=0.4)
        st.plotly_chart(fig_pie)

    with col_chart2:
        # إحصائية بسيطة
        st.info(f"**Résumé du jour:**\n\n"
                f"- Total Turbines impactées: {len(downtime)}\n"
                f"- Alarme la plus fréquente: {alarm_counts.iloc[0]['Alarm'] if not alarm_counts.empty else 'N/A'}\n"
                f"- Moyenne de disponibilité: {final_stats['Operating_Hrs'].mean():.2f} Heures")

    # زر التنزيل
    output_name = f"Rapport_Journalier_AKH1_{target_date}.xlsx"
    result_df.to_excel(output_name, index=False)
    with open(output_name, "rb") as f:
        st.download_button("📥 Télécharger le Rapport Excel", f, file_name=output_name)
