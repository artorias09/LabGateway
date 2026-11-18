"""LabGateway HTTP interface. Run with gunicorn in deployment."""
import io
import csv
import json
import os
import secrets
import uuid
import zipfile
from pathlib import Path
from functools import wraps
from datetime import datetime, timezone
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
                  SESSION_COOKIE_SECURE=os.environ.get('LAB_SECURE_COOKIE','0')=='1',
                  LAB_VIEWER_USERNAME=os.environ.get('LAB_VIEWER_USERNAME','alunos').strip())
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

def is_viewer():
    username = app.config.get('LAB_VIEWER_USERNAME', 'alunos')
    return bool(username) and session.get('username') == username

def teacher_only(fn):
    @wraps(fn)
    @require_login
    def inner(*a,**kw):
        if session.get('role') != 'teacher':
            abort(403)
        return fn(*a,**kw)
    return inner

def monitor_access(fn):
    @wraps(fn)
    @require_login
    def inner(*a,**kw):
        if session.get('role') != 'teacher' and not is_viewer():
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
    if request.path == '/api/v1/measurements':
        return

    if session.get('uid') and is_viewer():
        allowed = (
            request.path == '/monitor' or
            request.path.startswith('/monitor/') or
            request.path.startswith('/api/v1/stations/') or
            request.path == '/logout' or
            request.path.startswith('/static/')
        )
        if not allowed:
            abort(403)
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
            return redirect(url_for('monitor') if is_viewer() else url_for('index'))
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
    if is_viewer():
        return redirect(url_for('monitor'))
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



def _ingest_authorized():
    expected = os.environ.get('LAB_INGEST_TOKEN', '')
    supplied = request.headers.get('X-LabGateway-Token', '')
    return len(expected) >= 24 and secrets.compare_digest(expected, supplied)


@app.post('/api/v1/measurements')
def ingest_measurements():
    if not _ingest_authorized():
        abort(401)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, 'JSON inválido')

    station_key = str(payload.get('station', '')).strip()
    station_name = str(payload.get('name', station_key)).strip()
    group_name = str(payload.get('group', '')).strip()
    values = payload.get('data')
    units = payload.get('units') or {}

    if not 1 <= len(station_key) <= 64 or not station_key.replace('_','').replace('-','').isalnum():
        abort(400, 'Identificador de estação inválido')
    if not 1 <= len(station_name) <= 100 or len(group_name) > 100:
        abort(400, 'Metadados da estação inválidos')
    if not isinstance(values, dict) or not 1 <= len(values) <= 32:
        abort(400, 'Envie de 1 a 32 medições em data')
    if not isinstance(units, dict):
        abort(400, 'units deve ser um objeto')

    captured_at = payload.get('captured_at')
    if captured_at:
        try:
            parsed = datetime.fromisoformat(str(captured_at).replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            captured_at = parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
        except ValueError:
            abort(400, 'captured_at inválido')
    else:
        captured_at = store.now()

    clean = []
    for metric, value in values.items():
        metric = str(metric).strip()
        if not 1 <= len(metric) <= 64:
            abort(400, 'Nome de variável inválido')
        try:
            number = float(value)
        except (TypeError, ValueError):
            abort(400, f'Valor inválido para {metric}')
        if not (-1e100 < number < 1e100):
            abort(400, f'Valor fora da faixa para {metric}')
        unit = str(units.get(metric, '')).strip()
        if len(unit) > 32:
            abort(400, f'Unidade muito longa para {metric}')
        clean.append((metric, number, unit))

    received_at = store.now()
    with store.connect() as db:
        station = db.execute('SELECT id FROM stations WHERE station_key=?',(station_key,)).fetchone()
        if station is None:
            cur = db.execute(
                'INSERT INTO stations(station_key,name,group_name,created_at,last_seen_at) VALUES(?,?,?,?,?)',
                (station_key,station_name,group_name,received_at,received_at)
            )
            station_id = cur.lastrowid
        else:
            station_id = station['id']
            db.execute(
                'UPDATE stations SET name=?,group_name=?,last_seen_at=? WHERE id=?',
                (station_name,group_name,received_at,station_id)
            )
        db.executemany(
            'INSERT INTO measurements(station_id,metric,value,unit,captured_at,received_at) VALUES(?,?,?,?,?,?)',
            [(station_id,metric,value,unit,captured_at,received_at) for metric,value,unit in clean]
        )
    return {'ok': True, 'station': station_key, 'received_at': received_at, 'metrics': len(clean)}, 201


@app.get('/monitor')
@monitor_access
def monitor():
    with store.connect() as db:
        stations = db.execute('''SELECT s.*,
            (SELECT COUNT(*) FROM measurements m WHERE m.station_id=s.id) AS measurement_count,
            (SELECT COUNT(DISTINCT metric) FROM measurements m WHERE m.station_id=s.id) AS metric_count
            FROM stations s ORDER BY s.name''').fetchall()
    return render_template('monitor.html', stations=stations)


@app.get('/monitor/<int:station_id>')
@monitor_access
def monitor_station(station_id):
    with store.connect() as db:
        station = db.execute('SELECT * FROM stations WHERE id=?',(station_id,)).fetchone()
        if station is None:
            abort(404)
        metrics = db.execute('''SELECT m.metric,
            COALESCE(l.label,m.metric) AS label,
            COALESCE(NULLIF(l.unit,''),MAX(m.unit),'') AS display_unit,
            COUNT(*) AS n,MIN(m.captured_at) AS first_at,MAX(m.captured_at) AS last_at
            FROM measurements m
            LEFT JOIN station_metric_labels l ON l.station_id=m.station_id AND l.metric=m.metric
            WHERE m.station_id=?
            GROUP BY m.metric,l.label,l.unit
            ORDER BY m.metric''',(station_id,)).fetchall()
        latest = db.execute('''SELECT m.metric,m.value,
            COALESCE(l.label,m.metric) AS label,
            COALESCE(NULLIF(l.unit,''),m.unit,'') AS display_unit,
            m.captured_at
            FROM measurements m
            JOIN (SELECT metric,MAX(id) AS id FROM measurements WHERE station_id=? GROUP BY metric) x ON x.id=m.id
            LEFT JOIN station_metric_labels l ON l.station_id=m.station_id AND l.metric=m.metric
            ORDER BY m.metric''',(station_id,)).fetchall()
    return render_template('monitor_station.html',station=station,metrics=metrics,latest=latest)


@app.post('/monitor/<int:station_id>/labels')
@teacher_only
def update_station_labels(station_id):
    with store.connect() as db:
        station = db.execute('SELECT id FROM stations WHERE id=?',(station_id,)).fetchone()
        if station is None:
            abort(404)
        metrics = db.execute('SELECT DISTINCT metric FROM measurements WHERE station_id=? ORDER BY metric',(station_id,)).fetchall()
        for row in metrics:
            metric = row['metric']
            label = request.form.get(f'label_{metric}', '').strip()
            unit = request.form.get(f'unit_{metric}', '').strip()
            if not label:
                label = metric
            if len(label) > 100 or len(unit) > 32:
                abort(400,'Nome ou unidade muito longos')
            db.execute('''INSERT INTO station_metric_labels(station_id,metric,label,unit)
                VALUES(?,?,?,?)
                ON CONFLICT(station_id,metric) DO UPDATE SET label=excluded.label,unit=excluded.unit''',
                (station_id,metric,label,unit))
    flash('Nomes das variáveis atualizados.')
    return redirect(url_for('monitor_station',station_id=station_id))


@app.get('/monitor/<int:station_id>/download.csv')
@monitor_access
def download_station_csv(station_id):
    with store.connect() as db:
        station = db.execute('SELECT * FROM stations WHERE id=?',(station_id,)).fetchone()
        if station is None:
            abort(404)
        labels = {
            r['metric']: (r['label'], r['unit'])
            for r in db.execute(
                'SELECT metric,label,unit FROM station_metric_labels WHERE station_id=?',
                (station_id,)
            ).fetchall()
        }
        rows = db.execute('''SELECT metric,value,unit,captured_at,received_at
            FROM measurements WHERE station_id=? ORDER BY captured_at,id''',(station_id,)).fetchall()

    measured_units = {}
    for row in rows:
        if row['unit']:
            measured_units[row['metric']] = row['unit']

    metrics = []
    for row in rows:
        if row['metric'] not in metrics:
            metrics.append(row['metric'])

    samples = []
    current = None
    for row in rows:
        if current is None or row['metric'] in current['values'] or row['captured_at'] != current['captured_at']:
            if current is not None:
                samples.append(current)
            current = {
                'captured_at': row['captured_at'],
                'received_at': row['received_at'],
                'values': {}
            }
        current['values'][row['metric']] = row['value']
        current['received_at'] = row['received_at']
    if current is not None:
        samples.append(current)

    out = io.StringIO()
    writer = csv.writer(out)
    headers = ['captured_at','received_at']
    for metric in metrics:
        label, configured_unit = labels.get(metric,(metric,''))
        unit = configured_unit or measured_units.get(metric,'')
        if unit:
            headers.append(f'{label} ({unit})')
        else:
            headers.append(label)
    writer.writerow(headers)
    for sample in samples:
        writer.writerow([
            sample['captured_at'],
            sample['received_at'],
            *[sample['values'].get(metric,'') for metric in metrics]
        ])

    data = io.BytesIO(out.getvalue().encode('utf-8-sig'))
    filename = secure_filename(station['name']).strip('._-') or f'estacao-{station_id}'
    return send_file(data,mimetype='text/csv',as_attachment=True,
                     download_name=f'{filename}-historico.csv',max_age=0)


@app.get('/api/v1/stations/<int:station_id>/series')
@monitor_access
def station_series(station_id):
    metric = request.args.get('metric','').strip()
    try:
        limit = min(max(int(request.args.get('limit','500')),10),2000)
    except ValueError:
        limit = 500
    with store.connect() as db:
        station = db.execute('SELECT id FROM stations WHERE id=?',(station_id,)).fetchone()
        if station is None:
            abort(404)
        if not metric:
            row = db.execute('SELECT metric FROM measurements WHERE station_id=? ORDER BY id DESC LIMIT 1',(station_id,)).fetchone()
            metric = row['metric'] if row else ''
        label_row = db.execute(
            'SELECT label,unit FROM station_metric_labels WHERE station_id=? AND metric=?',
            (station_id,metric)
        ).fetchone() if metric else None
        rows = db.execute('''SELECT captured_at,value,unit FROM (
            SELECT id,captured_at,value,unit FROM measurements
            WHERE station_id=? AND metric=? ORDER BY id DESC LIMIT ?
        ) ORDER BY id''',(station_id,metric,limit)).fetchall() if metric else []
    label = label_row['label'] if label_row else metric
    display_unit = label_row['unit'] if label_row and label_row['unit'] else (rows[-1]['unit'] if rows else '')
    points = []
    for r in rows:
        item = dict(r)
        if display_unit:
            item['unit'] = display_unit
        points.append(item)
    return {'metric':metric,'label':label,'points':points}


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
