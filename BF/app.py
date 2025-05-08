from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import smtplib
import datetime as dt
import pytz
import logging
from threading import Thread
from logging.handlers import RotatingFileHandler
from flask import Flask,session, jsonify, abort, make_response, request, url_for, render_template, send_from_directory
import random
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash


# Configurazione dell'app Flask
app = Flask(__name__, static_folder='static')
CORS(app)  # Abilita CORS per comunicare con React

# Configurazione del database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configurazione Flask-Mail
app.config['MAIL_SERVER'] = 'sandbox.smtp.mailtrap.io'  # Sostituisci con il tuo server SMTP
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'd58b96d6f79133'
app.config['MAIL_PASSWORD'] = 'e2bc5a25e892c0'
app.config['MAIL_DEFAULT_SENDER'] = 'noreply@fitbreak.com'

mail = Mail(app)

handler = RotatingFileHandler('notifications.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

# Definizione dei modelli del database
# Definizione del modello User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))  # Nome dell'utente
    email = db.Column(db.String(100), unique=True)  # Email unica
    password = db.Column(db.String(100))  # Password (in chiaro, da hashare in produzione)
    break_duration = db.Column(db.Integer)  # Durata della pausa (5 o 10 minuti)
    morning_time = db.Column(db.String(5))   # Orario della notifica mattutina
    afternoon_time = db.Column(db.String(5)) # Orario della notifica pomeridiana
    evening_time = db.Column(db.String(5))   # Orario della notifica serale
#tabella per progressi
class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'))
    date = db.Column(db.String(10))  # Formato "YYYY-MM-DD"
    completed = db.Column(db.Boolean)
#tabella per esercizi
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Nome dell'esercizio
    description = db.Column(db.Text)  # Descrizione dell'esercizio
    duration = db.Column(db.Integer)  # Durata in minuti
    type = db.Column(db.String(50))  # Tipo (stretching, cardio, corpo libero)
    image_url = db.Column(db.String(200))  # Link a un'immagine o video

# Crea il database (esegui solo una volta)
with app.app_context():
    db.create_all()


def get_exercise_by_time(time_slot):
    """Restituisce il messaggio per l'esercizio in base all'orario"""
    exercises = {
        'morning': {
            'subject': '🌅 Esercizio Mattutino - FitBreak',
            'body': 'È ora di fare stretching! Inizia la giornata con qualche minuti di allungamenti o corpo libero'
        },
        'afternoon': {
            'subject': '🏃‍♂️ Pausa Pomeridiana - FitBreak',
            'body': 'Tempo per una camminata veloce o corsa di qualche minuti!'
        },
        'evening': {
            'subject': '🌙 Routine Serale - FitBreak',
            'body': 'Fai qualche minuti di stretching per rilassarti prima di dormire.'
        }
    }
    return exercises.get(time_slot)

def send_notification(user, time_slot):
    """Invia l'email di notifica"""
    exercise = get_exercise_by_time(time_slot)
    if not exercise:
        return

    try:
        msg = Message(
            subject=exercise['subject'],
            recipients=[user.email],
            body=exercise['body'].format(duration=user.break_duration),
            html=f'''
            <h2>Ciao {user.name},</h2>
            <p>{exercise['body'].format(duration=user.break_duration)}</p>
            <p>TI ASPETTIAMO IN APP!!!</p>
            <p>Team FitBreak</p>
            '''
        )
        Thread(target=send_async_email, args=(msg,)).start()
        app.logger.info(f"Email inviata a {user.email} per {time_slot}")
    except smtplib.SMTPServerDisconnected as e:
        app.logger.error(f"Errore connessione SMTP: {str(e)}")
    except Exception as e:
        app.logger.error(f"Errore invio email a {user.email}: {str(e)}")



def check_notifications():
    """Controlla gli orari e invia le notifiche"""
    with app.app_context():
        roma_tz = pytz.timezone('Europe/Rome')
        now = dt.datetime.now(roma_tz).strftime("%H:%M")
        users = User.query.filter(
            (User.morning_time != None) |
            (User.afternoon_time != None) |
            (User.evening_time != None)
        ).all()

        for user in users:
            matched = False
            if user.morning_time == now:
                send_notification(user, 'morning')
                matched = True
            if user.afternoon_time == now and not matched:
                send_notification(user, 'afternoon')
                matched = True
            if user.evening_time == now and not matched:
                send_notification(user, 'evening')

# Configurazione scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=check_notifications,
    trigger='cron',
    minute='*',
    max_instances=1
)
scheduler.start()


def send_async_email(msg):
    with app.app_context():
        mail.send(msg)

# Shutdown scheduler quando l'app si chiude
atexit.register(lambda: scheduler.shutdown())

#funzione per inviare un email di test
def send_test_email():
    try:
        msg = Message(
            subject="Test Notifica FitBreak",
            recipients=["test@example.com"],
            html="<h1>Prova notifica!</h1>"
        )
        Thread(target=send_async_email, args=(msg,)).start()
        print("Email catturata in Mailtrap!")
    except Exception as e:
        print(f"Errore: {str(e)}")

#funzione per popolare la tabella Exercise
def add_exercises():
    exercises = [
        {
            "name": "Decopression-Circuit",
            "description": "esercizio importante per spalle e cervicale 1 min per ogni posizione",
            "duration": 5,
            "type": "stretching",
            "image_url": "static/img/decopression.jpg"
        }
    ]
    for ex in exercises:
        exercise = Exercise(
            name=ex['name'],
            description=ex['description'],
            duration=ex['duration'],
            type=ex['type'],
            image_url=ex['image_url']
        )
        db.session.add(exercise)
    db.session.commit()
#funzione per eliminare un esercizio in base all'id
def delete_exercises(id):
    for i in id:
        Exercise.query.filter_by(id=i).delete()
    db.session.commit()

#API per registrazione
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    # Verifica se l'email è già registrata
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email già registrata"}), 400
    # Crea un nuovo utente
    new_user = User(
        name=data['name'],
        email=data['email'],
        password=data['password'],  # In produzione, usa password hashate!
        break_duration=data['break_duration'],
        morning_time=data['morning_time'],
        afternoon_time=data['afternoon_time'],
        evening_time=data['evening_time']
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Utente registrato con successo!"}), 201

#route per servire CSS e immagini a cartella templates
@app.route('/static/<path:filename>')
def server_static(filename):
    return send_from_directory(app.static_folder, filename)

#API per login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email'], password=data['password']).first()
    if user:
        return jsonify({'iduser': user.id,
                        'break_duration':user.break_duration,
                        'name':user.name,
                        'morning_time':user.morning_time,
                        'afternoon_time':user.afternoon_time,
                        'evening_time':user.evening_time,
                        "message":"Accesso effettuato con successo!"})
    return jsonify({"error": "Credenziali non valide"}), 401

#API per ottenere la lista degli esercizi
@app.route('/api/exercises', methods=['GET'])
def get_exercises():
    exercises = Exercise.query.all()
    return jsonify([{
        "id": ex.id,
        "name": ex.name,
        "description": ex.description,
        "duration": ex.duration,
        "type": ex.type,
        "image_url": ex.image_url
    } for ex in exercises])

#api per aggiungere progresso

@app.route('/api/progres', methods=['POST'])
def add_progress():
    data = request.json
    new_progress = Progress(
        user_id=data['id_user'],
        exercise_id=data['exercise_id'],
        date=dt.date.today().strftime('%Y-%m-%d'),
        completed=data['completed']
    )
    db.session.add(new_progress)
    db.session.commit()
    return jsonify({"message": "Progresso aggiunto con successo!"}), 201


#api per prendere progressi di un utente
@app.route('/api/progress', methods=['GET'])
def get_progress():
    user_id = request.args.get('id')
    ptot=db.session.query(Progress).filter(Progress.user_id==user_id).all()
    one_week_ago = (dt.date.today() - dt.timedelta(days=6)).strftime('%Y-%m-%d')
    today = dt.date.today().strftime('%Y-%m-%d')
    psett = db.session.query(Progress).filter(
        Progress.user_id == user_id,
        Progress.date >= one_week_ago,
        Progress.date <= today
    ).all()
    #gestisci parte di ricerca dati
    progress = {
        "weekly_progress": len(psett),  # Esercizi completati questa settimana
        "total_progress": len(ptot)  # Esercizi totali completati
    }
    return jsonify(progress)
#api per predere dati utente con id
@app.route('/api/user/<id>', methods=['GET'])
def get_user(id):
    user = User.query.filter_by(id=id).first()
    if not user:
        return jsonify({"error": "Utente non trovato"}), 404
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "break_duration": user.break_duration,
        "morning_time": user.morning_time,
        "afternoon_time": user.afternoon_time,
        "evening_time": user.evening_time
    })


# TODO:Endpoint per aggiornare i dati utente
@app.route('/api/update-user', methods=['PUT'])
def update_user(current_user):
    data = request.get_json()

    # Aggiorna i campi modificabili
    if 'name' in data:
        current_user.name = data['name']
    if 'email' in data:
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user and existing_user.id != current_user.id:
            return jsonify({'error': 'Email già registrata'}), 400
        current_user.email = data['email']
    if 'break_duration' in data:
        current_user.break_duration = data['break_duration']
    if 'morning_time' in data:
        current_user.morning_time = data['morning_time']
    if 'afternoon_time' in data:
        current_user.afternoon_time = data['afternoon_time']
    if 'evening_time' in data:
        current_user.evening_time = data['evening_time']

    # Aggiornamento password (se fornita)
    if 'current_password' in data and 'new_password' in data:
        if not check_password_hash(current_user.password, data['current_password']):
            return jsonify({'error': 'Password corrente errata'}), 401
        current_user.password = generate_password_hash(data['new_password'])

    db.session.commit()

    return jsonify({'message': 'Profilo aggiornato con successo'}), 200


#api per ottenere un es
@app.route('/api/exercise/<type>', methods=['GET'])
def get_exercise_by_type(type):
    exercises = db.session.query(Exercise).filter(Exercise.type==type).all()

    if not exercises:
        return jsonify({"error": "No exercises found for type '{}'".format(type)}), 404

    if (type == "stretching"):
        ex =  exercises[random.randint(0, len(exercises)-1)]
    elif (type == "corpo_libero"):
        ex =  exercises[random.randint(0, len(exercises)-1)]
    elif (type == "run"):
        ex = exercises[0]
    elif (type == "walk"):
        ex = exercises[0]

    return jsonify({
        "id": ex.id,
        "name": ex.name,
        "description": ex.description,
        "duration": ex.duration,
        "type": ex.type,
        "image_url": ex.image_url
    })

#api di modifica dati user
@app.route('/api/update-settings', methods=['PUT'])
def update_settings():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User ID mancante'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utente non trovato'}), 404

    # Aggiorna solo i campi delle impostazioni
    if 'break_duration' in data:
        user.break_duration = data['break_duration']
    if 'morning_time' in data:
        user.morning_time = data['morning_time']
    if 'afternoon_time' in data:
        user.afternoon_time = data['afternoon_time']
    if 'evening_time' in data:
        user.evening_time = data['evening_time']

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Impostazioni aggiornate con successo',
            'user': {
                'break_duration': user.break_duration,
                'morning_time': user.morning_time,
                'afternoon_time': user.afternoon_time,
                'evening_time': user.evening_time
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Rotta di test
@app.route('/')
def home():
    #add_exercises()
    return render_template('index.html')

#ultima route del file che reindirizza  di tutte le richieste non gestite da index.html
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return send_from_directory(app.static_folder, 'index.html')

# Avvia l'app
if __name__ == '__main__':
    app.run(debug=True)
