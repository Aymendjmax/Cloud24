# main.py
import os
import uuid
import json
import datetime
import time
import hashlib
from datetime import timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from io import BytesIO
import threading
from functools import wraps
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cloud24-secret-key-2025")

# إعدادات Cloudinary
CLOUDINARY_CLOUD_NAME = "dnphkgppf"  # استبدل ببياناتك
CLOUDINARY_API_KEY = "319752582295455"        # استبدل ببياناتك
CLOUDINARY_API_SECRET = "h7cVYhOLeXMIrtiIsur6lVLU3gg"  # استبدل ببياناتك

# تهيئة Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# إزالة قيود أنواع الملفات - السماح بجميع أنواع الملفات
ALLOWED_EXTENSIONS = set()  # مجموعة فارغة للسماح بجميع الملفات

# قاعدة بيانات مؤقتة (في بيئة حقيقية استخدم قاعدة بيانات حقيقية)
projects_db = {}
files_db = {}

# ديكورات المساعدة
def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

# وظائف مساعدة
def safe_filename(filename, project_id):
    """إنشاء اسم ملف آمن مع تجنب التكرار"""
    timestamp = str(int(time.time()))
    file_hash = hashlib.md5(f"{project_id}_{filename}_{timestamp}".encode()).hexdigest()[:8]
    name, ext = os.path.splitext(filename)
    safe_name = f"{file_hash}_{name[:50]}{ext}"  # تقليل طول الاسم لتجنب مشاكل المسار
    return safe_name

def allowed_file(filename):
    """التحقق من أن امتداد الملف مسموح - السماح بجميع الملفات الآن"""
    # السماح بجميع الملفات بدون قيود
    return '.' in filename  # فقط التحقق من وجود امتداد

@retry_on_failure(max_retries=3, delay=1)
def upload_file_to_cloudinary(file_data, file_name, project_id):
    """رفع ملف إلى Cloudinary مع معالجة محسنة للأخطاء"""
    try:
        # إنشاء مسار الملف
        file_path = f"{project_id}/{file_name}"
        
        # رفع الملف إلى Cloudinary
        result = cloudinary.uploader.upload(
            file_data,
            public_id=file_path,
            resource_type="auto"  # يكتشف نوع الملف تلقائياً
        )
        
        if result and 'secure_url' in result:
            print(f"Successfully uploaded to Cloudinary: {file_name}")
            return result
        else:
            print(f"Failed to upload to Cloudinary: {file_name}")
            return None
            
    except Exception as e:
        print(f"Error uploading file to Cloudinary: {e}")
        return None

def get_file_url(project_id, file_name):
    """الحصول على رابط التحميل من Cloudinary"""
    file_path = f"{project_id}/{file_name}"
    return cloudinary.CloudinaryImage(file_path).build_url()

@retry_on_failure(max_retries=3, delay=1)
def download_file_from_cloudinary(file_url):
    """تحميل ملف من Cloudinary"""
    try:
        response = requests.get(file_url)
        if response.status_code == 200:
            return response.content
        else:
            print(f"Error downloading file from Cloudinary: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading file from Cloudinary: {e}")
        return None

@retry_on_failure(max_retries=3, delay=1)
def delete_project_files(project_id):
    """حذف جميع ملفات المشروع من Cloudinary مع معالجة محسنة للأخطاء"""
    try:
        print(f"Attempting to delete files for project: {project_id}")
        
        # حذف جميع الموارد في مجلد المشروع
        result = cloudinary.api.delete_resources_by_prefix(f"{project_id}/")
        
        if result and 'deleted' in result:
            print(f"Successfully deleted {len(result['deleted'])} files for project {project_id}")
            return True
        else:
            print(f"No files found to delete for project {project_id}")
            return True
            
    except Exception as e:
        print(f"Error deleting project files from Cloudinary: {e}")
        return False

def cleanup_expired_projects():
    """حذف المشاريع المنتهية الصلاحية"""
    while True:
        try:
            current_time = datetime.datetime.now()
            expired_projects = []
            
            for project_id, project_data in list(projects_db.items()):
                if current_time - project_data['created_at'] > timedelta(hours=24):
                    expired_projects.append(project_id)
            
            for project_id in expired_projects:
                if project_id in projects_db:
                    if delete_project_files(project_id):
                        del projects_db[project_id]
                        print(f"Deleted expired project: {project_id}")
            
            time.sleep(3600)  # التحقق كل ساعة
        except Exception as e:
            print(f"Error in cleanup_expired_projects: {e}")
            time.sleep(300)  # الانتظار 5 دقائق عند حدوث خطأ

# بدء عملية التنظيف في خيط منفصل
cleanup_thread = threading.Thread(target=cleanup_expired_projects, daemon=True)
cleanup_thread.start()

# Routes
@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/upload', methods=['POST'])
def upload_project():
    try:
        # التحقق من اسم المشروع
        project_name = request.form.get('projectName')
        if not project_name or not project_name.strip():
            print("Error: Project name is missing or empty")
            return jsonify({'success': False, 'message': 'اسم المشروع مطلوب'})
        
        project_name = project_name.strip()
        print(f"Processing project: {project_name}")
        
        # جمع الملفات المرفوعة
        uploaded_files = []
        total_size = 0
        max_file_size = 50 * 1024 * 1024  # 50 MB حد أقصى لكل ملف
        max_total_size = 200 * 1024 * 1024  # 200 MB حد أقصى للمشروع كاملاً
        
        # طريقة أفضل لجمع الملفات
        for key in request.files:
            files_list = request.files.getlist(key)
            for file in files_list:
                if file and file.filename and file.filename.strip():
                    filename = file.filename.strip()
                    
                    # التحقق من الامتداد (السماح بجميع الملفات الآن)
                    if not allowed_file(filename):
                        print(f"Warning: File without extension - {filename}")
                        continue
                    
                    # التحقق من حجم الملف
                    file.seek(0, 2)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size == 0:
                        print(f"Warning: Empty file skipped - {filename}")
                        continue
                    
                    if file_size > max_file_size:
                        return jsonify({
                            'success': False, 
                            'message': f'الملف {filename} كبير جداً (الحد الأقصى 50 MB)'
                        })
                    
                    total_size += file_size
                    uploaded_files.append({
                        'file': file,
                        'filename': filename,
                        'size': file_size
                    })
                    
                    print(f"Added file: {filename} ({file_size} bytes)")
        
        if not uploaded_files:
            print("Error: No valid files found")
            return jsonify({'success': False, 'message': 'يجب اختيار ملف واحد على الأقل'})
        
        if total_size > max_total_size:
            return jsonify({
                'success': False, 
                'message': f'حجم المشروع كبير جداً (الحد الأقصى 200 MB)'
            })
        
        print(f"Total files: {len(uploaded_files)}, Total size: {total_size} bytes")
        
        # إنشاء معرف فريد للمشروع
        project_id = str(uuid.uuid4())
        print(f"Created project ID: {project_id}")
        
        # رفع الملفات
        file_urls = {}
        failed_files = []
        successful_uploads = 0
        
        for file_data in uploaded_files:
            file = file_data['file']
            filename = file_data['filename']
            
            try:
                # إنشاء اسم ملف آمن
                safe_name = safe_filename(filename, project_id)
                
                # قراءة الملف بشكل أكثر كفاءة
                file.seek(0)
                
                # للملفات الكبيرة، يمكن قراءتها على دفعات
                if file_data['size'] > 10 * 1024 * 1024:  # 10 MB
                    # قراءة الملف على دفعات للملفات الكبيرة
                    file_content = bytearray()
                    chunk_size = 1024 * 1024  # 1 MB chunks
                    while True:
                        chunk = file.read(chunk_size)
                        if not chunk:
                            break
                        file_content.extend(chunk)
                    file_content = bytes(file_content)
                else:
                    # قراءة مباشرة للملفات الصغيرة
                    file_content = file.read()
                
                if not file_content:
                    failed_files.append(f"{filename} (محتوى فارغ)")
                    print(f"Failed: {filename} - empty content")
                    continue
                
                print(f"Uploading {filename} as {safe_name} ({len(file_content)} bytes)...")
                
                # رفع الملف إلى Cloudinary
                result = upload_file_to_cloudinary(file_content, safe_name, project_id)
                
                if result:
                    file_urls[filename] = {
                        'url': result['secure_url'],
                        'safe_name': safe_name
                    }
                    successful_uploads += 1
                    print(f"Successfully uploaded: {filename} as {safe_name}")
                else:
                    failed_files.append(filename)
                    print(f"Failed to upload: {filename}")
                    
            except Exception as file_error:
                print(f"Error processing file {filename}: {file_error}")
                failed_files.append(f"{filename} (خطأ في المعالجة)")
        
        # التحقق من نجاح رفع بعض الملفات على الأقل
        if not file_urls:
            error_msg = "فشل في رفع جميع الملفات"
            if failed_files:
                error_msg += f". الملفات الفاشلة: {', '.join(failed_files)}"
            
            print(f"Upload completely failed: {error_msg}")
            return jsonify({'success': False, 'message': error_msg})
        
        # حفظ بيانات المشروع
        projects_db[project_id] = {
            'name': project_name,
            'file_urls': file_urls,
            'created_at': datetime.datetime.now(),
            'total_files': len(file_urls),
            'total_size': total_size
        }
        
        # تحضير الاستجابة
        response_data = {
            'success': True, 
            'project_id': project_id,
            'uploaded_files': successful_uploads,
            'total_files': len(uploaded_files)
        }
        
        # إضافة تحذير إذا فشل بعض الملفات
        if failed_files:
            response_data['warning'] = f"تم رفع {successful_uploads} من {len(uploaded_files)} ملف. فشل في: {', '.join(failed_files)}"
            print(f"Partial success: {response_data['warning']}")
        
        print(f"Project {project_id} created successfully with {successful_uploads} files")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Critical error in upload_project: {e}")
        import traceback
        traceback.print_exc()
        
        # تنظيف البيانات في حالة الخطأ
        if 'project_id' in locals() and project_id in projects_db:
            try:
                # محاولة حذف الملفات المرفوعة جزئياً
                delete_project_files(project_id)
                del projects_db[project_id]
            except:
                pass
        
        return jsonify({
            'success': False, 
            'message': f'حدث خطأ غير متوقع أثناء رفع المشروع. يرجى المحاولة مرة أخرى.'
        })

@app.route('/api/project/<project_id>')
def api_get_project(project_id):
    if project_id not in projects_db:
        return jsonify({'success': False, 'message': 'المشروع غير موجود'})
    
    project = projects_db[project_id]
    
    # تحضير روابط الملفات للعرض
    display_file_urls = {}
    for filename, file_info in project['file_urls'].items():
        display_file_urls[filename] = file_info['url']
    
    return jsonify({
        'success': True, 
        'project': {
            'name': project['name'],
            'file_urls': display_file_urls,
            'created_at': project['created_at'].isoformat() + 'Z'  # إضافة Z للإشارة إلى UTC
        }
    })

@app.route('/project/<project_id>')
def view_project(project_id):
    if project_id not in projects_db:
        return """
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                document.getElementById('deletedProject').style.display = 'block';
                document.querySelector('.intro-section').style.display = 'none';
                document.querySelector('.upload-section').style.display = 'none';
            });
        </script>
        """ + HTML_TEMPLATE
    
    project = projects_db[project_id]
    project_name = project['name']
    created_at = project['created_at']
    
    # حساب الوقت المتبقي
    time_remaining = (created_at + timedelta(hours=24)) - datetime.datetime.now()
    if time_remaining.total_seconds() <= 0:
        return """
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                document.getElementById('deletedProject').style.display = 'block';
                document.querySelector('.intro-section').style.display = 'none';
                document.querySelector('.upload-section').style.display = 'none';
            });
        </script>
        """ + HTML_TEMPLATE
    
    hours, remainder = divmod(time_remaining.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    
    # إنشاء قائمة الملفات
    files_list = ""
    for filename, file_info in project['file_urls'].items():
        file_url = file_info['url']
        file_icon = get_file_icon_by_filename(filename)
        
        files_list += f"""
        <div class="project-file-item">
            <div class="project-file-info">
                <i class="{file_icon} project-file-icon"></i>
                <div class="project-file-details">
                    <h5>{filename}</h5>
                    <p>تم الرفع: {created_at.strftime('%Y-%m-%d %H:%M')}</p>
                </div>
            </div>
            <a class="download-btn" href="{file_url}" download="{filename}">
                <i class="fas fa-download"></i>
                تحميل
            </a>
        </div>
        """
    
    # تعديل HTML لعرض المشروع
    modified_html = HTML_TEMPLATE.replace(
        '<h3 id="projectTitle">مشروع تجريبي</h3>',
        f'<h3 id="projectTitle">{project_name}</h3>'
    ).replace(
        '<span id="countdown">23:59:59</span>',
        f'<span id="countdown">{countdown}</span>'
    ).replace(
        '<input type="text" id="projectLink" value="" readonly>',
        f'<input type="text" id="projectLink" value="{request.url}" readonly>'
    ).replace(
        '<!-- سيتم إضافة الملفات هنا ديناميكياً -->',
        files_list
    )
    
    return modified_html

def get_file_icon_by_filename(filename):
    ext = filename.split('.').pop().lower() if '.' in filename else ''
    
    # ملفات الصور
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'tif']:
        return 'fas fa-file-image'
    # ملفات الفيديو
    elif ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'm4v', '3gp', 'mpeg', 'mpg']:
        return 'fas fa-file-video'
    # ملفات الصوت
    elif ext in ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'mid', 'midi']:
        return 'fas fa-file-audio'
    # ملفات PDF
    elif ext == 'pdf':
        return 'fas fa-file-pdf'
    # ملفات Word
    elif ext in ['doc', 'docx', 'docm', 'dot', 'dotx']:
        return 'fas fa-file-word'
    # ملفات Excel
    elif ext in ['xls', 'xlsx', 'xlsm', 'xlt', 'xltx', 'csv']:
        return 'fas fa-file-excel'
    # ملفات PowerPoint
    elif ext in ['ppt', 'pptx', 'pptm', 'pot', 'potx', 'pps', 'ppsx']:
        return 'fas fa-file-powerpoint'
    # ملفات الأرشيف
    elif ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso']:
        return 'fas fa-file-archive'
    # ملفات النصوص
    elif ext in ['txt', 'rtf', 'md', 'tex', 'log']:
        return 'fas fa-file-alt'
    # ملفات البرمجة
    elif ext in ['html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 
                'php', 'rb', 'go', 'swift', 'kt', 'rs', 'sh', 'bat', 'ps1', 'vb', 'cs', 'sql', 'xml', 
                'json', 'yaml', 'yml', 'ini', 'cfg', 'conf']:
        return 'fas fa-file-code'
    # ملفات التطبيقات والتنفيذية
    elif ext in ['exe', 'msi', 'apk', 'app', 'deb', 'rpm', 'dmg', 'pkg']:
        return 'fas fa-cog'
    # ملفات الخطوط
    elif ext in ['ttf', 'otf', 'woff', 'woff2', 'eot']:
        return 'fas fa-font'
    # ملفات التصميم
    elif ext in ['psd', 'ai', 'eps', 'sketch', 'fig', 'xd']:
        return 'fas fa-paint-brush'
    # ملفات قواعد البيانات
    elif ext in ['db', 'sqlite', 'mdb', 'accdb', 'dbf']:
        return 'fas fa-database'
    # ملفات النسخ الاحتياطي
    elif ext in ['bak', 'tmp', 'temp', 'backup']:
        return 'fas fa-history'
    # ملفات التورنت
    elif ext == 'torrent':
        return 'fas fa-magnet'
    # ملفات القرص الافتراضي
    elif ext in ['vhd', 'vdi', 'vmware', 'ova', 'ovf']:
        return 'fas fa-hdd'
    # ملفات الإلكترونيات والطباعة ثلاثية الأبعاد
    elif ext in ['stl', 'obj', 'gcode', 'svg', 'dxf']:
        return 'fas fa-cube'
    # ملفات التشفير والمفاتيح
    elif ext in ['pem', 'key', 'crt', 'cer', 'pfx', 'p12']:
        return 'fas fa-key'
    # ملفات أخرى
    else:
        return 'fas fa-file'

@app.route('/download/<project_id>/<filename>')
def download_file(project_id, filename):
    if project_id not in projects_db:
        return "المشروع غير موجود", 404
    
    project = projects_db[project_id]
    if filename not in project['file_urls']:
        return "الملف غير موجود", 404
    
    try:
        # الحصول على رابط الملف من Cloudinary
        file_url = project['file_urls'][filename]['url']
        
        # تحميل الملف
        file_content = download_file_from_cloudinary(file_url)
        
        if file_content:
            return send_file(
                BytesIO(file_content),
                as_attachment=True,
                download_name=filename
            )
        else:
            # إذا فشل التحميل المباشر، إعادة التوجيه إلى رابط Cloudinary
            return redirect(file_url)
    except Exception as e:
        print(f"Error downloading file: {e}")
        # إذا فشل التحميل، إعادة التوجيه إلى رابط Cloudinary
        return redirect(project['file_urls'][filename]['url'])

# إضافة route للتحقق من حالة Cloudinary
@app.route('/api/cloudinary/status')
def check_cloudinary_status():
    """التحقق من حالة الاتصال مع Cloudinary"""
    try:
        # اختبار بسيط للاتصال مع Cloudinary
        test_result = cloudinary.uploader.upload(
            b"test file content",
            public_id="test/connection_test",
            resource_type="raw"
        )
        
        if test_result and 'secure_url' in test_result:
            # حذف الملف الاختباري
            cloudinary.uploader.destroy(test_result['public_id'])
            return jsonify({'status': 'success', 'message': 'اتصال Cloudinary يعمل بشكل صحيح'})
        else:
            return jsonify({'status': 'error', 'message': 'فشل في الاتصال بـ Cloudinary'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'خطأ في التحقق: {str(e)}'})

@app.route('/ping')
def ping():
    return "pong", 200

@app.errorhandler(404)
def not_found(error):
    return "الصفحة غير موجودة", 404

@app.errorhandler(500)
def internal_error(error):
    return "حدث خطأ داخلي في الخادم", 500

# إضافة route لاختبار شامل لاتصال Cloudinary
@app.route('/test-cloudinary')
def test_cloudinary_connection():
    """اختبار شامل لاتصال Cloudinary"""
    try:
        # اختبار رفع ملف تجريبي
        test_data = b"test file content for Cloud24"
        
        result = cloudinary.uploader.upload(
            test_data,
            public_id="test/connection_test",
            resource_type="raw"
        )
        
        if result and 'secure_url' in result:
            # حذف الملف الاختباري
            cloudinary.uploader.destroy(result['public_id'])
            return jsonify({
                'status': 'success',
                'message': 'اتصال Cloudinary يعمل بشكل مثالي!',
                'details': {
                    'cloud_name': CLOUDINARY_CLOUD_NAME,
                    'upload_test': 'نجح'
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'فشل في اختبار الرفع إلى Cloudinary'
            })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطأ عام: {str(e)}',
            'suggestion': 'تحقق من تثبيت مكتبة cloudinary: pip install cloudinary'
        })

# route إضافي لاختبار سريع
@app.route('/config-check')
def config_check():
    """فحص سريع للإعدادات"""
    return jsonify({
        'cloudinary_cloud_name': CLOUDINARY_CLOUD_NAME,
        'has_cloudinary_key': bool(CLOUDINARY_API_KEY and len(CLOUDINARY_API_KEY) > 10),
        'has_cloudinary_secret': bool(CLOUDINARY_API_SECRET and len(CLOUDINARY_API_SECRET) > 10)
    })

# HTML template (نفس محتوى index.html)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloud24 - تخزين سحابي مؤقت</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        /* إعدادات عامة */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Cairo', sans-serif;
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            color: #333;
            line-height: 1.6;
            overflow-x: hidden;
            position: relative;
            min-height: 100vh;
        }

        /* الخلفية المتحركة */
        .animated-background {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }

        .floating-icon {
            position: absolute;
            color: rgba(220, 53, 69, 0.1);
            font-size: 2rem;
            animation: float 15s infinite linear;
        }

        .floating-icon:nth-child(1) {
            top: 10%;
            left: 10%;
            animation-delay: 0s;
            animation-duration: 20s;
        }

        .floating-icon:nth-child(2) {
            top: 20%;
            right: 15%;
            animation-delay: -3s;
            animation-duration: 18s;
        }

        .floating-icon:nth-child(3) {
            top: 60%;
            left: 5%;
            animation-delay: -6s;
            animation-duration: 22s;
        }

        .floating-icon:nth-child(4) {
            top: 80%;
            right: 20%;
            animation-delay: -9s;
            animation-duration: 16s;
        }

        .floating-icon:nth-child(5) {
            top: 40%;
            left: 80%;
            animation-delay: -12s;
            animation-duration: 19s;
        }

        .floating-icon:nth-child(6) {
            top: 70%;
            right: 60%;
            animation-delay: -15s;
            animation-duration: 21s;
        }

        .floating-icon:nth-child(7) {
            top: 30%;
            left: 60%;
            animation-delay: -18s;
            animation-duration: 17s;
        }

        .floating-icon:nth-child(8) {
            top: 90%;
            left: 40%;
            animation-delay: -21s;
            animation-duration: 23s;
        }

        @keyframes float {
            0% {
                transform: translateY(0px) rotate(0deg);
                opacity: 0.1;
            }
            50% {
                transform: translateY(-20px) rotate(180deg);
                opacity: 0.3;
            }
            100% {
                transform: translateY(0px) rotate(360deg);
                opacity: 0.1;
            }
        }

        /* الحاوي الرئيسي */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            position: relative;
            z-index: 1;
        }

        /* الهيدر */
        .header {
            text-align: center;
            padding: 40px 0;
        }

        .logo-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }

        .logo {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: 4px solid #dc3545;
            box-shadow: 0 10px 30px rgba(220, 53, 69, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .logo:hover {
            transform: scale(1.1);
            box-shadow: 0 15px 40px rgba(220, 53, 69, 0.4);
        }

        .site-title {
            font-size: 3rem;
            font-weight: 700;
            color: #dc3545;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
            margin: 0;
        }

        /* المحتوى الرئيسي */
        .main-content {
            padding: 20px 0;
        }

        /* قسم التعريف */
        .intro-section {
            text-align: center;
            margin-bottom: 50px;
        }

        .intro-title {
            font-size: 2.5rem;
            color: #dc3545;
            margin-bottom: 20px;
            font-weight: 600;
        }

        .intro-description {
            font-size: 1.2rem;
            color: #666;
            max-width: 800px;
            margin: 0 auto 40px;
            line-height: 1.8;
        }

        /* شبكة المميزات */
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin: 50px 0;
        }

        .feature-card {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border-top: 4px solid #dc3545;
        }

        .feature-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
        }

        .feature-icon {
            font-size: 3rem;
            color: #dc3545;
            margin-bottom: 20px;
        }

        .feature-card h3 {
            font-size: 1.5rem;
            color: #333;
            margin-bottom: 15px;
            font-weight: 600;
        }

        .feature-card p {
            color: #666;
            line-height: 1.6;
        }

        /* كيفية الاستخدام */
        .how-to-use {
            margin: 50px 0;
            text-align: center;
        }

        .how-to-use h3 {
            font-size: 2rem;
            color: #dc3545;
            margin-bottom: 30px;
            font-weight: 600;
        }

        .steps {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            max-width: 1000px;
            margin: 0 auto;
        }

        .step {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 3px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .step:hover {
            transform: translateY(-5px);
        }

        .step-number {
            background: #dc3545;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 1.2rem;
            flex-shrink: 0;
        }

        .step p {
            color: #333;
            font-weight: 500;
        }

        /* قسم الرفع */
        .upload-section {
            text-align: center;
            margin: 50px 0;
        }

        .upload-btn {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            border: none;
            padding: 20px 40px;
            font-size: 1.3rem;
            font-weight: 600;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 5px 20px rgba(220, 53, 69, 0.3);
            display: inline-flex;
            align-items: center;
            gap: 15px;
            font-family: 'Cairo', sans-serif;
        }

        .upload-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(220, 53, 69, 0.4);
            background: linear-gradient(135deg, #c82333 0%, #a71e2a 100%);
        }

        .upload-btn i {
            font-size: 1.5rem;
        }

        /* نموذج المشروع */
        .project-form {
            margin: 50px 0;
            animation: slideIn 0.5s ease;
        }

        .form-container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            margin: 0 auto;
            border-top: 4px solid #dc3545;
        }

        .form-container h3 {
            text-align: center;
            color: #dc3545;
            font-size: 2rem;
            margin-bottom: 30px;
            font-weight: 600;
        }

        .input-group {
            margin-bottom: 25px;
        }

        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
            font-size: 1.1rem;
        }

        .input-group input[type="text"] {
            width: 100%;
            padding: 15px;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
            font-family: 'Cairo', sans-serif;
        }

        .input-group input[type="text"]:focus {
            outline: none;
            border-color: #dc3545;
            box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.1);
        }

        /* منطقة رفع الملفات */
        .file-upload-area {
            border: 3px dashed #dc3545;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }

        .file-upload-area:hover {
            background: rgba(220, 53, 69, 0.05);
            border-color: #c82333;
        }

        .upload-icon {
            font-size: 3rem;
            color: #dc3545;
            margin-bottom: 15px;
        }

        .file-upload-area p {
            color: #666;
            font-size: 1.1rem;
            margin: 0;
        }

        /* قائمة الملفات */
        .files-list {
            margin-top: 20px;
        }

        .file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 10px;
            border-left: 4px solid #dc3545;
            flex-wrap: wrap;
        }

        .file-info {
            display: flex;
            align-items: center;
            gap: 15px;
            flex: 1;
            min-width: 0;
        }

        .file-icon {
            font-size: 1.5rem;
            color: #dc3545;
            flex-shrink: 0;
        }

        .file-details {
            min-width: 0;
            overflow: hidden;
        }

        .file-details h4 {
            margin: 0;
            color: #333;
            font-size: 1rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .file-details p {
            margin: 0;
            color: #666;
            font-size: 0.9rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .delete-file-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s ease;
            flex-shrink: 0;
        }

        .delete-file-btn:hover {
            background: #c82333;
        }

        /* أزرار النموذج */
        .form-actions {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }

        .cancel-btn, .submit-btn {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'Cairo', sans-serif;
        }

        .cancel-btn {
            background: #6c757d;
            color: white;
        }

        .cancel-btn:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }

        .submit-btn {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
        }

        .submit-btn:hover {
            background: linear-gradient(135deg, #c82333 0%, #a71e2a 100%);
            transform: translateY(-2px);
        }

        /* عرض المشروع */
        .project-view {
            margin: 50px 0;
            animation: slideIn 0.5s ease;
        }

        .project-container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            max-width: 800px;
            margin: 0 auto;
            border-top: 4px solid #dc3545;
        }

        .project-container h3 {
            text-align: center;
            color: #dc3545;
            font-size: 2.5rem;
            margin-bottom: 30px;
            font-weight: 600;
        }

        /* قسم المؤقت */
        .timer-section {
            text-align: center;
            margin: 30px 0;
            padding: 30px;
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            border-radius: 15px;
            color: white;
        }

        .timer-display {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-bottom: 10px;
        }

        .timer-display i {
            font-size: 2rem;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }

        .timer-display span {
            font-size: 3rem;
            font-weight: 700;
            font-family: 'Courier New', monospace;
        }

        .timer-section p {
            font-size: 1.1rem;
            opacity: 0.9;
        }

        /* قسم رابط المشروع */
        .project-link-section {
            margin: 30px 0;
        }

        .project-link-section label {
            display: block;
            margin-bottom: 10px;
            color: #333;
            font-weight: 600;
            font-size: 1.1rem;
        }

        .link-container {
            display: flex;
            gap: 10px;
        }

        .link-container input {
            flex: 1;
            padding: 15px;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            font-size: 1rem;
            background: #f8f9fa;
            font-family: 'Cairo', sans-serif;
        }

        .copy-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 15px 20px;
            border-radius: 10px;
            cursor: pointer;
            transition: background 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: 'Cairo', sans-serif;
        }

        .copy-btn:hover {
            background: #c82333;
        }

        /* قسم ملفات المشروع */
        .project-files-section {
            margin: 30px 0;
        }

        .project-files-section h4 {
            color: #333;
            font-size: 1.3rem;
            margin-bottom: 20px;
            font-weight: 600;
        }

        .project-files-list {
            display: grid;
            gap: 15px;
        }

        .project-file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            border-left: 4px solid #dc3545;
            transition: transform 0.3s ease;
            flex-wrap: wrap;
        }

        .project-file-item:hover {
            transform: translateX(-5px);
        }

        .project-file-info {
            display: flex;
            align-items: center;
            gap: 15px;
            flex: 1;
            min-width: 0;
        }

        .project-file-icon {
            font-size: 2rem;
            color: #dc3545;
            flex-shrink: 0;
        }

        .project-file-details {
            min-width: 0;
            overflow: hidden;
        }

        .project-file-details h5 {
            margin: 0;
            color: #333;
            font-size: 1.1rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .project-file-details p {
            margin: 0;
            color: #666;
            font-size: 0.9rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .download-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: 'Cairo', sans-serif;
            flex-shrink: 0;
            text-decoration: none;
        }

        .download-btn:hover {
            background: #218838;
        }

        /* أزرار المشروع */
        .project-actions {
            text-align: center;
            margin-top: 30px;
        }

        .back-btn {
            background: #6c757d;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1rem;
            font-family: 'Cairo', sans-serif;
        }

        .back-btn:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }

        /* صفحة المشروع المحذوف */
        .deleted-project {
            margin: 50px 0;
            animation: slideIn 0.5s ease;
        }

        .deleted-container {
            text-align: center;
            background: white;
            padding: 60px 40px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            margin: 0 auto;
            border-top: 4px solid #dc3545;
        }

        .deleted-icon {
            font-size: 5rem;
            color: #dc3545;
            margin-bottom: 20px;
        }

        .deleted-container h3 {
            color: #dc3545;
            font-size: 2rem;
            margin-bottom: 15px;
            font-weight: 600;
        }

        .deleted-container p {
            color: #666;
            font-size: 1.1rem;
            margin-bottom: 30px;
            line-height: 1.6;
        }

        /* الفوتر */
        .footer {
            text-align: center;
            padding: 30px 0;
            margin-top: 50px;
            border-top: 1px solid #e9ecef;
        }

        .footer p {
            color: #666;
            font-size: 1rem;
            margin: 0;
            line-height: 1.5;
        }

        .footer a {
            color: #dc3545 !important;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s ease;
        }

        .footer a:hover {
            color: #c82333 !important;
            text-decoration: underline;
        }

        /* الرسوم المتحركة */
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* التصميم المتجاوب */
        @media (max-width: 768px) {
            .container {
                padding: 0 15px;
            }
            
            .site-title {
                font-size: 2.5rem;
            }
            
            .intro-title {
                font-size: 2rem;
            }
            
            .features-grid {
                grid-template-columns: 1fr;
                gap: 20px;
            }
            
            .steps {
                grid-template-columns: 1fr;
            }
            
            .form-container {
                padding: 30px 20px;
            }
            
            .project-container {
                padding: 30px 20px;
            }
            
            .link-container {
                flex-direction: column;
            }
            
            .timer-display span {
                font-size: 2rem;
            }
            
            .form-actions {
                flex-direction: column;
            }
            
            .cancel-btn, .submit-btn {
                width: 100%;
            }

            .file-item, .project-file-item {
                flex-direction: column;
                align-items: flex-start;
            }

            .file-info, .project-file-info {
                width: 100%;
                margin-bottom: 10px;
            }

            .delete-file-btn, .download-btn {
                align-self: flex-end;
            }
        }

        @media (max-width: 480px) {
            .logo {
                width: 100px;
                height: 100px;
            }
            
            .site-title {
                font-size: 2rem;
            }
            
            .intro-title {
                font-size: 1.8rem;
            }
            
            .intro-description {
                font-size: 1rem;
            }
            
            .upload-btn {
                padding: 15px 30px;
                font-size: 1.1rem;
            }
            
            .timer-display {
                flex-direction: column;
                gap: 10px;
            }
            
            .timer-display span {
                font-size: 1.8rem;
            }

            .file-upload-area {
                padding: 20px;
            }

            .file-item, .project-file-item {
                padding: 12px;
            }

            .file-icon, .project-file-icon {
                font-size: 1.2rem;
            }

            .file-details h4, .project-file-details h5 {
                font-size: 0.9rem;
            }

            .file-details p, .project-file-details p {
                font-size: 0.8rem;
            }

            .footer p {
                font-size: 0.85rem;
            }
        }
    </style>
</head>
<body>
    <!-- خلفية متحركة -->
    <div class="animated-background">
        <div class="floating-icon"><i class="fas fa-cloud"></i></div>
        <div class="floating-icon"><i class="fas fa-file"></i></div>
        <div class="floating-icon"><i class="fas fa-folder"></i></div>
        <div class="floating-icon"><i class="fas fa-upload"></i></div>
        <div class="floating-icon"><i class="fas fa-download"></i></div>
        <div class="floating-icon"><i class="fas fa-server"></i></div>
        <div class="floating-icon"><i class="fas fa-database"></i></div>
        <div class="floating-icon"><i class="fas fa-shield-alt"></i></div>
    </div>

    <!-- الحاوي الرئيسي -->
    <div class="container">
        <!-- الهيدر -->
        <header class="header">
            <div class="logo-container">
                <img src="https://i.postimg.cc/9Fv1kXBp/A-logo-for-a-website-that-expresses-its-name-Cloud24-The-logo-must-be-re-20250824-045026.jpg" alt="Cloud24 Logo" class="logo">
                <h1 class="site-title">Cloud24</h1>
            </div>
        </header>

        <!-- القسم الرئيسي -->
        <main class="main-content">
            <!-- قسم التعريف -->
            <section class="intro-section">
                <h2 class="intro-title">مرحباً بك في Cloud24</h2>
                <p class="intro-description">
                    خدمة التخزين السحابي المؤقت الأكثر سهولة وأماناً. ارفع مشاريعك وملفاتك واحتفظ بها لمدة 24 ساعة كاملة، 
                    ثم شاركها مع الآخرين بكل سهولة. بعد انتهاء المدة، تختفي ملفاتك تلقائياً لضمان خصوصيتك وأمانك.
                </p>
                
                <div class="features-grid">
                    <div class="feature-card">
                        <i class="fas fa-clock feature-icon"></i>
                        <h3>24 ساعة فقط</h3>
                        <p>ملفاتك محفوظة لمدة 24 ساعة ثم تختفي تلقائياً</p>
                    </div>
                    <div class="feature-card">
                        <i class="fas fa-shield-alt feature-icon"></i>
                        <h3>آمن ومحمي</h3>
                        <p>حماية عالية لملفاتك مع تشفير متقدم</p>
                    </div>
                    <div class="feature-card">
                        <i class="fas fa-share-alt feature-icon"></i>
                        <h3>مشاركة سهلة</h3>
                        <p>احصل على رابط مباشر لمشاركة مشروعك</p>
                    </div>
                </div>

                <div class="how-to-use">
                    <h3>كيفية الاستخدام:</h3>
                    <div class="steps">
                        <div class="step">
                            <span class="step-number">1</span>
                            <p>اضغط على "ارفع مشروع جديد"</p>
                        </div>
                        <div class="step">
                            <span class="step_number">2</span>
                            <p>أدخل اسم المشروع واختر الملفات</p>
                        </div>
                        <div class="step">
                            <span class="step_number">3</span>
                            <p>اضغط "ارفع المشروع" واحصل على الرابط</p>
                        </div>
                        <div class="step">
                            <span class="step_number">4</span>
                            <p>شارك الرابط مع من تريد</p>
                        </div>
                    </div>
                </div>
            </section>

            <!-- زر رفع مشروع جديد -->
            <section class="upload-section">
                <button class="upload-btn" id="newProjectBtn">
                    <i class="fas fa-cloud-upload-alt"></i>
                    ارفع مشروع جديد
                </button>
            </section>

            <!-- نموذج رفع المشروع -->
            <section class="project-form" id="projectForm" style="display: none;">
                <div class="form-container">
                    <h3>إنشاء مشروع جديد</h3>
                    
                    <div class="input-group">
                        <label for="projectName">اسم المشروع:</label>
                        <input type="text" id="projectName" placeholder="أدخل اسم المشروع..." required>
                    </div>

                    <div class="input-group">
                        <label for="projectFiles">ملفات المشروع:</label>
                        <div class="file-upload-area" id="fileUploadArea">
                            <i class="fas fa-cloud-upload-alt upload-icon"></i>
                            <p>اسحب الملفات هنا أو اضغط لاختيار الملفات</p>
                            <input type="file" id="projectFiles" multiple style="display: none;">
                        </div>
                    </div>

                    <div class="files-list" id="filesList"></div>

                    <div class="form-actions">
                        <button class="cancel-btn" id="cancelBtn">إلغاء</button>
                        <button class="submit-btn" id="submitBtn">ارفع المشروع</button>
                    </div>
                </div>
            </section>

            <!-- صفحة المشروع -->
            <section class="project-view" id="projectView" style="display: none;">
                <div class="project-container">
                    <h3 id="projectTitle">مشروع تجريبي</h3>
                    
                    <div class="timer-section">
                        <div class="timer-display">
                            <i class="fas fa-hourglass-half"></i>
                            <span id="countdown">23:59:59</span>
                        </div>
                        <p>الوقت المتبقي قبل حذف المشروع</p>
                    </div>

                    <div class="project-link-section">
                        <label>رابط المشروع المباشر:</label>
                        <div class="link-container">
                            <input type="text" id="projectLink" value="" readonly>
                            <button class="copy-btn" id="copyBtn">
                                <i class="fas fa-copy"></i>
                                نسخ
                            </button>
                        </div>
                    </div>

                    <div class="project-files-section">
                        <h4>ملفات المشروع:</h4>
                        <div class="project-files-list" id="projectFilesList">
                            <!-- سيتم إضافة الملفات هنا ديناميكياً -->
                        </div>
                    </div>

                    <div class="project-actions">
                        <button class="back-btn" id="backBtn">
                            <i class="fas fa-arrow-right"></i>
                            العودة للرئيسية
                        </button>
                    </div>
                </div>
            </section>

            <!-- صفحة المشروع المحذوف -->
            <section class="deleted-project" id="deletedProject" style="display: none;">
                <div class="deleted-container">
                    <i class="fas fa-exclamation-triangle deleted-icon"></i>
                    <h3>المشروع غير موجود</h3>
                    <p>عذراً، هذا المشروع قد تم حذفه بعد انتهاء مدة الـ 24 ساعة.</p>
                    <button class="back-btn" id="backToHomeBtn">
                        <i class="fas fa-home"></i>
                        العودة للرئيسية
                    </button>
                </div>
            </section>
        </main>

        <!-- الفوتر -->
        <footer class="footer">
            <p>جميع الحقوق محفوظة 2025 للمطور <a href="https://adm-web.ct.ws" target="_blank">Aymen Dj Max</a></p>
        </footer>
    </div>

    <script>
        // متغيرات عامة
        let selectedFiles = [];
        let countdownTimer;
        let lastMouse = { x: 0, y: 0 };
        let uploadAbortController = null;

        // عند تحميل الصفحة
        document.addEventListener('DOMContentLoaded', function() {
            initializeEventListeners();
            updateFloatingIcons();
            
            // التحقق مما إذا كنا في صفحة مشروع
            const pathParts = window.location.pathname.split('/');
            if (pathParts[1] === 'project' && pathParts[2]) {
                loadProject(pathParts[2]);
            } else {
                showHomePage();
            }
        });

        // تهيئة مستمعي الأحداث - النسخة المصححة
        function initializeEventListeners() {
            console.log('Initializing event listeners...');
            
            // زر رفع مشروع جديد
            const newProjectBtn = document.getElementById('newProjectBtn');
            if (newProjectBtn) {
                newProjectBtn.addEventListener('click', showProjectForm);
            }

            // زر الإلغاء
            const cancelBtn = document.getElementById('cancelBtn');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', showHomePage);
            }

            // زر الإرسال
            const submitBtn = document.getElementById('submitBtn');
            if (submitBtn) {
                submitBtn.addEventListener('click', submitProject);
            }

            // منطقة رفع الملفات
            const fileUploadArea = document.getElementById('fileUploadArea');
            const projectFiles = document.getElementById('projectFiles');
            
            if (fileUploadArea && projectFiles) {
                fileUploadArea.addEventListener('click', () => projectFiles.click());
                fileUploadArea.addEventListener('dragover', handleDragOver);
                fileUploadArea.addEventListener('drop', handleFileDrop);
                fileUploadArea.addEventListener('dragleave', handleDragLeave);
                projectFiles.addEventListener('change', handleFileSelect);
            }

            // زر النسخ
            const copyBtn = document.getElementById('copyBtn');
            if (copyBtn) {
                copyBtn.addEventListener('click', copyProjectLink);
            }

            // أزرار العودة
            const backBtn = document.getElementById('backBtn');
            const backToHomeBtn = document.getElementById('backToHomeBtn');
            
            if (backBtn) {
                backBtn.addEventListener('click', showHomePage);
            }
            
            if (backToHomeBtn) {
                backToHomeBtn.addEventListener('click', showHomePage);
            }

            // تتبع حركة الماوس لتأثير الأيقونات العائمة
            document.addEventListener('mousemove', function(e) {
                lastMouse.x = e.clientX;
                lastMouse.y = e.clientY;
            });
        }

        // تحميل بيانات المشروع
        function loadProject(projectId) {
            fetch(`/api/project/${projectId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Project not found');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        showProjectView(data.project.name, projectId, data.project.file_urls, data.project.created_at);
                    } else {
                        showDeletedProject();
                    }
                })
                .catch(error => {
                    console.error('Error loading project:', error);
                    showDeletedProject();
                });
        }

        // عرض الصفحة الرئيسية
        function showHomePage() {
            hideAllSections();
            document.querySelector('.intro-section').style.display = 'block';
            document.querySelector('.upload-section').style.display = 'block';
            
            // إعادة تعيين النموذج
            resetForm();
            
            // تحديث عنوان الصفحة
            window.history.pushState({}, '', '/');
        }

        // عرض نموذج المشروع
        function showProjectForm() {
            hideAllSections();
            document.getElementById('projectForm').style.display = 'block';
            
            // التركيز على حقل اسم المشروع
            setTimeout(() => {
                const projectNameInput = document.getElementById('projectName');
                if (projectNameInput) {
                    projectNameInput.focus();
                }
            }, 100);
        }

        // عرض صفحة المشروع
        function showProjectView(projectName, projectId, fileUrls, createdAt) {
            hideAllSections();
            document.getElementById('projectView').style.display = 'block';
            
            // تحديث عنوان الصفحة
            window.history.pushState({}, '', `/project/${projectId}`);
            
            // تحديث عنوان المشروع
            document.getElementById('projectTitle').textContent = projectName || 'مشروع جديد';
            
            // عرض الملفات
            displayProjectFiles(fileUrls, createdAt);
            
            // بدء العد التنازلي
            startCountdown(createdAt);
            
            // إنشاء رابط المشروع
            const projectLink = `${window.location.origin}/project/${projectId}`;
            document.getElementById('projectLink').value = projectLink;
        }

        // عرض صفحة المشروع المحذوف
        function showDeletedProject() {
            hideAllSections();
            document.getElementById('deletedProject').style.display = 'block';
        }

        // إخفاء جميع الأقسام
        function hideAllSections() {
            const sections = [
                '.intro-section',
                '.upload-section',
                '#projectForm',
                '#projectView',
                '#deletedProject'
            ];
            
            sections.forEach(selector => {
                const element = document.querySelector(selector);
                if (element) {
                    element.style.display = 'none';
                }
            });
        }

        // التعامل مع سحب الملفات
        function handleDragOver(e) {
            e.preventDefault();
            e.stopPropagation();
            e.currentTarget.style.background = 'rgba(220, 53, 69, 0.1)';
        }

        // التعامل مع إسقاط الملفات
        function handleFileDrop(e) {
            e.preventDefault();
            e.stopPropagation();
            e.currentTarget.style.background = '#f8f9fa';
            
            const files = Array.from(e.dataTransfer.files);
            addFilesToList(files);
        }

        // التعامل مع مغادرة منطقة السحب
        function handleDragLeave(e) {
            e.preventDefault();
            e.stopPropagation();
            e.currentTarget.style.background = '#f8f9fa';
        }

        // التعامل مع اختيار الملفات
        function handleFileSelect(e) {
            const files = Array.from(e.target.files);
            addFilesToList(files);
        }

        // إضافة الملفات إلى القائمة
        function addFilesToList(files) {
            const maxFiles = 50; // حد أقصى لعدد الملفات
            
            if (selectedFiles.length + files.length > maxFiles) {
                alert(`يمكن رفع ${maxFiles} ملف كحد أقصى`);
                return;
            }
            
            let addedCount = 0;
            let skippedCount = 0;
            
            files.forEach(file => {
                // التحقق من عدم وجود نفس الملف
                const existingFile = selectedFiles.find(f => 
                    f.name === file.name && 
                    f.size === file.size && 
                    f.lastModified === file.lastModified
                );
                
                if (!existingFile) {
                    selectedFiles.push(file);
                    addedCount++;
                    console.log(`Added file: ${file.name} (${file.size} bytes, ${file.type})`);
                } else {
                    skippedCount++;
                    console.log(`Skipped duplicate file: ${file.name}`);
                }
            });
            
            if (skippedCount > 0) {
                alert(`تم تجاهل ${skippedCount} ملف مكرر`);
            }
            
            displayFilesList();
            
            console.log(`Files added: ${addedCount}, Total files: ${selectedFiles.length}`);
        }

        // عرض قائمة الملفات
        function displayFilesList() {
            const filesList = document.getElementById('filesList');
            if (!filesList) return;
            
            filesList.innerHTML = '';
            
            selectedFiles.forEach((file, index) => {
                const fileItem = createFileItem(file, index);
                filesList.appendChild(fileItem);
            });
        }

        // إنشاء عنصر ملف (آمن من XSS باستخدام textContent)
        function createFileItem(file, index) {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            
            const fileInfo = document.createElement('div');
            fileInfo.className = 'file-info';
            
            const fileIcon = document.createElement('i');
            fileIcon.className = getFileIcon(file.type, file.name) + ' file-icon';
            
            const fileDetails = document.createElement('div');
            fileDetails.className = 'file-details';
            
            const fileName = document.createElement('h4');
            fileName.textContent = file.name; // آمن من XSS
            
            const fileMeta = document.createElement('p');
            fileMeta.textContent = `${formatFileSize(file.size)} - ${file.type || 'نوع غير معروف'}`;
            
            fileDetails.appendChild(fileName);
            fileDetails.appendChild(fileMeta);
            fileInfo.appendChild(fileIcon);
            fileInfo.appendChild(fileDetails);
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-file-btn';
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
            deleteBtn.addEventListener('click', () => removeFile(index));
            
            fileItem.appendChild(fileInfo);
            fileItem.appendChild(deleteBtn);
            
            return fileItem;
        }

        // الحصول على أيقونة الملف (مع fallback للامتداد)
        function getFileIcon(fileType, fileName = '') {
            if (fileType) {
                if (fileType.startsWith('image/')) return 'fas fa-file-image';
                if (fileType.startsWith('video/')) return 'fas fa-file-video';
                if (fileType.startsWith('audio/')) return 'fas fa-file-audio';
                if (fileType.includes('pdf')) return 'fas fa-file-pdf';
                if (fileType.includes('word') || fileType.includes('document')) return 'fas fa-file-word';
                if (fileType.includes('excel') || fileType.includes('spreadsheet')) return 'fas fa-file-excel';
                if (fileType.includes('powerpoint') || fileType.includes('presentation')) return 'fas fa-file-powerpoint';
                if (fileType.includes('zip') || fileType.includes('rar') || fileType.includes('compressed')) return 'fas fa-file-archive';
                if (fileType.includes('text')) return 'fas fa-file-alt';
            }
            
            // Fallback: استخدام امتداد الملف
            const ext = fileName.split('.').pop().toLowerCase();
            
            if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'tif'].includes(ext)) return 'fas fa-file-image';
            if (['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'm4v', '3gp', 'mpeg', 'mpg'].includes(ext)) return 'fas fa-file-video';
            if (['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'mid', 'midi'].includes(ext)) return 'fas fa-file-audio';
            if (ext === 'pdf') return 'fas fa-file-pdf';
            if (['doc', 'docx', 'docm', 'dot', 'dotx'].includes(ext)) return 'fas fa-file-word';
            if (['xls', 'xlsx', 'xlsm', 'xlt', 'xltx', 'csv'].includes(ext)) return 'fas fa-file-excel';
            if (['ppt', 'pptx', 'pptm', 'pot', 'potx', 'pps', 'ppsx'].includes(ext)) return 'fas fa-file-powerpoint';
            if (['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso'].includes(ext)) return 'fas fa-file-archive';
            if (['txt', 'rtf', 'md', 'tex', 'log'].includes(ext)) return 'fas fa-file-alt';
            if (['html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 
                'php', 'rb', 'go', 'swift', 'kt', 'rs', 'sh', 'bat', 'ps1', 'vb', 'cs', 'sql', 'xml', 
                'json', 'yaml', 'yml', 'ini', 'cfg', 'conf'].includes(ext)) return 'fas fa-file-code';
            if (['exe', 'msi', 'apk', 'app', 'deb', 'rpm', 'dmg', 'pkg'].includes(ext)) return 'fas fa-cog';
            if (['ttf', 'otf', 'woff', 'woff2', 'eot'].includes(ext)) return 'fas fa-font';
            if (['psd', 'ai', 'eps', 'sketch', 'fig', 'xd'].includes(ext)) return 'fas fa-paint-brush';
            if (['db', 'sqlite', 'mdb', 'accdb', 'dbf'].includes(ext)) return 'fas fa-database';
            if (['bak', 'tmp', 'temp', 'backup'].includes(ext)) return 'fas fa-history';
            if (ext === 'torrent') return 'fas fa-magnet';
            if (['vhd', 'vdi', 'vmware', 'ova', 'ovf'].includes(ext)) return 'fas fa-hdd';
            if (['stl', 'obj', 'gcode', 'svg', 'dxf'].includes(ext)) return 'fas fa-cube';
            if (['pem', 'key', 'crt', 'cer', 'pfx', 'p12'].includes(ext)) return 'fas fa-key';
            
            return 'fas fa-file';
        }

        // تنسيق حجم الملف
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 بايت';
            
            const k = 1024;
            const sizes = ['بايت', 'كيلوبايت', 'ميجابايت', 'جيجابايت'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // حذف ملف
        function removeFile(index) {
            selectedFiles.splice(index, 1);
            displayFilesList();
        }

        // إرسال المشروع (النسخة المحسنة)
        function submitProject() {
            const projectName = document.getElementById('projectName').value.trim();
            
            // التحقق من صحة البيانات
            if (!projectName) {
                alert('يرجى إدخال اسم المشروع');
                return;
            }
            
            if (selectedFiles.length === 0) {
                alert('يرجى اختيار ملف واحد على الأقل');
                return;
            }
            
            // التحقق من أحجام الملفات
            const maxFileSize = 50 * 1024 * 1024; // 50 MB
            const maxTotalSize = 200 * 1024 * 1024; // 200 MB
            let totalSize = 0;
            
            for (let file of selectedFiles) {
                if (file.size > maxFileSize) {
                    alert(`الملف ${file.name} كبير جداً (الحد الأقصى 50 MB)`);
                    return;
                }
                totalSize += file.size;
            }
            
            if (totalSize > maxTotalSize) {
                alert('حجم المشروع كبير جداً (الحد الأقصى 200 MB)');
                return;
            }
            
            console.log(`Submitting project: ${projectName}`);
            console.log(`Files count: ${selectedFiles.length}`);
            console.log(`Total size: ${(totalSize / 1024 / 1024).toFixed(2)} MB`);
            
            // بدء عملية الرفع
            showLoadingAnimation();
            
            // إنشاء FormData بطريقة صحيحة
            const formData = new FormData();
            formData.append('projectName', projectName);
            
            // إضافة الملفات بطريقة صحيحة - استخدام نفس المفتاح لجميع الملفات
            selectedFiles.forEach((file, index) => {
                console.log(`Adding file ${index}: ${file.name} (${file.size} bytes, ${file.type})`);
                // استخدام نفس المفتاح 'files' لجميع الملفات
                formData.append('files', file, file.name);
            });
            
            // إعدادات الطلب مع timeout محسن
            uploadAbortController = new AbortController();
            const signal = uploadAbortController.signal;
            
            const requestOptions = {
                method: 'POST',
                body: formData,
                signal: signal
            };
            
            // إرسال الطلب مع معالجة أفضل للأخطاء
            fetch('/upload', requestOptions)
                .then(response => {
                    console.log(`Response status: ${response.status}`);
                    
                    // معالجة أخطاء HTTP مختلفة
                    if (!response.ok) {
                        if (response.status === 413) {
                            throw new Error('حجم الملفات كبير جداً');
                        } else if (response.status === 500) {
                            throw new Error('خطأ في الخادم');
                        } else if (response.status === 400) {
                            throw new Error('بيانات غير صحيحة');
                        } else {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                    }
                    
                    return response.json();
                })
                .then(data => {
                    hideLoadingAnimation();
                    console.log('Upload response:', data);
                    
                    if (data.success) {
                        // عرض تحذير إذا كان هناك ملفات فشلت
                        if (data.warning) {
                            alert(`تم رفع المشروع مع تحذير: ${data.warning}`);
                        }
                        
                        // إعادة توجيه إلى صفحة المشروع
                        console.log(`Redirecting to project: ${data.project_id}`);
                        window.location.href = `/project/${data.project_id}`;
                    } else {
                        alert(`فشل رفع المشروع: ${data.message || 'خطأ غير معروف'}`);
                    }
                })
                .catch(error => {
                    hideLoadingAnimation();
                    console.error('Upload error:', error);
                    
                    let errorMessage = 'حدث خطأ أثناء رفع المشروع.';
                    
                    if (error.name === 'AbortError') {
                        errorMessage = 'تم إلغاء عملية الرفع.';
                    } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
                        errorMessage = 'مشكلة في الاتصال. تحقق من الإنترنت.';
                    } else if (error.message.includes('كبير جداً')) {
                        errorMessage = error.message;
                    } else if (error.message.includes('خادم')) {
                        errorMessage = 'خطأ في الخادم. حاول مرة أخرى لاحقاً.';
                    } else {
                        errorMessage = `${errorMessage} التفاصيل: ${error.message}`;
                    }
                    
                    alert(errorMessage);
                });
        }

        // عرض رسوم متحركة للتحميل
        function showLoadingAnimation() {
            const submitBtn = document.getElementById('submitBtn');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع...';
                submitBtn.disabled = true;
                submitBtn.style.opacity = '0.7';
                submitBtn.style.cursor = 'not-allowed';
            }
            
            // منع إغلاق النموذج أثناء الرفع
            const cancelBtn = document.getElementById('cancelBtn');
            if (cancelBtn) {
                cancelBtn.disabled = true;
                cancelBtn.style.opacity = '0.5';
                cancelBtn.style.cursor = 'not-allowed';
            }
            
            // منع المستخدم من إغلاق الصفحة أثناء الرفع
            window.addEventListener('beforeunload', preventClose);
        }

        // إخفاء رسوم متحركة للتحميل
        function hideLoadingAnimation() {
            const submitBtn = document.getElementById('submitBtn');
            if (submitBtn) {
                submitBtn.innerHTML = 'ارفع المشروع';
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1';
                submitBtn.style.cursor = 'pointer';
            }
            
            const cancelBtn = document.getElementById('cancelBtn');
            if (cancelBtn) {
                cancelBtn.disabled = false;
                cancelBtn.style.opacity = '1';
                cancelBtn.style.cursor = 'pointer';
            }
            
            // إزالة منع إغلاق الصفحة
            window.removeEventListener('beforeunload', preventClose);
        }

        // دالة منع إغلاق الصفحة أثناء الرفع
        function preventClose(e) {
            e.preventDefault();
            e.returnValue = 'عملية رفع الملفات جارية. هل تريد المغادرة؟';
            return 'عملية رفع الملفات جارية. هل تريد المغادرة؟';
        }

        // عرض ملفات المشروع
        function displayProjectFiles(fileUrls, createdAt) {
            const projectFilesList = document.getElementById('projectFilesList');
            if (!projectFilesList) return;
            
            projectFilesList.innerHTML = '';
            
            for (const [filename, fileUrl] of Object.entries(fileUrls)) {
                const fileItem = createProjectFileItem(filename, fileUrl, createdAt);
                projectFilesList.appendChild(fileItem);
            }
        }

        // إنشاء عنصر ملف المشروع (آمن من XSS)
        function createProjectFileItem(filename, fileUrl, createdAt) {
            const fileItem = document.createElement('div');
            fileItem.className = 'project-file-item';
            
            const fileInfo = document.createElement('div');
            fileInfo.className = 'project-file-info';
            
            const fileIcon = document.createElement('i');
            fileIcon.className = getFileIconByFilename(filename) + ' project-file-icon';
            
            const fileDetails = document.createElement('div');
            fileDetails.className = 'project-file-details';
            
            const fileName = document.createElement('h5');
            fileName.textContent = filename; // آمن من XSS
            
            const fileMeta = document.createElement('p');
            fileMeta.textContent = `تم الرفع: ${parseCreatedAt(createdAt).toLocaleString('ar-SA')}`;
            
            fileDetails.appendChild(fileName);
            fileDetails.appendChild(fileMeta);
            fileInfo.appendChild(fileIcon);
            fileInfo.appendChild(fileDetails);
            
            const downloadLink = document.createElement('a');
            downloadLink.className = 'download-btn';
            downloadLink.href = fileUrl;
            downloadLink.download = filename;
            downloadLink.innerHTML = '<i class="fas fa-download"></i> تحميل';
            
            fileItem.appendChild(fileInfo);
            fileItem.appendChild(downloadLink);
            
            return fileItem;
        }

        // الحصول على أيقونة الملف بناءً على اسم الملف
        function getFileIconByFilename(filename) {
            const ext = filename.split('.').pop().toLowerCase();
            
            if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'tif'].includes(ext)) return 'fas fa-file-image';
            if (['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'm4v', '3gp', 'mpeg', 'mpg'].includes(ext)) return 'fas fa-file-video';
            if (['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'mid', 'midi'].includes(ext)) return 'fas fa-file-audio';
            if (ext === 'pdf') return 'fas fa-file-pdf';
            if (['doc', 'docx', 'docm', 'dot', 'dotx'].includes(ext)) return 'fas fa-file-word';
            if (['xls', 'xlsx', 'xlsm', 'xlt', 'xltx', 'csv'].includes(ext)) return 'fas fa-file-excel';
            if (['ppt', 'pptx', 'pptm', 'pot', 'potx', 'pps', 'ppsx'].includes(ext)) return 'fas fa-file-powerpoint';
            if (['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso'].includes(ext)) return 'fas fa-file-archive';
            if (['txt', 'rtf', 'md', 'tex', 'log'].includes(ext)) return 'fas fa-file-alt';
            if (['html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 
                'php', 'rb', 'go', 'swift', 'kt', 'rs', 'sh', 'bat', 'ps1', 'vb', 'cs', 'sql', 'xml', 
                'json', 'yaml', 'yml', 'ini', 'cfg', 'conf'].includes(ext)) return 'fas fa-file-code';
            if (['exe', 'msi', 'apk', 'app', 'deb', 'rpm', 'dmg', 'pkg'].includes(ext)) return 'fas fa-cog';
            if (['ttf', 'otf', 'woff', 'woff2', 'eot'].includes(ext)) return 'fas fa-font';
            if (['psd', 'ai', 'eps', 'sketch', 'fig', 'xd'].includes(ext)) return 'fas fa-paint-brush';
            if (['db', 'sqlite', 'mdb', 'accdb', 'dbf'].includes(ext)) return 'fas fa-database';
            if (['bak', 'tmp', 'temp', 'backup'].includes(ext)) return 'fas fa-history';
            if (ext === 'torrent') return 'fas fa-magnet';
            if (['vhd', 'vdi', 'vmware', 'ova', 'ovf'].includes(ext)) return 'fas fa-hdd';
            if (['stl', 'obj', 'gcode', 'svg', 'dxf'].includes(ext)) return 'fas fa-cube';
            if (['pem', 'key', 'crt', 'cer', 'pfx', 'p12'].includes(ext)) return 'fas fa-key';
            
            return 'fas fa-file';
        }

        // تحليل التاريخ من السيرفر (مع معالجة التوقيت العالمي)
        function parseCreatedAt(createdAt) {
            // إذا كان التاريخ يحتوي على Z (توقيت عالمي)
            if (createdAt.includes('Z')) {
                return new Date(createdAt);
            }
            
            // إذا لم يكن هناك Z، نضيفها لفرض التوقيت العالمي
            const d = new Date(createdAt + 'Z');
            if (!isNaN(d)) return d;
            
            // إذا فشل ذلك، نعود إلى التاريخ الأصلي
            return new Date(createdAt);
        }

        // بدء العد التنازلي
        function startCountdown(createdAt) {
            const createdTime = parseCreatedAt(createdAt).getTime();
            const expiryTime = createdTime + (24 * 60 * 60 * 1000); // 24 ساعة
            
            const countdownElement = document.getElementById('countdown');
            
            if (countdownTimer) {
                clearInterval(countdownTimer);
            }
            
            countdownTimer = setInterval(() => {
                const now = new Date().getTime();
                const distance = expiryTime - now;
                
                if (distance < 0) {
                    clearInterval(countdownTimer);
                    countdownElement.textContent = "00:00:00";
                    showDeletedProject();
                    return;
                }
                
                const hours = Math.floor(distance / (1000 * 60 * 60));
                const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                
                const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                
                if (countdownElement) {
                    countdownElement.textContent = timeString;
                }
            }, 1000);
        }

        // نسخ رابط المشروع باستخدام Clipboard API مع fallback
        async function copyProjectLink() {
            const projectLinkInput = document.getElementById('projectLink');
            if (!projectLinkInput) return;
            
            const text = projectLinkInput.value;
            const copyBtn = document.getElementById('copyBtn');
            
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text);
                } else {
                    // Fallback لبعض المتصفحات القديمة
                    projectLinkInput.select();
                    document.execCommand('copy');
                }
                
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check"></i> تم النسخ';
                copyBtn.style.background = '#28a745';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                    copyBtn.style.background = '#dc3545';
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
                alert('فشل النسخ، الرجاء النسخ يدوياً.');
            }
        }

        // إعادة تعيين النموذج
        function resetForm() {
            const projectName = document.getElementById('projectName');
            const projectFiles = document.getElementById('projectFiles');
            
            if (projectName) projectName.value = '';
            if (projectFiles) projectFiles.value = '';
            
            selectedFiles = [];
            displayFilesList();
            
            if (countdownTimer) {
                clearInterval(countdownTimer);
            }
            
            // إلغاء أي طلب جاري
            if (uploadAbortController) {
                uploadAbortController.abort();
                uploadAbortController = null;
            }
        }

        // تأثيرات إضافية للتفاعل - تحسين أداء الأيقونات العائمة
        function updateFloatingIcons() {
            const floatingIcons = document.querySelectorAll('.floating-icon');
            
            floatingIcons.forEach((icon, index) {
                const speed = (index + 1) * 0.00008;
                const x = (lastMouse.x - window.innerWidth/2) * speed;
                const y = (lastMouse.y - window.innerHeight/2) * speed;
                
                icon.style.transform = `translate(${x}px, ${y}px)`;
            });
            
            requestAnimationFrame(updateFloatingIcons);
        }

        // تأثير التمرير السلس
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });

        // تأثيرات الرسوم المتحركة عند التمرير
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, observerOptions);

        // مراقبة العناصر للرسوم المتحركة
        document.addEventListener('DOMContentLoaded', function() {
            const animatedElements = document.querySelectorAll('.feature-card, .step, .form-container, .project-container');
            
            animatedElements.forEach(el => {
                el.style.opacity = '0';
                el.style.transform = 'translateY(30px)';
                el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                observer.observe(el);
            });
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
