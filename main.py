from flask import Flask, session, redirect, url_for, request, render_template, flash, g, abort  # escape
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, BooleanField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, NumberRange  # Length, NumberRange
from flask_script import Manager
from flask_sqlalchemy import SQLAlchemy
from config import DevConfig
from datetime import datetime


app = Flask(__name__)
app.config.from_object(DevConfig)
manager = Manager(app)
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)


class AdminUser(db.Model):
    __tablename__ = 'tadmin_user'
    user_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    user_email = db.Column(db.String(80), nullable=False, unique=True)
    user_pass = db.Column(db.String(100), nullable=False)
    activated = db.Column(db.Boolean(), nullable=False, default=True)

    def __init__(self, first_name, last_name, user_email, user_pass):
        self.first_name = first_name
        self.last_name = last_name
        self.user_email = user_email
        self.user_pass = user_pass

    def __repr__(self):
        return '<user: {}>'.format(self.user_email)


# Formulaire web pour l'écran de login
class LoginForm(FlaskForm):
    email = StringField('Courriel', validators=[DataRequired(), Email(message='Le courriel est invalide.')])
    password = PasswordField('Mot de Passe', [DataRequired(message='Le mot de passe est obligatoire.')])
    request_password_change = BooleanField('Changer le mot de passe?')
    password_1 = PasswordField('Nouveau Mot de passe',
                               [EqualTo('password_2', message='Les mots de passe doivent être identiques.')])
    password_2 = PasswordField('Confirmation')
    submit = SubmitField('Se connecter')


# Formulaire web pour l'écran de register
class RegisterForm(FlaskForm):
    first_name = StringField('Prénom', validators=[DataRequired(message='Le prénom est requis.')])
    last_name = StringField('Nom de famille', validators=[DataRequired(message='Le nom de famille est requis.')])
    email = StringField('Courriel', validators=[DataRequired(), Email(message='Le courriel est invalide.')])
    password_1 = PasswordField('Mot de passe',
                               [DataRequired(message='Le mot de passe est obligatoire.'),
                                EqualTo('password_2', message='Les mots de passe doivent être identiques.')])
    password_2 = PasswordField('Confirmation')
    submit = SubmitField('S\'enrégistrer')


# The following functions are views
@app.route('/')
def index():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering index()')
    first_name = session.get('first_name', None)
    return render_template('todo.html', user=first_name)


@app.route('/login', methods=['GET', 'POST'])
def login():
    # The method is GET when the form is displayed and POST to process the form
    app.logger.debug('Entering login()')
    form = LoginForm()
    if form.validate_on_submit():
        user_email = request.form['email']
        password = request.form['password']
        if db_validate_user(user_email, password):
            session['active_time'] = datetime.now()
            request_pwd_change = request.form.get('request_password_change', None)
            if request_pwd_change:
                app.logger.debug("Changer le mot de passe")
                new_password = request.form['password_1']
                db_change_password(user_email, new_password)
            return redirect(url_for('index'))
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    app.logger.debug('Entering logout()')
    session.pop('first_name', None)
    session.pop('last_name', None)
    session.pop('user_email', None)
    session.pop('active_time', None)
    flash('Vous êtes maintenant déconnecté.')
    return redirect(url_for('index'))


def logged_in():
    user_email = session.get('user_email', None)
    if user_email:
        active_time = session['active_time']
        delta = datetime.now() - active_time
        if (delta.days > 0) or (delta.seconds > 1800):
            flash('Votre session est expirée.')
            return False
        session['active_time'] = datetime.now()
        return True
    else:
        return False


@app.route('/register', methods=['GET', 'POST'])
def register():
    app.logger.debug('Entering register')
    form = RegisterForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new registration')
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        user_email = request.form['email']
        user_pass = generate_password_hash(request.form['password_1'])
        if db_user_exists(user_email):
            flash('Cet usager existe déjà. Veuillez vous connecter.')
            return redirect(url_for('login'))
        else:
            user = AdminUser(first_name, last_name, user_email, user_pass)
            db.session.add(user)
            db.session.commit()
            flash('Come back when your login will be activated.')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/list_users')
def list_users():
    if not logged_in():
        return redirect(url_for('login'))
    # pred_vars = Predef_Var.query.order_by(Predef_Var.var_name).all()
    # return render_template('list_vars.html', pred_vars=pred_vars)


def db_user_exists(user_email):
    app.logger.debug('Entering user_exists with: ' + user_email)
    try:
        user = AdminUser.query.filter_by(user_email=user_email).first()
        if user is None:
            app.logger.debug('user_exists returns False')
            return False
        else:
            app.logger.debug('user_exists returns True' + user_email)
            return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False


def db_change_password(user_email, new_password):
    try:
        user = AdminUser.query.filter_by(user_email=user_email).first()
        if user is None:
            flash("Mot de passe inchangé. L'usager n'a pas été retrouvé.")
            return False
        else:
            user.user_pass = generate_password_hash(new_password)
            db.session.commit()
            flash("Mot de passe changé.")
            return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        flash("Mot de passe inchangé. Une erreur interne s'est produite.")
        return False


# Validate if a user is defined in tadmin_user with the proper password.
def db_validate_user(user_email, password):
    try:
        user = AdminUser.query.filter_by(user_email=user_email).first()
        if user is None:
            flash("L'usager n'existe pas.")
            return False

        if not user.activated:
            flash("L'usager n'est pas activé.")
            return False

        if check_password_hash(user.user_pass, password):
            session['user_email'] = user.user_email
            session['first_name'] = user.first_name
            session['last_name'] = user.last_name
            return True
        else:
            flash("Mauvais mot de passe!")
            return False
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        flash("Connection impossible. Une erreur interne s'est produite.")
        return False


# Start the server for the application
if __name__ == '__main__':
    manager.run()
