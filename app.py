from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for frontend communication

DB = 'allocation.db'

# Initialize database
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        skills TEXT,
        interests TEXT,
        location_preference TEXT,
        internship_type TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS organizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        projects TEXT,
        requirements TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        organization_id INTEGER,
        project TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id),
        FOREIGN KEY(organization_id) REFERENCES organizations(id)
    )''')

    conn.commit()
    conn.close()

init_db()

# Helper function
def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, args)
    rv = c.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# ====================== Registration ======================

@app.route('/api/register/student', methods=['POST'])
def register_student():
    data = request.json
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('INSERT INTO students (name, email, password, skills, interests, location_preference, internship_type) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (data['name'], data['email'], data['password'], json.dumps(data['skills']), json.dumps(data['interests']), data['location_preference'], data['internship_type']))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Student registered successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already registered'}), 400

@app.route('/api/register/organization', methods=['POST'])
def register_organization():
    data = request.json
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('INSERT INTO organizations (name, email, password, projects, requirements) VALUES (?, ?, ?, ?, ?)',
                  (data['name'], data['email'], data['password'], json.dumps(data['projects']), json.dumps(data['requirements'])))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Organization registered successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already registered'}), 400

# ====================== Login ======================

@app.route('/api/login/student', methods=['POST'])
def login_student():
    data = request.json
    user = query_db('SELECT * FROM students WHERE email=? AND password=?', (data['email'], data['password']), one=True)
    if user:
        user_data = {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'skills': json.loads(user[4]),
            'interests': json.loads(user[5]),
            'location_preference': user[6],
            'internship_type': user[7]
        }
        return jsonify(user_data)
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/login/organization', methods=['POST'])
def login_organization():
    data = request.json
    user = query_db('SELECT * FROM organizations WHERE email=? AND password=?', (data['email'], data['password']), one=True)
    if user:
        user_data = {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'projects': json.loads(user[4]),
            'requirements': json.loads(user[5])
        }
        return jsonify(user_data)
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

# ====================== Organization updates ======================

@app.route('/api/organization/<int:org_id>/update_projects', methods=['POST'])
def update_projects(org_id):
    data = request.json
    projects = data.get('projects', [])
    requirements = data.get('requirements', [])
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('UPDATE organizations SET projects=?, requirements=? WHERE id=?', (json.dumps(projects), json.dumps(requirements), org_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Projects updated successfully'})

# ====================== Dashboard ======================

@app.route('/api/student/<int:student_id>', methods=['GET'])
def get_student(student_id):
    user = query_db('SELECT * FROM students WHERE id=?', (student_id,), one=True)
    if user:
        user_data = {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'skills': json.loads(user[4]),
            'interests': json.loads(user[5]),
            'location_preference': user[6],
            'internship_type': user[7]
        }
        return jsonify(user_data)
    else:
        return jsonify({'error': 'Student not found'}), 404

@app.route('/api/organization/<int:org_id>', methods=['GET'])
def get_organization(org_id):
    user = query_db('SELECT * FROM organizations WHERE id=?', (org_id,), one=True)
    if user:
        user_data = {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'projects': json.loads(user[4]),
            'requirements': json.loads(user[5])
        }
        return jsonify(user_data)
    else:
        return jsonify({'error': 'Organization not found'}), 404

# ====================== Admin ======================

@app.route('/api/admin/data', methods=['GET'])
def admin_data():
    students = query_db('SELECT id, name, email FROM students')
    organizations = query_db('SELECT id, name, email FROM organizations')
    return jsonify({
        'students': [{'id': s[0], 'name': s[1], 'email': s[2]} for s in students],
        'organizations': [{'id': o[0], 'name': o[1], 'email': o[2]} for o in organizations]
    })

# ====================== Allocation logic ======================

def allocate():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('DELETE FROM allocations')  # Clear old allocations

    c.execute('SELECT * FROM students')
    students = c.fetchall()

    c.execute('SELECT * FROM organizations')
    organizations = c.fetchall()

    allocations = []

    for student in students:
        student_id = student[0]
        student_skills = set(json.loads(student[4]))
        student_location = student[6]
        student_internship_type = student[7]

        best_match = None
        best_score = -1

        for org in organizations:
            org_id = org[0]
            org_projects = json.loads(org[4])
            org_requirements = json.loads(org[5]) if org[5] else []

            for i, project in enumerate(org_projects):
                req_skills = set(org_requirements[i]) if i < len(org_requirements) else set()
                skill_match = len(student_skills.intersection(req_skills))
                location_match = 1 if student_location.lower() in project.get('location', '').lower() else 0
                internship_type_match = 1 if (student_internship_type == project.get('internship_type', 'paid')) else 0

                score = skill_match * 2 + location_match + internship_type_match

                if score > best_score:
                    best_score = score
                    best_match = (org_id, project.get('title', ''))

        if best_match:
            c.execute('INSERT INTO allocations (student_id, organization_id, project) VALUES (?, ?, ?)',
                      (student_id, best_match[0], best_match[1]))
            allocations.append({'student_id': student_id, 'organization_id': best_match[0], 'project': best_match[1]})

    conn.commit()
    conn.close()
    return allocations

@app.route('/api/admin/allocate', methods=['POST'])
def run_allocation():
    allocations = allocate()
    return jsonify({'message': 'Allocation done', 'allocations': allocations})

# ====================== Get student allocation ======================

@app.route('/api/student/<int:student_id>/allocation', methods=['GET'])
def get_student_allocation(student_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT organizations.name, allocations.project FROM allocations
                 JOIN organizations ON allocations.organization_id = organizations.id
                 WHERE allocations.student_id=?''', (student_id,))
    results = c.fetchall()
    conn.close()
    if results:
        allocations = [{'organization': r[0], 'project': r[1]} for r in results]
        return jsonify({'allocations': allocations})
    else:
        return jsonify({'message': 'No allocation found for this student'}), 404

# ====================== Run Flask ======================

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

