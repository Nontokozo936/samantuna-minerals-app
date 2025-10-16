from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import plotly.express as px
import folium
import json
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'secretkey123'  # Secure session key

# -------------------- FILE PATHS --------------------
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
COUNTRIES_FILE = os.path.join(DATA_DIR, "countries.csv")
MINERALS_FILE = os.path.join(DATA_DIR, "minerals.csv")
PRODUCTION_FILE = os.path.join(DATA_DIR, "production.csv")

# -------------------- LOAD FUNCTIONS --------------------
def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def load_country_data():
    return pd.read_csv(COUNTRIES_FILE)

def load_mineral_data():
    return pd.read_csv(MINERALS_FILE)

def load_production_data():
    return pd.read_csv(PRODUCTION_FILE)

# Combine datasets
def load_combined_production_data():
    countries = load_country_data()
    minerals = load_mineral_data()
    production = load_production_data()

    df = production.merge(countries, on="CountryID").merge(minerals, on="MineralID")

    df = df.rename(columns={
        "CountryName": "Country",
        "MineralName": "Mineral",
        "Production_tonnes": "Production (Tonnes)",
        "ExportValue_BillionUSD": "Export Value (Billion USD)"
    })
    return df

# -------------------- LOGIN PROTECTION --------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------- AUTH ROUTES --------------------
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form['username']
    password = request.form['password']
    users = load_users()
    for user in users:
        if user['username'] == username and user['password'] == password:
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
    return render_template('login.html', error="Invalid username or password")

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# -------------------- DASHBOARD --------------------
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=session['username'], role=session['role'])

# -------------------- COUNTRIES --------------------
@app.route('/countries')
@login_required
def country_list():
    df = load_country_data()
    return render_template('countries.html', countries=df.to_dict(orient='records'))

@app.route('/country/<country_name>')
@login_required
def country_profile(country_name):
    df = load_country_data()
    row = df[df['CountryName'] == country_name]
    if row.empty:
        return render_template('country.html', error="Country not found.")
    info = row.iloc[0]
    return render_template(
        'country.html',
        country=info['CountryName'],
        gdp=info['GDP_BillionUSD'],
        revenue=info['MiningRevenue_BillionUSD'],
        project=info['KeyProjects']
    )

# -------------------- MINERALS --------------------
@app.route('/minerals')
@login_required
def mineral_list():
    df = load_mineral_data()
    return render_template('minerals.html', minerals=df.to_dict(orient='records'))

@app.route('/mineral/<mineral_name>')
@login_required
def mineral_profile(mineral_name):
    df = load_mineral_data()
    row = df[df['MineralName'] == mineral_name]
    if row.empty:
        return render_template('mineral.html', error="Mineral not found.")
    info = row.iloc[0]
    return render_template(
        'mineral.html',
        mineral=info['MineralName'],
        description=info['Description'],
        price=info['MarketPriceUSD_per_tonne']
    )

# -------------------- PRODUCTION --------------------
@app.route('/production')
@login_required
def production_list():
    df = load_combined_production_data()
    return render_template('production.html', production=df.to_dict(orient='records'))

@app.route('/chart')
@login_required
def production_chart():
    df = load_combined_production_data()
    fig = px.bar(
        df,
        x="Country",
        y="Production (tonnes)",
        color="Mineral",
        facet_col="Year",
        barmode="group",
        title="Annual Mineral Production by Country and Mineral"
    )
    chart_html = fig.to_html(full_html=False)
    return render_template('chart.html', chart=chart_html)

# -------------------- MAP --------------------
@app.route('/map')
@login_required
def map_view():
    df = load_country_data()
    m = folium.Map(location=[-10, 25], zoom_start=3)
    for _, row in df.iterrows():
        popup_info = f"<b>{row['CountryName']}</b><br>GDP: {row['GDP_BillionUSD']} B USD<br>Mining Revenue: {row['MiningRevenue_BillionUSD']} B USD<br>Project: {row['KeyProjects']}"
        folium.Marker(
            location=[-10 + _ * 2, 20 + _ * 3],  # placeholder coordinates
            popup=popup_info
        ).add_to(m)
    map_html = m._repr_html_()
    return render_template('map.html', map=map_html)

# -------------------- ADMIN UPLOAD --------------------
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if session['role'] != 'Admin':
        return redirect(url_for('dashboard'))

    message = ""
    if request.method == 'POST':
        update_type = request.form['updateType']
        file = request.files['file']
        if file:
            save_path = os.path.join(DATA_DIR, file.filename)
            file.save(save_path)

            if update_type == "minerals":
                os.replace(save_path, MINERALS_FILE)
                message = " Minerals database updated successfully!"
            elif update_type == "countries":
                os.replace(save_path, COUNTRIES_FILE)
                message = " Countries data updated successfully!"
            elif update_type == "production":
                os.replace(save_path, PRODUCTION_FILE)
                message = " Production data updated successfully!"

    return render_template('upload.html', message=message)

# -------------------- MAIN --------------------
if __name__ == "__main__":
    app.run(debug=True)
