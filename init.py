import os
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import pymysql.cursors
from config import OthersConfig
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret key"

app.config.from_object(OthersConfig)

conn = pymysql.connect(host='localhost',
                       port=app.config['DATABASE_PORT'],
                       user=app.config['DB_USER'],
                       password=app.config['DB_PASSWORD'],
                       db=app.config['DB_NAME'],
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

pages = ['jesse', 'j_card', 'j_photo', 'j_music', 'geordy', 'geo_card', 'geo_photo','geo_art',
         'gail', 'g_card', 'g_photo', 'g_art', 'g_music', 'dash', 'd_letter', 'd_photo',
         'maxxy', 'm_letter', 'm_photo']  # Add more page names as needed

# Define a route to hello function
@app.route('/')
def hello():
  if 'username' in session:
    return redirect('home')
  return render_template('index.html')

# Define route for login
@app.route('/login')
def login():
  if 'username' in session:
    return redirect('home')
  return render_template('login.html')


# Define route for register
@app.route('/register')
def register():
  return render_template('register.html')

# Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
  # grabs information from the forms
  email = request.form['email']
  username = request.form['username']
  passwd = request.form['password']
  code = request.form['code']

  if (code != "021603061013"):
    error = "You have entered the wrong code."
    return render_template('register.html', error=error)

  
  # cursor used to send queries
  cursor = conn.cursor()
  # executes query
  query = 'SELECT * FROM Users WHERE username = %s'
  cursor.execute(query, (username))
  # stores the results in a variable
  data = cursor.fetchone()
  # use fetchall() if you are expecting more than 1 data row
  error = None
  if (data):
    # If the previous query returns data, then user exists
    error = "This user already exists"
    return render_template('register.html', error=error)
  else:
    hashed_password = generate_password_hash(passwd, method='pbkdf2:sha256')
    
    ins = 'INSERT INTO Users (username, passwd, email) VALUES (%s, %s, %s, %s)'
    cursor.execute(ins, (username, hashed_password, email))
    conn.commit()
    cursor.close()
    return render_template('index.html')

# Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
  # grabs information from the forms
  username = request.form['username']
  password = request.form['password']
  
  # cursor used to send queries
  cursor = conn.cursor()
  # executes query
  query = 'SELECT * FROM Users WHERE username = %s'
  cursor.execute(query, (username))
  data = cursor.fetchone()
  cursor.close()
  
  error = None
  # print(data['passwd'])
  
  if (data and check_password_hash(data['passwd'], password)):
    session['username'] = username
    return redirect(url_for('home'))
  else:
    # returns an error message to the html page
    error = 'Invalid login or username'
    return render_template('login.html', error=error)

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('login')

    cursor = conn.cursor()
    query = 'SELECT filename, filepath, filetype, upload_date, username FROM Files ORDER BY upload_date DESC'
    cursor.execute(query)
    files = cursor.fetchall()
    cursor.close()

    return render_template('home.html', username=session['username'], files=files)


@app.route('/delete_file', methods=['GET', 'POST'])
def delete_pet():
  if 'username' not in session:
    return redirect('/login')
  
  username = session['username']
  fileName = request.form.get('filename')
  
  cursor = conn.cursor()
  query = 'DELETE FROM Files WHERE filename = %s AND username = %s'
  cursor.execute(query, (fileName, username))
  conn.commit()
  cursor.close()
  
  return redirect('/home')

def create_route(page):
    @app.route(f'/{page}', endpoint=page)
    def render_page(page=page):
        if 'username' not in session:
            return redirect('login')

        cursor = conn.cursor()
        query = 'SELECT filename, filepath, filetype, upload_date, username FROM Files ORDER BY upload_date DESC'
        cursor.execute(query)
        files = cursor.fetchall()
        cursor.close()
        return render_template(f'{page}.html',username=session['username'], files=files)

for page in pages:
    create_route(page)


@app.route('/logout')
def logout():
  session.pop('username')
  return redirect('/')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        upload_page = request.form.get('upload_page')
        print(request.form)  # Print all form data
        print(f"Upload page: {upload_page}")  # Debugging statement to check the value

        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_type = filename.rsplit('.', 1)[1].lower()  # Get file extension for filetype
            cursor = conn.cursor()
            query = 'INSERT INTO Files (username, filename, filepath, filetype, upload_page) VALUES (%s, %s, %s, %s, %s)'
            cursor.execute(query, (session['username'], filename, file_path, file_type, upload_page))
            conn.commit()
            cursor.close()
            flash('File successfully uploaded')
            return redirect(url_for('home'))
    return render_template('upload.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == "__main__":
  app.run('127.0.0.1', 7000, debug=True)