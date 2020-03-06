from flask import (Flask,
                   session,
                   redirect,
                   url_for,
                   request,
                   render_template,
                   flash,
                   g,
                   abort,
                   escape)
from werkzeug.security import (generate_password_hash,
                               check_password_hash)
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import (StringField,
                     PasswordField,
                     TextAreaField,
                     BooleanField,
                     SubmitField,
                     IntegerField,
                     SelectField)
from wtforms.validators import (DataRequired,
                                Email,
                                EqualTo,
                                NumberRange)  # Length, NumberRange
from wtforms.fields import (DateField,
                            RadioField)
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
class AppUser(db.Model):
    __tablename__ = 'tapp_user'
    user_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    user_email = db.Column(db.String(80), nullable=False, unique=True)
    user_pass = db.Column(db.String(100), nullable=False)
    activated = db.Column(db.Boolean(), nullable=False, default=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    tasks = db.relationship('Assignment', backref='tapp_user', lazy='dynamic')

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
    list_name = db.Column(db.String(50), nullable=False, unique=True)
    list_desc = db.Column(db.Text(), nullable=False, default='')
    audit_crt_user = db.Column(db.String(80), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.String(80), nullable=True)
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
    task_name = db.Column(db.String(50), nullable=False)
    task_desc = db.Column(db.Text, nullable=False, default='')
    audit_crt_user = db.Column(db.String(80), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.String(80), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    tags = db.relationship('TaskTag', backref='ttask', lazy='dynamic')
    schedules = db.relationship('TaskSched', backref='ttask', lazy='dynamic')
    assignees = db.relationship('Assignment', backref='ttask', lazy='dynamic')
    occurences = db.relationship('TaskOccurence', backref='ttask', lazy='dynamic')

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
    sched_last_occ_dt = db.Column(db.Date, nullable=False)     # Last occurence date
    sched_dow = db.Column(db.String(1), nullable=True)         # Day of week, 0..6
    sched_dom = db.Column(db.SmallInteger(), nullable=True)    # Day of month 0..31
    sched_int = db.Column(db.SmallInteger(), nullable=True)    # Interval for every x D,W,M
    audit_crt_user = db.Column(db.String(80), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.String(80), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)
    occurences = db.relationship('TaskOccurence', backref='ttask_sched', lazy='dynamic')

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
        self.audit_crt_user= audit_crt_user
        self.audit_crt_ts = audit_crt_ts

    def __repr__(self):
        return '<task_sched: {}'.format(self.sched_id)


class TaskOccurence(db.Model):
    __tablename__ = 'ttask_occur'
    occur_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer(), db.ForeignKey('ttask.task_id'))
    sched_id = db.Column(db.Integer(), db.ForeignKey('ttask_sched.sched_id'))
    sched_dt = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(1), nullable=False, default='T')  # T:Todo, D:Done, C:Cancelled
    audit_upd_user = db.Column(db.String(80), nullable=True)
    audit_upd_ts = db.Column(db.DateTime(), nullable=True)

    def __init__(self):
        return

    def __repr__(self):
        return '<task_occurence: {}:{}'.format(self.task_id, self.sched_id)


class Assignment(db.Model):
    __tablename__ = 'tassignment'
    asgn_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('tapp_user.user_id'))
    task_id = db.Column(db.Integer, db.ForeignKey('ttask.task_id'))

    def __init__(self, checklist_id, var_id):
        self.checklist_id = checklist_id
        self.var_id = var_id

    def __repr__(self):
        return '<assignment: {}:{}>'.format(self.task_id, self.user_id)


class Tag(db.Model):
    __tablename__ = 'ttag'
    tag_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    tag_name = db.Column(db.String(50), nullable=False, unique=True)
    audit_crt_user = db.Column(db.String(80), nullable=False)
    audit_crt_ts = db.Column(db.DateTime(), nullable=False)
    audit_upd_user = db.Column(db.String(80), nullable=True)
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
    task_sched_type = RadioField('O', choices=[('O', "Une fois"), ('d', "Quotidien"), ('w', "Hebdomadaire"),
                                               ('m', "Mensuel")])  # O:one, d:daily, w:weekly, m:monthly, D,W,M every x
    submit = SubmitField('Ajouter')


# Formulaires pour ajouter une étiquette
class AddTagForm(FlaskForm):
    tag_name = StringField("Nom de l'étiquette", validators=[DataRequired(message='Le nom est requis.')])
    submit = SubmitField('Ajouter')


# Formulaire de la mise à jour d'une étiquette
class UpdTagForm(FlaskForm):
    tag_name = StringField("Nom de l'étiquette", validators=[DataRequired(message='Le nom est requis.')])
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
        app_users = AppUser.query.order_by(AppUser.first_name).all()
        return render_template('list_users.html', app_users=app_users)
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
        app.logger.error('DB Error' + str(e))
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
        app.logger.error('DB Error' + str(e))
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
    session['tasklist_id'] = list_id
    tasklist = TaskList.query.get(list_id)
    if tasklist is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('list_tasklists'))
    form = UpdTaskListForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a tasklist')
        list_name = form.list_name.data
        list_desc = form.list_desc.data
        if db_tasklist_exists(list_name):
            flash('Ce nom de liste existe déjà. Veuillez en choisir un autre.')
            return render_template("upd_tasklist.html", form=form, list_id=list_id,
                                   name=tasklist.list_name, desc=tasklist.list_desc)
        if db_upd_tasklist(list_id, list_name, list_desc):
            flash("La liste a été modifiée.")
        else:
            flash("Quelque chose n'a pas fonctionné.")
        return redirect(url_for('list_tasklists'))
    else:
        form.list_name.data = tasklist.list_name
        form.list_desc.data = tasklist.list_desc
#            sections = Section.query.filter_by(checklist_id=checklist_id, deleted_ind='N') \
#                .order_by(Section.section_seq).all()
        return render_template("upd_tasklist.html", form=form, list_id=list_id,
                               name=tasklist.list_name, desc=tasklist.list_desc)


@app.route('/del_tasklist/<int:list_id>', methods=['GET', 'POST'])
def del_tasklist(list_id):
    # TODO Refuser s'il y a des tâches dans la liste
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
            app.logger.error('DB Error' + str(e))
            abort(500)


# Views for Tasks
# Ordre des vues: list, show, add, upd, del
@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if not logged_in():
        return redirect(url_for('login'))
    app.logger.debug('Entering add_task')
    form = AddTaskForm()
    if form.validate_on_submit():
        app.logger.debug('Inserting a new tasklist')
        task_name = request.form['task_name']
        task_desc = request.form['task_desc']
        if db_task_exists(task_name):
            flash('Ce nom de liste existe déjà. Veuillez en choisir un autre.')
            return render_template('add_task.html', form=form)
        else:
            if db_add_tasklist():
                flash('La nouvelle liste est ajoutée.')
                return redirect(url_for('list_tasks'))
            else:
                flash('Une erreur de base de données est survenue.')
                abort(500)
    return render_template('add_task.html', form=form)


# Views for Tags
# Ordre des vues: list, show, add, upd, del
@app.route('/list_tags')
def list_tags():
    if not logged_in():
        return redirect(url_for('login'))
    try:
        tags = Tag.query.order_by(Tag.tag_name).all()
        return render_template('list_tags.html', tags=tags)
    except Exception as e:
        flash("Quelque chose n'a pas fonctionné.")
        app.logger.error('DB Error' + str(e))
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
    tag = Tag.query.get(tag_id)
    if tag is None:
        flash("L'information n'a pas pu être retrouvée.")
        return redirect(url_for('list_tags'))
    form = UpdTagForm()
    if form.validate_on_submit():
        app.logger.debug('Updating a tag')
        tag_name = form.tag_name.data
        if db_tag_exists(tag_name):
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
        try:
            tag = Tag.query.get(tag_id)
            # Ici ce serait une bonne place pour voir s'il y a des tâches
            if tag:
                return render_template('del_tag.html', form=form, tag_name=tag.tag_name)
            else:
                flash("L'information n'a pas pu être retrouvée.")
                return redirect(url_for('list_tags'))
        except Exception as e:
            flash("Quelque chose n'a pas fonctionné.")
            app.logger.error('DB Error' + str(e))
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
        user = AppUser.query.get(user_id)
        user.activated = True
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
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
        app.logger.error('DB Error' + str(e))
        return False


def db_change_password(user_email, new_password):
    try:
        user = AppUser.query.filter_by(user_email=user_email).first()
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


# Validate if a user is defined in tapp_user with the proper password.
def db_validate_user(user_email, password):
    try:
        user = AppUser.query.filter_by(user_email=user_email).first()
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


def db_tasklist_exists(list_name):
    app.logger.debug('Entering tasklist_exists with: ' + list_name)
    try:
        tasklist = TaskList.query.filter_by(list_name=list_name).first()
        if tasklist is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False


# DB functions for Task
def db_add_tasklist():
    return True


def db_task_exists(task_name):
    return False


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


# DB functions for Tag
def db_add_tag(tag_name):
    audit_crt_user = session.get('user_email', None)
    audit_crt_ts = datetime.now()
    tag = Tag(tag_name, audit_crt_user, audit_crt_ts)
    try:
        db.session.add(tag)
        db.session.commit()
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False
    return True


def db_tag_exists(tag_name):
    app.logger.debug('Entering tag_exists with: ' + tag_name)
    try:
        tag = Tag.query.filter_by(tag_name=tag_name).first()
        if tag is None:
            return False
        else:
            return True
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False


def db_upd_tag(tag_id, tag_name):
    audit_upd_user = session.get('user_email', None)
    audit_upd_ts = datetime.now()
    try:
        tag = Tag.query.get(tag_id)
        tag.tag_name = tag_name
        tag.audit_upd_user = audit_upd_user
        tag.audit_upd_ts = audit_upd_ts
        db.session.commit()
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False
    return True


def db_del_tag(tag_id):
    try:
        tag = Tag.query.get(tag_id)
        db.session.delete(tag)
        db.session.commit()
    except Exception as e:
        app.logger.error('DB Error' + str(e))
        return False
    return True


# Start the server for the application
if __name__ == '__main__':
    manager.run()
