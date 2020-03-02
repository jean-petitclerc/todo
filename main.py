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


# Database Model
# ----------------------------------------------------------------------------------------------------------------------
class AdminUser(db.Model):
    __tablename__ = 'tadmin_user'
    user_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    user_email = db.Column(db.String(80), nullable=False, unique=True)
    user_pass = db.Column(db.String(100), nullable=False)
    activated = db.Column(db.Boolean(), nullable=False, default=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)

    def __init__(self, first_name, last_name, user_email, user_pass, audit_crt_ts):
        self.first_name = first_name
        self.last_name = last_name
        self.user_email = user_email
        self.user_pass = user_pass
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<user: {}>'.format(self.user_email)


class TaskList(db.Model):
    __tablename__ = 'ttask_list'
    list_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    list_name = db.Column(db.String(50), nullable=False)
    list_desc = db.Column(db.Text(), nullable=False, default='')
    audit_crt_user = db.Column(db.String(80), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.String(80), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)

    def __init__(self, list_name, list_desc, audit_crt_user, audit_crt_ts):
        self.list_name = list_name
        self.list_desc = list_desc
        self.audit_crt_user = audit_crt_user
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<task_list: {}'.format(self.list_name)


# Classes pour définir les formulaires WTF
# ----------------------------------------------------------------------------------------------------------------------

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


# Formulaires pour ajouter une liste de tâches
class AddTaskListForm(FlaskForm):
    list_name = StringField('Nom de la liste', validators=[DataRequired(message='Le nom est requis.')])
    list_desc = TextAreaField('Description')
    submit = SubmitField('Ajouter')


# Formulaire de la mise à jour d'une liste de tâches
class UpdTaskListForm(FlaskForm):
    list_name = StringField('Nom de la liste', validators=[DataRequired(message='Le nom est requis.')])
    list_desc = TextAreaField('Description')
    submit = SubmitField('Modifier')


# Formulaire pour confirmer la suppression d'une liste de tâches
class DelTaskListForm(FlaskForm):
    submit = SubmitField('Supprimer')


# The following functions are views
# ----------------------------------------------------------------------------------------------------------------------

# Custom error pages
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# Index
@app.route('/')
def index():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering index()')
    first_name = session.get('first_name', None)
    return render_template('todo.html', user=first_name)


# Views for Register, logging in, logging out and listing users
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
    session.pop('user_id', None)
    session.pop('first_name', None)
    session.pop('last_name', None)
    session.pop('user_email', None)
    session.pop('active_time', None)
    flash('Vous êtes maintenant déconnecté.')
    return redirect(url_for('index'))


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
            if db_add_user(first_name, last_name, user_email, user_pass):
                flash('Vous pourrez vous connecter quand votre usager sera activé.')
                return redirect(url_for('login'))
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
    return render_template('register.html', form=form)


@app.route('/list_users')
def list_users():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        admin_users = AdminUser.query.order_by(AdminUser.first_name).all()
        return render_template('list_users.html', admin_users=admin_users)
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return redirect(url_for('index'))


@app.route('/act_user/<int:user_id>', methods=['GET', 'POST'])
def act_user(user_id):
    if not logged_in():
        return redirect(url_for('login'))
    if db_act_user(user_id):
        flash("L'utilisateur est activé.")
    else:
        flash("Quelque chose n'a pas fonctionné.")
    return redirect(url_for('list_users'))


# Views for Lists of Tasks
# Ordre des vues: list, show, add, upd, del
@app.route('/list_tasklists')
def list_tasklists():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasklists = TaskList.query.order_by(TaskList.list_name).all()
        return render_template('list_tasklists.html', tasklists=tasklists)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        abort(500)


@app.route('/show_tasklist/<int:list_id>')
def show_tasklist(list_id):
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasklist = TaskList.query.get(list_id)
        if tasklist:
            return render_template("show_tasklist.html", tasklist=tasklist)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('list_tasklists'))
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        abort(500)


@app.route('/add_tasklist', methods=['GET', 'POST'])
def add_tasklist():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_tasklist')
    form = AddTaskListForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new tasklist')
        list_name = request.form['list_name']
        list_desc = request.form['list_desc']
        if db_add_tasklist(list_name, list_desc):
            flash('La nouvelle liste est ajoutée.')
            return redirect(url_for('list_tasklists'))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_tasklist.html', form=form)


@app.route('/upd_tasklist/<int:list_id>', methods=['GET', 'POST'])
def upd_tasklist(list_id):
    if not logged_in():
        return redirect(url_for('login'))
    session['tasklist_id'] = list_id
    form = UpdTaskListForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a tasklist')
        list_name = form.list_name.data
        list_desc = form.list_desc.data
        if db_upd_tasklist(list_id, list_name, list_desc):
            flash("La liste a été modifiée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tasklists'))
    else:
        tasklist = TaskList.query.get(list_id)
        if tasklist:
            form.list_name.data = tasklist.list_name
            form.list_desc.data = tasklist.list_desc
#            sections = Section.query.filter_by(checklist_id=checklist_id, deleted_ind='N') \
#                .order_by(Section.section_seq).all()
            return render_template("upd_tasklist.html", form=form, list_id=list_id,
                                   name=tasklist.list_name, desc=tasklist.list_desc)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('list_tasklists'))


@app.route('/del_tasklist/<int:list_id>', methods=['GET', 'POST'])
def del_tasklist(list_id):
    # TODO Refuser s'il y a des tâches dans la liste
    if not logged_in():
        return redirect(url_for('login'))
    form = DelTaskListForm()
    if form.validate_on_submit():
        app.logger.debug('Deleting a tasklist')
        if db_del_tasklist(list_id):
            flash("La liste a été effacée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tasklists'))
    else:
        try:
            tasklist = TaskList.query.get(list_id)
            # Ici ce serait une bonne place pour voir s'il y a des tâches
            if tasklist:
                return render_template('del_tasklist.html', form=form, list_name=tasklist.list_name)
            else:
               flash("L'information n'a pas pu être retrouvée.")
               return redirect(url_for('list_tasklists'))
        except Exception as e:
            flash("Quelque chose n'a pas fonctionné.")
            abort(500)


# Application functions
# ----------------------------------------------------------------------------------------------------------------------
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


# Database functions
# ----------------------------------------------------------------------------------------------------------------------

# Database functions for AdminUser
def db_add_user(first_name, last_name, user_email, user_pass):
    audit_crt_ts = datetime.now()
    try:
        user = AdminUser(first_name, last_name, user_email, user_pass, audit_crt_ts)
        if user_email == "jean.petitclerc@groupepp.com":
            user.activated = True
        db.session.add(user)
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False


def db_act_user(user_id):
    try:
        user = AdminUser.query.get(user_id)
        user.activated = True
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False


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
            session['user_id'] = user.user_id
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


# DB functions for TaskList
def db_add_tasklist(list_name, list_desc):
    audit_crt_user = session.get('user_email', None)
    audit_crt_ts = datetime.now()
    tasklist = TaskList(list_name, list_desc, audit_crt_user, audit_crt_ts)
    try:
        db.session.add(tasklist)
        db.session.commit()
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False
    return True


def db_upd_tasklist(list_id, list_name, list_desc):
    audit_upd_user = session.get('user_email', None)
    audit_upd_ts = datetime.now()
    try:
        tasklist = TaskList.query.get(list_id)
        tasklist.list_name = list_name
        tasklist.list_desc = list_desc
        tasklist.audit_upd_user = audit_upd_user
        tasklist.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False
    return True


def db_del_tasklist(list_id):
    try:
        tasklist = TaskList.query.get(list_id)
        db.session.delete(tasklist)
        db.session.commit()
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False
    return True


# Start the server for the application
if __name__ == '__main__':
    manager.run()
