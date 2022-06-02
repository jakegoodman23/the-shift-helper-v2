from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory, session, Markup
from flask_bootstrap import Bootstrap
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.fields.html5 import DateField, EmailField
from wtforms.validators import DataRequired, Email, Length
from dotenv import load_dotenv
from datetime import datetime, date
import os
import pandas as pd
import smtplib

abspath = os.path.abspath(__file__)
dirname = os.path.dirname(abspath)

email_address = os.environ.get("EMAIL")
email_password = os.environ.get("EMAIL_PASSWORD")

app = Flask(__name__)
debug = False
DEV = False
if DEV:
    os.chdir(dirname)
    debug = True
    parent_path = os.path.abspath(os.path.dirname(__file__))
    load_dotenv(os.path.join(parent_path, 'info.env'))
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///shifthelper.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = 'filesystem'

# allow app to use Session functionality
Session(app)

# allow app to use Bootstrap formatting
Bootstrap(app)

# allow app to have default current user characteristics such as is_authenticated status
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    """
    load the info for the current user
    """
    return Hospital.query.get(int(user_id))


# allow SQLAlchemy to be incorporated from a db perspective
db = SQLAlchemy(app)


# user class and db table
class Hospital(UserMixin, db.Model):
    """
    The class (and db table) for the hospital data. Each entry will be a new "user" of the app.

    This info ix mixed in as the user info so we can maintain info of the user that's currently logged in
    """
    id = db.Column(db.Integer, primary_key=True)
    hospital_name = db.Column(db.String(1000))
    admin_name = db.Column(db.String(1000))
    admin_email = db.Column(db.String(100))
    admin_password = db.Column(db.String(1000))
    staff_password = db.Column(db.String(1000))
    created_date = db.Column(db.TIMESTAMP)


class Shifts(db.Model):
    """
    The class (and db table) for the shift data. Each entry will be a distinct shift in the system
    """
    shift_id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer)
    area = db.Column(db.String)
    role = db.Column(db.String)
    date = db.Column(db.Date)
    start_time = db.Column(db.String)
    end_time = db.Column(db.String)
    comments = db.Column(db.String)
    status = db.Column(db.String)
    picked_up_by = db.Column(db.String)
    approved_dt_tm = db.Column(db.TIMESTAMP)
    create_dt_tm = db.Column(db.TIMESTAMP)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)


class Requests(db.Model):
    """
    The class (and db table) for the request data. Each entry will be a distinct request in the system
    """
    transaction_id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer)
    hospital_id = db.Column(db.Integer)
    status = db.Column(db.String)
    create_dt_tm = db.Column(db.TIMESTAMP)
    approved_dt_tm = db.Column(db.TIMESTAMP)
    requested_by_name = db.Column(db.String)
    requested_by_email = db.Column(db.String)
    requested_by_phone = db.Column(db.String)
    comments = db.Column(db.String)


# class to have a user sign up their location
class SignupForm(FlaskForm):
    """
    structure of the signup form of a FlaskForm object
    """
    admin_name = StringField(label='Name', validators=[DataRequired()])
    admin_email = EmailField(label='Email', validators=[DataRequired(), Email()])
    hospital_name = StringField(label='Hospital Name', validators=[DataRequired()])
    admin_password = StringField(label='Admin Login', validators=[Length(min=4)])
    staff_password = StringField(label='Staff Login', validators=[Length(min=4)])
    submit = SubmitField(label='Sign up')


# class to indicate the fields that'll be used on the app's Add Shift form
class ShiftForm(FlaskForm):
    """
    structure of the add shift form of a FlaskForm object
    """
    area = StringField(label='Area (e.g. ICU)', validators=[DataRequired()])
    role = SelectField(label='Role', choices=["RN", "CRNA", "Medical Assistant", "Scrub Tech"]
                       , validators=[DataRequired()])
    date = DateField(label='Shift Date', format='%Y-%m-%d', validators=[DataRequired()])
    start_time = StringField(label='Start Time (e.g. 8am)', validators=[DataRequired()])
    end_time = StringField(label='End Time (e.g. 5pm)', validators=[DataRequired()])
    contact_name = StringField(label="Contact's name", validators=[DataRequired()])
    contact_email = EmailField(label="Contact's email", validators=[DataRequired(), Email()])
    comments = StringField(label='Comments (competencies, random notes, etc.)')
    submit = SubmitField(label="Add Open Shift")


class RequestForm(FlaskForm):
    """
    structure of the request shift form of a FlaskForm object
    """
    requestor_name = StringField(label="What's your name?", validators=[DataRequired()])
    label_for_email = Markup(
        "What's your email? <span class='email-italic'>(will be used to provide updates on shift)</span>")
    requestor_email = EmailField(label_for_email
                                 , validators=[DataRequired(), Email()])
    requestor_phone_num = StringField(label="What's your phone number?")
    requestor_comments = StringField(label="Any comments you'd like to share?")
    submit = SubmitField(label="Request Open Shift")


# create the databases with the above tables
db.create_all()


@app.route('/')
def home():
    """
    Will take the user back to the home page that allows the user to either log in or register
    """
    if 'admin_password' in session:
        session.pop('admin_password')

    if 'staff_password' in session:
        session.pop('staff_password')

    return render_template('index.html')


@app.route('/about')
def about():
    """
    take user to the about page
    """
    if current_user.is_authenticated:
        cur_hospital = Hospital.query.get(current_user.id)
        return render_template('about.html', hospital=cur_hospital, logged_in=True)
    elif session.get('hospital_id'):
        hospital_id = session.get('hospital_id')
        cur_hospital = Hospital.query.get(hospital_id)
        return render_template('about.html', hospital=cur_hospital, logged_in=True)
    else:
        return render_template('about.html', hospital_id=0)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    logs the user in the system assuming they enter in the proper info
    """
    if request.method == 'POST':
        password = request.form['password']
        hospitals = db.session.query(Hospital).all()
        for hospital in hospitals:
            if check_password_hash(hospital.admin_password, password):
                login_user(hospital)
                return redirect(url_for('pending_shifts', hospital_id=current_user.id))

        for hospital in hospitals:
            if check_password_hash(hospital.staff_password, password):
                return redirect(url_for('shifts', hospital_id=hospital.id))

        flash("Login does not exist. Please try again or contact your site's administrator")
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    allows the user to access and complete the signup form
    """
    signup_form = SignupForm()
    signup_form.validate_on_submit()
    if request.method == "POST":
        hashed_admin_password = generate_password_hash(
            signup_form.admin_password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        hashed_staff_password = generate_password_hash(
            signup_form.staff_password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        hospitals = db.session.query(Hospital).all()
        if signup_form.staff_password.data == signup_form.admin_password.data:
            flash('Admin and Staff logins cannot match. Please choose separate logins.')
            return redirect(url_for('signup'))
        for hospital in hospitals:
            if check_password_hash(hospital.admin_password, signup_form.admin_password.data):
                flash('This admin password has already been taken. Please choose another one.')
                return redirect(url_for('signup'))
        for hospital in hospitals:
            if check_password_hash(hospital.staff_password, signup_form.staff_password.data):
                flash('This staff password has already been taken. Please choose another one.')
                return redirect(url_for('signup'))

        cur_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur_dt = datetime.strptime(cur_dt, "%Y-%m-%d %H:%M")

        new_hospital = Hospital(
            hospital_name=signup_form.hospital_name.data,
            admin_name=signup_form.admin_name.data,
            admin_email=signup_form.admin_email.data,
            admin_password=hashed_admin_password,
            staff_password=hashed_staff_password,
            created_date=cur_dt
        )
        db.session.add(new_hospital)
        db.session.commit()
        login_user(new_hospital)

        session['admin_password'] = signup_form.admin_password.data
        session['staff_password'] = signup_form.staff_password.data
        return redirect(url_for('signup_success', hospital_id=new_hospital.id))

    return render_template('signup.html', form=signup_form)


@app.route('/signup_success/', methods=['GET'])
@login_required
def signup_success():
    """
    if the signup is successful, they will be taken to this page which displays the information they just submitted
    so they can keep for their personal records
    """
    hospital_id = request.args['hospital_id']
    hospital = Hospital.query.get(hospital_id)

    contents = f"Thank you so much for signing up for Shift Helper! Below you will find your registration info so " \
               f"you're able to retrieve as needed.\n\n" \
               f"Hospital Name: {hospital.hospital_name}\n" \
               f"Admin Name: {hospital.admin_name}\n" \
               f"Admin Email: {hospital.admin_email}\n" \
               f"Admin Login: {session['admin_password']}\n" \
               f"Staff Login: {session['staff_password']}\n\n" \
               "From,\nYour trusty pals at Shift Helper"

    with smtplib.SMTP("smtp.office365.com", 587) as connection:
        connection.starttls()
        connection.login(email_address, email_password)
        connection.sendmail(
            from_addr=email_address,
            to_addrs=hospital.admin_email,
            msg=f"Subject: Shift Helper Signup Info!\n\n{contents}"
        )
    return render_template('signup_success.html', hospital=hospital, logged_in=True)


@app.route('/add_shifts', methods=['GET', 'POST'])
@login_required
def add_shifts():
    """
    allows the user to add a shift if they're logged in
    """
    shift_form = ShiftForm()
    shift_form.validate_on_submit()
    cur_hospital = Hospital.query.get(current_user.id)
    if request.method == 'POST':
        cur_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur_dt = datetime.strptime(cur_dt, "%Y-%m-%d %H:%M:%S")
        new_shift = Shifts(
            hospital_id=current_user.id,
            area=shift_form.area.data,
            role=shift_form.role.data,
            date=shift_form.date.data,
            start_time=shift_form.start_time.data,
            end_time=shift_form.end_time.data,
            comments=shift_form.comments.data,
            status='Posted',
            create_dt_tm=cur_dt,
            contact_name=shift_form.contact_name.data,
            contact_email=shift_form.contact_email.data
        )

        db.session.add(new_shift)
        db.session.commit()

        return redirect(url_for('shifts', hospital_id=current_user.id))

    return render_template('add_shifts.html', hospital=cur_hospital, logged_in=True, form=shift_form)


@app.route('/shifts', methods=['GET'])
def shifts():
    """
    displays all available shifts
    """
    hospital_id = request.args['hospital_id']
    session['hospital_id'] = hospital_id
    cur_hospital = Hospital.query.get(hospital_id)
    cur_date = date.today()
    available_shifts = db.session.query(Shifts) \
        .filter(Shifts.status != 'Approved', Shifts.status != 'Removed', Shifts.date >= cur_date
                , Shifts.hospital_id == hospital_id) \
        .order_by(Shifts.date, Shifts.start_time, Shifts.area, Shifts.role)

    return render_template('shifts.html', hospital=cur_hospital, shifts=available_shifts, logged_in=True)


@app.route('/request_shift', methods=['GET', 'POST'])
def request_shift():
    """
    allows any user to request an available shift
    """
    request_form = RequestForm()
    request_form.validate_on_submit()
    shift_id = request.args.get('id')
    shift_info = Shifts.query.get(shift_id)
    cur_hospital = Hospital.query.get(shift_info.hospital_id)
    if request.method == 'POST':
        cur_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur_dt = datetime.strptime(cur_dt, "%Y-%m-%d %H:%M")
        new_request = Requests(
            shift_id=shift_id,
            hospital_id=shift_info.hospital_id,
            status='Requested',
            create_dt_tm=cur_dt,
            requested_by_name=request_form.requestor_name.data,
            requested_by_email=request_form.requestor_email.data,
            requested_by_phone=request_form.requestor_phone_num.data,
            comments=request_form.requestor_comments.data
        )
        db.session.add(new_request)
        shift_to_update = Shifts.query.get(shift_id)
        shift_to_update.status = 'Requested'
        db.session.commit()

        return redirect(url_for('staff_request_email', shift=shift_to_update.shift_id,
                                staff_request_name=new_request.requested_by_name,
                                staff_request_email=new_request.requested_by_email))

    return render_template('request_shift.html', form=request_form, shift=shift_info, hospital=cur_hospital
                           , logged_in=True)


@app.route('/pending_shifts', methods=['GET', 'POST'])
@login_required
def pending_shifts():
    """
    allows admin users to see all the pending shifts and the corresponding request info
    """
    cur_hospital = Hospital.query.get(current_user.id)
    cur_date = date.today()
    open_shifts = db.session.query(Shifts) \
        .join(Requests, Requests.shift_id == Shifts.shift_id, isouter=True) \
        .filter(Shifts.date >= cur_date, Shifts.hospital_id == current_user.id, Shifts.status != 'Approved'
                , Shifts.status != 'Removed') \
        .order_by(Shifts.area, Shifts.role, Shifts.date, Shifts.start_time, Shifts.end_time) \
        .with_entities(Shifts.area, Shifts.role, Shifts.date, Shifts.start_time, Shifts.end_time, Shifts.shift_id
                       , Shifts.contact_name, Shifts.contact_email
                       , Shifts.comments.label('shift_comments'), func.count(Requests.shift_id).label('request_count')) \
        .group_by(Shifts.area, Shifts.role, Shifts.date, Shifts.start_time, Shifts.end_time, Shifts.shift_id
                  , Shifts.comments, Shifts.contact_name, Shifts.contact_email)
    return render_template('pending_shifts.html', shifts=open_shifts, hospital=cur_hospital, logged_in=True)


@app.route('/approve_request', methods=['GET', 'POST'])
@login_required
def approve_request():
    """
    allows admin users to approve requests.

    approving a request will drop all the other requests for that shift
    """
    cur_hospital = Hospital.query.get(current_user.id)
    if request.method == "POST":
        cur_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur_dt = datetime.strptime(cur_dt, "%Y-%m-%d %H:%M")
        cur_shift_id = request.form["shift_id"]
        cur_request_id = request.form["request_id"]
        shift_to_update = Shifts.query.get(cur_shift_id)
        request_to_approve = Requests.query.get(cur_request_id)
        shift_to_update.status = 'Approved'
        shift_to_update.approved_dt_tm = cur_dt
        shift_to_update.picked_up_by = request_to_approve.requested_by_email
        request_to_approve.status = 'Approved'
        db.session.commit()
        request_to_approve.approved_dt_tm = cur_dt

        requests_to_pass = db.session.query(Requests) \
            .filter(Requests.shift_id == cur_shift_id, Requests.status != 'Approved')
        for req in requests_to_pass:
            req.status = 'Passed'
        db.session.commit()
        return redirect(url_for('app_request_email', shift=shift_to_update.shift_id,
                                app_request=request_to_approve.transaction_id))

    request_id = request.args.get('id')
    cur_request = Requests.query.get(request_id)
    cur_shift = Shifts.query.get(cur_request.shift_id)
    return render_template("approve_request.html", request=cur_request, shift=cur_shift, hospital=cur_hospital,
                           logged_in=True)


@app.route('/request_details', methods=['GET', 'POST'])
@login_required
def request_detail():
    """
    allows admins to dig deeper in the requests for the pending shifts
    """
    cur_hospital = Hospital.query.get(current_user.id)
    shift_id = request.args.get('id')
    request_details = db.session.query(Requests) \
        .join(Shifts, Shifts.shift_id == Requests.shift_id) \
        .filter(Requests.shift_id == shift_id) \
        .order_by(Requests.create_dt_tm) \
        .with_entities(Requests.requested_by_name, Requests.requested_by_email
                       , Requests.comments.label('requestor_comments'), Requests.create_dt_tm.label('request_date')
                       , Shifts.date.label('shift_date'), Shifts.area, Shifts.role, Shifts.start_time, Shifts.end_time
                       , Requests.transaction_id)

    return render_template('request_details.html', requests=request_details, hospital=cur_hospital, logged_in=True)


@app.route('/shift_history', methods=['GET'])
def shift_history():
    """
    allows anybody to see all approved shifts
    """
    hospital_id = request.args['hospital_id']
    cur_hospital = Hospital.query.get(hospital_id)
    shift_history_list = db.session.query(Shifts) \
        .filter(Shifts.status == 'Approved', Shifts.hospital_id == hospital_id) \
        .order_by(Shifts.picked_up_by, Shifts.date, Shifts.start_time, Shifts.area, Shifts.role)

    return render_template('shift_history.html', hospital=cur_hospital, shifts=shift_history_list, logged_in=True)


@app.route('/remove_shift', methods=['GET', 'POST'])
@login_required
def remove_shift():
    """
    allows admins to remove pending shifts
    """
    cur_hospital = Hospital.query.get(current_user.id)
    if request.method == "POST":
        cur_shift_id = request.form["id"]
        shift_to_remove = Shifts.query.get(cur_shift_id)
        shift_to_remove.status = "Removed"
        db.session.commit()
        return redirect(url_for('pending_shifts'))
    shift_id = request.args.get('id')
    cur_shift = Shifts.query.get(shift_id)
    return render_template("remove_shift.html", shift=cur_shift, hospital=cur_hospital, logged_in=True)


@app.route('/edit_shift', methods=['GET', 'POST'])
@login_required
def edit_shift():
    """
    allows admins to edit pending shifts
    """
    cur_hospital = Hospital.query.get(current_user.id)
    if request.method == "POST":
        shift_id = request.form["id"]
        shift_to_update = Shifts.query.get(shift_id)
        shift_to_update.area = request.form["area"]
        shift_to_update.role = request.form["role"]
        shift_to_update.date = datetime.strptime(request.form["date"], '%Y-%m-%d')
        shift_to_update.start_time = request.form["start_time"]
        shift_to_update.end_time = request.form["end_time"]
        shift_to_update.comments = request.form["comments"]
        shift_to_update.contact_name = request.form["contact_name"]
        shift_to_update.contact_email = request.form["contact_email"]
        db.session.commit()
        return redirect(url_for('pending_shifts'))
    shift_id = request.args.get('id')
    shift_info = Shifts.query.get(shift_id)
    return render_template("edit_shift.html", shift=shift_info, hospital=cur_hospital, logged_in=True)


@app.route('/app_request_email', methods=['GET', 'POST'])
@login_required
def app_request_email():
    """
    triggers emails to be sent if request is approved
    """
    shift_id = request.args['shift']
    shift = Shifts.query.get(shift_id)
    shift_email = shift.contact_email
    shift_name = shift.contact_name

    app_request_id = request.args['app_request']
    app_request = Requests.query.get(app_request_id)
    request_email = app_request.requested_by_email
    request_name = app_request.requested_by_name

    contents = f"{request_name} - great news, your request for the {shift.date} shift in the {shift.area} area " \
               f"was approved!\n" \
               f"Please reach out to {shift_name} ({shift_email}) with any questions you might have.\n" \
               "From,\nYour trusty pals at Shift Helper"

    with smtplib.SMTP("smtp.office365.com", 587) as connection:
        connection.starttls()
        connection.login(email_address, email_password)
        connection.sendmail(
            from_addr=email_address,
            to_addrs=[request_email, shift_email],
            msg=f"Subject:Your request for the {shift.date} shift has been approved!\n\n{contents}"
        )

    pass_emails = []
    requests_to_pass = db.session.query(Requests) \
        .filter(Requests.shift_id == shift_id, Requests.status == 'Passed')

    for req in requests_to_pass:
        pass_emails.append(req.requested_by_email)

    contents = f"Thank you for submitting a request for the {shift.date} shift in the {shift.area} area.\n" \
               "Unfortunately this shift was given to someone else. Thanks again for your interest in this shift and " \
               "please do continue to requesting more shifts. We need all the help we can get\n" \
               "From, Your trusty pals at Shift Helper"

    pass_emails.append(email_address)
    to_adds = ", ".join(pass_emails)
    with smtplib.SMTP("smtp.office365.com", 587) as connection:
        connection.starttls()
        connection.login(email_address, email_password)
        connection.sendmail(
            from_addr=email_address,
            to_addrs=to_adds,
            msg=f"Subject:Sorry, request for the {shift.date} shift was approved for someone else\n\n{contents}"
        )

    return redirect(url_for('pending_shifts'))


@app.route('/staff_request_email', methods=['GET', 'POST'])
def staff_request_email():
    """
    triggers emails to be sent if request is made for a shift
    """
    shift_id = request.args['shift']
    shift = Shifts.query.get(shift_id)
    shift_email = shift.contact_email
    shift_name = shift.contact_name

    cur_hospital = Hospital.query.get(shift.hospital_id)
    staff_request_name = request.args['staff_request_name']
    staff_request_email_addr = request.args['staff_request_email']

    contents = f"{shift_name} - great news, your posted shift on {shift.date} in the {shift.area} area " \
               f"was requested by {staff_request_name} ({staff_request_email_addr})!\n" \
               "Please navigate to the app to review the request.\n\n" \
               "From,\nYour trusty pals at Shift Helper"

    with smtplib.SMTP("smtp.office365.com", 587) as connection:
        connection.starttls()
        connection.login(email_address, email_password)
        connection.sendmail(
            from_addr=email_address,
            to_addrs=[shift_email],
            msg=f"Subject:Your posted shift on {shift.date} in the {shift.area} area  has been requested!\n\n{contents}"
        )
    return render_template('request_success.html', contact=shift.contact_name, hospital=cur_hospital
                           , logged_in=True)


# logout
@app.route('/logout')
def logout():
    """
    Will log the user out and un-authenticate the user's session so access to the app's features is no longer allowed
    until the user logs back in
    """
    logout_user()
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=debug)
