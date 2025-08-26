# main.py
import os
import uuid
import json
import datetime
from datetime import timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from io import BytesIO
import threading
import time
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cloud24-secret-key-2025")

# بيانات Supabase
SUPABASE_URL = "https://gehboaskzdhotdyzzjae.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdlaGJvYXNremRob3RkeXp6amFlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYxNzMyMTYsImV4cCI6MjA3MTc0OTIxNn0.r0Z2f3xxnM9fv_oQDmOZV5rQCmaBm7OC885WQupmQ4o"
BUCKET_NAME = "my-bucket"

# تهيئة Supabase Client
def get_supabase_client():
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None

# قاعدة بيانات مؤقتة (في بيئة حقيقية استخدم قاعدة بيانات حقيقية)
projects_db = {}
files_db = {}

# HTML template (نفس محتوى index.html مع تعديلات طفيفة)
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
                            <span class="step-number">2</span>
                            <p>أدخل اسم المشروع واختر الملفات</p>
                        </div>
                        <div class="step">
                            <span class="step-number">3</span>
                            <p>اضغط "ارفع المشروع" واحصل على الرابط</p>
                        </div>
                        <div class="step">
                            <span class="step-number">4</span>
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
                            <input type="file" id="projectFiles" multiple accept="*/*" style="display: none;">
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

        // عند تحميل الصفحة
        document.addEventListener('DOMContentLoaded', function() {
            initializeEventListeners();
            showHomePage();
        });

        // تهيئة مستمعي الأحداث
        function initializeEventListeners() {
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
        }

        // عرض الصفحة الرئيسية
        function showHomePage() {
            hideAllSections();
            document.querySelector('.intro-section').style.display = 'block';
            document.querySelector('.upload-section').style.display = 'block';
            
            // إعادة تعيين النموذج
            resetForm();
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
        function showProjectView(projectName, projectId) {
            hideAllSections();
            document.getElementById('projectView').style.display = 'block';
            
            // تحديث عنوان المشروع
            document.getElementById('projectTitle').textContent = projectName || 'مشروع جديد';
            
            // عرض الملفات
            displayProjectFiles();
            
            // بدء العد التنازلي
            startCountdown();
            
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

        // التعامل مع اختيار الملفات
        function handleFileSelect(e) {
            const files = Array.from(e.target.files);
            addFilesToList(files);
        }

        // إضافة الملفات إلى القائمة
        function addFilesToList(files) {
            files.forEach(file => {
                if (!selectedFiles.find(f => f.name === file.name && f.size === file.size)) {
                    selectedFiles.push(file);
                }
            });
            
            displayFilesList();
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

        // إنشاء عنصر ملف
        function createFileItem(file, index) {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            
            const fileIcon = getFileIcon(file.type);
            const fileSize = formatFileSize(file.size);
            
            fileItem.innerHTML = `
                <div class="file-info">
                    <i class="${fileIcon} file-icon"></i>
                    <div class="file-details">
                        <h4>${file.name}</h4>
                        <p>${fileSize} - ${file.type || 'نوع غير معروف'}</p>
                    </div>
                </div>
                <button class="delete-file-btn" onclick="removeFile(${index})">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            
            return fileItem;
        }

        // الحصول على أيقونة الملف
        function getFileIcon(fileType) {
            if (!fileType) return 'fas fa-file';
            
            if (fileType.startsWith('image/')) return 'fas fa-file-image';
            if (fileType.startsWith('video/')) return 'fas fa-file-video';
            if (fileType.startsWith('audio/')) return 'fas fa-file-audio';
            if (fileType.includes('pdf')) return 'fas fa-file-pdf';
            if (fileType.includes('word') || fileType.includes('document')) return 'fas fa-file-word';
            if (fileType.includes('excel') || fileType.includes('spreadsheet')) return 'fas fa-file-excel';
            if (fileType.includes('powerpoint') || fileType.includes('presentation')) return 'fas fa-file-powerpoint';
            if (fileType.includes('zip') || fileType.includes('rar') || fileType.includes('compressed')) return 'fas fa-file-archive';
            if (fileType.includes('text')) return 'fas fa-file-alt';
            
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

        // إرسال المشروع
        function submitProject() {
            const projectName = document.getElementById('projectName').value.trim();
            
            if (!projectName) {
                alert('يرجى إدخال اسم المشروع');
                return;
            }
            
            if (selectedFiles.length === 0) {
                alert('يرجى اختيار ملف واحد على الأقل');
                return;
            }
            
            // محاكاة رفع الملفات
            showLoadingAnimation();
            
            // إنشاء FormData وإرسال الملفات إلى الخادم
            const formData = new FormData();
            formData.append('projectName', projectName);
            
            selectedFiles.forEach((file, index) => {
                formData.append(`file${index}`, file);
            });
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                hideLoadingAnimation();
                if (data.success) {
                    showProjectView(projectName, data.project_id);
                } else {
                    alert('حدث خطأ أثناء رفع المشروع: ' + data.message);
                }
            })
            .catch(error => {
                hideLoadingAnimation();
                alert('حدث خطأ أثناء رفع المشروع. يرجى المحاولة مرة أخرى.');
                console.error('Error:', error);
            });
        }

        // عرض رسوم متحركة للتحميل
        function showLoadingAnimation() {
            const submitBtn = document.getElementById('submitBtn');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع...';
                submitBtn.disabled = true;
            }
        }

        // إخفاء رسوم متحركة للتحميل
        function hideLoadingAnimation() {
            const submitBtn = document.getElementById('submitBtn');
            if (submitBtn) {
                submitBtn.innerHTML = 'ارفع المشروع';
                submitBtn.disabled = false;
            }
        }

        // عرض ملفات المشروع
        function displayProjectFiles() {
            const projectFilesList = document.getElementById('projectFilesList');
            if (!projectFilesList) return;
            
            projectFilesList.innerHTML = '';
            
            selectedFiles.forEach(file => {
                const fileItem = createProjectFileItem(file);
                projectFilesList.appendChild(fileItem);
            });
        }

        // إنشاء عنصر ملف المشروع
        function createProjectFileItem(file) {
            const fileItem = document.createElement('div');
            fileItem.className = 'project-file-item';
            
            const fileIcon = getFileIcon(file.type);
            const fileSize = formatFileSize(file.size);
            
            fileItem.innerHTML = `
                <div class="project-file-info">
                    <i class="${fileIcon} project-file-icon"></i>
                    <div class="project-file-details">
                        <h5>${file.name}</h5>
                        <p>${fileSize} - ${file.type || 'نوع غير معروف'}</p>
                    </div>
                </div>
                <button class="download-btn" onclick="downloadFile('${file.name}')">
                    <i class="fas fa-download"></i>
                    تحميل
                </button>
            `;
            
            return fileItem;
        }

        // تحميل ملف (وهمي)
        function downloadFile(fileName) {
            alert(`سيتم تحميل الملف: ${fileName}`);
        }

        // بدء العد التنازلي
        function startCountdown() {
            // 24 ساعة بالثواني
            let timeLeft = 24 * 60 * 60;
            
            const countdownElement = document.getElementById('countdown');
            
            if (countdownTimer) {
                clearInterval(countdownTimer);
            }
            
            countdownTimer = setInterval(() => {
                const hours = Math.floor(timeLeft / 3600);
                const minutes = Math.floor((timeLeft % 3600) / 60);
                const seconds = timeLeft % 60;
                
                const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                
                if (countdownElement) {
                    countdownElement.textContent = timeString;
                }
                
                timeLeft--;
                
                if (timeLeft < 0) {
                    clearInterval(countdownTimer);
                    showDeletedProject();
                }
            }, 1000);
        }

        // نسخ رابط المشروع
        function copyProjectLink() {
            const projectLink = document.getElementById('projectLink');
            if (projectLink) {
                projectLink.select();
                document.execCommand('copy');
                
                const copyBtn = document.getElementById('copyBtn');
                const originalText = copyBtn.innerHTML;
                
                copyBtn.innerHTML = '<i class="fas fa-check"></i> تم النسخ';
                copyBtn.style.background = '#28a745';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                    copyBtn.style.background = '#dc3545';
                }, 2000);
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
        }

        // تأثيرات إضافية للتفاعل
        document.addEventListener('mousemove', function(e) {
            const floatingIcons = document.querySelectorAll('.floating-icon');
            
            floatingIcons.forEach((icon, index) => {
                const speed = (index + 1) * 0.0001;
                const x = (e.clientX * speed);
                const y = (e.clientY * speed);
                
                icon.style.transform += ` translate(${x}px, ${y}px)`;
            });
        });

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

# وظائف مساعدة لإدارة المشاريع والملفات مع Supabase
def upload_file_to_supabase(supabase, file_data, file_name, project_id):
    """رفع ملف إلى Supabase Storage"""
    try:
        # إنشاء مسار الملف باستخدام معرف المشروع
        file_path = f"{project_id}/{file_name}"
        
        # رفع الملف إلى Supabase
        res = supabase.storage.from_(BUCKET_NAME).upload(file_path, file_data)
        return True
    except Exception as e:
        print(f"Error uploading file to Supabase: {e}")
        return False

def get_file_url(project_id, file_name):
    """الحصول على رابط التحميل من Supabase"""
    file_path = f"{project_id}/{file_name}"
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"

def download_file_from_supabase(supabase, project_id, file_name):
    """تحميل ملف من Supabase Storage"""
    try:
        file_path = f"{project_id}/{file_name}"
        downloaded = supabase.storage.from_(BUCKET_NAME).download(file_path)
        return downloaded
    except Exception as e:
        print(f"Error downloading file from Supabase: {e}")
        return None

def delete_project_files(supabase, project_id):
    """حذف جميع ملفات المشروع من Supabase"""
    try:
        # الحصول على قائمة جميع الملفات في مجلد المشروع
        file_list = supabase.storage.from_(BUCKET_NAME).list(project_id)
        
        if file_list:
            # إنشاء قائمة بمسارات الملفات للحذف
            files_to_delete = [f"{project_id}/{file['name']}" for file in file_list]
            
            # حذف جميع الملفات
            res = supabase.storage.from_(BUCKET_NAME).remove(files_to_delete)
            return True
    except Exception as e:
        print(f"Error deleting project files from Supabase: {e}")
    
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
                supabase = get_supabase_client()
                if supabase and project_id in projects_db:
                    if delete_project_files(supabase, project_id):
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
        project_name = request.form.get('projectName')
        if not project_name:
            return jsonify({'success': False, 'message': 'اسم المشروع مطلوب'})
        
        # الحصول على عميل Supabase
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'success': False, 'message': 'خطأ في الاتصال بخدمة التخزين'})
        
        # إنشاء معرف فريد للمشروع
        project_id = str(uuid.uuid4())
        
        # رفع الملفات
        file_ids = {}
        for key in request.files:
            file = request.files[key]
            if file.filename:
                try:
                    success = upload_file_to_supabase(supabase, file.read(), file.filename, project_id)
                    if success:
                        file_ids[file.filename] = get_file_url(project_id, file.filename)
                except Exception as e:
                    print(f"Error uploading file {file.filename}: {e}")
                    return jsonify({'success': False, 'message': f'حدث خطأ أثناء رفع الملف {file.filename}'})
        
        # حفظ بيانات المشروع
        projects_db[project_id] = {
            'name': project_name,
            'file_urls': file_ids,
            'created_at': datetime.datetime.now()
        }
        
        return jsonify({'success': True, 'project_id': project_id})
    
    except Exception as e:
        print(f"Error uploading project: {e}")
        return jsonify({'success': False, 'message': 'حدث خطأ أثناء رفع المشروع'})

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
    hours, remainder = divmod(time_remaining.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    
    # إنشاء قائمة الملفات
    files_list = ""
    for filename, file_url in project['file_urls'].items():
        file_icon = "fas fa-file"
        if any(ext in filename.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            file_icon = "fas fa-file-image"
        elif any(ext in filename.lower() for ext in ['.mp4', '.avi', '.mov']):
            file_icon = "fas fa-file-video"
        elif any(ext in filename.lower() for ext in ['.mp3', '.wav']):
            file_icon = "fas fa-file-audio"
        elif '.pdf' in filename.lower():
            file_icon = "fas fa-file-pdf"
        elif any(ext in filename.lower() for ext in ['.doc', '.docx']):
            file_icon = "fas fa-file-word"
        elif any(ext in filename.lower() for ext in ['.xls', '.xlsx']):
            file_icon = "fas fa-file-excel"
        elif any(ext in filename.lower() for ext in ['.zip', '.rar']):
            file_icon = "fas fa-file-archive"
        
        files_list += f"""
        <div class="project-file-item">
            <div class="project-file-info">
                <i class="{file_icon} project-file-icon"></i>
                <div class="project-file-details">
                    <h5>{filename}</h5>
                    <p>تم الرفع: {created_at.strftime('%Y-%m-%d %H:%M')}</p>
                </div>
            </div>
            <a class="download-btn" href="/download/{project_id}/{filename}">
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

@app.route('/download/<project_id>/<filename>')
def download_file(project_id, filename):
    if project_id not in projects_db:
        return "المشروع غير موجود", 404
    
    project = projects_db[project_id]
    if filename not in project['file_urls']:
        return "الملف غير موجود", 404
    
    try:
        supabase = get_supabase_client()
        file_content = download_file_from_supabase(supabase, project_id, filename)
        
        if file_content:
            return send_file(
                BytesIO(file_content),
                as_attachment=True,
                download_name=filename
            )
        else:
            return "حدث خطأ أثناء تحميل الملف", 500
    except Exception as e:
        print(f"Error downloading file: {e}")
        return "حدث خطأ أثناء تحميل الملف", 500

@app.route('/ping')
def ping():
    return "pong", 200

@app.errorhandler(404)
def not_found(error):
    return "الصفحة غير موجودة", 404

@app.errorhandler(500)
def internal_error(error):
    return "حدث خطأ داخلي في الخادم", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
