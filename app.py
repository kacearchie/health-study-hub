import os
import json
import glob
import random
import hashlib
import datetime
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['DEBUG'] = True

# ============================================================
# DIRECTORIES
# ============================================================
DATA_DIR = 'data'
NOTES_DIR = os.path.join(DATA_DIR, 'notes')
QUIZZES_DIR = os.path.join(DATA_DIR, 'quizzes')
USERS_DIR = os.path.join(DATA_DIR, 'users')

for dir_path in [DATA_DIR, NOTES_DIR, QUIZZES_DIR, USERS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"✅ Created: {dir_path}")

print(f"📁 Current directory: {os.getcwd()}")
print(f"📁 Templates exist: {os.path.exists('templates')}")
print(f"📁 Notes folder exists: {os.path.exists(NOTES_DIR)}")
print(f"📁 Quizzes folder exists: {os.path.exists(QUIZZES_DIR)}")
print(f"📁 Users folder exists: {os.path.exists(USERS_DIR)}")

# ============================================================
# OPENAI SETUP
# ============================================================
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
USE_AI = OPENAI_API_KEY and OPENAI_API_KEY != '' and OPENAI_API_KEY != 'your-openai-api-key-here'

if USE_AI:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        print("✅ OpenAI loaded")
    except:
        print("⚠️ OpenAI not installed")
        USE_AI = False

# ============================================================
# AI POWERED QUIZ GRADING
# ============================================================
def ai_grade_question(question_text, user_answer_text, correct_answer_text, options):
    """
    Use AI to intelligently grade a question.
    Returns: (is_correct, explanation, confidence)
    """
    if not USE_AI:
        # Fallback to text comparison if AI is not available
        return (user_answer_text.strip().lower() == correct_answer_text.strip().lower(), 
                "Fallback: Text comparison", 0.5)
    
    # If user didn't answer
    if not user_answer_text or user_answer_text == '' or user_answer_text == '-1':
        return (False, "No answer provided", 0)
    
    try:
        prompt = f"""Grade this multiple choice question answer:

Question: {question_text}

Options:
{chr(10).join([f"{chr(65+i)}. {opt}" for i, opt in enumerate(options)])}

Student selected: {user_answer_text}

Correct answer according to the answer key: {correct_answer_text}

Task: Determine if the student's answer should be considered CORRECT or WRONG.
Consider:
1. If the student selected the exact correct answer → CORRECT
2. If the student selected a close/similar answer (synonyms, different wording but same meaning) → CORRECT
3. If the student selected a clearly different answer → WRONG
4. If the question has multiple valid interpretations, be generous

Return ONLY valid JSON:
{{
    "is_correct": true/false,
    "explanation": "Brief explanation of why",
    "confidence": 0.0-1.0
}}"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator grading quiz answers. Be fair and intelligent in your assessment. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        result_text = response['choices'][0]['message']['content']
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0]
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0]
        result_text = result_text.strip()
        
        result = json.loads(result_text)
        return (result.get('is_correct', False), 
                result.get('explanation', ''), 
                result.get('confidence', 0.5))
        
    except Exception as e:
        print(f"AI Grading Error: {e}")
        # Fallback to text comparison
        return (user_answer_text.strip().lower() == correct_answer_text.strip().lower(), 
                "AI fallback: Text comparison", 0.5)

# ============================================================
# USER MANAGEMENT
# ============================================================
def get_user_file(username):
    return os.path.join(USERS_DIR, f"{username}.json")

def load_user(username):
    try:
        with open(get_user_file(username), 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def save_user(username, data):
    try:
        with open(get_user_file(username), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving user {username}: {e}")
        return False

def user_exists(username):
    return os.path.exists(get_user_file(username))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ============================================================
# CONTENT LOADING
# ============================================================
note_cache = {}
quiz_cache = {}

def load_note(filename):
    if filename in note_cache:
        return note_cache[filename]
    filepath = os.path.join(NOTES_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            note_cache[filename] = data
            return data
    except:
        return None

def load_quiz(filename):
    if filename in quiz_cache:
        return quiz_cache[filename]
    filepath = os.path.join(QUIZZES_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            quiz_cache[filename] = data
            return data
    except:
        return None

def get_all_notes():
    files = glob.glob(os.path.join(NOTES_DIR, '*.json'))
    return [os.path.basename(f) for f in files]

def get_all_quizzes():
    files = glob.glob(os.path.join(QUIZZES_DIR, '*.json'))
    return [os.path.basename(f) for f in files]

def get_note_title(filename):
    name = filename.replace('.json', '')
    title = name.replace('_', ' ')
    words = title.split()
    formatted = []
    for w in words:
        if w.lower() in ['and', 'of', 'the', 'for', 'with', 'in', 'on', 'at']:
            formatted.append(w.lower())
        else:
            formatted.append(w.capitalize())
    return ' '.join(formatted)

def categorize_notes():
    all_notes = get_all_notes()
    categories = {}
    for note in all_notes:
        note_lower = note.lower()
        if 'inorganic_chemistry' in note_lower or 'inorganic' in note_lower:
            cat = 'Inorganic Chemistry'
        elif 'organic_chemistry' in note_lower or 'organic' in note_lower or 'alcohols' in note_lower or 'carbonyl' in note_lower or 'amines' in note_lower or 'amides' in note_lower:
            cat = 'Organic Chemistry'
        elif 'anatomy' in note_lower:
            cat = 'Anatomy'
        elif 'physiology' in note_lower:
            cat = 'Physiology'
        elif 'biochemistry' in note_lower:
            cat = 'Biochemistry'
        else:
            cat = 'General'
        
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'filename': note,
            'title': get_note_title(note)
        })
    return categories

def extract_questions_from_data(data):
    questions = []
    if not data:
        return questions
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if 'questions' in data and isinstance(data['questions'], list):
            return data['questions']
        if 'quiz' in data and isinstance(data['quiz'], list):
            return data['quiz']
        if 'mcq_questions' in data and isinstance(data['mcq_questions'], list):
            return data['mcq_questions']
        if 'content' in data and isinstance(data['content'], list):
            for item in data['content']:
                if isinstance(item, dict):
                    if 'questions' in item and isinstance(item['questions'], list):
                        return item['questions']
                    if 'quiz' in item and isinstance(item['quiz'], list):
                        return item['questions']
                    if item.get('type') == 'quiz' and 'questions' in item:
                        return item['questions']
    return questions

def get_correct_answer(q):
    """Get the correct answer from a question, supporting both 'answer' and 'correct_answer' keys"""
    if 'correct_answer' in q:
        return q['correct_answer']
    elif 'answer' in q:
        return q['answer']
    return None

def get_explanation(q):
    """Get the explanation from a question"""
    if 'explanation' in q:
        return q['explanation']
    return ''

# ============================================================
# CREATE DEFAULT USER
# ============================================================
def create_default_user():
    """Create a default test user if no users exist"""
    username = "testuser"
    password = "Test123"
    
    if not user_exists(username):
        user_data = {
            'username': username,
            'password_hash': hash_password(password),
            'created_at': datetime.datetime.now().isoformat(),
            'study_time': 0,
            'streak': 1,
            'last_study_date': datetime.datetime.now().isoformat(),
            'quiz_history': [],
            'exam_history': [],
            'full_exam_history': [],
            'topic_scores': {},
            'mastered_concepts': [],
            'flashcards': [],
            'tasks': [],
            'clinical_skills': [],
            'wrong_answers': [],
            'activity_log': [],
            'study_groups': [],
            'badges': ['🌟 First Login'],
            'total_questions_answered': 0,
            'total_correct_answers': 0,
            'last_login': datetime.datetime.now().isoformat()
        }
        save_user(username, user_data)
        print(f"✅ Default user created: {username} / {password}")
        return True
    return False

# ============================================================
# AUTH ROUTES
# ============================================================
@app.route('/api/user/create', methods=['POST'])
def create_user():
    data = request.json
    print(f"📝 Signup attempt: {data}")
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    firstName = data.get('firstName', '').strip()
    lastName = data.get('lastName', '').strip()
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    if user_exists(username):
        return jsonify({'error': 'Username already exists'}), 400
    
    user_data = {
        'username': username,
        'password_hash': hash_password(password),
        'created_at': datetime.datetime.now().isoformat(),
        'study_time': 0,
        'streak': 1,
        'last_study_date': datetime.datetime.now().isoformat(),
        'quiz_history': [],
        'exam_history': [],
        'full_exam_history': [],
        'topic_scores': {},
        'mastered_concepts': [],
        'flashcards': [],
        'tasks': [],
        'clinical_skills': [],
        'wrong_answers': [],
        'activity_log': [],
        'study_groups': [],
        'badges': ['🌟 First Login'],
        'total_questions_answered': 0,
        'total_correct_answers': 0,
        'last_login': datetime.datetime.now().isoformat()
    }
    
    if save_user(username, user_data):
        print(f"✅ User created: {username}")
        return jsonify({
            'success': True,
            'username': username,
            'message': 'Account created successfully!'
        })
    else:
        print(f"❌ Failed to create user: {username}")
        return jsonify({'error': 'Failed to create account'}), 500

# ============================================================
# ADDED: /api/user/register ALIAS ROUTE
# ============================================================
@app.route('/api/user/register', methods=['POST'])
def register_user():
    """Alias for /api/user/create - maintains compatibility with frontend"""
    print("📝 Registration via /api/user/register alias")
    return create_user()

# ============================================================
# QUICK SIGNUP (Test Endpoint)
# ============================================================
@app.route('/api/quick-signup')
def quick_signup():
    """Quick test endpoint to create a test user"""
    username = "testuser"
    password = "Test123"
    
    if user_exists(username):
        return jsonify({'message': 'User already exists', 'username': username})
    
    user_data = {
        'username': username,
        'password_hash': hash_password(password),
        'created_at': datetime.datetime.now().isoformat(),
        'study_time': 0,
        'streak': 1,
        'last_study_date': datetime.datetime.now().isoformat(),
        'quiz_history': [],
        'exam_history': [],
        'full_exam_history': [],
        'topic_scores': {},
        'mastered_concepts': [],
        'flashcards': [],
        'tasks': [],
        'clinical_skills': [],
        'wrong_answers': [],
        'activity_log': [],
        'study_groups': [],
        'badges': ['🌟 First Login'],
        'total_questions_answered': 0,
        'total_correct_answers': 0,
        'last_login': datetime.datetime.now().isoformat()
    }
    
    if save_user(username, user_data):
        return jsonify({
            'success': True,
            'username': username,
            'password': password,
            'message': 'Test user created! Login with testuser/Test123'
        })
    return jsonify({'error': 'Failed to create user'}), 500

@app.route('/api/test-signup')
def test_signup():
    """Test endpoint to verify signup API is working"""
    return jsonify({
        'message': 'Signup API is working',
        'status': 'ok',
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/user/login', methods=['POST'])
def login_user():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    print(f"🔐 Login attempt: {username}")
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user_data = load_user(username)
    
    if not user_data:
        print(f"❌ User not found: {username}")
        return jsonify({'error': 'User not found'}), 404
    
    stored_hash = user_data.get('password_hash', '')
    computed_hash = hash_password(password)
    
    if stored_hash != computed_hash:
        print(f"❌ Incorrect password for: {username}")
        return jsonify({'error': 'Incorrect password'}), 401
    
    user_data['last_login'] = datetime.datetime.now().isoformat()
    user_data['last_study_date'] = datetime.datetime.now().isoformat()
    save_user(username, user_data)
    
    print(f"✅ Login successful: {username}")
    
    return jsonify({
        'success': True,
        'username': username,
        'user_data': {
            'study_time': user_data.get('study_time', 0),
            'streak': user_data.get('streak', 0),
            'quiz_history': user_data.get('quiz_history', []),
            'exam_history': user_data.get('exam_history', []),
            'full_exam_history': user_data.get('full_exam_history', []),
            'topic_scores': user_data.get('topic_scores', {}),
            'mastered_concepts': user_data.get('mastered_concepts', []),
            'flashcards': user_data.get('flashcards', []),
            'tasks': user_data.get('tasks', []),
            'clinical_skills': user_data.get('clinical_skills', []),
            'wrong_answers': user_data.get('wrong_answers', []),
            'badges': user_data.get('badges', []),
            'total_questions_answered': user_data.get('total_questions_answered', 0),
            'total_correct_answers': user_data.get('total_correct_answers', 0)
        }
    })

# ============================================================
# USER DATA ROUTE - FIXED
# ============================================================
@app.route('/api/user/<username>/data', methods=['GET', 'POST'])
def user_data_route(username):
    print(f"📊 User data request for: {username}, method: {request.method}")
    
    if request.method == 'GET':
        user_data = load_user(username)
        if not user_data:
            print(f"❌ User not found: {username}")
            return jsonify({'error': 'User not found'}), 404
        safe_data = {k: v for k, v in user_data.items() if k != 'password_hash'}
        return jsonify(safe_data)
    
    elif request.method == 'POST':
        data = request.json
        user_data = load_user(username)
        if not user_data:
            print(f"❌ User not found: {username}")
            return jsonify({'error': 'User not found'}), 404
        
        allowed_fields = ['study_time', 'streak', 'last_study_date', 'quiz_history', 
                         'exam_history', 'full_exam_history', 'topic_scores', 
                         'mastered_concepts', 'flashcards', 'tasks', 'clinical_skills', 
                         'wrong_answers', 'activity_log', 'badges', 
                         'total_questions_answered', 'total_correct_answers']
        
        for key, value in data.items():
            if key in allowed_fields and value is not None:
                user_data[key] = value
        
        user_data['updated_at'] = datetime.datetime.now().isoformat()
        save_user(username, user_data)
        return jsonify({'success': True, 'message': 'Data saved successfully!'})

# ============================================================
# USER ANALYTICS ROUTE - ADDED!
# ============================================================
@app.route('/api/user/<username>/analytics')
def get_user_analytics(username):
    """Get analytics data for a user"""
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    # Get all activity history
    quiz_history = user_data.get('quiz_history', [])
    exam_history = user_data.get('exam_history', [])
    full_exam_history = user_data.get('full_exam_history', [])
    
    # Combine all history
    all_history = quiz_history + exam_history + full_exam_history
    
    # Calculate scores
    scores = []
    for item in all_history:
        score = item.get('score')
        if score is not None:
            scores.append(score)
    
    # Get weekly scores (last 4 weeks)
    weekly_scores = []
    weekly_labels = []
    now = datetime.datetime.now()
    
    for i in range(3, -1, -1):
        week_start = now - datetime.timedelta(days=(i * 7) + 7)
        week_end = now - datetime.timedelta(days=i * 7)
        week_scores = []
        
        for item in all_history:
            try:
                item_date_str = item.get('date', '')
                if item_date_str:
                    item_date = datetime.datetime.fromisoformat(item_date_str)
                    if week_start <= item_date < week_end:
                        if item.get('score') is not None:
                            week_scores.append(item.get('score'))
            except:
                pass
        
        avg_score = sum(week_scores) / len(week_scores) if week_scores else 0
        weekly_scores.append(round(avg_score, 1))
        weekly_labels.append(f'Week {i+1}')
    
    # Get recent activity
    recent_activity = user_data.get('activity_log', [])[-10:]
    
    # Calculate weak topics from topic_scores
    topic_scores = user_data.get('topic_scores', {})
    weak_topics = []
    for topic, score_data in topic_scores.items():
        if isinstance(score_data, list):
            avg = sum(score_data) / len(score_data) if score_data else 0
            if avg < 50:
                weak_topics.append(topic)
        elif isinstance(score_data, (int, float)) and score_data < 50:
            weak_topics.append(topic)
    
    return jsonify({
        'study_time': user_data.get('study_time', 0),
        'average_score': round(sum(scores) / len(scores), 1) if scores else 0,
        'concepts_mastered': len(user_data.get('mastered_concepts', [])),
        'weakest_topics': weak_topics[:5],
        'weekly_scores': weekly_scores,
        'weekly_labels': weekly_labels,
        'recent_activity': recent_activity,
        'total_quizzes': len(quiz_history),
        'total_exams': len(exam_history),
        'total_full_exams': len(full_exam_history)
    })

# ============================================================
# USER ADAPTIVE ROUTE - ADDED!
# ============================================================
@app.route('/api/user/<username>/adaptive')
def get_adaptive_data(username):
    """Get adaptive learning recommendations for a user"""
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    # Get topic scores
    topic_scores = user_data.get('topic_scores', {})
    mastered = set(user_data.get('mastered_concepts', []))
    
    # Analyze performance
    strong_areas = []
    weak_areas = []
    recommended_topics = []
    study_recommendations = []
    
    # Get all available topics from notes
    all_notes = get_all_notes()
    all_topics = [get_note_title(note) for note in all_notes]
    
    # Calculate performance for each topic
    for topic in all_topics:
        score_data = topic_scores.get(topic)
        
        if score_data is not None:
            if isinstance(score_data, list):
                avg_score = sum(score_data) / len(score_data) if score_data else 0
            else:
                avg_score = score_data
            
            if avg_score >= 80 and topic in mastered:
                strong_areas.append(topic)
            elif avg_score < 60 and avg_score > 0:
                weak_areas.append(topic)
        else:
            # Topic not yet studied
            if topic not in mastered:
                recommended_topics.append(topic)
    
    # Generate study recommendations based on history
    quiz_history = user_data.get('quiz_history', [])
    exam_history = user_data.get('exam_history', [])
    full_exam_history = user_data.get('full_exam_history', [])
    
    all_activities = quiz_history + exam_history + full_exam_history
    
    # Find best study time
    if all_activities:
        hour_counts = {}
        for activity in all_activities:
            try:
                if activity.get('date'):
                    dt = datetime.datetime.fromisoformat(activity['date'])
                    hour = dt.hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
            except:
                pass
        
        if hour_counts:
            best_hour = max(hour_counts, key=hour_counts.get)
            study_recommendations.append(f"Your most productive study time: {best_hour}:00 - {best_hour+1}:00")
    
    # Add other recommendations
    if len(all_activities) == 0:
        study_recommendations.append("Start with a 25-minute Pomodoro session on a topic you're curious about.")
    elif len(all_activities) < 5:
        study_recommendations.append("Try completing 3 short quizzes this week to build momentum.")
    
    if weak_areas:
        study_recommendations.append(f"Focus on: {', '.join(weak_areas[:3])} this week.")
    
    if recommended_topics:
        study_recommendations.append(f"New topics to explore: {', '.join(recommended_topics[:3])}")
    
    return jsonify({
        'recommended_topics': recommended_topics[:5],
        'strong_areas': strong_areas[:5],
        'weak_areas': weak_areas[:5],
        'study_recommendations': study_recommendations[:5],
        'total_quizzes_taken': len(quiz_history),
        'total_exams_taken': len(exam_history),
        'total_full_exams_taken': len(full_exam_history),
        'streak': user_data.get('streak', 0)
    })

# ============================================================
# USER RECOMMENDATIONS ROUTE
# ============================================================
@app.route('/api/user/<username>/recommendations')
def get_recommendations(username):
    user_data = load_user(username)
    if not user_data:
        return jsonify([])
    
    recommendations = []
    topic_scores = user_data.get('topic_scores', {})
    mastered = set(user_data.get('mastered_concepts', []))
    
    for note_file in get_all_notes():
        topic_name = get_note_title(note_file)
        if topic_name not in topic_scores:
            recommendations.append({
                'topic': topic_name,
                'filename': note_file,
                'reason': 'Not studied yet',
                'priority': 'High'
            })
        elif topic_name in topic_scores and topic_scores[topic_name] < 60:
            recommendations.append({
                'topic': topic_name,
                'filename': note_file,
                'reason': f'Score: {topic_scores[topic_name]}% - Needs improvement',
                'priority': 'High' if topic_scores[topic_name] < 40 else 'Medium'
            })
        elif topic_name in mastered:
            recommendations.append({
                'topic': topic_name,
                'filename': note_file,
                'reason': 'Mastered! Keep up the good work!',
                'priority': 'Low'
            })
    
    priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
    recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
    
    return jsonify(recommendations[:15])

@app.route('/api/user/<username>/reminders')
def get_reminders(username):
    user_data = load_user(username)
    if not user_data:
        return jsonify([])
    
    reminders = []
    last_study = user_data.get('last_study_date')
    if last_study:
        last_date = datetime.datetime.fromisoformat(last_study)
        today = datetime.datetime.now()
        days_since = (today - last_date).days
        if days_since > 1:
            reminders.append({
                'message': f"You haven't studied in {days_since} days. Time to review! 📚",
                'priority': 'high'
            })
    
    weak_topics = [(t, s) for t, s in user_data.get('topic_scores', {}).items() if s < 50]
    if weak_topics:
        reminders.append({
            'message': f'You need to review: {", ".join([t for t, _ in weak_topics[:3]])} 📖',
            'priority': 'high'
        })
    
    return jsonify(reminders)

@app.route('/api/user/<username>/clinical-skills', methods=['POST'])
def update_clinical_skills(username):
    data = request.json
    skill_id = data.get('skill_id')
    completed = data.get('completed', True)
    
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    skills = user_data.get('clinical_skills', [])
    if completed:
        if skill_id not in skills:
            skills.append(skill_id)
    else:
        if skill_id in skills:
            skills.remove(skill_id)
    
    user_data['clinical_skills'] = skills
    save_user(username, user_data)
    return jsonify({'success': True, 'skills': skills})

# ============================================================
# SYNC ROUTES
# ============================================================
@app.route('/api/sync', methods=['POST'])
def sync_data():
    data = request.json
    username = data.get('userId')
    incoming = data.get('data', {})
    
    if not username:
        return jsonify({'error': 'User ID required'}), 400
    
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    for key in ['flashcards', 'tasks', 'wrong_answers', 'clinical_skills', 
                'quiz_history', 'exam_history', 'full_exam_history', 'topic_scores', 'mastered_concepts',
                'badges', 'total_questions_answered', 'total_correct_answers']:
        if key in incoming:
            if key in ['flashcards', 'tasks', 'wrong_answers', 'quiz_history', 'exam_history', 'full_exam_history', 'badges']:
                existing = user_data.get(key, [])
                existing_ids = set(str(item.get('id', item.get('front', ''))) for item in existing)
                for item in incoming[key]:
                    item_id = str(item.get('id', item.get('front', '')))
                    if item_id and item_id not in existing_ids:
                        existing.append(item)
                user_data[key] = existing
            else:
                user_data[key] = incoming[key]
    
    if 'study_time' in incoming:
        user_data['study_time'] = max(user_data.get('study_time', 0), incoming['study_time'])
    
    if 'streak' in incoming:
        user_data['streak'] = max(user_data.get('streak', 0), incoming['streak'])
    
    user_data['last_sync'] = datetime.datetime.now().isoformat()
    
    if save_user(username, user_data):
        return jsonify({
            'success': True,
            'message': 'Sync completed',
            'server_data': {
                'flashcards': user_data.get('flashcards', []),
                'tasks': user_data.get('tasks', []),
                'study_time': user_data.get('study_time', 0),
                'streak': user_data.get('streak', 0),
                'badges': user_data.get('badges', [])
            }
        })
    
    return jsonify({'error': 'Sync failed'}), 500

@app.route('/api/offline/download', methods=['POST'])
def download_offline_content():
    data = request.json
    user_id = data.get('user_id')
    
    offline_package = {
        'notes': {},
        'quizzes': {},
        'user_data': None,
        'version': '2.0',
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    for note_file in get_all_notes():
        note_data = load_note(note_file)
        if note_data:
            offline_package['notes'][note_file] = note_data
    
    for quiz_file in get_all_quizzes():
        quiz_data = load_quiz(quiz_file)
        if quiz_data:
            offline_package['quizzes'][quiz_file] = quiz_data
    
    if user_id and user_id != 'guest' and user_exists(user_id):
        user_data = load_user(user_id)
        if user_data:
            safe_data = {k: v for k, v in user_data.items() if k != 'password_hash'}
            offline_package['user_data'] = safe_data
    
    return jsonify(offline_package)

# ============================================================
# CONTENT ROUTES
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/notes')
def get_notes():
    return jsonify(categorize_notes())

@app.route('/api/notes/<filename>')
def get_note_content(filename):
    if not filename.endswith('.json'):
        filename += '.json'
    data = load_note(filename)
    if data:
        return jsonify(data)
    return jsonify({'error': 'Note not found'}), 404

@app.route('/api/quizzes')
def get_quizzes():
    all_quizzes = get_all_quizzes()
    return jsonify([{
        'filename': q,
        'title': get_note_title(q)
    } for q in all_quizzes])

@app.route('/api/quizzes/<filename>')
def get_quiz_content(filename):
    if not filename.endswith('.json'):
        filename += '.json'
    data = load_quiz(filename)
    if data:
        return jsonify(data)
    return jsonify({'error': 'Quiz not found'}), 404

@app.route('/api/stats')
def get_stats():
    all_notes = get_all_notes()
    all_quizzes = get_all_quizzes()
    total_questions = 0
    for q in all_quizzes:
        quiz_data = load_quiz(q)
        if quiz_data:
            questions = extract_questions_from_data(quiz_data)
            total_questions += len(questions)
    return jsonify({
        'total_notes': len(all_notes),
        'total_quizzes': len(all_quizzes),
        'total_questions': total_questions
    })

@app.route('/api/exam-questions')
def get_exam_questions():
    all_questions = []
    for note_file in get_all_notes():
        note_data = load_note(note_file)
        if note_data:
            questions = extract_questions_from_data(note_data)
            for q in questions:
                if isinstance(q, dict):
                    q['source'] = get_note_title(note_file)
                    all_questions.append(q)
    for quiz_file in get_all_quizzes():
        quiz_data = load_quiz(quiz_file)
        if quiz_data:
            questions = extract_questions_from_data(quiz_data)
            for q in questions:
                if isinstance(q, dict):
                    q['source'] = get_note_title(quiz_file)
                    all_questions.append(q)
    random.shuffle(all_questions)
    return jsonify(all_questions)

@app.route('/api/clinical-skills')
def get_clinical_skills():
    skills = [
        {"id": "vital_signs", "name": "Vital Signs Measurement", "category": "Basic"},
        {"id": "patient_history", "name": "Patient History Taking", "category": "Basic"},
        {"id": "physical_exam", "name": "Physical Examination", "category": "Basic"},
        {"id": "wound_care", "name": "Wound Care and Dressing", "category": "Basic"},
        {"id": "iv_cannulation", "name": "IV Cannulation", "category": "Procedure"},
        {"id": "blood_draw", "name": "Blood Draw", "category": "Procedure"},
        {"id": "ecg_interpretation", "name": "ECG Interpretation", "category": "Diagnostic"},
        {"id": "cpr", "name": "CPR and Basic Life Support", "category": "Emergency"},
        {"id": "patient_counseling", "name": "Patient Counseling", "category": "Communication"},
        {"id": "medication_admin", "name": "Medication Administration", "category": "Pharmacology"},
        {"id": "chest_xray", "name": "Chest X-Ray Interpretation", "category": "Diagnostic"},
        {"id": "suturing", "name": "Suturing Techniques", "category": "Procedure"},
        {"id": "intubation", "name": "Endotracheal Intubation", "category": "Procedure"},
        {"id": "defibrillation", "name": "Defibrillation", "category": "Emergency"},
        {"id": "aseptic_technique", "name": "Aseptic Technique", "category": "Basic"},
        {"id": "patient_transfer", "name": "Patient Transfer", "category": "Basic"},
    ]
    return jsonify(skills)

@app.route('/api/pronunciation/search')
def search_pronunciation():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    
    medical_terms = {
        "hypertension": "hy-per-TEN-shun",
        "hypotension": "hy-po-TEN-shun",
        "tachycardia": "tak-ee-KAR-dee-ah",
        "bradycardia": "brad-ee-KAR-dee-ah",
        "myocardial": "my-oh-KAR-dee-al",
        "ischemia": "iss-KEE-mee-ah",
        "arrhythmia": "ah-RITH-mee-ah",
        "atherosclerosis": "ath-er-oh-skleh-ROE-sis",
        "electrocardiogram": "ee-lek-tro-KAR-dee-oh-gram",
        "auscultation": "aw-skel-TAY-shun",
        "edema": "eh-DEE-mah",
        "anaphylaxis": "an-ah-fih-LAK-sis",
        "pharmacokinetics": "far-ma-ko-kih-NET-iks",
        "pharmacodynamics": "far-ma-ko-dye-NAM-iks",
        "hemoglobin": "hee-muh-GLOH-bin",
        "creatinine": "kree-AT-ih-neen",
        "glucose": "GLOO-kose",
        "potassium": "puh-TAS-ee-um",
        "sodium": "SO-dee-um",
        "chloride": "KLOR-ide",
        "calcium": "KAL-see-um",
        "magnesium": "mag-NEE-zee-um",
        "albumin": "al-BYOO-min",
        "bilirubin": "bil-ee-ROO-bin"
    }
    
    results = []
    for term, pron in medical_terms.items():
        if query in term or query in pron.lower():
            results.append({'term': term, 'pronunciation': pron})
    
    return jsonify(results[:20])

# ============================================================
# QUIZ BANK - AI POWERED GRADING
# ============================================================
@app.route('/api/quiz/submit', methods=['POST'])
def submit_quiz():
    """Submit quiz and grade with AI"""
    data = request.json
    quiz_id = data.get('quiz_id', datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
    answers = data.get('answers', {})
    questions = data.get('questions', [])
    time_taken = data.get('time_taken', 0)
    username = data.get('username', '')
    quiz_title = data.get('title', 'Quiz')
    
    print(f"\n📝 AI Quiz submission: {quiz_title}, {len(questions)} questions, username: {username}")
    
    correct = 0
    total = len(questions)
    results = []
    wrong_questions = []
    ai_feedback = []
    
    for i, q in enumerate(questions):
        user_answer = answers.get(str(i), -1)
        
        correct_answer = get_correct_answer(q)
        if correct_answer is None:
            print(f"  Q{i+1}: No correct answer found!")
            continue
        
        options = q.get('options', [])
        question_text = q.get('question', '')
        explanation = get_explanation(q)
        
        selected_text = ""
        if isinstance(user_answer, int) and 0 <= user_answer < len(options):
            selected_text = options[user_answer]
        else:
            selected_text = str(user_answer)
        
        correct_text = ""
        if isinstance(correct_answer, str):
            correct_text = correct_answer
        elif isinstance(correct_answer, int) and 0 <= correct_answer < len(options):
            correct_text = options[correct_answer]
        else:
            correct_text = str(correct_answer)
        
        is_correct, grade_explanation, confidence = ai_grade_question(
            question_text, selected_text, correct_text, options
        )
        
        print(f"  Q{i+1}: '{selected_text}' vs '{correct_text}' -> {is_correct} (confidence: {confidence})")
        
        if is_correct:
            correct += 1
            ai_feedback.append({
                'question': question_text,
                'selected': selected_text,
                'correct': correct_text,
                'is_correct': True,
                'explanation': grade_explanation,
                'confidence': confidence
            })
        else:
            wrong_questions.append({
                'question': question_text,
                'options': options,
                'correct_answer': correct_text,
                'user_answer': user_answer,
                'explanation': explanation or grade_explanation,
                'source': q.get('source', quiz_title),
                'ai_explanation': grade_explanation
            })
            ai_feedback.append({
                'question': question_text,
                'selected': selected_text,
                'correct': correct_text,
                'is_correct': False,
                'explanation': grade_explanation,
                'confidence': confidence
            })
        
        results.append({
            'question_index': i,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'question': question_text,
            'options': options,
            'explanation': explanation or grade_explanation,
            'ai_confidence': confidence
        })
    
    score_percentage = round((correct / total) * 100) if total > 0 else 0
    
    print(f"📊 AI Quiz results: {correct}/{total} correct, {score_percentage}%")
    
    if username and user_exists(username):
        user_data = load_user(username)
        if user_data:
            if 'quiz_history' not in user_data:
                user_data['quiz_history'] = []
            user_data['quiz_history'].append({
                'quiz_id': quiz_id,
                'date': datetime.datetime.now().isoformat(),
                'score': score_percentage,
                'correct': correct,
                'total': total,
                'time_taken': time_taken,
                'title': quiz_title,
                'type': 'quiz',
                'ai_graded': True,
                'ai_feedback': ai_feedback
            })
            user_data['total_questions_answered'] = user_data.get('total_questions_answered', 0) + total
            user_data['total_correct_answers'] = user_data.get('total_correct_answers', 0) + correct
            
            if 'wrong_answers' not in user_data:
                user_data['wrong_answers'] = []
            for wq in wrong_questions:
                user_data['wrong_answers'].append(wq)
            
            if 'badges' not in user_data:
                user_data['badges'] = []
            if len(user_data['quiz_history']) == 1:
                user_data['badges'].append('📝 First Quiz')
            if score_percentage == 100:
                user_data['badges'].append('🌟 Perfect Quiz')
            if len(user_data['quiz_history']) >= 10:
                user_data['badges'].append('🏅 10 Quizzes')
            
            user_data['study_time'] = user_data.get('study_time', 0) + time_taken
            user_data['last_study_date'] = datetime.datetime.now().isoformat()
            
            save_user(username, user_data)
            print(f"✅ AI Quiz saved for user: {username}")
    
    return jsonify({
        'quiz_id': quiz_id,
        'score': score_percentage,
        'correct': correct,
        'total': total,
        'time_taken': time_taken,
        'results': results,
        'passed': score_percentage >= 70,
        'wrong_questions': wrong_questions,
        'ai_feedback': ai_feedback,
        'message': 'Great job!' if score_percentage >= 70 else 'Keep practicing!'
    })

# ============================================================
# EXAM SIMULATOR
# ============================================================
@app.route('/api/exam/generate', methods=['POST'])
def generate_exam():
    data = request.json
    topic = data.get('topic', 'all')
    num_questions = min(data.get('count', 10), 50)
    difficulty = data.get('difficulty', 'medium')
    time_limit = data.get('time_limit', 15)
    
    all_questions = []
    
    if topic == 'all':
        for note_file in get_all_notes():
            note_data = load_note(note_file)
            if note_data:
                questions = extract_questions_from_data(note_data)
                for q in questions:
                    if isinstance(q, dict) and 'question' in q and 'options' in q:
                        q['source'] = get_note_title(note_file)
                        q['topic'] = categorize_notes().get(get_note_title(note_file), 'General')
                        all_questions.append(q)
        for quiz_file in get_all_quizzes():
            quiz_data = load_quiz(quiz_file)
            if quiz_data:
                questions = extract_questions_from_data(quiz_data)
                for q in questions:
                    if isinstance(q, dict) and 'question' in q and 'options' in q:
                        q['source'] = get_note_title(quiz_file)
                        q['topic'] = categorize_notes().get(get_note_title(quiz_file), 'General')
                        all_questions.append(q)
    else:
        for note_file in get_all_notes():
            if topic.lower() in note_file.lower() or topic.lower() in get_note_title(note_file).lower():
                note_data = load_note(note_file)
                if note_data:
                    questions = extract_questions_from_data(note_data)
                    for q in questions:
                        if isinstance(q, dict) and 'question' in q and 'options' in q:
                            q['source'] = get_note_title(note_file)
                            q['topic'] = topic
                            all_questions.append(q)
        for quiz_file in get_all_quizzes():
            if topic.lower() in quiz_file.lower() or topic.lower() in get_note_title(quiz_file).lower():
                quiz_data = load_quiz(quiz_file)
                if quiz_data:
                    questions = extract_questions_from_data(quiz_data)
                    for q in questions:
                        if isinstance(q, dict) and 'question' in q and 'options' in q:
                            q['source'] = get_note_title(quiz_file)
                            q['topic'] = topic
                            all_questions.append(q)
    
    random.shuffle(all_questions)
    selected = all_questions[:num_questions]
    
    for q in selected:
        q['difficulty'] = difficulty.capitalize()
    
    return jsonify({
        'exam_id': datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
        'questions': selected,
        'total_questions': len(selected),
        'time_limit': time_limit,
        'estimated_time': len(selected) * 1.5,
        'topic': topic,
        'difficulty': difficulty,
        'generated_at': datetime.datetime.now().isoformat()
    })

@app.route('/api/exam/submit', methods=['POST'])
def submit_exam():
    data = request.json
    exam_id = data.get('exam_id')
    answers = data.get('answers', {})
    questions = data.get('questions', [])
    time_taken = data.get('time_taken', 0)
    username = data.get('username')
    
    print(f"📝 AI Exam submission: {exam_id}, {len(questions)} questions, username: {username}")
    
    correct = 0
    total = len(questions)
    results = []
    wrong_questions = []
    ai_feedback = []
    
    for i, q in enumerate(questions):
        user_answer = answers.get(str(i), -1)
        
        correct_answer = get_correct_answer(q)
        if correct_answer is None:
            print(f"  Q{i+1}: No correct answer found!")
            continue
        
        options = q.get('options', [])
        question_text = q.get('question', '')
        explanation = get_explanation(q)
        
        selected_text = ""
        if isinstance(user_answer, int) and 0 <= user_answer < len(options):
            selected_text = options[user_answer]
        else:
            selected_text = str(user_answer)
        
        correct_text = ""
        if isinstance(correct_answer, str):
            correct_text = correct_answer
        elif isinstance(correct_answer, int) and 0 <= correct_answer < len(options):
            correct_text = options[correct_answer]
        else:
            correct_text = str(correct_answer)
        
        is_correct, grade_explanation, confidence = ai_grade_question(
            question_text, selected_text, correct_text, options
        )
        
        print(f"  Q{i+1}: '{selected_text}' vs '{correct_text}' -> {is_correct} (confidence: {confidence})")
        
        if is_correct:
            correct += 1
            ai_feedback.append({
                'question': question_text,
                'selected': selected_text,
                'correct': correct_text,
                'is_correct': True,
                'explanation': grade_explanation,
                'confidence': confidence
            })
        else:
            wrong_questions.append({
                'question': question_text,
                'options': options,
                'correct_answer': correct_text,
                'user_answer': user_answer,
                'explanation': explanation or grade_explanation,
                'source': q.get('source', 'Unknown'),
                'ai_explanation': grade_explanation
            })
            ai_feedback.append({
                'question': question_text,
                'selected': selected_text,
                'correct': correct_text,
                'is_correct': False,
                'explanation': grade_explanation,
                'confidence': confidence
            })
        
        results.append({
            'question_index': i,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'question': question_text,
            'options': options,
            'explanation': explanation or grade_explanation,
            'ai_confidence': confidence
        })
    
    score_percentage = round((correct / total) * 100) if total > 0 else 0
    
    print(f"📊 AI Exam results: {correct}/{total} correct, {score_percentage}%")
    
    if username and user_exists(username):
        user_data = load_user(username)
        if user_data:
            if 'exam_history' not in user_data:
                user_data['exam_history'] = []
            user_data['exam_history'].append({
                'exam_id': exam_id,
                'date': datetime.datetime.now().isoformat(),
                'score': score_percentage,
                'correct': correct,
                'total': total,
                'time_taken': time_taken,
                'topic': data.get('topic', 'General'),
                'difficulty': data.get('difficulty', 'Medium'),
                'type': 'exam_simulator',
                'ai_graded': True,
                'ai_feedback': ai_feedback
            })
            user_data['total_questions_answered'] = user_data.get('total_questions_answered', 0) + total
            user_data['total_correct_answers'] = user_data.get('total_correct_answers', 0) + correct
            
            if 'wrong_answers' not in user_data:
                user_data['wrong_answers'] = []
            for wq in wrong_questions:
                user_data['wrong_answers'].append(wq)
            
            if 'topic_scores' not in user_data:
                user_data['topic_scores'] = {}
            topic = data.get('topic', 'General')
            if topic not in user_data['topic_scores']:
                user_data['topic_scores'][topic] = []
            user_data['topic_scores'][topic].append(score_percentage)
            
            if 'badges' not in user_data:
                user_data['badges'] = []
            
            if len(user_data['exam_history']) == 1:
                user_data['badges'].append('🎯 First Exam')
            if score_percentage == 100:
                user_data['badges'].append('🌟 Perfect Score')
            if len(user_data['exam_history']) >= 5:
                user_data['badges'].append('📚 5 Exams Completed')
            if len(user_data['exam_history']) >= 10:
                user_data['badges'].append('🏆 10 Exams Completed')
            
            user_data['study_time'] = user_data.get('study_time', 0) + time_taken
            user_data['last_study_date'] = datetime.datetime.now().isoformat()
            
            save_user(username, user_data)
            print(f"✅ AI Exam saved for user: {username}")
    
    return jsonify({
        'exam_id': exam_id,
        'score': score_percentage,
        'correct': correct,
        'total': total,
        'time_taken': time_taken,
        'results': results,
        'passed': score_percentage >= 70,
        'wrong_questions': wrong_questions,
        'ai_feedback': ai_feedback,
        'message': 'Great job!' if score_percentage >= 70 else 'Keep practicing!'
    })

# ============================================================
# FULL EXAM
# ============================================================
@app.route('/api/full-exam/generate', methods=['POST'])
def generate_full_exam():
    """Generate exam from Full_Examination_Question_Bank.json"""
    data = request.json
    username = data.get('username')
    
    exam_file = os.path.join(QUIZZES_DIR, 'Full_Examination_Question_Bank.json')
    
    if not os.path.exists(exam_file):
        return jsonify({'error': 'Full Examination Question Bank not found'}), 404
    
    try:
        with open(exam_file, 'r', encoding='utf-8') as f:
            exam_data = json.load(f)
    except Exception as e:
        return jsonify({'error': f'Error loading exam file: {str(e)}'}), 500
    
    mcq_questions = exam_data.get('mcq_questions', [])
    if not mcq_questions:
        mcq_questions = exam_data.get('questions', [])
    
    essay_questions = exam_data.get('essay_questions', [])
    
    print(f"📊 Found {len(mcq_questions)} MCQ questions and {len(essay_questions)} Essay questions")
    
    if len(mcq_questions) < 18:
        return jsonify({'error': f'Not enough MCQ questions. Found {len(mcq_questions)}, need 18.'}), 400
    
    if len(essay_questions) < 2:
        return jsonify({'error': f'Not enough Essay questions. Found {len(essay_questions)}, need 2.'}), 400
    
    selected_mcqs = random.sample(mcq_questions, 18)
    selected_essays = random.sample(essay_questions, 2)
    
    formatted_questions = []
    
    for q in selected_mcqs:
        formatted_questions.append({
            'id': q.get('id'),
            'question': q.get('question', ''),
            'options': q.get('options', []),
            'answer': get_correct_answer(q),
            'explanation': get_explanation(q),
            'type': 'mcq',
            'source': 'Full Examination Bank'
        })
    
    for q in selected_essays:
        formatted_questions.append({
            'id': q.get('id'),
            'question': q.get('question', ''),
            'type': 'essay',
            'hint': q.get('topic', ''),
            'maxScore': q.get('maxScore', 15),
            'source': 'Full Examination Bank'
        })
    
    random.shuffle(formatted_questions)
    
    return jsonify({
        'exam_id': datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
        'questions': formatted_questions,
        'total_questions': len(formatted_questions),
        'time_limit': 60,
        'estimated_time': 60,
        'type': 'full_exam',
        'generated_at': datetime.datetime.now().isoformat()
    })

@app.route('/api/full-exam/submit', methods=['POST'])
def submit_full_exam():
    """Submit full exam and grade with AI"""
    data = request.json
    exam_id = data.get('exam_id')
    answers = data.get('answers', {})
    questions = data.get('questions', [])
    time_taken = data.get('time_taken', 0)
    username = data.get('username')
    
    print(f"📝 AI Full Exam submission: {exam_id}, {len(questions)} questions, username: {username}")
    
    mcq_correct = 0
    mcq_total = 0
    wrong_questions = []
    results = []
    essay_results = []
    ai_feedback = []
    
    for i, q in enumerate(questions):
        if q.get('type') == 'mcq':
            mcq_total += 1
            user_answer = answers.get(str(i), -1)
            correct_answer = get_correct_answer(q)
            if correct_answer is None:
                print(f"  MCQ{i+1}: No correct answer found!")
                continue
            
            options = q.get('options', [])
            question_text = q.get('question', '')
            explanation = get_explanation(q)
            
            selected_text = ""
            if isinstance(user_answer, int) and 0 <= user_answer < len(options):
                selected_text = options[user_answer]
            else:
                selected_text = str(user_answer)
            
            correct_text = ""
            if isinstance(correct_answer, str):
                correct_text = correct_answer
            elif isinstance(correct_answer, int) and 0 <= correct_answer < len(options):
                correct_text = options[correct_answer]
            else:
                correct_text = str(correct_answer)
            
            is_correct, grade_explanation, confidence = ai_grade_question(
                question_text, selected_text, correct_text, options
            )
            
            print(f"  MCQ{i+1}: '{selected_text}' vs '{correct_text}' -> {is_correct} (confidence: {confidence})")
            
            if is_correct:
                mcq_correct += 1
                ai_feedback.append({
                    'question': question_text,
                    'selected': selected_text,
                    'correct': correct_text,
                    'is_correct': True,
                    'explanation': grade_explanation,
                    'confidence': confidence
                })
            else:
                wrong_questions.append({
                    'question': question_text,
                    'options': options,
                    'correct_answer': correct_text,
                    'user_answer': user_answer,
                    'explanation': explanation or grade_explanation,
                    'source': q.get('source', 'Full Exam'),
                    'ai_explanation': grade_explanation
                })
                ai_feedback.append({
                    'question': question_text,
                    'selected': selected_text,
                    'correct': correct_text,
                    'is_correct': False,
                    'explanation': grade_explanation,
                    'confidence': confidence
                })
            
            results.append({
                'question_index': i,
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'question': question_text,
                'options': options,
                'type': 'mcq',
                'explanation': explanation or grade_explanation,
                'ai_confidence': confidence
            })
        
        elif q.get('type') == 'essay':
            user_answer = answers.get(str(i), '')
            essay_results.append({
                'question_index': i,
                'question': q.get('question', ''),
                'user_answer': user_answer,
                'maxScore': q.get('maxScore', 15),
                'hint': q.get('hint', '')
            })
    
    mcq_score = round((mcq_correct / mcq_total) * 100) if mcq_total > 0 else 0
    
    print(f"📊 MCQ results: {mcq_correct}/{mcq_total} correct, {mcq_score}%")
    
    essay_feedback = []
    total_essay_score = 0
    max_essay_score = 0
    
    for essay in essay_results:
        max_score = essay.get('maxScore', 15)
        max_essay_score += max_score
        
        if USE_AI and essay.get('user_answer', '').strip():
            try:
                prompt = f"""Grade this health science essay answer.

Question: {essay['question']}

Student Answer: {essay['user_answer']}

Score out of {max_score}. Provide:
1. Score (number)
2. Feedback (2-3 sentences)
3. What was good
4. What could be improved

Return ONLY valid JSON:
{{
    "score": 0,
    "feedback": "",
    "strengths": [],
    "improvements": []
}}"""
                
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a medical educator grading essays. Be fair and constructive."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=400,
                    temperature=0.3
                )
                
                result_text = response['choices'][0]['message']['content']
                if '```json' in result_text:
                    result_text = result_text.split('```json')[1].split('```')[0]
                elif '```' in result_text:
                    result_text = result_text.split('```')[1].split('```')[0]
                result_text = result_text.strip()
                
                grade = json.loads(result_text)
                essay_score = grade.get('score', 0)
                total_essay_score += essay_score
                
                essay_feedback.append({
                    'question': essay['question'],
                    'user_answer': essay['user_answer'],
                    'score': essay_score,
                    'maxScore': max_score,
                    'feedback': grade.get('feedback', ''),
                    'strengths': grade.get('strengths', []),
                    'improvements': grade.get('improvements', [])
                })
            except Exception as e:
                print(f"AI Essay Grading Error: {e}")
                essay_score = max_score // 2 if essay.get('user_answer', '').strip() else 0
                total_essay_score += essay_score
                essay_feedback.append({
                    'question': essay['question'],
                    'user_answer': essay['user_answer'],
                    'score': essay_score,
                    'maxScore': max_score,
                    'feedback': 'AI grading temporarily unavailable. Score based on attempt.',
                    'strengths': [],
                    'improvements': ['Enable AI for detailed feedback.']
                })
        else:
            essay_score = max_score // 2 if essay.get('user_answer', '').strip() else 0
            total_essay_score += essay_score
            essay_feedback.append({
                'question': essay['question'],
                'user_answer': essay['user_answer'],
                'score': essay_score,
                'maxScore': max_score,
                'feedback': 'Score based on attempt.' if essay.get('user_answer', '').strip() else 'No answer provided.',
                'strengths': [],
                'improvements': ['Please write more detail for a better score.']
            })
    
    mcq_weight = 0.6
    essay_weight = 0.4
    
    mcq_percent = mcq_score
    essay_percent = (total_essay_score / max_essay_score * 100) if max_essay_score > 0 else 0
    
    final_score = round((mcq_percent * mcq_weight) + (essay_percent * essay_weight))
    
    print(f"📊 Full Exam results: MCQ: {mcq_correct}/{mcq_total} ({mcq_percent}%), Essay: {essay_percent}%, Final: {final_score}%")
    
    if username and user_exists(username):
        user_data = load_user(username)
        if user_data:
            if 'full_exam_history' not in user_data:
                user_data['full_exam_history'] = []
            user_data['full_exam_history'].append({
                'exam_id': exam_id,
                'date': datetime.datetime.now().isoformat(),
                'score': final_score,
                'mcq_score': mcq_percent,
                'essay_score': essay_percent,
                'mcq_correct': mcq_correct,
                'mcq_total': mcq_total,
                'essay_feedback': essay_feedback,
                'time_taken': time_taken,
                'ai_feedback': ai_feedback,
                'ai_graded': True
            })
            
            if 'wrong_answers' not in user_data:
                user_data['wrong_answers'] = []
            for wq in wrong_questions:
                user_data['wrong_answers'].append(wq)
            
            if 'topic_scores' not in user_data:
                user_data['topic_scores'] = {}
            if 'Full Exam' not in user_data['topic_scores']:
                user_data['topic_scores']['Full Exam'] = []
            user_data['topic_scores']['Full Exam'].append(final_score)
            
            if 'badges' not in user_data:
                user_data['badges'] = []
            if len(user_data['full_exam_history']) == 1:
                user_data['badges'].append('📝 First Full Exam')
            if len(user_data['full_exam_history']) >= 5:
                user_data['badges'].append('🏅 5 Full Exams')
            if final_score >= 80:
                user_data['badges'].append('🌟 Excellent Score')
            
            user_data['study_time'] = user_data.get('study_time', 0) + time_taken
            user_data['last_study_date'] = datetime.datetime.now().isoformat()
            user_data['total_questions_answered'] = user_data.get('total_questions_answered', 0) + mcq_total
            
            save_user(username, user_data)
            print(f"✅ AI Full Exam saved for user: {username}")
    
    return jsonify({
        'exam_id': exam_id,
        'final_score': final_score,
        'mcq_score': mcq_percent,
        'essay_score': essay_percent,
        'mcq_correct': mcq_correct,
        'mcq_total': mcq_total,
        'essay_feedback': essay_feedback,
        'results': results,
        'wrong_questions': wrong_questions,
        'ai_feedback': ai_feedback,
        'passed': final_score >= 70,
        'time_taken': time_taken,
        'message': 'Great job!' if final_score >= 70 else 'Keep practicing!'
    })

# ============================================================
# RANDOM QUESTION
# ============================================================
@app.route('/api/random-question')
def random_question():
    """Get a random question - AI powered with fallback"""
    
    all_questions = []
    
    for note_file in get_all_notes():
        note_data = load_note(note_file)
        if note_data:
            questions = extract_questions_from_data(note_data)
            for q in questions:
                if isinstance(q, dict):
                    if 'question' in q and 'options' in q:
                        q['source'] = get_note_title(note_file)
                        q['topic'] = categorize_notes().get(get_note_title(note_file), 'General')
                        all_questions.append(q)
    
    for quiz_file in get_all_quizzes():
        quiz_data = load_quiz(quiz_file)
        if quiz_data:
            questions = extract_questions_from_data(quiz_data)
            for q in questions:
                if isinstance(q, dict):
                    if 'question' in q and 'options' in q:
                        q['source'] = get_note_title(quiz_file)
                        q['topic'] = categorize_notes().get(get_note_title(quiz_file), 'General')
                        all_questions.append(q)
    
    if all_questions:
        q = random.choice(all_questions)
        return jsonify({
            'question': q.get('question', ''),
            'options': q.get('options', []),
            'answer': get_correct_answer(q) or 0,
            'source': q.get('source', 'Unknown'),
            'topic': q.get('topic', 'General'),
            'explanation': get_explanation(q)
        })
    
    if USE_AI:
        try:
            topics = [
                'Cardiovascular System', 'Respiratory System', 'Nervous System',
                'Endocrine System', 'Renal System', 'Gastrointestinal System',
                'Musculoskeletal System', 'Reproductive System', 'Immunology',
                'Pharmacology', 'Biochemistry', 'Pathology', 'Microbiology'
            ]
            selected_topic = random.choice(topics)
            
            prompt = f"""Generate one multiple choice question about {selected_topic} for health science students at MUST.

CRITICAL RULES:
1. Use REAL answer choices - NEVER use "Option A", "Option B", "Option C", "Option D"
2. Make the options realistic medical content
3. Return ONLY valid JSON

Return ONLY valid JSON:
{{
    "question": "The question text?",
    "options": ["Real option 1", "Real option 2", "Real option 3", "Real option 4"],
    "correct_answer": "The correct answer text",
    "topic": "{selected_topic}",
    "explanation": "Explanation of why the answer is correct"
}}"""
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical educator. Return only valid JSON. Use REAL medical content in options."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.8
            )
            
            result_text = response['choices'][0]['message']['content']
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0]
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0]
            result_text = result_text.strip()
            
            q = json.loads(result_text)
            
            if 'question' not in q or 'options' not in q or 'correct_answer' not in q:
                raise ValueError("Invalid question format")
            
            return jsonify({
                'question': q.get('question', ''),
                'options': q.get('options', []),
                'answer': q.get('correct_answer', 0),
                'source': 'AI Generated',
                'topic': q.get('topic', selected_topic),
                'explanation': q.get('explanation', '')
            })
        except Exception as e:
            print(f"AI Random Question Error: {e}")
    
    default_questions = [
        {
            'question': 'What is the normal resting heart rate for an adult?',
            'options': ['40-60 beats per minute', '60-100 beats per minute', '100-120 beats per minute', '120-140 beats per minute'],
            'answer': '60-100 beats per minute',
            'source': 'Default',
            'topic': 'Cardiology',
            'explanation': 'The normal resting heart rate for adults is 60-100 beats per minute.'
        },
        {
            'question': 'How many chambers does the human heart have?',
            'options': ['2 chambers (atria only)', '3 chambers (2 atria, 1 ventricle)', '4 chambers (2 atria, 2 ventricles)', '5 chambers'],
            'answer': '4 chambers (2 atria, 2 ventricles)',
            'source': 'Default',
            'topic': 'Anatomy',
            'explanation': 'The human heart has 4 chambers: 2 atria and 2 ventricles.'
        },
        {
            'question': 'Which organ produces insulin?',
            'options': ['Liver', 'Pancreas', 'Kidney', 'Stomach'],
            'answer': 'Pancreas',
            'source': 'Default',
            'topic': 'Endocrinology',
            'explanation': 'The pancreas produces insulin in the islets of Langerhans.'
        }
    ]
    
    q = random.choice(default_questions)
    return jsonify(q)

# ============================================================
# PRODUCTIVITY ROUTES
# ============================================================
@app.route('/api/productivity/stats')
def productivity_stats():
    username = request.args.get('username')
    if not username or not user_exists(username):
        return jsonify({
            'total_study_time': 0,
            'total_questions_answered': 0,
            'average_score': 0,
            'streak_days': 0,
            'weekly_data': [{'date': '', 'activity': 0, 'time': 0} for _ in range(7)],
            'total_quizzes_taken': 0,
            'total_exams_taken': 0,
            'total_full_exams_taken': 0,
            'badges': [],
            'mastered_concepts': 0
        })
    
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    total_study_time = user_data.get('study_time', 0)
    total_questions_answered = user_data.get('total_questions_answered', 0)
    
    quiz_history = user_data.get('quiz_history', [])
    exam_history = user_data.get('exam_history', [])
    full_exam_history = user_data.get('full_exam_history', [])
    
    all_scores = []
    for q in quiz_history:
        if q.get('score') is not None:
            all_scores.append(q.get('score'))
    for e in exam_history:
        if e.get('score') is not None:
            all_scores.append(e.get('score'))
    for f in full_exam_history:
        if f.get('score') is not None:
            all_scores.append(f.get('score'))
    
    average_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    
    daily_stats = {}
    all_activities = quiz_history + exam_history + full_exam_history
    for activity in all_activities:
        date = activity.get('date', '').split('T')[0] if activity.get('date') else ''
        if date:
            if date not in daily_stats:
                daily_stats[date] = {'activities': 0, 'time': 0}
            daily_stats[date]['activities'] += 1
            daily_stats[date]['time'] += activity.get('time_taken', 0)
    
    streak = 0
    if daily_stats:
        sorted_dates = sorted(daily_stats.keys(), reverse=True)
        for date in sorted_dates:
            if daily_stats[date]['activities'] > 0:
                streak += 1
            else:
                break
    
    weekly_data = []
    today = datetime.datetime.now()
    for i in range(7):
        date = (today - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        if date in daily_stats:
            weekly_data.append({
                'date': date,
                'activity': daily_stats[date]['activities'],
                'time': daily_stats[date]['time']
            })
        else:
            weekly_data.append({'date': date, 'activity': 0, 'time': 0})
    
    return jsonify({
        'total_study_time': total_study_time,
        'total_questions_answered': total_questions_answered,
        'average_score': average_score,
        'streak_days': streak if streak > 0 else user_data.get('streak', 0),
        'weekly_data': weekly_data,
        'total_quizzes_taken': len(quiz_history),
        'total_exams_taken': len(exam_history),
        'total_full_exams_taken': len(full_exam_history),
        'badges': user_data.get('badges', []),
        'mastered_concepts': len(user_data.get('mastered_concepts', []))
    })

@app.route('/api/productivity/update', methods=['POST'])
def update_productivity():
    data = request.json
    username = data.get('username')
    activity_type = data.get('type', 'study')
    duration = data.get('duration', 0)
    details = data.get('details', {})
    
    if not username or not user_exists(username):
        return jsonify({'error': 'User not found'}), 404
    
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    if 'activity_log' not in user_data:
        user_data['activity_log'] = []
    
    user_data['activity_log'].append({
        'timestamp': datetime.datetime.now().isoformat(),
        'type': activity_type,
        'duration': duration,
        'details': details
    })
    
    if activity_type == 'study':
        user_data['study_time'] = user_data.get('study_time', 0) + duration
    
    user_data['last_study_date'] = datetime.datetime.now().isoformat()
    
    save_user(username, user_data)
    return jsonify({'success': True, 'streak': user_data.get('streak', 0)})

# ============================================================
# AI ROUTES
# ============================================================
@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({'response': 'Please ask a question.'})
    
    if not USE_AI:
        return jsonify({'response': "I'm here to help with health sciences! What would you like to learn about?"})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant for health science students at MUST in Uganda."},
                {"role": "user", "content": message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return jsonify({'response': response['choices'][0]['message']['content']})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({'response': "I'm having trouble with AI right now. Please try again later."})

@app.route('/api/ai/generate-questions', methods=['POST'])
def ai_generate_questions():
    data = request.json
    topic = data.get('topic', 'general_medicine')
    count = min(data.get('count', 5), 20)
    question_type = data.get('type', 'mixed')
    
    topic_names = {
        'anatomy': 'Anatomy', 'physiology': 'Physiology', 'biochemistry': 'Biochemistry',
        'pharmacology': 'Pharmacology', 'pathology': 'Pathology', 'microbiology': 'Microbiology',
        'immunology': 'Immunology', 'genetics': 'Genetics', 'cardiology': 'Cardiology',
        'neurology': 'Neurology', 'endocrinology': 'Endocrinology', 'gastroenterology': 'Gastroenterology',
        'nephrology': 'Nephrology', 'pulmonology': 'Pulmonology', 'hematology': 'Hematology',
        'oncology': 'Oncology', 'infectious_disease': 'Infectious Disease', 'psychiatry': 'Psychiatry',
        'pediatrics': 'Pediatrics', 'obstetrics': 'Obstetrics', 'gynecology': 'Gynecology',
        'emergency_medicine': 'Emergency Medicine', 'surgery': 'Surgery', 'general_medicine': 'General Medicine'
    }
    
    topic_display = topic_names.get(topic, topic.replace('_', ' ').title())
    
    if not USE_AI:
        fallback_questions = [
            {
                "type": "mcq",
                "question": f"What is the primary function of the {topic_display}?",
                "options": [
                    "Regulate body functions and maintain homeostasis",
                    "Provide structural support and protection",
                    "Transport oxygen and nutrients throughout the body",
                    "Produce hormones and enzymes"
                ],
                "correct_answer": "Regulate body functions and maintain homeostasis",
                "explanation": f"This is the key function of the {topic_display}."
            }
        ]
        return jsonify({'questions': fallback_questions[:count]})
    
    try:
        if question_type == 'essay':
            prompt = f"""Generate {count} essay questions about "{topic_display}" for health science students at MUST.

Return ONLY valid JSON in this format:
[
    {{
        "type": "essay",
        "question": "Write a detailed essay about a specific aspect of {topic_display}",
        "hint": "Include specific guidance on what to cover"
    }}
]"""
        
        elif question_type == 'mcq':
            prompt = f"""Generate {count} multiple choice questions about "{topic_display}" for health science students at MUST.

IMPORTANT RULES:
1. Each question MUST be about "{topic_display}" specifically
2. Each question MUST have 4 DISTINCT, REALISTIC answer choices
3. The correct answer MUST be one of the realistic choices
4. Make questions relevant to East African healthcare context

Return ONLY valid JSON in this format:
[
    {{
        "type": "mcq",
        "question": "Specific question about {topic_display}?",
        "options": ["Real option 1", "Real option 2", "Real option 3", "Real option 4"],
        "correct_answer": "The correct option text",
        "explanation": "Explanation of why this is correct"
    }}
]"""
        
        else:  # mixed
            mcq_count = count // 2
            essay_count = count - mcq_count
            prompt = f"""Generate {mcq_count} multiple choice questions and {essay_count} essay questions about "{topic_display}" for health science students at MUST.

For MCQ questions: MUST have 4 DISTINCT, REALISTIC answer choices with correct_answer as the text.
For Essay questions: Make them specific and relevant to East African healthcare.

Return ONLY valid JSON."""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator creating high-quality assessment questions. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        result_text = response['choices'][0]['message']['content']
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0]
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0]
        result_text = result_text.strip()
        
        questions = json.loads(result_text)
        
        validated_questions = []
        for q in questions[:count]:
            if not isinstance(q, dict) or 'question' not in q:
                continue
            
            q_type = q.get('type', 'mcq')
            
            if q_type == 'mcq':
                if 'options' not in q or not isinstance(q['options'], list) or len(q['options']) < 4:
                    q['options'] = [
                        f"Key concept of {topic_display}",
                        f"Clinical application of {topic_display}",
                        f"Pathophysiology of {topic_display}",
                        f"Treatment approach for {topic_display}"
                    ]
                if 'correct_answer' not in q:
                    q['correct_answer'] = q['options'][0] if q['options'] else "Option 1"
                if 'explanation' not in q:
                    q['explanation'] = "This is the correct answer based on clinical guidelines."
            
            elif q_type == 'essay':
                if 'hint' not in q:
                    q['hint'] = f"Consider the key concepts, mechanisms, and clinical applications of {topic_display}."
            
            validated_questions.append(q)
        
        return jsonify({'questions': validated_questions})
    except Exception as e:
        print(f"AI Error: {e}")
        fallback_questions = [
            {
                "type": "mcq",
                "question": f"What is the most common cause of {topic_display} in East Africa?",
                "options": [
                    "Infectious etiology",
                    "Genetic predisposition",
                    "Environmental factors",
                    "Lifestyle choices"
                ],
                "correct_answer": "Infectious etiology",
                "explanation": "This is the most common cause based on regional data."
            }
        ]
        return jsonify({'questions': fallback_questions[:count]})

@app.route('/api/ai/generate-case', methods=['POST'])
def ai_generate_case():
    data = request.json
    specialty = data.get('specialty', 'general_medicine')
    
    if not USE_AI:
        return jsonify({'case': {
            "title": "Clinical Case",
            "patient": "Patient presents with symptoms related to the condition.",
            "labs": "Lab results pending.",
            "questions": [
                {"q": "What is the most likely diagnosis?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct_answer": "Option A", "rationale": "Based on presentation."}
            ],
            "diagnosis": "Diagnosis",
            "treatment": "Standard treatment"
        }})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator. Return only valid JSON."},
                {"role": "user", "content": "Generate a clinical case study with patient presentation, lab findings, 2-3 questions, diagnosis, and treatment."}
            ],
            max_tokens=1200,
            temperature=0.8
        )
        
        result_text = response['choices'][0]['message']['content']
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0]
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0]
        result_text = result_text.strip()
        
        case = json.loads(result_text)
        return jsonify({'case': case})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({'case': {
            "title": "Clinical Case",
            "patient": "Patient presents with symptoms.",
            "labs": "Lab results pending.",
            "questions": [
                {"q": "What is the most likely diagnosis?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct_answer": "Option A", "rationale": "Based on presentation."}
            ],
            "diagnosis": "Diagnosis",
            "treatment": "Standard treatment"
        }})

@app.route('/api/ai/summarize', methods=['POST'])
def ai_summarize():
    data = request.json
    content = data.get('content', '')
    topic = data.get('topic', 'health science')
    
    if not content:
        return jsonify({'summary': 'No content provided'})
    
    if not USE_AI:
        sentences = content.split('.')[:3]
        return jsonify({'summary': f"📌 Key points: {'. '.join(sentences)}..."})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator. Summarize the content into key takeaways."},
                {"role": "user", "content": f"Summarize this about {topic}: {content[:2000]}"}
            ],
            max_tokens=300,
            temperature=0.5
        )
        return jsonify({'summary': response['choices'][0]['message']['content']})
    except Exception as e:
        print(f"AI Error: {e}")
        sentences = content.split('.')[:3]
        return jsonify({'summary': f"📌 Key points: {'. '.join(sentences)}..."})

@app.route('/api/ai/grade-essay', methods=['POST'])
def ai_grade_essay():
    data = request.json
    essay = data.get('essay', '')
    question = data.get('question', '')
    
    if not essay or not question:
        return jsonify({'error': 'Essay and question required'}), 400
    
    if not USE_AI:
        return jsonify({
            'score': 50,
            'feedback': 'Enable AI for detailed grading.',
            'strengths': [],
            'areas_for_improvement': [],
            'suggested_score': 50
        })
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator grading essays. Return only valid JSON."},
                {"role": "user", "content": f"Grade this essay.\nQuestion: {question}\n\nEssay: {essay}"}
            ],
            max_tokens=800,
            temperature=0.3
        )
        
        result_text = response['choices'][0]['message']['content']
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0]
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0]
        result_text = result_text.strip()
        
        return jsonify(json.loads(result_text))
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({
            'score': 50,
            'feedback': 'Error grading. Please try again.',
            'strengths': [],
            'areas_for_improvement': [],
            'suggested_score': 50
        })

@app.route('/api/ai/mindmap')
def get_mind_map():
    topic = request.args.get('topic', 'general')
    mind_map = {
        'topic': topic,
        'nodes': [
            {'id': '1', 'label': topic, 'children': [
                {'label': 'Definition', 'type': 'heading'},
                {'label': 'Key Concepts', 'type': 'heading'},
                {'label': 'Clinical Features', 'type': 'heading'},
                {'label': 'Diagnosis', 'type': 'heading'},
                {'label': 'Treatment', 'type': 'heading'}
            ]}
        ]
    }
    return jsonify(mind_map)

# ============================================================
# PWA & FAVICON ROUTES
# ============================================================
@app.route('/manifest.json')
def manifest():
    return {
        "name": "Health Study Hub",
        "short_name": "Health Hub",
        "description": "Health Sciences Study Platform",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "icons": [
            {"src": "/static/icons/icon-72x72.png", "sizes": "72x72", "type": "image/png"},
            {"src": "/static/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }

@app.route('/sw.js')
def service_worker():
    return """const CACHE_NAME = 'health-hub-v2';
const ASSETS = ['/'];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => keys.filter(k => k !== CACHE_NAME))
            .then(keys => Promise.all(keys.map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    e.respondWith(
        caches.match(e.request)
            .then(response => response || fetch(e.request))
            .catch(() => fetch('/'))
    );
});""", 200, {'Content-Type': 'application/javascript'}

@app.route('/favicon.ico')
def favicon():
    try:
        return send_file('static/favicon.ico', mimetype='image/x-icon')
    except:
        return '', 204

# ============================================================
# HEALTH CHECK
# ============================================================
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'users': len([f for f in os.listdir(USERS_DIR) if f.endswith('.json')]),
        'notes': len(get_all_notes()),
        'quizzes': len(get_all_quizzes()),
        'ai': USE_AI,
        'version': '2.0'
    })

# ============================================================
# CREATE DEFAULT USER ON STARTUP
# ============================================================
create_default_user()

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Health Study Hub v2.0 - AI Powered Complete Edition")
    print("="*60)
    print(f"📁 Data Directory: {DATA_DIR}")
    print(f"👤 Users: {len([f for f in os.listdir(USERS_DIR) if f.endswith('.json')])}")
    print(f"🤖 AI: {'ENABLED' if USE_AI else 'DISABLED'}")
    print(f"📚 Notes: {len(get_all_notes())}")
    print(f"📝 Quizzes: {len(get_all_quizzes())}")
    print("\n📋 Features:")
    print("  ✅ Study Notes & Modules")
    print("  ✅ Flashcards (with Creator)")
    print("  ✅ Quiz Bank (AI Graded - Intelligent)")
    print("  ✅ AI Generator (All Health Science Topics)")
    print("  ✅ Calculators & Lab Reference")
    print("  ✅ Case Simulator")
    print("  ✅ User Profile & Authentication")
    print("  ✅ Exam Simulator (AI Graded - Intelligent)")
    print("  ✅ Full Exam (18 MCQs + 2 Essays, 1 Hour Timer - AI Graded)")
    print("  ✅ AI-Powered Random Question Generator")
    print("  ✅ Productivity Dashboard")
    print("  ✅ Pomodoro Timer (25-120 min options)")
    print("  ✅ Progress Tracking")
    print("  ✅ Wrong Bank")
    print("  ✅ Cloud Sync")
    print("  ✅ Offline Support")
    print("  ✅ PWA (Install as App)")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=10000, debug=True)