from flask import (Flask,
                   session,
                   redirect,
                   url_for,
                   request,
                   render_template,
                   flash,
                   abort)  # g, escape
from werkzeug.security import (generate_password_hash,
                               check_password_hash)
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import (StringField,
                            PasswordField,
                            TextAreaField,
                            BooleanField,
                            SubmitField,
                            IntegerField,
                            SelectField)  # RadioField
from wtforms.fields.html5 import DateField
from wtforms.widgets import Select
from wtforms.widgets.html5 import (DateInput,
                                   NumberInput)
from wtforms.validators import (DataRequired,
                                Email,
                                EqualTo,
                                Optional)  # Length, NumberRange
from flask_script import Manager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from config import Config
from datetime import timedelta
from datetime import datetime
from calendar import monthrange

app = Flask(__name__)
app.config.from_object(Config)
manager = Manager(app)
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
dow = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
dow_choices = [('6', 'Dimanche'), ('0', 'Lundi'), ('1', 'Mardi'), ('2', 'Mercredi'),
               ('3', 'Jeudi'), ('4', 'Vendredi'), ('5', 'Samedi')]
sched_types = {'O': 'Unique', 'd': 'Quotidienne', 'w': 'Hebdomadaire', 'm': 'Mensuelle',
               'D': 'À chaque x jours', 'W': 'À chaque x semaines', 'M': 'À chaque x mois'}
task_status = {'T': 'À Faire', 'D': 'Faite', 'C': 'Annulée', 'S': 'Sautée'}


# Database Model
# ----------------------------------------------------------------------------------------------------------------------
class AppUser(db.Model):
    __tablename__ = 'tapp_user'
    user_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    user_email = db.Column(db.String(80), nullable=False, unique=True)
    user_pass = db.Column(db.String(100), nullable=False)
    activated_ts = db.Column(db.DateTime(), nullable=True)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    user_role = db.Column(db.String(10), nullable=False, default='Régulier')
    tasks = db.relationship('Assignment', backref='tapp_user', lazy='dynamic')

    def __init__(self, first_name, last_name, user_email, user_pass, audit_crt_ts):
        self.first_name = first_name
        self.last_name = last_name
        self.user_email = user_email
        self.user_pass = user_pass
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<user: {} {}>'.format(self.first_name, self.last_name)

    def user_name(self):
        return '{} {}'.format(self.first_name, self.last_name)


class TaskList(db.Model):
    __tablename__ = 'ttask_list'
    list_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    list_name = db.Column(db.String(50), nullable=False, unique=True)
    list_desc = db.Column(db.Text(), nullable=False, default='')
    audit_crt_user = db.Column(db.Integer(), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.Integer(), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    tasks = db.relationship('Task', backref='ttask_list', lazy='dynamic')

    def __init__(self, list_name, list_desc, audit_crt_user, audit_crt_ts):
        self.list_name = list_name
        self.list_desc = list_desc
        self.audit_crt_user = audit_crt_user
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<task_list: {}'.format(self.list_name)


class Task(db.Model):
    __tablename__ = 'ttask'
    task_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    list_id = db.Column(db.Integer(), db.ForeignKey('ttask_list.list_id'))
    task_name = db.Column(db.String(50), nullable=False, unique=True)
    task_desc = db.Column(db.Text, nullable=False, default='')
    audit_crt_user = db.Column(db.Integer(), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.Integer(), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    tags = db.relationship('TaskTag', cascade="all,delete", backref='ttask', lazy='dynamic')
    schedules = db.relationship('TaskSched', cascade="all,delete", backref='ttask', lazy='dynamic')
    assignees = db.relationship('Assignment', cascade="all,delete", backref='ttask', lazy='dynamic')
    occurences = db.relationship('TaskOccurence', cascade="all,delete", backref='ttask', lazy='dynamic')

    def __init__(self, list_id, task_name, task_desc, audit_crt_user, audit_crt_ts):
        self.list_id = list_id
        self.task_name = task_name
        self.task_desc = task_desc
        self.audit_crt_user = audit_crt_user
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<task: {}'.format(self.task_name)


class TaskSched(db.Model):
    __tablename__ = 'ttask_sched'
    sched_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer(), db.ForeignKey('ttask.task_id'))
    sched_type = db.Column(db.String(1), nullable=False)       # O:one, d:daily, w:weekly, m:monthly, D,W,M every x
    sched_start_dt = db.Column(db.Date, nullable=False)
    sched_end_dt = db.Column(db.Date, nullable=True)
    sched_last_occ_dt = db.Column(db.Date, nullable=True)     # Last occurence date
    sched_dow = db.Column(db.SmallInteger(), nullable=True)    # Day of week, 0..6
    sched_dom = db.Column(db.SmallInteger(), nullable=True)    # Day of month 0..31
    sched_int = db.Column(db.SmallInteger(), nullable=True)    # Interval for every x D,W,M
    audit_crt_user = db.Column(db.Integer(), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.Integer(), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    occurences = db.relationship('TaskOccurence', cascade="all,delete", backref='ttask_sched', lazy='dynamic')

    def __init__(self, task_id, sched_type, sched_start_dt, sched_end_dt, sched_last_occ_dt,
                 sched_dow, sched_dom, sched_int, audit_crt_user, audit_crt_ts):
        self.task_id = task_id
        self.sched_type = sched_type
        self.sched_start_dt = sched_start_dt
        self.sched_end_dt = sched_end_dt
        self.sched_last_occ_dt = sched_last_occ_dt
        self.sched_dow = sched_dow
        self.sched_dom = sched_dom
        self.sched_int = sched_int
        self.audit_crt_user = audit_crt_user
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<task_sched: {}'.format(self.sched_id)


class TaskOccurence(db.Model):
    __tablename__ = 'ttask_occur'
    occur_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer(), db.ForeignKey('ttask.task_id'))
    sched_id = db.Column(db.Integer(), db.ForeignKey('ttask_sched.sched_id'))
    sched_dt = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(1), nullable=False, default='T')  # T:To_do, D:Done, C:Cancelled, S:Skipped
    audit_upd_user = db.Column(db.Integer(), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)

    def __init__(self, task_id, sched_id, sched_dt):
        self.task_id = task_id
        self.sched_id = sched_id
        self.sched_dt = sched_dt
        self.status = 'T'
        return

    def __repr__(self):
        return '<task_occurence: {}:{}'.format(self.task_id, self.sched_id)


class Assignment(db.Model):
    # TODO: Unique on user_id, task_id
    __tablename__ = 'tassignment'
    # __table_args__ = (
    #     db.UniqueConstraint('user_id', 'task_id', name='x1')
    #     )
    asgn_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('tapp_user.user_id'))
    task_id = db.Column(db.Integer, db.ForeignKey('ttask.task_id'))

    def __init__(self, task_id, user_id):
        self.task_id = task_id
        self.user_id = user_id

    def __repr__(self):
        return '<assignment: {}:{}>'.format(self.task_id, self.user_id)


class Tag(db.Model):
    __tablename__ = 'ttag'
    tag_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    tag_name = db.Column(db.String(50), nullable=False, unique=True)
    audit_crt_user = db.Column(db.Integer(), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.Integer(), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    tasks = db.relationship('TaskTag', backref='ttag', lazy='dynamic')

    def __init__(self, tag_name, audit_crt_user, audit_crt_ts):
        self.tag_name = tag_name
        self.audit_crt_user = audit_crt_user
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<tag: {}'.format(self.tag_name)


class TaskTag(db.Model):
    __tablename__ = 'ttask_tag'
    task_id = db.Column(db.Integer(), db.ForeignKey('ttask.task_id'), primary_key=True)
    tag_id = db.Column(db.Integer(), db.ForeignKey('ttag.tag_id'), primary_key=True)

    def __init__(self, task_id, tag_id):
        self.tag_id = tag_id
        self.task_id = task_id

    def __repr__(self):
        return '<task_tag: {}.{}'.format(self.task_id, self.tag_id)


# Classes pour définir les formulaires WTF
# ----------------------------------------------------------------------------------------------------------------------

# Formulaire pour confirmer la suppression d'une entitée
class DelEntityForm(FlaskForm):
    submit = SubmitField('Supprimer')


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


# Formulaires pour ajouter une tâches
class AddTaskForm(FlaskForm):
    task_name = StringField('Nom de la tâche', validators=[DataRequired(message='Le nom est requis.')])
    task_desc = TextAreaField('Description')
#    task_sched_type = RadioField('O', choices=[('O', "Une fois"), ('d', "Quotidien"), ('w', "Hebdomadaire"),
#                                               ('m', "Mensuel")])  # O:one, d:daily, w:weekly, m:monthly, D,W,M every x
    submit = SubmitField('Ajouter')


# Formulaire de la mise à jour d'une tâche
class UpdTaskForm(FlaskForm):
    task_name = StringField('Nom de la tâche', validators=[DataRequired(message='Le nom est requis.')])
    task_desc = TextAreaField('Description')
    submit = SubmitField('Modifier')


# Formulaires pour ajouter une étiquette
class AddTagForm(FlaskForm):
    tag_name = StringField("Nom de l'étiquette", validators=[DataRequired(message='Le nom est requis.')])
    submit = SubmitField('Ajouter')


# Formulaire de la mise à jour d'une étiquette
class UpdTagForm(FlaskForm):
    tag_name = StringField("Nom de l'étiquette", validators=[DataRequired(message='Le nom est requis.')])
    submit = SubmitField('Modifier')


# Formulaires pour ajouter une cédule
class AddSchedForm(FlaskForm):
    #    sched_type = SelectField("Type de cédule", choices=['O', 'd', 'w', 'm', 'D', 'W', 'M'],
    #                             validators=[DataRequired(message='Le type est requis.')])
    submit = SubmitField('Suivant')


class AddSchedOneForm(FlaskForm):
    sched_start_dt = DateField("Date: ",
                               validators=[DataRequired(message='La date est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    submit = SubmitField('Ajouter')


class UpdSchedOneForm(FlaskForm):
    sched_start_dt = DateField("Date: ",
                               validators=[DataRequired(message='La date est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    submit = SubmitField('Modifier')


class AddSchedDailyForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    submit = SubmitField('Ajouter')


class UpdSchedDailyForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    submit = SubmitField('Modifier')


class AddSchedWeeklyForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_dow = SelectField("Jour de la semaine: ", choices=dow_choices,
                            validators=[DataRequired(message="Le jour de la semaine doit être choisi.")],
                            default=0, widget=Select())
    submit = SubmitField('Ajouter')


class UpdSchedWeeklyForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_dow = SelectField("Jour de la semaine: ", choices=dow_choices,
                            validators=[DataRequired(message="Le jour de la semaine doit être choisi.")],
                            default=0, widget=Select())
    submit = SubmitField('Modifier')


class AddSchedMonthlyForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    submit = SubmitField('Ajouter')


class UpdSchedMonthlyForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    submit = SubmitField('Ajouter')


class AddSchedEveryXDaysForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_int = IntegerField('Interval (en jours): ', default=3,
                             validators=[DataRequired(message="L'interval est requis.")],
                             widget=NumberInput(min=1, max=30))
    submit = SubmitField('Ajouter')


class UpdSchedEveryXDaysForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_int = IntegerField('Interval (en jours): ', default=3,
                             validators=[DataRequired(message="L'interval est requis.")],
                             widget=NumberInput(min=1, max=30))
    submit = SubmitField('Modifier')


class AddSchedEveryXWeeksForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_dow = SelectField("Jour de la semaine: ", choices=dow_choices,
                            validators=[DataRequired(message="Le jour de la semaine doit être choisi.")],
                            default='0', widget=Select())
    sched_int = IntegerField('Interval (en semaines): ', default=2,
                             validators=[DataRequired(message="L'interval est requis.")],
                             widget=NumberInput(min=1, max=30))
    submit = SubmitField('Ajouter')


class UpdSchedEveryXWeeksForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_dow = SelectField("Jour de la semaine: ", choices=dow_choices,
                            validators=[DataRequired(message="Le jour de la semaine doit être choisi.")],
                            widget=Select())
    sched_int = IntegerField('Interval (en semaines): ', default=2,
                             validators=[DataRequired(message="L'interval est requis.")],
                             widget=NumberInput(min=1, max=30))
    submit = SubmitField('Modifier')


class AddSchedEveryXMonthsForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_int = IntegerField('Interval (en mois): ', default=2,
                             validators=[DataRequired(message="L'interval est requis.")],
                             widget=NumberInput(min=1, max=30))
    submit = SubmitField('Ajouter')


class UpdSchedEveryXMonthsForm(FlaskForm):
    sched_start_dt = DateField("Date de début: ",
                               validators=[DataRequired(message='La date de début est requise.')],
                               format='%Y-%m-%d', widget=DateInput())
    sched_end_dt = DateField("Date de fin (Optionelle): ", format='%Y-%m-%d',
                             validators=[Optional()], widget=DateInput())
    sched_int = IntegerField('Interval (en mois): ', default=2,
                             validators=[DataRequired(message="L'interval est requis.")],
                             widget=NumberInput(min=1, max=30))
    submit = SubmitField('Modifier')


# The following functions are views
# ----------------------------------------------------------------------------------------------------------------------

# Custom error pages
@app.errorhandler(404)
def page_not_found(e):
    app.logger.error('Page non trouvée. ' + str(e))
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error('Erreur interne. ' + str(e))
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
            flash('Cet utilisateur existe déjà. Veuillez vous connecter.')
            return redirect(url_for('login'))
        else:
            if db_add_user(first_name, last_name, user_email, user_pass):
                flash('Vous pourrez vous connecter quand votre utilisateur sera activé.')
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
        user_id = session.get('user_id')
        admin_user = db_user_is_admin(user_id)
        app_users = AppUser.query.order_by(AppUser.first_name).all()
        return render_template('list_users.html', app_users=app_users, admin_user=admin_user)
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return redirect(url_for('index'))


@app.route('/act_user/<int:user_id>', methods=['GET', 'POST'])
def act_user(user_id):
    if not logged_in():
        return redirect(url_for('login'))
    cur_user_id = session.get('user_id')
    if db_user_is_admin(cur_user_id):
        if db_upd_user_status(user_id, 'A'):
            flash("L'utilisateur est activé.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
    else:
        flash("Vous n'êtes pas autorisé à changer le status d'un utilisateur.")
    return redirect(url_for('list_users'))


@app.route('/inact_user/<int:user_id>', methods=['GET', 'POST'])
def inact_user(user_id):
    if not logged_in():
        return redirect(url_for('login'))
    cur_user_id = session.get('user_id')
    if db_user_is_admin(cur_user_id):
        if db_upd_user_status(user_id, 'D'):
            flash("L'utilisateur est désactivé.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
    else:
        flash("Vous n'êtes pas autorisé à changer le status d'un utilisateur.")
    return redirect(url_for('list_users'))


@app.route('/set_user_admin/<int:user_id>', methods=['GET', 'POST'])
def set_user_admin(user_id):
    if not logged_in():
        return redirect(url_for('login'))
    cur_user_id = session.get('user_id')
    if db_user_is_admin(cur_user_id):
        if db_upd_user_role(user_id, 'A'):
            flash("L'utilisateur est maintenant administrateur.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
    else:
        flash("Vous n'êtes pas autorisé à changer le rôle d'un utilisateur.")
    return redirect(url_for('list_users'))


@app.route('/set_user_regular/<int:user_id>', methods=['GET', 'POST'])
def set_user_regular(user_id):
    if not logged_in():
        return redirect(url_for('login'))
    cur_user_id = session.get('user_id')
    if db_user_is_admin(cur_user_id):
        if db_upd_user_role(user_id, 'R'):
            flash("L'utilisateur est maintenant un utilisateur régulier.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
    else:
        flash("Vous n'êtes pas autorisé à changer le rôle d'un utilisateur.")
    return redirect(url_for('list_users'))


@app.route('/del_user/<int:user_id>', methods=['GET', 'POST'])
def del_user(user_id):
    if not logged_in():
        return redirect(url_for('login'))
    cur_user_id = session.get('user_id')
    if db_user_is_admin(cur_user_id):
        form = DelEntityForm()
        if form.validate_on_submit():
            app.logger.debug('Deleting a user')
            # if db_del_user(user_id):
            #    flash("L'utilisateur a été effacé.")
            # else:
            #    flash("Quelque chose n'a pas fonctionné.")
            flash("Cette fonction n'est pas encore implantée. ")
        else:
            user = db_user_by_id(user_id)
            if user:
                return render_template('del_user.html', form=form, user=user)
            else:
                flash("L'information n'a pas pu être retrouvée.")
    else:
        flash("Vous n'êtes pas autorisé à supprimer un utilisateur.")
    return redirect(url_for('list_users'))


# Views for Lists of Tasks
# Ordre des vues: list, show, add, upd, del
@app.route('/list_tasklists')
def list_tasklists():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasklists = TaskList.query.order_by(TaskList.list_name).all()
        for tasklist in tasklists:
            u = db_user_by_id(tasklist.audit_crt_user)
            tasklist.audit_crt_user_name = u.user_name()
        return render_template('list_tasklists.html', tasklists=tasklists)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/show_tasklist/<int:list_id>')
def show_tasklist(list_id):
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasklist = TaskList.query.get(list_id)
        if tasklist:
            u = db_user_by_id(tasklist.audit_crt_user)
            tasklist.audit_crt_user_name = u.user_name()
            if tasklist.audit_upd_user:
                u = db_user_by_id(tasklist.audit_upd_user)
                tasklist.audit_upd_user_name = u.user_name()
            tasks = Task.query.filter_by(list_id=list_id) \
                .order_by(Task.task_name).all()
            return render_template("show_tasklist.html", tasklist=tasklist, tasks=tasks)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('list_tasklists'))
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
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
        if db_tasklist_exists(list_name):
            flash('Ce nom de liste existe déjà. Veuillez en choisir un autre.')
            return render_template('add_tasklist.html', form=form)
        else:
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
    session['list_id'] = list_id
    tasklist = db_tasklist_by_id(list_id)
    if tasklist is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('list_tasklists'))
    else:
        tasks = Task.query.filter_by(list_id=list_id) \
            .order_by(Task.task_name).all()
    form = UpdTaskListForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a tasklist')
        save_list_name = tasklist.list_name
        list_name = form.list_name.data
        list_desc = form.list_desc.data
        if (list_name != save_list_name) and db_tasklist_exists(list_name):
            flash('Ce nom de liste existe déjà. Veuillez en choisir un autre.')
            return render_template("upd_tasklist.html", form=form, list_id=list_id, tasks=tasks)
        if db_upd_tasklist(list_id, list_name, list_desc):
            flash("La liste a été modifiée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tasklists'))
    else:
        form.list_name.data = tasklist.list_name
        form.list_desc.data = tasklist.list_desc
        return render_template("upd_tasklist.html", form=form, list_id=list_id, tasks=tasks)


@app.route('/del_tasklist/<int:list_id>', methods=['GET', 'POST'])
def del_tasklist(list_id):
    if not logged_in():
        return redirect(url_for('login'))
    form = DelEntityForm()
    if form.validate_on_submit():
        app.logger.debug('Deleting a tasklist')
        if db_del_tasklist(list_id):
            flash("La liste a été effacée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tasklists'))
    else:
        tasklist = db_tasklist_by_id(list_id)
        tasks = db_tasklist_has_tasks(list_id)
        if tasks is None:
            flash("L'application n'a pas pu déterminer s'il y avait des tâches dans la liste.")
            return redirect(url_for('list_tasklists'))
        if tasks > 0:
            flash("La liste a des tâches. Elle ne peut pas être effacée.")
            return redirect(url_for('list_tasklists'))
        if tasklist:
            return render_template('del_tasklist.html', form=form, list_name=tasklist.list_name)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('list_tasklists'))


# Views for Tasks
# Ordre des vues: list, show, add, upd, del
@app.route('/list_tasks_for_me')
def list_tasks_for_me():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        user_id = session.get('user_id', None)
        if user_id:
            user = AppUser.query.get(user_id)
            tasks = AppUser.query.join(Assignment, AppUser.user_id == Assignment.user_id)\
                .join(Task, Assignment.task_id == Task.task_id)\
                .join(TaskSched, Task.task_id == TaskSched.task_id)\
                .join(TaskOccurence, TaskSched.sched_id == TaskOccurence.sched_id)\
                .filter(AppUser.user_id == user_id, TaskOccurence.status == 'T')\
                .add_columns(Task.task_id, Task.task_name,
                             TaskSched.sched_type, TaskSched.sched_int, TaskSched.sched_dow, TaskSched.sched_dom,
                             TaskOccurence.sched_dt, TaskOccurence.occur_id)\
                .order_by(TaskOccurence.sched_dt)
            return render_template('list_tasks_for_me.html', user=user, tasks=tasks, sched_types=sched_types, dow=dow)
        else:
            flash("Quelque chose n'a pas fonctionné.")
            abort(500)
        return render_template('todo.html')
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/list_tasks_for_all')
def list_tasks_for_all():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasks = AppUser.query.join(Assignment, AppUser.user_id == Assignment.user_id)\
            .join(Task, Assignment.task_id == Task.task_id)\
            .join(TaskSched, Task.task_id == TaskSched.task_id)\
            .join(TaskOccurence, TaskSched.sched_id == TaskOccurence.sched_id)\
            .filter(TaskOccurence.status == 'T')\
            .add_columns(AppUser.first_name,
                         Task.task_id, Task.task_name,
                         TaskSched.sched_type, TaskSched.sched_int, TaskSched.sched_dow, TaskSched.sched_dom,
                         TaskOccurence.sched_dt, TaskOccurence.occur_id)\
            .order_by(TaskOccurence.sched_dt, Task.task_name, TaskSched.sched_id, AppUser.first_name)
        return render_template('list_tasks_for_all.html', tasks=tasks, sched_types=sched_types, dow=dow)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/list_tasks_not_assigned')
def list_tasks_not_assigned():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasks = Task.query.join(TaskList, Task.list_id == TaskList.list_id)\
            .add_columns(TaskList.list_name, Task.task_id, Task.task_name)\
            .order_by(TaskList.list_name, Task.task_name)
        l_tasks = []
        for task in tasks:
            assignee = Assignment.query.filter_by(task_id=task.task_id).first()
            if assignee is None:
                l_tasks.append(task)
        return render_template('list_tasks_not_assigned.html', tasks=l_tasks)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/list_tasks_no_sched')
def list_tasks_no_sched():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasks = Task.query.join(TaskList, Task.list_id == TaskList.list_id)\
            .add_columns(TaskList.list_name, Task.task_id, Task.task_name)\
            .order_by(TaskList.list_name, Task.task_name)
        l_tasks = []
        for task in tasks:
            sched = TaskSched.query.filter_by(task_id=task.task_id).first()
            if sched is None:
                l_tasks.append(task)
        return render_template('list_tasks_no_sched.html', tasks=l_tasks)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/list_tasks_inactive')
def list_tasks_inactive():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tasks = Task.query.join(TaskList, Task.list_id == TaskList.list_id)\
            .add_columns(TaskList.list_name, Task.task_id, Task.task_name)\
            .order_by(TaskList.list_name, Task.task_name)
        l_tasks = []
        for task in tasks:
            inactive = True
            occ = TaskOccurence.query.filter_by(task_id=task.task_id, status='T').first()
            if occ is None:
                l_tasks.append(task)
        return render_template('list_tasks_inactive.html', tasks=l_tasks)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/list_tasks_by_tag/<int:tag_id>')
def list_tasks_by_tag(tag_id):
    if not logged_in():
        return redirect(url_for('login'))
    try:
        session['tag_id'] = tag_id
        tag = db_tag_by_id(tag_id)
        tasks = AppUser.query.join(Assignment, AppUser.user_id == Assignment.user_id)\
            .join(Task, Assignment.task_id == Task.task_id)\
            .join(TaskTag, Task.task_id == TaskTag.task_id)\
            .join(TaskSched, Task.task_id == TaskSched.task_id)\
            .join(TaskOccurence, TaskSched.sched_id == TaskOccurence.sched_id)\
            .filter(TaskTag.tag_id == tag_id, TaskOccurence.status == 'T')\
            .add_columns(AppUser.first_name,
                         Task.task_id, Task.task_name,
                         TaskSched.sched_type, TaskSched.sched_int, TaskSched.sched_dow, TaskSched.sched_dom,
                         TaskOccurence.sched_dt, TaskOccurence.occur_id)\
            .order_by(TaskOccurence.sched_dt, Task.task_name, TaskSched.sched_id, AppUser.first_name)
        return render_template('list_tasks_by_tag.html', tasks=tasks, tag=tag, sched_types=sched_types, dow=dow)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)

@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_task')
    list_id = session['list_id']
    form = AddTaskForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new task')
        task_name = request.form['task_name']
        task_desc = request.form['task_desc']
        if db_task_exists(task_name):
            flash('Ce nom de liste existe déjà. Veuillez en choisir un autre.')
            return render_template('add_task.html', form=form, list_id=list_id)
        else:
            if db_add_task(list_id, task_name, task_desc):
                flash('La nouvelle tâche est ajoutée.')
                return redirect(url_for('upd_tasklist', list_id=list_id))
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
    return render_template('add_task.html', form=form, list_id=list_id)


@app.route('/upd_task/<int:task_id>', methods=['GET', 'POST'])
def upd_task(task_id):
    if not logged_in():
        return redirect(url_for('login'))
    list_id = session['list_id']
    session['task_id'] = task_id
    task = db_task_by_id(task_id)
    if task is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_tasklist', list_id=list_id))
    else:
        app.logger.debug('getting assignees')
        list_id = task.list_id
        session['list_id'] = list_id
        count_assignees = 0
        assignees = []
        for a in task.assignees:
            asgn = {}
            asgn['asgn_id'] = a.asgn_id
            u = AppUser.query.filter_by(user_id=a.user_id).first()
            asgn['user_name'] = u.first_name + ' ' + u.last_name
            assignees.append(asgn)
            count_assignees += 1
        count_tags = 0
        tags = []
        for t_tag in task.tags:
            tag = {}
            tag['tag_id'] = t_tag.tag_id
            qtag = Tag.query.filter_by(tag_id=t_tag.tag_id).first()
            tag['tag_name'] = qtag.tag_name
            tags.append(tag)
            count_tags += 1
        count_scheds = 0
        for _ in task.schedules:
            count_scheds += 1

    form = UpdTaskForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a task')
        save_task_name = task.task_name
        task_name = form.task_name.data
        task_desc = form.task_desc.data
        if (task_name != save_task_name) and db_task_exists(task_name):
            flash('Ce nom de tâche existe déjà. Veuillez en choisir un autre.')
            return render_template("upd_task.html", form=form, list_id=list_id, task=task, dow=dow,
                                   count_assignees=count_assignees, count_tags=count_tags, count_scheds=count_scheds)
        if db_upd_task(task_id, task_name, task_desc):
            flash("La tâche a été modifiée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_tasklist', list_id=list_id))
    else:
        form.task_name.data = task.task_name
        form.task_desc.data = task.task_desc
        return render_template("upd_task.html", form=form, list_id=list_id, task=task, dow=dow,
                               assignees=assignees, count_assignees=count_assignees,
                               tags=tags, count_tags=count_tags, count_scheds=count_scheds)


@app.route('/del_task/<int:task_id>', methods=['GET', 'POST'])
def del_task(task_id):
    if not logged_in():
        return redirect(url_for('login'))
    list_id = session['list_id']
    form = DelEntityForm()
    if form.validate_on_submit():
        app.logger.debug('Deleting a task')
        if db_del_task(task_id):
            flash("La tâche a été effacée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_tasklist', list_id=list_id))
    else:
        task = db_task_by_id(task_id)
        if task:
            return render_template('del_task.html', form=form, task_name=task.task_name, list_id=list_id)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('upd_tasklist', list_id=list_id))


# Views for Assignments
# Ordre des vues: list, show, add, upd, del
@app.route('/sel_asgn/<int:task_id>')
def sel_asgn(task_id):
    if not logged_in():
        return redirect(url_for('login'))

    assignments = Assignment.query.filter_by(task_id=task_id).all()
    for a in assignments:
        u = AppUser.query.filter_by(user_id=a.user_id).first()
        a.user_name = u.first_name + ' ' + u.last_name

    tmp_users = AppUser.query.order_by(AppUser.first_name).all()
    users = []
    for u in tmp_users:
        if not db_asgn_exists(task_id, u.user_id):
            users.append(u)
    return render_template('sel_asgn.html', task_id=task_id, users=users, assignments=assignments)


@app.route('/add_asgn/<int:task_id>/<int:user_id>')
def add_asgn(task_id, user_id):
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_asgn')
    if db_add_asgn(task_id, user_id):
        flash('La tâche a été assignée.')
        return redirect(url_for('sel_asgn', task_id=task_id))
    else:
        flash('Une erreur de base de données est survenue.')
        abort(500)


@app.route('/del_asgn/<int:asgn_id>/<int:redir_to>')
def del_asgn(asgn_id, redir_to):
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering del_asgn')
    task_id = session['task_id']
    if db_del_asgn(asgn_id):
        flash('La tâche a été désassignée.')
        if redir_to == 1:
            return redirect(url_for('sel_asgn', task_id=task_id))
        else:
            return redirect(url_for('upd_task', task_id=task_id))
    else:
        flash('Une erreur de base de données est survenue.')
        abort(500)


# Views for Tags
# Ordre des vues: list, show, add, upd, del
@app.route('/list_tags')
def list_tags():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tags = Tag.query.order_by(Tag.tag_name).all()
        for tag in tags:
            u = db_user_by_id(tag.audit_crt_user)
            tag.audit_crt_user_name = u.user_name()
        return render_template('list_tags.html', tags=tags)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/show_tag/<int:tag_id>')
def show_tag(tag_id):
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tag = db_tag_by_id(tag_id)
        if tag:
            u = db_user_by_id(tag.audit_crt_user)
            tag.audit_crt_user_name = u.user_name()
            if tag.audit_upd_user:
                u = db_user_by_id(tag.audit_upd_user)
                tag.audit_upd_user_name = u.user_name()
            return render_template("show_tag.html", tag=tag)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('list_tags'))
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/add_tag', methods=['GET', 'POST'])
def add_tag():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_tag')
    form = AddTagForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new tag')
        tag_name = request.form['tag_name']
        if db_tag_exists(tag_name):
            flash("Ce nom d'étiquette existe déjà. Veuillez en choisir un autre.")
            return render_template('add_tag.html', form=form)
        else:
            if db_add_tag(tag_name):
                flash('La nouvelle étiquette est ajoutée.')
                return redirect(url_for('list_tags'))
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
    return render_template('add_tag.html', form=form)


@app.route('/upd_tag/<int:tag_id>', methods=['GET', 'POST'])
def upd_tag(tag_id):
    if not logged_in():
        return redirect(url_for('login'))
    tag = db_tag_by_id(tag_id)
    if tag is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('list_tags'))
    form = UpdTagForm()
    save_tag_name = tag.tag_name
    if form.validate_on_submit():
        app.logger.debug('Updating a tag')
        tag_name = form.tag_name.data
        if (tag_name != save_tag_name) and db_tag_exists(tag_name):
            flash("Ce nom d'étiquette existe déjà. Veuillez en choisir un autre.")
            return render_template("upd_tag.html", form=form, tag_id=tag_id, tag_name=tag.tag_name)
        if db_upd_tag(tag_id, tag_name):
            flash("L'étiquette a été modifiée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tags'))
    else:
        form.tag_name.data = tag.tag_name
        return render_template("upd_tag.html", form=form, tag_id=tag_id, tag_name=tag.tag_name)


@app.route('/del_tag/<int:tag_id>', methods=['GET', 'POST'])
def del_tag(tag_id):
    # TODO Confirmer avant d'effacer une étiquette utilisée
    if not logged_in():
        return redirect(url_for('login'))
    form = DelEntityForm()
    if form.validate_on_submit():
        app.logger.debug('Deleting a tag')
        if db_del_tag(tag_id):
            flash("L'étiquette a été effacée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tags'))
    else:
        tag = db_tag_by_id(tag_id)
        # Ici ce serait une bonne place pour voir s'il y a des tâches
        if tag:
            return render_template('del_tag.html', form=form, tag_name=tag.tag_name)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('list_tags'))


# Views for TaskTag
# Ordre des vues: list, show, add, upd, del
@app.route('/sel_ttag/<int:task_id>')
def sel_ttag(task_id):
    if not logged_in():
        return redirect(url_for('login'))

    task_tags = TaskTag.query.filter_by(task_id=task_id).all()
    for t_tag in task_tags:
        tag = Tag.query.filter_by(tag_id=t_tag.tag_id).first()
        t_tag.tag_name = tag.tag_name

    tmp_tags = Tag.query.order_by(Tag.tag_name).all()
    tags = []
    for t in tmp_tags:
        if not db_ttag_exists(task_id, t.tag_id):
            tags.append(t)
    return render_template('sel_ttag.html', task_id=task_id, tags=tags, task_tags=task_tags)


@app.route('/add_ttag/<int:task_id>/<int:tag_id>')
def add_ttag(task_id, tag_id):
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_ttag')
    if db_add_ttag(task_id, tag_id):
        flash("L'étiquette a été ajoutée.")
        return redirect(url_for('sel_ttag', task_id=task_id))
    else:
        flash('Une erreur de base de données est survenue.')
        abort(500)


@app.route('/del_ttag/<int:tag_id>/<int:redir_to>')
def del_ttag(tag_id, redir_to):
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering del_ttag')
    task_id = session['task_id']
    if db_del_ttag(task_id, tag_id):
        flash("L'étiquette a été enlevée.")
        if redir_to == 1:
            return redirect(url_for('sel_ttag', task_id=task_id))
        else:
            return redirect(url_for('upd_task', task_id=task_id))
    else:
        flash('Une erreur de base de données est survenue.')
        abort(500)


# Views for TaskSched
# Ordre des vues: list, show, add, upd, del
@app.route('/add_sched', methods=['GET', 'POST'])
def add_sched():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched')
    task_id = session['task_id']
    form = AddSchedForm()
    if form.validate_on_submit():
        app.logger.debug('Creating a new schedule')
        sched_type = request.form['sched_type']
        if sched_type == 'O':
            return redirect(url_for('add_sched_one'))
        elif sched_type == 'd':
            return redirect(url_for('add_sched_dly'))
        elif sched_type == 'w':
            return redirect(url_for('add_sched_wly'))
        elif sched_type == 'm':
            return redirect(url_for('add_sched_mly'))
        elif sched_type == 'D':
            return redirect(url_for('add_sched_xdy'))
        elif sched_type == 'W':
            return redirect(url_for('add_sched_xwk'))
        elif sched_type == 'M':
            return redirect(url_for('add_sched_xmo'))
    return render_template('add_sched.html', form=form, task_id=task_id)


@app.route('/add_sched_one', methods=['GET', 'POST'])
def add_sched_one():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_one')
    task_id = session['task_id']
    form = AddSchedOneForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'O'
        #sched_start_dt = datetime.strptime(request.form['sched_start_dt'], '%Y-%m-%d')
        sched_start_dt = form.sched_start_dt.data
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, None, sched_start_dt, None, None, None)
        if sched_id:
            flash('La nouvelle cédule unique a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche a été ajoutée.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_one.html', form=form, task_id=task_id)


@app.route('/add_sched_dly', methods=['GET', 'POST'])
def add_sched_dly():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_dly')
    task_id = session['task_id']
    form = AddSchedDailyForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'd'
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début (' +
                      str(sched_start_dt) + ').')
                return render_template('add_sched_dly.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, None, None, None, None)
        if sched_id:
            flash('La nouvelle cédule quotidienne a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche ont été ajoutées.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_dly.html', form=form, task_id=task_id)


@app.route('/add_sched_wly', methods=['GET', 'POST'])
def add_sched_wly():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_wly')
    task_id = session['task_id']
    form = AddSchedWeeklyForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'w'
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dow = request.form['sched_dow']
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début (' +
                      str(sched_start_dt) + ').')
                return render_template('add_sched_wly.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, None, sched_dow, None, None)
        if sched_id:
            flash('La nouvelle cédule hebdomadaire a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche a été ajoutée.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_wly.html', form=form, task_id=task_id)


@app.route('/add_sched_mly', methods=['GET', 'POST'])
def add_sched_mly():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_mly')
    task_id = session['task_id']
    form = AddSchedMonthlyForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'm'
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dom = sched_start_dt.day
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début (' +
                      str(sched_start_dt) + ').')
                return render_template('add_sched_mly.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, None, None, sched_dom, None)
        if sched_id:
            flash('La nouvelle cédule mensuelle a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche a été ajoutée.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_mly.html', form=form, task_id=task_id)


@app.route('/add_sched_xdy', methods=['GET', 'POST'])
def add_sched_xdy():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_xdy')
    task_id = session['task_id']
    form = AddSchedEveryXDaysForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'D'
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_int = request.form['sched_int']
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début (' +
                      str(sched_start_dt) + ').')
                return render_template('add_sched_xdy.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, None, None, None, sched_int)
        if sched_id:
            flash('La nouvelle cédule en interval de jours a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche a été ajoutée.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_xdy.html', form=form, task_id=task_id)


@app.route('/add_sched_xwk', methods=['GET', 'POST'])
def add_sched_xwk():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_xwk')
    task_id = session['task_id']
    form = AddSchedEveryXWeeksForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'W'
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dow = request.form['sched_dow']
        sched_int = request.form['sched_int']
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début (' +
                      str(sched_start_dt) + ').')
                return render_template('add_sched_xwk.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, None, sched_dow, None, sched_int)
        if sched_id:
            flash('La nouvelle cédule en interval de semaines a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche a été ajoutée.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_xwk.html', form=form, task_id=task_id)


@app.route('/add_sched_xmo', methods=['GET', 'POST'])
def add_sched_xmo():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_sched_xmo')
    task_id = session['task_id']
    form = AddSchedEveryXMonthsForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new schedule')
        sched_type = 'M'
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dom = sched_start_dt.day
        sched_int = request.form['sched_int']
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début (' +
                      str(sched_start_dt) + ').')
                return render_template('add_sched_xmo.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        sched_id = db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, None, None, sched_dom, sched_int)
        if sched_id:
            flash('La nouvelle cédule en interval de mois a été ajoutée.')
            if db_add_occur(sched_id):
                flash('Une occurence de cette tâche a été ajoutée.')
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
            return redirect(url_for('upd_task', task_id=task_id))
        else:
            flash('Une erreur de base de données est survenue.')
            abort(500)
    return render_template('add_sched_xmo.html', form=form, task_id=task_id)


@app.route('/upd_sched_one/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_one(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedOneForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        if db_upd_sched_one(sched_id, sched_start_dt):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        return render_template("upd_sched_one.html", form=form, task_id=task_id, sched=sched)


@app.route('/upd_sched_dly/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_dly(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedDailyForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début ('
                      + str(sched_start_dt) + ').')
                return render_template('upd_sched_dly.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        if db_upd_sched_dly(sched_id, sched_start_dt, sched_end_dt):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        form.sched_end_dt.data = sched.sched_end_dt
        return render_template("upd_sched_dly.html", form=form, task_id=task_id, sched=sched)


@app.route('/upd_sched_wly/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_wly(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedWeeklyForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dow = form.sched_dow.data
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début ('
                      + str(sched_start_dt) + ').')
                return render_template('upd_sched_wly.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        if db_upd_sched_wly(sched_id, sched_start_dt, sched_end_dt, sched_dow):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        form.sched_end_dt.data = sched.sched_end_dt
        form.sched_dow.data = str(sched.sched_dow)
        return render_template("upd_sched_wly.html", form=form, task_id=task_id, sched=sched)


@app.route('/upd_sched_mly/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_mly(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedMonthlyForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dom = int(str(sched_start_dt)[8:])
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début ('
                      + str(sched_start_dt) + ').')
                return render_template('upd_sched_mly.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        if db_upd_sched_mly(sched_id, sched_start_dt, sched_end_dt, sched_dom):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        form.sched_end_dt.data = sched.sched_end_dt
        return render_template("upd_sched_mly.html", form=form, task_id=task_id, sched=sched)


@app.route('/upd_sched_xdy/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_xdy(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedEveryXDaysForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_int = form.sched_int.data
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début ('
                      + str(sched_start_dt) + ').')
                return render_template('upd_sched_xdy.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        if db_upd_sched_xdy(sched_id, sched_start_dt, sched_end_dt, sched_int):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        form.sched_end_dt.data = sched.sched_end_dt
        form.sched_int.data = sched.sched_int
        return render_template("upd_sched_xdy.html", form=form, task_id=task_id, sched=sched)


@app.route('/upd_sched_xwk/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_xwk(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedEveryXWeeksForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dow = form.sched_dow.data
        sched_int = form.sched_int.data
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début ('
                      + str(sched_start_dt) + ').')
                return render_template('upd_sched_xwk.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        if db_upd_sched_xwk(sched_id, sched_start_dt, sched_end_dt, sched_dow, sched_int):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        form.sched_end_dt.data = sched.sched_end_dt
        form.sched_dow.data = str(sched.sched_dow)
        form.sched_int.data = sched.sched_int
        return render_template("upd_sched_xwk.html", form=form, task_id=task_id, sched=sched)


@app.route('/upd_sched_xmo/<int:sched_id>', methods=['GET', 'POST'])
def upd_sched_xmo(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    sched = db_sched_by_id(sched_id)
    if sched is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('upd_task', task_id=task_id))
    form = UpdSchedEveryXMonthsForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a schedule')
        sched_start_dt = form.sched_start_dt.data
        sched_end_dt = form.sched_end_dt.data
        sched_dom = str(sched_start_dt)[8:]
        sched_int = form.sched_int.data
        if sched_end_dt:
            if sched_start_dt > sched_end_dt:
                flash('La date de fin (' + str(sched_end_dt) + ') doit être après la date de début ('
                      + str(sched_start_dt) + ').')
                return render_template('upd_sched_xmo.html', form=form, task_id=task_id)
        else:
            sched_end_dt = None
        if db_upd_sched_xmo(sched_id, sched_start_dt, sched_end_dt, sched_dom, sched_int):
            flash("La cédule a été modifiée.")
            db_add_occur(sched_id, update_mode='Y')
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        form.sched_start_dt.data = sched.sched_start_dt
        form.sched_end_dt.data = sched.sched_end_dt
        form.sched_int.data = sched.sched_int
        return render_template("upd_sched_xmo.html", form=form, task_id=task_id, sched=sched)


@app.route('/del_sched/<int:sched_id>', methods=['GET', 'POST'])
def del_sched(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    form = DelEntityForm()
    if form.validate_on_submit():
        app.logger.debug('Deleting a schedule')
        if db_del_sched(sched_id):
            flash("La cédule a été effacée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('upd_task', task_id=task_id))
    else:
        sched = db_sched_by_id(sched_id)
        if sched:
            return render_template('del_sched.html', form=form, task_id=task_id, sched=sched)
        else:
            flash("L'information n'a pas pu être retrouvée.")
            return redirect(url_for('upd_task', task_id=task_id))


@app.route('/list_occurs/<int:sched_id>')
def list_occurs(sched_id):
    if not logged_in():
        return redirect(url_for('login'))
    task_id = session['task_id']
    try:
        task = db_task_by_id(task_id)
        occurs = TaskOccurence.query.filter_by(sched_id=sched_id).order_by(TaskOccurence.sched_dt).all()
        for occ in occurs:
            if occ.audit_upd_user:
                u = db_user_by_id(occ.audit_upd_user)
                occ.audit_upd_user_name = u.user_name()
            else:
                occ.audit_upd_user_name = 'N/A'
        return render_template('list_occurs.html', occurs=occurs, task=task, task_status=task_status)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
        abort(500)


@app.route('/set_occur_status/<int:occur_id>/<string:status>/<int:redir_to>')
def set_occur_status(occur_id, status, redir_to):
    if not logged_in():
        return redirect(url_for('login'))
    # task_status = {'T': 'À Faire', 'D': 'Faite', 'C': 'Annulée', 'S': 'Sautée'}
    app.logger.debug('Entering set_occur_status')
    try:
        occ = db_occur_by_id(occur_id)
        if occ:
            sched = db_sched_by_id(occ.sched_id)
            if sched:
                if db_set_occ_status(occur_id, status):
                    flash("Le status a été changé.")
                    if sched.sched_type != 'O':
                        if db_add_occur(occ.sched_id, update_mode='N'):
                            flash("L'occurence suivante a été ajoutée.")
                        else:
                            flash('Une erreur de base de données est survenue.')
                            abort(500)
                    if redir_to == 1:
                        return redirect(url_for('list_tasks_for_me'))
                    elif redir_to == 2:
                        return redirect(url_for('list_tasks_for_all'))
                    elif redir_to == 3:
                        tag_id = session['tag_id']
                        return redirect(url_for('list_tasks_by_tag', tag_id=tag_id))
                    else:
                        flash("Je ne sais pas ou retourner.")
                        abort(500)
                else:
                    flash('Une erreur de base de données est survenue.')
                    abort(500)
            else:
                flash("L'info n'a pas pu être retrouvée.")
                if redir_to == 1:
                    return redirect(url_for('list_tasks_for_me'))
                elif redir_to == 2:
                    return redirect(url_for('list_tasks_for_all'))
                elif redir_to == 3:
                    tag_id = session['tag_id']
                    return redirect(url_for('list_tasks_by_tag', tag_id=tag_id))
                else:
                    flash("Je ne sais pas ou retourner.")
                    abort(500)
        else:
            flash("L'info n'a pas pu être retrouvée.")
            if redir_to == 1:
                return redirect(url_for('list_tasks_for_me'))
            elif redir_to == 2:
                return redirect(url_for('list_tasks_for_all'))
            elif redir_to == 3:
                tag_id = session['tag_id']
                return redirect(url_for('list_tasks_by_tag', tag_id=tag_id))
            else:
                flash("Je ne sais pas ou retourner.")
                abort(500)

    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('Error: ' + str(e))
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

# Database functions for AppUser
def db_add_user(first_name, last_name, user_email, user_pass):
    audit_crt_ts = datetime.now()
    try:
        user = AppUser(first_name, last_name, user_email, user_pass, audit_crt_ts)
        if user_email == app.config.get('ADMIN_EMAILID'):
            user.activated_ts = datetime.now()
            user.user_role = 'SuperAdmin'
        else:
            user.user_role = 'Régulier'
        db.session.add(user)
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_upd_user_status(user_id, status):
    try:
        user = AppUser.query.get(user_id)
        if status == 'A':
            user.activated_ts = datetime.now()
        else:
            user.activated_ts = None
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_upd_user_role(user_id, user_role):
    try:
        user = AppUser.query.get(user_id)
        if user_role == 'A':
            user.user_role = 'Admin'
        else:
            user.user_role = 'Régulier'
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_user_exists(user_email):
    app.logger.debug('Entering user_exists with: ' + user_email)
    try:
        user = AppUser.query.filter_by(user_email=user_email).first()
        if user is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_user_is_admin(user_id):
    app.logger.debug('Entering db_user_is_admin with: ' + str(user_id))
    try:
        user = AppUser.query.get(user_id)
        if user is None:
            return False
        else:
            if user.user_role in ['Admin', 'SuperAdmin']:
                return True
            else:
                return False
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_user_by_id(user_id):
    try:
        u = AppUser.query.get(user_id)
        return u
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


def db_change_password(user_email, new_password):
    try:
        user = AppUser.query.filter_by(user_email=user_email).first()
        if user is None:
            flash("Mot de passe inchangé. L'utilisateur n'a pas été retrouvé.")
            return False
        else:
            user.user_pass = generate_password_hash(new_password)
            user.audit_upd_ts = datetime.now()
            db.session.commit()
            flash("Mot de passe changé.")
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        flash("Mot de passe inchangé. Une erreur interne s'est produite.")
        return False


# Validate if a user is defined in tapp_user with the proper password.
def db_validate_user(user_email, password):
    try:
        user = AppUser.query.filter_by(user_email=user_email).first()
        if user is None:
            flash("L'utilisateur n'existe pas.")
            return False

        if not user.activated_ts:
            flash("L'utilisateur n'est pas activé.")
            return False
#        return True
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
        app.logger.error('Error: ' + str(e))
        flash("Connection impossible. Une erreur interne s'est produite.")
        return False


def db_del_user(user_id):
    try:
        user = AppUser.query.get(user_id)
        for secret in user.secrets:
            db.session.delete(secret)
        db.session.delete(user)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# DB functions for TaskList: exists, by_id, add, upd, del, others
def db_tasklist_exists(list_name):
    app.logger.debug('Entering tasklist_exists with: ' + list_name)
    try:
        tasklist = TaskList.query.filter_by(list_name=list_name).first()
        if tasklist is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_tasklist_by_id(list_id):
    try:
        lst = TaskList.query.get(list_id)
        return lst
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


def db_add_tasklist(list_name, list_desc):
    audit_crt_user = session.get('user_id', None)
    audit_crt_ts = datetime.now()
    tasklist = TaskList(list_name, list_desc, audit_crt_user, audit_crt_ts)
    try:
        db.session.add(tasklist)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_tasklist(list_id, list_name, list_desc):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        tasklist = TaskList.query.get(list_id)
        tasklist.list_name = list_name
        tasklist.list_desc = list_desc
        tasklist.audit_upd_user = audit_upd_user
        tasklist.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_del_tasklist(list_id):
    try:
        tasklist = TaskList.query.get(list_id)
        db.session.delete(tasklist)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_tasklist_has_tasks(list_id):
    try:
        n = Task.query.filter_by(list_id=list_id).count()
        if n > 0:
            return True
        else:
            return False
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


# DB functions for Task: exists, by_id, add, upd, del, others
def db_task_exists(task_name):
    app.logger.debug('Entering task_exists with: ' + task_name)
    try:
        task = Task.query.filter_by(task_name=task_name).first()
        if task is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_task_by_id(task_id):
    try:
        t = Task.query.get(task_id)
        return t
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


def db_add_task(list_id, task_name, task_desc):
    audit_crt_user = session.get('user_id', None)
    audit_crt_ts = datetime.now()
    task = Task(list_id, task_name, task_desc, audit_crt_user, audit_crt_ts)
    try:
        db.session.add(task)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_task(task_id, task_name, task_desc):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        task = Task.query.get(task_id)
        task.task_name = task_name
        task.task_desc = task_desc
        task.audit_upd_user = audit_upd_user
        task.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_del_task(task_id):
    try:
        task = Task.query.get(task_id)
        assignments = Assignment.query.filter_by(task_id=task_id).all()
        for a in assignments:
            db.session.delete(a)
        tags = TaskTag.query.filter_by(task_id=task_id).all()
        for t in tags:
            db.session.delete(t)
        schedules = TaskSched.query.filter_by(task_id=task_id).all()
        for s in schedules:
            occurrences = TaskOccurence.query.filter_by(sched_id=s.sched_id).all()
            for o in occurrences:
                db.session.delete(o)
            db.session.delete(s)
        db.session.delete(task)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# DB functions for Task: exists, by_id, add, upd, del, others
def db_sched_by_id(sched_id):
    try:
        s = TaskSched.query.get(sched_id)
        return s
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


def db_add_sched(task_id, sched_type, sched_start_dt, sched_end_dt, sched_last_occ_dt,
                 sched_dow, sched_dom, sched_int):
    audit_crt_user = session.get('user_id', None)
    audit_crt_ts = datetime.now()
    sched = TaskSched(task_id, sched_type, sched_start_dt, sched_end_dt, sched_last_occ_dt,
                      sched_dow, sched_dom, sched_int, audit_crt_user, audit_crt_ts)
    try:
        db.session.add(sched)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return sched.sched_id


def db_upd_sched_one(sched_id, sched_start_dt):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_sched_dly(sched_id, sched_start_dt, sched_end_dt):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.sched_end_dt = sched_end_dt
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_sched_wly(sched_id, sched_start_dt, sched_end_dt, sched_dow):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.sched_end_dt = sched_end_dt
        sched.sched_dow = sched_dow
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_sched_mly(sched_id, sched_start_dt, sched_end_dt, sched_dom):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.sched_end_dt = sched_end_dt
        sched.sched_dom = sched_dom
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_sched_xdy(sched_id, sched_start_dt, sched_end_dt, sched_int):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.sched_end_dt = sched_end_dt
        sched.sched_int = sched_int
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_sched_xwk(sched_id, sched_start_dt, sched_end_dt, sched_dow, sched_int):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.sched_end_dt = sched_end_dt
        sched.sched_dow = sched_dow
        sched.sched_int = sched_int
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_sched_xmo(sched_id, sched_start_dt, sched_end_dt, sched_dom, sched_int):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        sched = TaskSched.query.get(sched_id)
        sched.sched_start_dt = sched_start_dt
        sched.sched_end_dt = sched_end_dt
        sched.sched_dom = sched_dom
        sched.sched_int = sched_int
        sched.audit_upd_user = audit_upd_user
        sched.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_del_sched(sched_id):
    try:
        sched = TaskSched.query.get(sched_id)
        for occ in sched.occurences:
            db.session.delete(occ)
        db.session.delete(sched)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# DB functions for TaskOccurence: exists, by_id, add, upd, del, others
def db_occur_by_id(occur_id):
    try:
        o = TaskOccurence.query.get(occur_id)
        return o
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


def db_add_occur(sched_id, update_mode='N'):
    app.logger.debug('Entering db_add_occur')
    try:
        sched = db_sched_by_id(sched_id)
        if sched:
            app.logger.debug('sched is found')
            app.logger.debug('sched type: ' + sched.sched_type)
        else:
            app.logger.debug('sched is NOT found')

        # In update_mode, delete the occurences with a status To_Do
        if update_mode == 'Y':
            for occ in sched.occurences:
                if occ.status == 'T':
                    db.session.delete(occ)
            occ_max = TaskOccurence.query.filter_by(sched_id=sched_id).order_by(desc(TaskOccurence.sched_dt)).first()
            if occ_max:
                app.logger.debug('Last occurence date:' + str(occ_max.sched_dt))
                sched.sched_last_occ_dt = occ_max.sched_dt
            else:
                app.logger.debug('Last occurence date is set to null.')
                sched.sched_last_occ_dt = None

        if sched.sched_type == 'O':
            sched.sched_last_occ_dt = sched.sched_start_dt
            occur = TaskOccurence(sched.task_id, sched_id, sched.sched_start_dt)
            db.session.add(occur)
            db.session.commit()

        elif sched.sched_type == 'd':
            if sched.sched_last_occ_dt is None:
                sched_dt = sched.sched_start_dt
            else:
                sched_dt = sched.sched_last_occ_dt + timedelta(days=1)
            if (sched.sched_end_dt is None) or (sched_dt <= sched.sched_end_dt):
                sched.sched_last_occ_dt = sched_dt
                occur = TaskOccurence(sched.task_id, sched_id, sched_dt)
                db.session.add(occur)
            db.session.commit()

        elif sched.sched_type == 'w':
            app.logger.debug('weekly')
            if sched.sched_last_occ_dt is None:
                app.logger.debug('last occ dt is none')
                sched_dt = sched.sched_start_dt
                sched_dow = sched.sched_dow
                dow_start_dt = sched_dt.weekday()
                if sched_dow > dow_start_dt:
                    sched_dt = sched_dt + timedelta(days=sched_dow - dow_start_dt)
                elif sched_dow < dow_start_dt:
                    delta_days = 7 - (dow_start_dt - sched_dow)
                    sched_dt = sched_dt + timedelta(days=delta_days)
            else:
                if update_mode == 'Y':
                    app.logger.debug('Update mode')
                    sched_dt = sched.sched_last_occ_dt
                    app.logger.debug('sched_dt: ' + str(sched_dt))
                    sched_dow = sched.sched_dow
                    app.logger.debug('sched_dow: ' + str(sched_dow))
                    dow_start_dt = sched_dt.weekday()
                    if sched_dow > dow_start_dt:
                        sched_dt = sched_dt + timedelta(days=sched_dow - dow_start_dt)
                    elif sched_dow < dow_start_dt:
                        delta_days = 7 - (dow_start_dt - sched_dow)
                        sched_dt = sched_dt + timedelta(days=delta_days)
                else:
                    sched_dt = sched.sched_last_occ_dt + timedelta(days=7)
            if (sched.sched_end_dt is None) or (sched_dt <= sched.sched_end_dt):
                occur = TaskOccurence(sched.task_id, sched_id, sched_dt)
                sched.sched_last_occ_dt = sched_dt
                db.session.add(occur)
            db.session.commit()

        elif sched.sched_type == 'm':
            if sched.sched_last_occ_dt is None:
                sched_dt = sched.sched_start_dt
            else:
                temp_dt = sched.sched_last_occ_dt
                days_in_month = monthrange(temp_dt.year, temp_dt.month)[1]
                temp_dt = temp_dt + timedelta(days=(days_in_month - temp_dt.day + 1))  # First day of next month
                days_in_next_month = monthrange(temp_dt.year, temp_dt.month)[1]
                if sched.sched_dom > days_in_next_month:
                    sched_dt = temp_dt + timedelta(days=(days_in_next_month - 1))
                else:
                    sched_dt = temp_dt + timedelta(days=(sched.sched_dom - 1))
            if (sched.sched_end_dt is None) or (sched_dt <= sched.sched_end_dt):
                occur = TaskOccurence(sched.task_id, sched_id, sched_dt)
                sched.sched_last_occ_dt = sched_dt
                db.session.add(occur)
            db.session.commit()

        elif sched.sched_type == 'D':
            if sched.sched_last_occ_dt is None:
                sched_dt = sched.sched_start_dt
            else:
                sched_dt = sched.sched_last_occ_dt + timedelta(days=sched.sched_int)
            if (sched.sched_end_dt is None) or (sched_dt <= sched.sched_end_dt):
                occur = TaskOccurence(sched.task_id, sched_id, sched_dt)
                sched.sched_last_occ_dt = sched_dt
                db.session.add(occur)
            db.session.commit()

        elif sched.sched_type == 'W':
            if sched.sched_last_occ_dt is None:
                sched_dt = sched.sched_start_dt
                sched_dow = sched.sched_dow
                dow_start_dt = sched_dt.weekday()
                if sched_dow > dow_start_dt:
                    sched_dt = sched_dt + timedelta(days=sched_dow - dow_start_dt)
                elif sched_dow < dow_start_dt:
                    delta_days = 7 - (dow_start_dt - sched_dow)
                    sched_dt = sched_dt + timedelta(days=delta_days)
            else:
                if update_mode == 'Y':
                    app.logger.debug('Update mode')
                    sched_dt = sched.sched_last_occ_dt
                    app.logger.debug('sched_dt: ' + str(sched_dt))
                    sched_dow = sched.sched_dow
                    app.logger.debug('sched_dow: ' + str(sched_dow))
                    dow_start_dt = sched_dt.weekday()
                    if sched_dow > dow_start_dt:
                        sched_dt = sched_dt + timedelta(days=sched_dow - dow_start_dt)
                    elif sched_dow < dow_start_dt:
                        delta_days = 7 - (dow_start_dt - sched_dow)
                        sched_dt = sched_dt + timedelta(days=delta_days)
                else:
                    sched_dt = sched.sched_last_occ_dt + timedelta(days=(7 * sched.sched_int))
            if (sched.sched_end_dt is None) or (sched_dt <= sched.sched_end_dt):
                occur = TaskOccurence(sched.task_id, sched_id, sched_dt)
                sched.sched_last_occ_dt = sched_dt
                db.session.add(occur)
            db.session.commit()

        elif sched.sched_type == 'M':
            if sched.sched_last_occ_dt is None:
                sched_dt = sched.sched_start_dt
            else:
                temp_dt = sched.sched_last_occ_dt
                temp_dt = temp_dt - timedelta(days=(sched.sched_last_occ_dt.day - 1))  # Go to first of month
                for _ in range(sched.sched_int):  # Repeat for the number of times in the interval
                    days_in_month = monthrange(temp_dt.year, temp_dt.month)[1]
                    temp_dt = temp_dt + timedelta(days=days_in_month)  # Go to the First day of next month
                days_in_month = monthrange(temp_dt.year, temp_dt.month)[1]
                if sched.sched_dom > days_in_month:
                    sched_dt = temp_dt + timedelta(days=(days_in_month - 1))
                else:
                    sched_dt = temp_dt + timedelta(days=(sched.sched_dom - 1))
            if (sched.sched_end_dt is None) or (sched_dt <= sched.sched_end_dt):
                occur = TaskOccurence(sched.task_id, sched_id, sched_dt)
                sched.sched_last_occ_dt = sched_dt
                db.session.add(occur)
            db.session.commit()
        else:
            return False

    except Exception as e:
        app.logger.error('DB Error: ' + str(e))
        return False
    return True


def db_set_occ_status(occur_id, status):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        occ = TaskOccurence.query.get(occur_id)
        if occ is None:
            return False
        else:
            occ.status = status
            occ.audit_upd_user = audit_upd_user
            occ.audit_upd_ts = audit_upd_ts
            db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# DB functions for Assignment: exists, by_id, add, upd, del, others
def db_asgn_exists(task_id, user_id):
    app.logger.debug('Entering asgn_exists with: ' + str(task_id) + ',' + str(user_id))
    try:
        asgn = Assignment.query.filter_by(task_id=task_id, user_id=user_id).first()
        if asgn is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_add_asgn(task_id, user_id):
    asgn = Assignment(task_id, user_id)
    try:
        db.session.add(asgn)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_del_asgn(asgn_id):
    try:
        asgn = Assignment.query.get(asgn_id)
        db.session.delete(asgn)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# DB functions for Tag: exists, by_id, add, upd, del, others
def db_tag_exists(tag_name):
    app.logger.debug('Entering tag_exists with: ' + tag_name)
    try:
        tag = Tag.query.filter_by(tag_name=tag_name).first()
        if tag is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_tag_by_id(tag_id):
    try:
        t = Tag.query.get(tag_id)
        return t
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return None


def db_add_tag(tag_name):
    audit_crt_user = session.get('user_id', None)
    audit_crt_ts = datetime.now()
    tag = Tag(tag_name, audit_crt_user, audit_crt_ts)
    try:
        db.session.add(tag)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_upd_tag(tag_id, tag_name):
    audit_upd_user = session.get('user_id', None)
    audit_upd_ts = datetime.now()
    try:
        tag = Tag.query.get(tag_id)
        tag.tag_name = tag_name
        tag.audit_upd_user = audit_upd_user
        tag.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_del_tag(tag_id):
    try:
        tag = Tag.query.get(tag_id)
        db.session.delete(tag)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# DB functions for TaskTag: exists, by_id, add, upd, del, others
def db_ttag_exists(task_id, tag_id):
    app.logger.debug('Entering ttag_exists with: ' + str(task_id) + ',' + str(tag_id))
    try:
        t_tag = TaskTag.query.filter_by(task_id=task_id, tag_id=tag_id).first()
        if t_tag is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False


def db_add_ttag(task_id, tag_id):
    t_tag = TaskTag(task_id, tag_id)
    try:
        db.session.add(t_tag)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


def db_del_ttag(task_id, tag_id):
    try:
        t_tag = TaskTag.query.filter_by(task_id=task_id, tag_id=tag_id).first()
        db.session.delete(t_tag)
        db.session.commit()
    except Exception as e:
        app.logger.error('Error: ' + str(e))
        return False
    return True


# Start the server for the application
if __name__ == '__main__':
    manager.run()
