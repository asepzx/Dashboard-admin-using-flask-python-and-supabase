from datetime import datetime
from io import BytesIO
import mimetypes
import zipfile
import requests
from flask import Flask, Response, abort, flash, redirect, request, jsonify,render_template, send_file,session, url_for
from supabase import create_client, Client
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)


SUPABASE_URL = 'https://oeihdxhhbfhlyoapcxlh.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9laWhkeGhoYmZobHlvYXBjeGxoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg3MTE1OCwiZXhwIjoyMDY1NDQ3MTU4fQ.IPT8NoEThkcvWfbMuKRlJrSGqc9Q-lCORWAlCGRQ0yU'


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app.secret_key = 'super-secret-key' 
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'foto_admin')


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
UPLOAD_FOLDER = 'static/foto_admin'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Folder penyimpanan sementara
DOWNLOAD_FOLDER = "downloaded_files"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Ambil data dari tabel admin berdasarkan email
            response = supabase.table('akun_admin').select('email, password, nama, foto').eq('email', email).execute()
            admin_data = response.data[0] if response.data else None
            if admin_data:
                if password == admin_data['password']:
                    session['user'] = admin_data['email']
                    session['nama_admin'] = admin_data['nama']
                    session['foto_admin'] = admin_data['foto']

                    flash('Login berhasil!', 'login_success')
                    return redirect(url_for('dashboard_grafik'))
                else:
                    flash('Login gagal: Password salah.', 'login_danger')
            else:
                flash('Login gagal: Email tidak ditemukan.', 'login_danger')

        except Exception as e:
            flash('Login gagal: ' , 'login_danger')

        return redirect(url_for('index'))

    return redirect(url_for('index'))


@app.route('/admin_add', methods=['POST'])
def admin_add():
    if 'user' not in session:
        return redirect(url_for('login'))

    nama = request.form['nama']
    email = request.form['email']
    password = request.form['password']
    foto = request.files['foto']

    existing = supabase.table("akun_admin").select("*").or_(f"email.eq.{email},nama.eq.{nama}").execute()
    if existing.data:
        flash("Email atau nama sudah digunakan.", "admin_danger")
        return redirect(url_for("dashboard"))

    filename = secure_filename(nama.lower().replace(" ", "_") + "_" + foto.filename)
    file_bytes = BytesIO(foto.read())

    try:
        supabase.storage.from_('admin-foto').upload(
            path=filename,
            file=file_bytes.getvalue(),
            file_options={"content-type": foto.mimetype}
        )
    except Exception as e:
        flash("Gagal upload foto: " , "admin_danger")
        return redirect(url_for('dashboard'))
    foto_url = f"https://{SUPABASE_URL.split('//')[1]}/storage/v1/object/public/admin-foto/{filename}"
    try:
        data_admin = {
            "nama": nama,
            "email": email,
            "password": password,
            "foto": foto_url
        }

        supabase.table("akun_admin").insert(data_admin).execute()
        flash('Akun berhasil ditambahkan!', 'admin_success')
    except Exception as e:
        flash('Gagal menambahkan akun: ' , 'admin_danger')

    return redirect(url_for('dashboard'))
def get_all_users():
    url = f"{SUPABASE_URL}/auth/v1/admin/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("users", [])
    else:
        print("Gagal mengambil data user:", response.text)
        return []
    
@app.route('/dashboard_grafik')
def dashboard_grafik():
    pendaftar = supabase.table("pendaftaran").select("*").execute().data
    total = len(pendaftar)
    diterima = len([p for p in pendaftar if p.get('verifikasi') == 'diterima' and 'Menunggu'])
    menunggu = len([p for p in pendaftar if p.get('verifikasi') == 'menunggu' and 'Menunggu'])
    ditolak = len([p for p in pendaftar if p.get('verifikasi') == 'Tidak Diterima' and 'tidak diterima'])

    return render_template("grafik.html",
                           total=total,
                           diterima=diterima,
                           ditolak=ditolak,
                           menunggu=menunggu,
                           nama_admin=session.get('nama_admin'),
                           foto_admin=session.get('foto_admin'))
    
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user' not in session:
        flash('Silakan login terlebih dahulu.', 'login_danger')
        return redirect(url_for('login'))

    users = get_all_users()
    return render_template('dashboard.html', users=users,
                           nama_admin=session.get('nama_admin'),
                           foto_admin=session.get('foto_admin'))
@app.route('/akun_admin')
def akun_admin():
    if 'user' not in session:
        return redirect(url_for('login'))

    try:
        response = supabase.table("akun_admin").select("*").execute()
        users = response.data if response.data else []
    except Exception as e:
        flash("Gagal mengambil data akun admin: " , "admin_danger")
        users = []

    return render_template("akun_admin.html",
                           nama_admin=session.get('nama_admin'),
                           foto_admin=session.get('foto_admin'),
                           users=users)

@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_id = request.form.get('uid') 

    try:
        supabase.table("akun_admin").delete().eq("id", user_id).execute()
        flash("Akun berhasil dihapus", "admin_success")
    except Exception as e:
        flash("Terjadi kesalahan saat menghapus akun: " , "admin_danger")

    return redirect(url_for('dashboard'))

@app.route('/edit_user', methods=['POST'])
def edit_user():
    user_id = request.form.get('uid')  
    new_email = request.form.get('email')
    new_nama = request.form.get('nama')
    new_password = request.form.get('new_password')
    try:
        update_data = {"email": new_email}
        if new_nama:
            update_data["nama"] = new_nama
        if new_password:
            update_data["password"] = new_password

        supabase.table("akun_admin").update(update_data).eq("id", user_id).execute()
        flash("Akun berhasil diperbarui", "admin_success")
    except Exception as e:
        flash("Terjadi kesalahan: " , "admin_danger")

    return redirect(url_for('dashboard'))

@app.route('/notifikasi', methods=['GET'])
def notifikasi():
    users = supabase.table("pendaftaran").select("*").execute().data
    return render_template("notifikasi.html",users=users,
                           nama_admin=session.get('nama_admin'),
                           foto_admin=session.get('foto_admin'),
                           )

@app.route('/update_status_pendaftaran', methods=['POST'])
def update_status_pendaftaran():
    user_id = request.form.get('user_id')
    new_status = request.form.get('isi')
    try:
        supabase.table("pendaftaran").update({"verifikasi": new_status}).eq("user_id",user_id).execute()
        flash("Status Pendaftaran berhasil diperbarui", "admin_success")
    except Exception as e:
        flash("Gagal memperbarui status Pendaftaran: " , "admin_danger")

    return redirect(url_for('notifikasi'))

@app.route('/pembayaran', methods=['GET'])
def pembayaran():
    # Ambil semua data pembayaran dan pendaftaran
    pembayaran_data = supabase.table("pembayaran").select("*").execute().data
    pendaftaran_data = supabase.table("pendaftaran").select("id, nama_lengkap").execute().data

    pendaftaran_dict = {p['id']: p['nama_lengkap'] for p in pendaftaran_data}
    for bayar in pembayaran_data:
        p_id = bayar.get("pendaftaran_id")
        bayar["nama_lengkap"] = pendaftaran_dict.get(p_id, "Tidak Ditemukan")

    return render_template("pembayaran.html", users=pembayaran_data,
                           nama_admin=session.get('nama_admin'),
                           foto_admin=session.get('foto_admin'))

@app.route('/update_status_pembayaran', methods=['POST'])
def update_status_pembayaran():
    user_id = request.form.get('user_id')
    new_status = request.form.get('isi')
    try:
        supabase.table("pembayaran").update({"status": new_status}).eq("id",user_id).execute()
        flash("Status Pembayaran berhasil diperbarui", "admin_success")
    except Exception as e:
        flash("Gagal memperbarui status Pembayaran: " , "admin_danger")
    return redirect(url_for('pembayaran'))

@app.route("/peserta_pendaftaran")
def peserta_pendaftaran():
    # Ambil semua dokumen
    dokumen_response = supabase.table("dokumen_pendaftaran").select("*").execute()
    dokumen_list = dokumen_response.data

    # Ambil semua pendaftaran
    pendaftaran_response = supabase.table("pendaftaran").select("*").execute()
    pendaftaran_list = {p['id']: p for p in pendaftaran_response.data}

    # Gabungkan data dokumen dengan data pendaftaran berdasarkan pendaftaran_id
    for doc in dokumen_list:
        pendaftar = pendaftaran_list.get(doc['pendaftaran_id'], {})
        doc['nik'] = pendaftar.get('nik', '-')
        doc['nama_lengkap'] = pendaftar.get('nama_lengkap', '-')
        doc['asal_sekolah'] = pendaftar.get('asal_sekolah', '-')
    users = get_all_users()
    return render_template("peserta_pendaftaran.html", dokumen_list=dokumen_list, users=users,
                           nama_admin=session.get('nama_admin'),
                           foto_admin=session.get('foto_admin'))
@app.route('/download/<path:url>')
def download_file(url):
    try:
        # Ubah kembali URL yang di-encode oleh browser (misalnya %2F jadi /)
        full_url = requests.utils.unquote(url)
        
        # Ambil file dari URL
        r = requests.get(full_url, stream=True)
        r.raise_for_status()  # Naikkan error kalau gagal

        # Dapatkan nama file dari URL
        filename = full_url.split("/")[-1]

        # Bungkus konten file ke BytesIO agar bisa dikirim oleh Flask
        return send_file(
            BytesIO(r.content),
            as_attachment=True,
            download_name=filename,
            mimetype=r.headers.get('Content-Type', 'application/octet-stream')
        )
    except Exception as e:
        return Response(f"Gagal mengunduh file: {e}", status=500)


@app.route("/download_all")
def download_all_zip():
    try:
        # Ambil semua data dari tabel dokumen_pendaftaran
        result = supabase.table("dokumen_pendaftaran").select("nama_file, url_file").execute()
        dokumen_list = result.data

        if not dokumen_list:
            return Response("Tidak ada dokumen ditemukan.", status=404)

        # Siapkan ZIP dalam memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for doc in dokumen_list:
                url_file = doc["url_file"]
                filename = doc["nama_file"]

                # Unduh file dari Supabase Storage
                response = requests.get(url_file, stream=True)
                if response.status_code == 200:
                    zipf.writestr(filename, response.content)
                else:
                    print(f"Gagal unduh: {filename} dari {url_file} — status {response.status_code}")

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="semua_dokumen.zip"
        )

    except Exception as e:
        return Response(f"Terjadi kesalahan saat membuat ZIP", status=500)

@app.route('/kirim_notifikasi', methods=['POST'])



@app.route('/logout', methods=['POST'])
def logout():
    session.clear() 
    return redirect(url_for('index')) 


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

