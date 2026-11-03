"""LabGateway HTTP interface. Run with gunicorn in deployment."""
import os
import secrets
import uuid
from functools import wraps
from flask import Flask, request, redirect, session, render_template, flash, abort, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from core import validate_submission, InvalidSubmission
import store

app = Flask(__name__)
app.secret_key = os.environ.get('LAB_SECRET_KEY', '')
if len(app.secret_key) < 32:
    raise RuntimeError('Defina LAB_SECRET_KEY (>= 32 caracteres aleatórios)')
app.config.update(MAX_CONTENT_LENGTH=2*1024*1024+100*1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('LAB_SECURE_COOKIE','0')=='1')
store.init()

def require_login(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if not session.get('uid'):
            return redirect(url_for('login'))
        return fn(*a,**kw)
    return inner

def teacher_only(fn):
    @wraps(fn)
    @require_login
    def inner(*a,**kw):
        if session.get('role') != 'teacher':
            abort(403)
        return fn(*a,**kw)
    return inner

def csrf():
    token = session.get('csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf'] = token
    return token

@app.context_processor
def add_csrf():
    return {'csrf':csrf}

@app.before_request
def csrf_check():
    if request.method == 'POST':
        if not secrets.compare_digest(request.form.get('_csrf',''),session.get('csrf','')):
            abort(400,'Token CSRF inválido')

@app.errorhandler(RequestEntityTooLarge)
def oversized(e):
    return 'Arquivo grande demais (máximo 2 MiB).',413

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user=store.verify(request.form.get('username',''),request.form.get('password',''))
        if user:
            session.clear()
            session.update(uid=user['id'], username=user['username'],role=user['role'],csrf=secrets.token_urlsafe(32))
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos.')
    return render_template('login.html')

@app.post('/logout')
@require_login
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.get('/')
@require_login
def index():
    with store.connect() as db:
        if session['role']=='teacher':
            items=db.execute('''SELECT s.id,s.title,s.created_at,u.username,
                (SELECT status FROM runs WHERE submission_id=s.id ORDER BY id DESC LIMIT 1) AS status
                FROM submissions s JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 100''').fetchall()
        else:
            items=db.execute('''SELECT s.id,s.title,s.created_at,u.username,
                (SELECT status FROM runs WHERE submission_id=s.id ORDER BY id DESC LIMIT 1) AS status
                FROM submissions s JOIN users u ON u.id=s.user_id WHERE s.user_id=? ORDER BY s.id DESC LIMIT 100''',(session['uid'],)).fetchall()
    return render_template('index.html',items=items)

@app.post('/upload')
@require_login
def upload():
    title=request.form.get('title','').strip()
    if not 1 <= len(title) <= 100:
        abort(400,'Título inválido')
    f=request.files.get('file')
    if not f or not (f.filename or '').lower().endswith('.zip'):
        abort(400,'Envie um arquivo .zip')
    try:
        files=validate_submission(f.read(2*1024*1024+1))
    except InvalidSubmission as err:
        abort(400,str(err))
    key=uuid.uuid4().hex
    path=store.UPLOAD/key
    path.mkdir(mode=0o755)
    for name,body in files.items():
        dest=path/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.parent.chmod(0o755)
        dest.write_bytes(body)
        dest.chmod(0o644)
    with store.connect() as db:
        db.execute('INSERT INTO submissions(user_id,title,path,created_at) VALUES(?,?,?,?)',
                   (session['uid'],title,str(path.resolve()),store.now()))
    flash('Projeto recebido; aguarde execução pelo professor.')
    return redirect(url_for('index'))

@app.post('/queue/<int:sid>')
@teacher_only
def queue(sid):
    with store.connect() as db:
        item=db.execute('SELECT id FROM submissions WHERE id=?',(sid,)).fetchone()
        if item is None: abort(404)
        running=db.execute("SELECT 1 FROM runs WHERE submission_id=? AND status IN ('queued','running')",(sid,)).fetchone()
        if not running:
            db.execute("INSERT INTO runs(submission_id,status) VALUES (?,'queued')",(sid,))
            flash('Execução adicionada à fila.')
    return redirect(url_for('detail',sid=sid))

@app.get('/project/<int:sid>')
@require_login
def detail(sid):
    with store.connect() as db:
        item=db.execute('SELECT s.*,u.username FROM submissions s JOIN users u ON u.id=s.user_id WHERE s.id=?',(sid,)).fetchone()
        if item is None: abort(404)
        if session['role']!='teacher' and item['user_id']!=session['uid']: abort(403)
        runs=db.execute('SELECT * FROM runs WHERE submission_id=? ORDER BY id DESC LIMIT 20',(sid,)).fetchall()
    return render_template('detail.html',item=item,runs=runs)

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('LAB_PORT', '5001')),debug=False)
