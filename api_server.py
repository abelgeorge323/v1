#!/usr/bin/env python3
"""
MIT Candidate Dashboard API Server
Serves Google Sheets data as JSON API for HTML frontend
"""

import pandas as pd
import hashlib
import random
from flask import Flask, jsonify, send_file
from flask_cors import CORS
import os

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for HTML frontend

# ---- DATA LOADING FUNCTIONS (from original app.py) ----
def load_data():
    """Load data from Google Sheets"""
    main_data_url = (
        "https://docs.google.com/spreadsheets/d/e/"
        "2PACX-1vTAdbdhuieyA-axzb4aLe8c7zdAYXBLPNrIxKRder6j1ZAlj2g4U1k0YzkZbm_dEcSwBik4CJ57FROJ/"
        "pub?gid=813046237&single=true&output=csv"
    )
    try:
        df = pd.read_csv(main_data_url, skiprows=1)  # Skip only the first row with "Training info"
        data_source = "Google Sheets"
    except Exception as e:
        print(f"⚠️ Google Sheets error: {e}")
        return pd.DataFrame(), "Error"

    df = df.dropna(how="all")
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    
    # Convert Status to lowercase like in original app.py
    df["Status"] = df["Status"].astype(str).str.strip().str.lower()
    
    return df, data_source

def load_jobs_data():
    """Load jobs data from Google Sheets"""
    # ✅ Correct Open Jobs Google Sheets URL from original app.py
    jobs_url = (
        "https://docs.google.com/spreadsheets/d/e/"
        "2PACX-1vSbD6wUrZEt9kuSQpUT2pw0FMOb7h1y8xeX-hDTeiiZUPjtV0ohK_WcFtCSt_4nuxdtn9zqFS8z8aGw/"
        "pub?gid=116813539&single=true&output=csv"
    )
    try:
        jobs_df = pd.read_csv(jobs_url, skiprows=5, header=0)
        jobs_df = jobs_df.loc[:, ~jobs_df.columns.str.contains("^Unnamed")]
        jobs_df = jobs_df.drop(columns=[c for c in ["JV Link", "JV ID"] if c in jobs_df.columns], errors="ignore")
        jobs_df = jobs_df.dropna(how="all").fillna("")
        return jobs_df
    except Exception as e:
        print(f"⚠️ Jobs data error: {e}")
        return pd.DataFrame()

def parse_salary(salary_value):
    """Parse salary from various formats to numeric value"""
    if pd.isna(salary_value):
        return 0
    
    # If already numeric, return it
    if isinstance(salary_value, (int, float)):
        return float(salary_value)
    
    # If string, clean it up
    if isinstance(salary_value, str):
        # Remove $, commas, and whitespace
        cleaned = salary_value.replace('$', '').replace(',', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0
    
    return 0

def generate_mock_scores(candidate_name):
    """Generate consistent mock scores based on candidate name"""
    # Use hash of name to ensure consistent scores
    hash_obj = hashlib.md5(candidate_name.encode())
    seed = int(hash_obj.hexdigest()[:8], 16)
    random.seed(seed)

    scores = {
        'qbr_score': random.randint(65, 90),
        'assessment_score': random.randint(70, 95),
        'performance_score': random.randint(75, 95),
        'confidence_score': random.randint(70, 90),
        'skill_ranking': random.choice(['Top 10%', 'Top 15%', 'Top 20%', 'Top 25%'])
    }
    random.seed()  # Reset random seed
    return scores

# ---- MAIN ROUTE ----

@app.route('/')
def serve_dashboard():
    """Serve the main dashboard HTML page"""
    return send_file('index.html')

# ---- API ENDPOINTS ----

@app.route('/api/dashboard-data')
def get_dashboard_data():
    """API endpoint for dashboard metrics"""
    try:
        # Load data
        df, data_source = load_data()
        jobs_df = load_jobs_data()
        
        if df.empty:
            return jsonify({'error': 'No data available'}), 500
        
        # Calculate metrics using CORRECT logic from original app.py
        
        # Debug: Print unique status values to understand the data
        print(f"DEBUG: Unique status values: {df['Status'].unique()}")
        
        # Offer Pending and Offer Accepted
        offer_pending = len(df[df["Status"] == "offer pending"])
        offer_accepted = len(df[df["Status"] == "offer accepted"])
        
        # Non-identified candidates (free agent, unassigned, training)
        non_identified = len(df[df["Status"].isin(["free agent discussing opportunity", "unassigned", "training"])])
        total_candidates = non_identified + offer_accepted
        
        # Ready for Placement: Week > 6 AND Status NOT IN ["position identified", "offer pending", "offer accepted"]
        ready_for_placement = df[
            df["Week"].apply(lambda x: isinstance(x, (int, float)) and x > 6)
            & (~df["Status"].isin(["position identified", "offer pending", "offer accepted"]))
        ]
        ready_count = len(ready_for_placement)
        
        # In Training: Status == "training" AND Week <= 6
        in_training = len(
            df[df["Status"].eq("training") & df["Week"].apply(lambda x: isinstance(x, (int, float)) and x <= 6)]
        )
        
        # Real open jobs count from Google Sheets
        open_jobs = len(jobs_df) if not jobs_df.empty else 0
        
        return jsonify({
            'total_candidates': total_candidates,
            'ready_for_placement': ready_count,
            'in_training': in_training,
            'offer_pending': offer_pending,
            'open_jobs': open_jobs,
            'data_source': data_source
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/candidates')
def get_candidates():
    """API endpoint for candidate list"""
    try:
        df, _ = load_data()
        
        if df.empty:
            return jsonify([])
        
        # Get ready for placement candidates using CORRECT logic
        ready_candidates = df[
            df["Week"].apply(lambda x: isinstance(x, (int, float)) and x > 6)
            & (~df["Status"].isin(["position identified", "offer pending", "offer accepted"]))
        ]
        
        candidates = []
        for _, row in ready_candidates.iterrows():
            # Handle NaN values properly
            week_value = row.get('Week', '—')
            if pd.isna(week_value):
                week_value = '—'
            
            salary_value = parse_salary(row.get('Salary', 0))
            
            candidates.append({
                'name': row['MIT Name'],
                'training_site': row.get('Training Site', '—'),
                'location': row.get('Location', '—'),
                'week': week_value,
                'level': row.get('Level', '—'),
                'salary': salary_value
            })
        
        return jsonify(candidates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/candidate/<name>')
def get_candidate_profile(name):
    """API endpoint for individual candidate profile"""
    try:
        df, _ = load_data()
        
        if df.empty:
            return jsonify({'error': 'No data available'}), 500
        
        # Find candidate
        candidate = df[df['MIT Name'] == name]
        
        if candidate.empty:
            return jsonify({'error': 'Candidate not found'}), 404
        
        row = candidate.iloc[0]
        mock_scores = generate_mock_scores(name)
        
        # Handle NaN values properly
        week_value = row.get('Week', '—')
        if pd.isna(week_value):
            week_value = '—'
        
        salary_value = parse_salary(row.get('Salary', 0))
        
        return jsonify({
            'name': row['MIT Name'],
            'training_site': row.get('Training Site', '—'),
            'location': row.get('Location', '—'),
            'week': week_value,
            'level': row.get('Level', '—'),
            'salary': salary_value,
            'scores': mock_scores
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/all-candidates')
def get_all_candidates():
    """API endpoint for all candidates"""
    try:
        df, _ = load_data()
        
        if df.empty:
            return jsonify([])
        
        # Offer Pending and Offer Accepted
        offer_accepted = df[df["Status"] == "offer accepted"]
        
        # Non-identified candidates (free agent, unassigned, training)
        non_identified = df[df["Status"].isin(["free agent discussing opportunity", "unassigned", "training"])]
        
        # Combine for all candidates
        all_candidates_df = pd.concat([non_identified, offer_accepted])
        
        candidates = []
        for _, row in all_candidates_df.iterrows():
            # Handle NaN values properly
            week_value = row.get('Week', '—')
            if pd.isna(week_value):
                week_value = '—'
            
            salary_value = parse_salary(row.get('Salary', 0))
            
            candidates.append({
                'name': row['MIT Name'],
                'training_site': row.get('Training Site', '—'),
                'location': row.get('Location', '—'),
                'week': week_value,
                'level': row.get('Level', '—'),
                'status': row.get('Status', '—'),
                'salary': salary_value
            })
        
        return jsonify(candidates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/in-training-candidates')
def get_in_training_candidates():
    """API endpoint for in training candidates"""
    try:
        df, _ = load_data()
        
        if df.empty:
            return jsonify([])
        
        # In Training: Status == "training" AND Week <= 6
        in_training = df[
            df["Status"].eq("training") & df["Week"].apply(lambda x: isinstance(x, (int, float)) and x <= 6)
        ]
        
        candidates = []
        for _, row in in_training.iterrows():
            # Handle NaN values properly
            week_value = row.get('Week', '—')
            if pd.isna(week_value):
                week_value = '—'
            
            salary_value = parse_salary(row.get('Salary', 0))
            
            candidates.append({
                'name': row['MIT Name'],
                'training_site': row.get('Training Site', '—'),
                'location': row.get('Location', '—'),
                'week': week_value,
                'level': row.get('Level', '—'),
                'salary': salary_value
            })
        
        return jsonify(candidates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/offer-pending-candidates')
def get_offer_pending_candidates():
    """API endpoint for offer pending candidates"""
    try:
        df, _ = load_data()
        
        if df.empty:
            return jsonify([])
        
        # Offer Pending: Status == "offer pending"
        offer_pending = df[df["Status"] == "offer pending"]
        
        candidates = []
        for _, row in offer_pending.iterrows():
            # Handle NaN values properly
            week_value = row.get('Week', '—')
            if pd.isna(week_value):
                week_value = '—'
            
            salary_value = parse_salary(row.get('Salary', 0))
            
            candidates.append({
                'name': row['MIT Name'],
                'training_site': row.get('Training Site', '—'),
                'location': row.get('Location', '—'),
                'week': week_value,
                'level': row.get('Level', '—'),
                'salary': salary_value
            })
        
        return jsonify(candidates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/open-positions')
def get_open_positions():
    """API endpoint for open positions"""
    try:
        jobs_df = load_jobs_data()
        
        if jobs_df.empty:
            return jsonify([])
        
        positions = []
        for _, row in jobs_df.iterrows():
            positions.append({
                'job_title': row.get('Job Title', '—'),
                'account': row.get('Account', '—'),
                'city': row.get('City', '—'),
                'state': row.get('State', '—'),
                'vertical': row.get('VERT', '—'),
                'salary': row.get('Salary', '—')
            })
        
        return jsonify(positions)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'MIT Dashboard API is running'})

# ---- MAIN ----
if __name__ == "__main__":
    print("Starting MIT Dashboard API Server...")
    print("API Endpoints:")
    print("   - GET /api/dashboard-data - Dashboard metrics")
    print("   - GET /api/candidates - Ready for placement candidates")
    print("   - GET /api/candidate/<name> - Individual candidate profile")
    print("   - GET /api/all-candidates - All candidates")
    print("   - GET /api/in-training-candidates - In training candidates")
    print("   - GET /api/offer-pending-candidates - Offer pending candidates")
    print("   - GET /api/open-positions - Open job positions")
    print("   - GET /api/health - Health check")
    print("\nAPI Server running on: http://localhost:5000")
    print("Open your HTML file to use the dashboard!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
