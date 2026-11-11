"""LabGateway HTTP interface. Run with gunicorn in deployment."""
import io
import json
import os
import secrets
import uuid
import zipfile
from pathlib import Path
from functools import wraps
from flask import Flask, request, redirect, session, render_template, flash, abort, url_for, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from core import validate_submission, InvalidSubmission, detect_project_type_from_path
from datasets import analyze_dataset, analyze_dataset_file, InvalidDataset, MAX_DATA_BYTES
import store

app = Flask(__name__)
app.secret_key = os.environ.get('LAB_SECRET_KEY', '')
if len(app.secret_key) < 32:
    raise RuntimeError('Defina LAB_SECRET_KEY (>= 32 caracteres aleatórios)')
app.config.update(MAX_CONTENT_LENGTH=MAX_DATA_BYTES+100*1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('LAB_SECURE_COOKIE','0')=='1')
store.init()

STATUS_LABELS = {'queued':'Na fila','running':'Executando','passed':'Concluído','failed':'Erro no programa','timeout':'Tempo excedido','error':'Falha no servidor'}

@app.context_processor
def labels():
    return {'status_label': lambda key: STATUS_LABELS.get(key, 'Aguardando execução')}

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response

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
        submitted = request.form.get('_csrf', '')
        expected = session.get('csrf')
        if not expected or not submitted or not secrets.compare_digest(submitted, expected):
            abort(400,'Token CSRF inválido')

@app.errorhandler(RequestEntityTooLarge)
def oversized(e):
    return 'Arquivo grande demais para este envio.',413

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


@app.get('/datasets')
@require_login
def datasets():
    with store.connect() as db:
        if session['role'] == 'teacher':
            items = db.execute('''SELECT d.*,u.username,s.title AS project_title
                FROM datasets d JOIN users u ON u.id=d.user_id
                LEFT JOIN submissions s ON s.id=d.submission_id
                ORDER BY d.id DESC LIMIT 200''').fetchall()
            projects = db.execute('SELECT id,title FROM submissions ORDER BY id DESC LIMIT 200').fetchall()
        else:
            items = db.execute('''SELECT d.*,u.username,s.title AS project_title
                FROM datasets d JOIN users u ON u.id=d.user_id
                LEFT JOIN submissions s ON s.id=d.submission_id
                WHERE d.user_id=? ORDER BY d.id DESC LIMIT 200''',(session['uid'],)).fetchall()
            projects = db.execute(
                'SELECT id,title FROM submissions WHERE user_id=? ORDER BY id DESC LIMIT 200',
                (session['uid'],)
            ).fetchall()
    return render_template('datasets.html',items=items,projects=projects)


@app.post('/datasets/upload')
@require_login
def upload_dataset():
    title = request.form.get('title','').strip()
    description = request.form.get('description','').strip()
    units = request.form.get('units','').strip()
    if not 1 <= len(title) <= 100:
        abort(400,'Nome do ensaio inválido')
    if len(description) > 500 or len(units) > 200:
        abort(400,'Metadados muito longos')

    submission_id = request.form.get('submission_id','').strip()
    linked_id = None
    if submission_id:
        try:
            linked_id = int(submission_id)
        except ValueError:
            abort(400,'Projeto relacionado inválido')
        with store.connect() as db:
            project = db.execute('SELECT id,user_id FROM submissions WHERE id=?',(linked_id,)).fetchone()
        if project is None:
            abort(400,'Projeto relacionado não encontrado')
        if session['role'] != 'teacher' and project['user_id'] != session['uid']:
            abort(403)

    f = request.files.get('file')
    filename = secure_filename(f.filename or '') if f else ''
    if not f or Path(filename).suffix.lower() not in ('.csv','.json'):
        abort(400,'Envie um arquivo .csv ou .json')
    raw = f.read(MAX_DATA_BYTES + 1)
    try:
        summary = analyze_dataset(raw, filename)
    except InvalidDataset as err:
        abort(400,str(err))

    stored_name = uuid.uuid4().hex + Path(filename).suffix.lower()
    path = store.DATASET_UPLOAD / stored_name
    path.write_bytes(raw)
    path.chmod(0o640)

    try:
        with store.connect() as db:
            db.execute('''INSERT INTO datasets(
                user_id,submission_id,title,description,units,original_name,path,
                file_type,row_count,columns_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
                session['uid'],linked_id,title,description,units,filename,str(path.resolve()),
                summary['file_type'],summary['row_count'],
                json.dumps(summary['columns'],ensure_ascii=False),store.now()
            ))
    except Exception:
        path.unlink(missing_ok=True)
        raise

    flash('Dados experimentais registrados.')
    return redirect(url_for('datasets'))


def _dataset_row(did):
    with store.connect() as db:
        item = db.execute('''SELECT d.*,u.username,s.title AS project_title
            FROM datasets d JOIN users u ON u.id=d.user_id
            LEFT JOIN submissions s ON s.id=d.submission_id
            WHERE d.id=?''',(did,)).fetchone()
    if item is None:
        abort(404)
    if session['role'] != 'teacher' and item['user_id'] != session['uid']:
        abort(403)
    return item


@app.get('/dataset/<int:did>')
@require_login
def dataset_detail(did):
    item = _dataset_row(did)
    path = Path(item['path']).resolve()
    try:
        path.relative_to(store.DATASET_UPLOAD.resolve())
    except ValueError:
        abort(400,'Caminho de dados inválido')
    if not path.is_file() or path.is_symlink():
        abort(404,'Arquivo de dados não encontrado')
    try:
        summary = analyze_dataset_file(path)
    except InvalidDataset:
        summary = {'columns': json.loads(item['columns_json']), 'preview': []}
    return render_template(
        'dataset_detail.html',
        item=item,
        columns=summary['columns'],
        preview=summary['preview'],
    )


@app.get('/dataset/<int:did>/download')
@require_login
def download_dataset(did):
    item = _dataset_row(did)
    path = Path(item['path']).resolve()
    try:
        path.relative_to(store.DATASET_UPLOAD.resolve())
    except ValueError:
        abort(400,'Caminho de dados inválido')
    if not path.is_file() or path.is_symlink():
        abort(404,'Arquivo de dados não encontrado')
    return send_file(
        path,
        as_attachment=True,
        download_name=item['original_name'],
        max_age=0,
    )


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
    flash('Projeto recebido; o professor já pode consultar e validar o envio.')
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


@app.get('/project/<int:sid>/download')
@teacher_only
def download_project(sid):
    with store.connect() as db:
        item=db.execute('SELECT s.*,u.username FROM submissions s JOIN users u ON u.id=s.user_id WHERE s.id=?',(sid,)).fetchone()
    if item is None:
        abort(404)
    source = Path(item['path']).resolve()
    try:
        source.relative_to(store.UPLOAD.resolve())
    except ValueError:
        abort(400, 'Caminho de projeto inválido')
    if not source.is_dir():
        abort(404, 'Arquivos do projeto não encontrados')

    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(source.rglob('*')):
            if file_path.is_symlink():
                abort(400, 'Projeto contém link simbólico inesperado')
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(source).as_posix())
    out.seek(0)

    base = secure_filename(item['title']).strip('._-') or f'projeto-{sid}'
    return send_file(
        out,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{base}.zip',
        max_age=0,
    )

@app.get('/project/<int:sid>')
@require_login
def detail(sid):
    with store.connect() as db:
        item=db.execute('SELECT s.*,u.username FROM submissions s JOIN users u ON u.id=s.user_id WHERE s.id=?',(sid,)).fetchone()
        if item is None: abort(404)
        if session['role']!='teacher' and item['user_id']!=session['uid']: abort(403)
        runs=db.execute('SELECT * FROM runs WHERE submission_id=? ORDER BY id DESC LIMIT 20',(sid,)).fetchall()
        linked_datasets=db.execute('''SELECT d.id,d.title,d.file_type,d.row_count,d.created_at
            FROM datasets d WHERE d.submission_id=? ORDER BY d.id DESC LIMIT 100''',(sid,)).fetchall()
    pending = any(r['status'] in ('queued','running') for r in runs)
    project_type = detect_project_type_from_path(item['path'])
    return render_template(
        'detail.html',
        item=item,
        runs=runs,
        pending=pending,
        project_type=project_type,
        linked_datasets=linked_datasets,
    )

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('LAB_PORT', '5001')),debug=False)
