import os, sqlite3, secrets, re, json
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE=os.path.dirname(__file__)
DB=os.environ.get('DATABASE_PATH',os.path.join(BASE,'mon_entre_deux.sqlite3'))
app=Flask(__name__,static_folder='static',static_url_path='')
app.secret_key=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE')=='1',MAX_CONTENT_LENGTH=2*1024*1024)
CATEGORIES=['Voirie et trottoirs','Déchets et propreté','Eau et assainissement','Éclairage public','Espaces verts','Sécurité et équipements','Autres']
STATUSES=['Reçu',"En cours d'analyse",'Intervention programmée','Résolu','Rejeté / hors compétence']
SERVICES=['Services techniques','Voirie','Environnement','Eau / partenaire','Éclairage','Autre']

def conn():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
 with conn() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, service TEXT NOT NULL)')
  c.execute('''CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, status TEXT NOT NULL, service TEXT NOT NULL DEFAULT 'Services techniques', photo TEXT NOT NULL DEFAULT '')''')
  c.execute('CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, report_id TEXT NOT NULL REFERENCES reports(id), changed_at TEXT NOT NULL, actor TEXT NOT NULL, old_status TEXT, new_status TEXT NOT NULL)')
  if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
   pwd=os.environ.get('ADMIN_PASSWORD')
   if not pwd or len(pwd)<12: raise RuntimeError('Définissez ADMIN_PASSWORD avec au moins 12 caractères avant le premier démarrage.')
   c.execute('INSERT INTO users(username,password_hash,role,service) VALUES(?,?,?,?)',('admin',generate_password_hash(pwd),'admin','Tous'))

def error(msg,status=400):return jsonify(error=msg),status

def require_login(fn):
 @wraps(fn)
 def wrapper(*a,**kw):
  if not session.get('user'):return error('Connexion requise',401)
  return fn(*a,**kw)
 return wrapper

def require_csrf():
 if request.headers.get('X-CSRF-Token')!=session.get('csrf') or not session.get('csrf'):abort(403)

@app.get('/')
def index():return send_from_directory(app.static_folder,'index.html')
@app.get('/api/session')
def whoami():
 session.setdefault('csrf',secrets.token_urlsafe(32))
 return jsonify(user=session.get('user'),role=session.get('role'),service=session.get('service'),csrf=session['csrf'])
@app.post('/api/login')
def login():
 require_csrf();data=request.get_json(silent=True) or {}
 with conn() as c:u=c.execute('SELECT * FROM users WHERE username=?',(str(data.get('username','')),)).fetchone()
 if not u or not check_password_hash(u['password_hash'],str(data.get('password',''))):return error('Identifiants invalides',401)
 session.clear();session.update(user=u['username'],role=u['role'],service=u['service'],csrf=secrets.token_urlsafe(32))
 return jsonify(ok=True,csrf=session['csrf'],user=u['username'],role=u['role'],service=u['service'])
@app.post('/api/logout')
def logout():require_csrf();session.clear();return jsonify(ok=True)
@app.post('/api/reports')
def create_report():
 require_csrf();d=request.get_json(silent=True) or {}
 try:lat=float(d.get('lat'));lng=float(d.get('lng'))
 except (ValueError,TypeError):return error('Coordonnées invalides')
 if not (-90<=lat<=90 and -180<=lng<=180):return error('Coordonnées invalides')
 title=str(d.get('title','')).strip();desc=str(d.get('description','')).strip();cat=d.get('category')
 if cat not in CATEGORIES or not (3<=len(title)<=100) or not (5<=len(desc)<=1500):return error('Catégorie, titre ou description invalide')
 photo=str(d.get('photo',''))
 if photo and (len(photo)>1400000 or not re.fullmatch(r'data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+',photo)):return error('Photo invalide (JPEG, PNG ou WebP, max 1 Mo)')
 rid='MED-'+datetime.now(timezone.utc).strftime('%Y%m%d')+'-'+secrets.token_hex(4).upper();now=datetime.now(timezone.utc).isoformat()
 with conn() as c:c.execute('INSERT INTO reports(id,created_at,category,title,description,lat,lng,status,photo) VALUES(?,?,?,?,?,?,?,?,?)',(rid,now,cat,title,desc,lat,lng,'Reçu',photo))
 return jsonify(id=rid,status='Reçu'),201
@app.get('/api/reports')
@require_login
def reports():
 with conn() as c:
  if session['role']=='agent':rows=c.execute('SELECT * FROM reports WHERE service=? ORDER BY created_at DESC',(session['service'],)).fetchall()
  else:rows=c.execute('SELECT * FROM reports ORDER BY created_at DESC').fetchall()
 return jsonify([{k:r[k] for k in r.keys() if k!='photo'}|{'has_photo':bool(r['photo'])} for r in rows])
@app.get('/api/reports/<rid>/photo')
@require_login
def photo(rid):
 with conn() as c:r=c.execute('SELECT service,photo FROM reports WHERE id=?',(rid,)).fetchone()
 if not r or (session['role']=='agent' and session['service']!=r['service']):abort(404)
 return jsonify(photo=r['photo'])
@app.patch('/api/reports/<rid>')
@require_login
def update(rid):
 require_csrf();d=request.get_json(silent=True) or {};status=d.get('status');service=d.get('service')
 if status not in STATUSES:return error('Statut invalide')
 if service is not None and service not in SERVICES:return error('Service invalide')
 with conn() as c:
  r=c.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone()
  if not r:return error('Dossier introuvable',404)
  if session['role']=='agent' and (r['service']!=session['service'] or (service is not None and service!=session['service'])):return error('Accès refusé',403)
  if session['role']=='responsable' and service is not None and service!=r['service']:return error('Affectation réservée à l’administrateur',403)
  c.execute('UPDATE reports SET status=?,service=? WHERE id=?',(status,service or r['service'],rid))
  c.execute('INSERT INTO history(report_id,changed_at,actor,old_status,new_status) VALUES(?,?,?,?,?)',(rid,datetime.now(timezone.utc).isoformat(),session['user'],r['status'],status))
 return jsonify(ok=True)
@app.post('/api/users')
@require_login
def add_user():
 require_csrf()
 if session['role']!='admin':return error('Accès refusé',403)
 d=request.get_json(silent=True) or {};username=str(d.get('username','')).strip();password=str(d.get('password',''));role=d.get('role');service=d.get('service')
 if not re.fullmatch('[a-zA-Z0-9_.-]{3,40}',username) or len(password)<12 or role not in ['admin','responsable','agent'] or service not in SERVICES+['Tous']:return error('Utilisateur invalide ou mot de passe trop court')
 try:
  with conn() as c:c.execute('INSERT INTO users(username,password_hash,role,service) VALUES(?,?,?,?)',(username,generate_password_hash(password),role,service))
 except sqlite3.IntegrityError:return error('Identifiant déjà utilisé',409)
 return jsonify(ok=True),201

if __name__=='__main__':
 init();app.run(host='127.0.0.1',port=int(os.environ.get('PORT','8080')),debug=False)
