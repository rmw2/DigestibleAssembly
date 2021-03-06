"""
Main file for handling server requests.
"""

# web packages
from flask import Flask, request, flash, redirect, render_template, session, g
from werkzeug.utils import secure_filename

# project files
from parse import process_asm, format_c
from dwarf import CDwarf

# standard packages
import os, subprocess, shutil, traceback
from elftools.elf.elffile import ELFFile
from uuid import uuid4

# Intialize Application
ALLOWED_EXTENSIONS = ['c']
UPLOADS_FOLDER = 'uploads'

app = Flask(__name__)
app.config['UPLOADS_FOLDER'] = UPLOADS_FOLDER

COMPILER = ['gcc']
#COMPILER = ['clang', '-target', 'x86_64-linux-elf']

# Secret key to maintain sessions
with open('.secret', 'r') as file:
    app.secret_key = file.readline()
    print(app.secret_key)

#**********************************************************************
# Request functions
#**********************************************************************

@app.route('/', methods=['GET', 'POST'])
def index():
    """ Index: serve the homepage and handle file uploads.
    Issue-- this currently re-renders the entire template every time...
    """
    g.debug = True

    # Manage session variables
    if 'uid' not in session:
        session['uid'] = str(uuid4())
    if 'opt' not in g:
        g.opt = '-O0'

    if request.method == 'POST':
        try:
            print('Received files: ', request.files)
            if 'srcfile' in request.files and request.files['srcfile'].filename != '':
                # Get file from request if it exists and save to uploads folder
                file = request.files['srcfile']
                if g.debug:
                    print('Using uploaded file: %s' % file.filename)

                # Save file on the server and cache name and source text on the session
                session['src'], session['filename'] = save_to_uploads(file)
                print('Session filename = ', session['filename'])

            elif 'filename' in session:
                if g.debug:
                    print('Using cached file: %s' % session['filename'])
            else:
                if g.debug:
                    print('File not found in upload and filename not in cache.')
                    print('Session variables:')
                    for key in session:
                        print('\t%s:\t%s' % (key, session[key]))
                raise RuntimeError('File not found')

            # Compile with specified optimization
            g.opt = request.form['opt']
            print("Compiling with optimization %s" % g.opt)

            try: asm, ofile = do_compile(session['filename'], g.opt)
            except RuntimeError:
                flash('compilation failed')
                return redirect(request.url)

            # Parse ELF
            dwarf = CDwarf(ofile, verbose=False)
            g.locs = dwarf.offset_to_name()
            if g.debug:
                from pprint import pprint
                pprint(g.locs)

            # Process
            (session['asm-markup'], colors) = process_asm(asm)
            session['src-markup'] = format_c(session['src'], colors)

            return render_template( 'index.html',
                    opt = g.opt,
                    fname=session['filename'],
                    srctext=session['src-markup'],
                    asmtext=session['asm-markup'])
        except Exception as e:
            flash('error')
            return render_template('index.html',
                    asmtext=traceback.format_exc()
                )


    return render_template( 'index.html',
            opt = g.opt,
            fname = 'no file selected',
            srctext = 'source goes here',
            asmtext = 'assembly goes here'
        )


# @app.route('/about')
# def about():
#     """ Serve the static about page.
#     """
#     return "It's some good stuff.  By Rob Whitaker."


# @app.after_request
# def clean(response):
#     """ Cleanup the server after a session.
#     """
#     if session['uid'] in os.listdir(UPLOADS_FOLDER):
#         print('\tCleaning directory for session: %s', session['uid'])
#         shutil.rmtree(os.path.join(UPLOADS_FOLDER, session['uid']))

#     return response

def clean_all():
    """ Cleanup on startup.
    """
    for d in os.listdir(UPLOADS_FOLDER):
        if os.path.isdir(os.path.join(UPLOADS_FOLDER, d)):
            print('\tCleaning directory for session: %s' % d)
            shutil.rmtree(os.path.join(UPLOADS_FOLDER, d))

# Run after loading module but before handling requests
# clean_all()

#**********************************************************************
# Utility functions
#**********************************************************************

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_to_uploads(file):
    # Decode source text
    src = [line.decode('UTF-8') for line in file.readlines()]

    # Save text of source file to uploads folder
    filename = secure_filename(file.filename)

    prefix = os.path.join(UPLOADS_FOLDER, session['uid'])

    # Create folder if necessary
    if not os.path.isdir(prefix):
        os.mkdir(prefix)

    # Save to newly created folder
    filepath = os.path.join(prefix, filename)

    with open(filepath, 'w') as cfile:
        cfile.write(''.join(src))

    return src, filename

def do_compile(filename, opt='-O0', compiler=COMPILER):
    """ Open, read, and save a c program represented as the object file.
    Compile with -g both to assembly and object code.
    Return src as a list of lines of C, asm as a list of lines in assembly,
    and ofile as an open stream for the object code file.
    """

    prefix = os.path.join(UPLOADS_FOLDER, session['uid'])
    filepath = os.path.join(prefix, filename)

    # Locations for new files
    sfilepath = os.path.join(prefix, filename[:-2] + '.s')
    ofilepath = os.path.join(prefix, filename[:-2] + '.o')

    # Compile source to assembly and ELF
    pres1 = subprocess.call(compiler + ['-g', '-S', opt, filepath, '-o', sfilepath])
    pres2 = subprocess.call(compiler + ['-g', '-c', opt, filepath, '-o', ofilepath])

    # Check for compilation errors
    if pres1 != 0 or pres2 != 0:
        raise RuntimeError('Compilation Failed')

    # Load assembly line-by-line into list
    with open(sfilepath, 'r') as sfile:
        asm = [line for line in sfile.readlines()]

    # open file stream for object code
    ofile = open(ofilepath, 'rb')

    return asm, ofile

