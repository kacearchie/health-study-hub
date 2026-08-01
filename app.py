import os
import json
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import glob
import random
import hashlib
import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['DEBUG'] = True

DATA_DIR = 'data'
NOTES_DIR = os.path.join(DATA_DIR, 'notes')
QUIZZES_DIR = os.path.join(DATA_DIR, 'quizzes')
USERS_DIR = os.path.join(DATA_DIR, 'users')
COURSES_FILE = os.path.join(DATA_DIR, 'courses.json')

# ============================================================
# OPENAI SETUP - FOR VERSION 0.28.0
# ============================================================
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
USE_AI = OPENAI_API_KEY is not None and OPENAI_API_KEY != '' and OPENAI_API_KEY != 'your-openai-api-key-here'

if USE_AI:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        print("✅ OpenAI API key loaded successfully (v0.28.0)")
    except ImportError:
        print("⚠️ OpenAI library not installed. Run: pip install openai==0.28.0")
        USE_AI = False
    except Exception as e:
        print(f"⚠️ Error loading OpenAI: {e}")
        USE_AI = False
else:
    print("⚠️ No valid OpenAI API key found. AI features will use fallback responses.")

# Create users directory if it doesn't exist
if not os.path.exists(USERS_DIR):
    os.makedirs(USERS_DIR)

# Create static directories for PWA
if not os.path.exists('static'):
    os.makedirs('static')
if not os.path.exists('static/icons'):
    os.makedirs('static/icons')

# Cache
note_cache = {}
quiz_cache = {}
courses_cache = None
user_cache = {}

# ============================================================
# USER MANAGEMENT
# ============================================================

def get_user_file(username):
    return os.path.join(USERS_DIR, f"{username}.json")

def load_user(username):
    if username in user_cache:
        return user_cache[username]
    filepath = get_user_file(username)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            user_cache[username] = data
            return data
    except:
        return None

def save_user(username, data):
    filepath = get_user_file(username)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    user_cache[username] = data

# ============================================================
# CONTENT LOADING
# ============================================================

def load_courses():
    global courses_cache
    if courses_cache is None:
        try:
            with open(COURSES_FILE, 'r', encoding='utf-8') as f:
                courses_cache = json.load(f)
        except:
            courses_cache = {"courses": []}
    return courses_cache

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
        if 'content' in data and isinstance(data['content'], list):
            for item in data['content']:
                if isinstance(item, dict):
                    if 'questions' in item and isinstance(item['questions'], list):
                        return item['questions']
                    if 'quiz' in item and isinstance(item['quiz'], list):
                        return item['quiz']
                    if item.get('type') == 'quiz' and 'questions' in item:
                        return item['questions']
    return questions

def categorize_notes():
    all_notes = get_all_notes()
    categories = {}
    for note in all_notes:
        if 'Inorganic_Chemistry' in note:
            cat = 'Inorganic Chemistry'
        elif 'Organic_Chemistry' in note or 'Alcohols' in note or 'Carbonyl' in note:
            cat = 'Organic Chemistry'
        elif 'Anatomy' in note:
            cat = 'Anatomy'
        elif 'Physiology' in note:
            cat = 'Physiology'
        elif 'Biochemistry' in note:
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

# ============================================================
# PWA ROUTES
# ============================================================

@app.route('/manifest.json')
def manifest():
    """PWA manifest file"""
    return {
        "name": "Health Study Hub",
        "short_name": "Health Hub",
        "description": "Health Sciences Study Platform for MUST Students",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/static/icons/icon-72x72.png", "sizes": "72x72", "type": "image/png"},
            {"src": "/static/icons/icon-96x96.png", "sizes": "96x96", "type": "image/png"},
            {"src": "/static/icons/icon-128x128.png", "sizes": "128x128", "type": "image/png"},
            {"src": "/static/icons/icon-144x144.png", "sizes": "144x144", "type": "image/png"},
            {"src": "/static/icons/icon-152x152.png", "sizes": "152x152", "type": "image/png"},
            {"src": "/static/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-384x384.png", "sizes": "384x384", "type": "image/png"},
            {"src": "/static/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }

@app.route('/sw.js')
def service_worker():
    """Service worker for offline support"""
    return send_file('static/sw.js', mimetype='application/javascript')

@app.route('/offline')
def offline():
    """Offline fallback page"""
    return render_template('offline.html')

# ============================================================
# OFFLINE SYNC ROUTES
# ============================================================

@app.route('/api/offline/download', methods=['POST'])
def download_offline_content():
    """Download all content for offline use"""
    data = request.json
    user_id = data.get('user_id')
    
    offline_package = {
        'notes': {},
        'quizzes': {},
        'user_data': None,
        'version': '1.0',
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    # Download all notes
    for note_file in get_all_notes():
        note_data = load_note(note_file)
        if note_data:
            offline_package['notes'][note_file] = note_data
    
    # Download all quizzes
    for quiz_file in get_all_quizzes():
        quiz_data = load_quiz(quiz_file)
        if quiz_data:
            offline_package['quizzes'][quiz_file] = quiz_data
    
    # Download user data if logged in
    if user_id and user_id != 'guest':
        user_data = load_user(user_id)
        if user_data:
            offline_package['user_data'] = user_data
    
    return jsonify(offline_package)

@app.route('/api/offline/sync', methods=['POST'])
def sync_offline_data():
    """Sync offline changes back to server"""
    data = request.json
    user_id = data.get('user_id')
    offline_data = data.get('data', {})
    
    if user_id and user_id != 'guest':
        user_data = load_user(user_id)
        if user_data:
            # Merge offline changes
            if 'quiz_results' in offline_data:
                user_data['quiz_history'] = user_data.get('quiz_history', []) + offline_data['quiz_results']
            if 'wrong_answers' in offline_data:
                user_data['wrong_answers'] = user_data.get('wrong_answers', []) + offline_data['wrong_answers']
            if 'tasks' in offline_data:
                user_data['tasks'] = offline_data['tasks']
            if 'flashcards' in offline_data:
                user_data['flashcards'] = offline_data['flashcards']
            if 'study_time' in offline_data:
                user_data['study_time'] = user_data.get('study_time', 0) + offline_data['study_time']
            if 'topic_scores' in offline_data:
                for topic, score in offline_data['topic_scores'].items():
                    if topic in user_data.get('topic_scores', {}):
                        user_data['topic_scores'][topic] = max(user_data['topic_scores'][topic], score)
                    else:
                        user_data['topic_scores'][topic] = score
            
            save_user(user_id, user_data)
            return jsonify({'success': True, 'message': 'Data synced successfully'})
    
    return jsonify({'error': 'Sync failed'}), 400

# ============================================================
# MAIN API ROUTES
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
    filepath = os.path.join(QUIZZES_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except:
        return jsonify({'error': 'Quiz not found'}), 404

@app.route('/api/stats')
def get_stats():
    all_notes = get_all_notes()
    all_quizzes = get_all_quizzes()
    total_questions = 0
    for q in all_quizzes:
        filepath = os.path.join(QUIZZES_DIR, q)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'questions' in data:
                    total_questions += len(data['questions'])
                elif 'quiz' in data:
                    total_questions += len(data['quiz'])
        except:
            pass
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
        filepath = os.path.join(QUIZZES_DIR, quiz_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                questions = extract_questions_from_data(data)
                for q in questions:
                    if isinstance(q, dict):
                        q['source'] = get_note_title(quiz_file)
                        all_questions.append(q)
        except:
            pass
    random.shuffle(all_questions)
    return jsonify(all_questions)

# ============================================================
# USER ROUTES
# ============================================================

@app.route('/api/user/create', methods=['POST'])
def create_user():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if load_user(username):
        return jsonify({'error': 'Username already exists'}), 400
    
    user_data = {
        'username': username,
        'password_hash': hashlib.sha256(password.encode()).hexdigest(),
        'created_at': datetime.datetime.now().isoformat(),
        'study_time': 0,
        'streak': 0,
        'last_study_date': None,
        'quiz_history': [],
        'topic_scores': {},
        'mastered_concepts': [],
        'flashcards': [],
        'tasks': [],
        'clinical_skills': [],
        'wrong_answers': [],
        'activity_log': [],
        'study_groups': []
    }
    
    save_user(username, user_data)
    return jsonify({'success': True, 'username': username})

@app.route('/api/user/login', methods=['POST'])
def login_user():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user_data.get('password_hash') != password_hash:
        return jsonify({'error': 'Incorrect password'}), 401
    
    return jsonify({
        'success': True,
        'username': username,
        'user_data': {
            'study_time': user_data.get('study_time', 0),
            'streak': user_data.get('streak', 0),
            'quiz_history': user_data.get('quiz_history', []),
            'topic_scores': user_data.get('topic_scores', {})
        }
    })

@app.route('/api/user/<username>/data', methods=['GET', 'POST'])
def user_data(username):
    if request.method == 'GET':
        user_data = load_user(username)
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(user_data)
    
    elif request.method == 'POST':
        data = request.json
        user_data = load_user(username)
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        for key, value in data.items():
            if key in ['study_time', 'streak', 'last_study_date', 'quiz_history', 
                       'topic_scores', 'mastered_concepts', 'flashcards', 'tasks',
                       'clinical_skills', 'wrong_answers', 'activity_log']:
                user_data[key] = value
        
        save_user(username, user_data)
        return jsonify({'success': True})

# ============================================================
# AI ROUTES - FOR OPENAI V0.28.0
# ============================================================

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.json
    message = data.get('message', '')
    username = data.get('username', None)
    context = data.get('context', None)
    
    if not message:
        return jsonify({'response': 'Please ask a question.'})
    
    if not USE_AI:
        print("⚠️ Using fallback response (AI disabled)")
        return jsonify({'response': generate_fallback_response(message)})
    
    try:
        print("🔄 Calling OpenAI API for chat...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a helpful AI assistant for a Health Science Study Hub. 
                Your purpose is to help students learn about health sciences, medicine, pharmacy, nursing, and related fields.
                You provide accurate, educational information. Keep responses clear, concise, and engaging.
                Always be encouraging and supportive of the student's learning journey."""},
                {"role": "user", "content": message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        ai_response = response['choices'][0]['message']['content']
        print(f"✅ OpenAI response received")
        return jsonify({'response': ai_response})
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return jsonify({'response': generate_fallback_response(message)})

@app.route('/api/ai/generate-questions', methods=['POST'])
def ai_generate_questions():
    data = request.json
    topic = data.get('topic', 'general health science')
    count = min(data.get('count', 5), 20)
    question_type = data.get('type', 'mixed')
    
    if not USE_AI:
        print("⚠️ Using fallback questions (AI disabled)")
        return jsonify({'questions': generate_fallback_questions(topic, count, question_type)})
    
    try:
        prompt = f"""Generate {count} {question_type} questions about {topic} for medical/health science students.
        
        For multiple choice questions: Include 4 options and mark the correct answer index (0-3).
        For essay questions: Include a hint or guidance.
        
        Return ONLY a JSON array with this format:
        [
            {{
                "type": "mcq" or "essay",
                "question": "The question text",
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "explanation": "Brief explanation",
                "hint": "Study hint"
            }}
        ]
        
        Make questions challenging but appropriate for university-level students.
        """
        
        print(f"🔄 Calling OpenAI API for questions (topic: {topic})...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator creating high-quality assessment questions. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.8
        )
        
        questions_text = response['choices'][0]['message']['content']
        if '```json' in questions_text:
            questions_text = questions_text.split('```json')[1].split('```')[0]
        elif '```' in questions_text:
            questions_text = questions_text.split('```')[1].split('```')[0]
        questions = json.loads(questions_text)
        print(f"✅ Generated {len(questions)} questions")
        return jsonify({'questions': questions})
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return jsonify({'questions': generate_fallback_questions(topic, count, question_type)})

@app.route('/api/ai/generate-case', methods=['POST'])
def ai_generate_case():
    data = request.json
    specialty = data.get('specialty', 'general medicine')
    
    if not USE_AI:
        print("⚠️ Using fallback case (AI disabled)")
        return jsonify({'case': generate_fallback_case()})
    
    try:
        prompt = f"""Generate a detailed clinical case study in {specialty} for medical/health science students.
        
        Include:
        1. Patient demographics (age, gender, presentation)
        2. Chief complaint and history
        3. Physical examination findings
        4. Laboratory results
        5. 2-3 multiple choice questions with answers and rationale
        6. The correct diagnosis and treatment plan
        
        Return ONLY a JSON object with this format:
        {{
            "title": "Case title",
            "patient": "Patient presentation description",
            "labs": "Lab findings",
            "questions": [
                {{
                    "q": "Question text",
                    "options": ["A", "B", "C", "D"],
                    "answer": 0,
                    "rationale": "Explanation"
                }}
            ],
            "diagnosis": "Final diagnosis",
            "treatment": "Treatment plan"
        }}
        """
        
        print(f"🔄 Calling OpenAI API for case (specialty: {specialty})...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator creating realistic clinical cases. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.8
        )
        
        case_text = response['choices'][0]['message']['content']
        if '```json' in case_text:
            case_text = case_text.split('```json')[1].split('```')[0]
        elif '```' in case_text:
            case_text = case_text.split('```')[1].split('```')[0]
        case = json.loads(case_text)
        print(f"✅ Case generated: {case.get('title', 'Untitled')}")
        return jsonify({'case': case})
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return jsonify({'case': generate_fallback_case()})

@app.route('/api/ai/summarize', methods=['POST'])
def ai_summarize():
    data = request.json
    content = data.get('content', '')
    topic = data.get('topic', 'health science')
    
    if not content:
        return jsonify({'summary': 'No content provided'})
    
    if not USE_AI:
        print("⚠️ Using fallback summary (AI disabled)")
        return jsonify({'summary': generate_fallback_summary(content)})
    
    try:
        print("🔄 Calling OpenAI API for summary...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator. Summarize the following content into key takeaways for students."},
                {"role": "user", "content": f"Summarize this content about {topic} into 3-5 key bullet points: {content[:3000]}"}
            ],
            max_tokens=300,
            temperature=0.5
        )
        summary = response['choices'][0]['message']['content']
        print("✅ Summary generated")
        return jsonify({'summary': summary})
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return jsonify({'summary': generate_fallback_summary(content)})

@app.route('/api/ai/grade-essay', methods=['POST'])
def ai_grade_essay():
    data = request.json
    essay_text = data.get('essay', '')
    question = data.get('question', '')
    rubric = data.get('rubric', None)
    
    if not essay_text or not question:
        return jsonify({'error': 'Essay and question required'}), 400
    
    if not USE_AI:
        return jsonify({
            'score': 50,
            'feedback': 'AI grading is not available. Please check your OpenAI API key.',
            'strengths': ['Enable AI for detailed feedback.'],
            'areas_for_improvement': ['Enable AI to get specific feedback.'],
            'suggested_score': 50
        })
    
    try:
        prompt = f"""Grade this medical/health science essay answer based on the following rubric:
        
Question: {question}
Student Answer: {essay_text}

Rubric (score out of 100):
- Content Accuracy (40%): Is the information medically accurate?
- Completeness (30%): Does it cover all key points?
- Organization (15%): Is it well-structured and logical?
- Clarity (15%): Is it well-written and clear?

Provide:
1. A score out of 100
2. Detailed feedback
3. Strengths of the answer
4. Areas for improvement
5. Suggested score

Format as JSON:
{{
    "score": 0,
    "feedback": "",
    "strengths": [],
    "areas_for_improvement": [],
    "suggested_score": 0
}}
"""
        
        print("🔄 Calling OpenAI API for essay grading...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical educator grading student essays. Be fair and constructive."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.3
        )
        
        result_text = response['choices'][0]['message']['content']
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0]
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0]
        
        print("✅ Essay graded")
        return jsonify(json.loads(result_text))
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return jsonify({
            'score': 50,
            'feedback': 'Error grading essay. Please try again.',
            'strengths': [],
            'areas_for_improvement': [],
            'suggested_score': 50
        })

@app.route('/api/ai/mindmap')
def get_mind_map():
    topic = request.args.get('topic', 'general')
    mind_map = {
        'topic': topic,
        'nodes': []
    }
    
    notes = get_all_notes()
    for note in notes:
        if topic.lower() in note.lower():
            note_data = load_note(note)
            if note_data:
                node = {
                    'id': note,
                    'label': get_note_title(note),
                    'children': []
                }
                if note_data.get('content') and isinstance(note_data['content'], list):
                    for item in note_data['content'][:3]:
                        if item.get('type') == 'heading':
                            node['children'].append({
                                'label': item.get('text', ''),
                                'type': 'heading'
                            })
                mind_map['nodes'].append(node)
    
    return jsonify(mind_map)

# ============================================================
# USER ANALYTICS
# ============================================================

@app.route('/api/user/<username>/analytics')
def get_user_analytics(username):
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    analytics = {
        'total_study_time': user_data.get('study_time', 0),
        'total_quizzes_taken': len(user_data.get('quiz_history', [])),
        'average_quiz_score': 0,
        'concepts_mastered': len(user_data.get('mastered_concepts', [])),
        'weakest_topics': [],
        'recent_activity': user_data.get('activity_log', [])[-10:],
        'quiz_history': user_data.get('quiz_history', [])
    }
    
    quiz_history = user_data.get('quiz_history', [])
    if quiz_history:
        scores = [q.get('score', 0) for q in quiz_history]
        analytics['average_quiz_score'] = round(sum(scores) / len(scores), 1)
    
    topic_scores = user_data.get('topic_scores', {})
    if topic_scores:
        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1])
        analytics['weakest_topics'] = sorted_topics[:3]
    
    return jsonify(analytics)

@app.route('/api/user/<username>/recommendations')
def get_adaptive_recommendations(username):
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    recommendations = []
    topic_scores = user_data.get('topic_scores', {})
    all_topics = get_all_notes()
    
    for topic in all_topics:
        topic_name = get_note_title(topic)
        if topic_name not in topic_scores or topic_scores[topic_name] < 70:
            recommendations.append({
                'topic': topic_name,
                'filename': topic,
                'reason': 'Low mastery score' if topic_name in topic_scores else 'Not studied yet',
                'priority': 'High' if topic_name in topic_scores and topic_scores[topic_name] < 50 else 'Medium'
            })
    
    return jsonify(sorted(recommendations, key=lambda x: 0 if x['priority'] == 'High' else 1)[:10])

@app.route('/api/user/<username>/reminders')
def get_reminders(username):
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    reminders = []
    last_study = user_data.get('last_study_date')
    if last_study:
        last_date = datetime.datetime.fromisoformat(last_study)
        today = datetime.datetime.now()
        if (today - last_date).days > 1:
            reminders.append({
                'type': 'study_reminder',
                'message': 'You haven\'t studied in a while. Time to review! 📚',
                'priority': 'high'
            })
    
    topic_scores = user_data.get('topic_scores', {})
    weak_topics = [t for t, s in topic_scores.items() if s < 50]
    if weak_topics:
        reminders.append({
            'type': 'weak_topic_reminder',
            'message': f'You need to review: {", ".join(weak_topics[:3])} 📖',
            'priority': 'high'
        })
    
    return jsonify(reminders)

@app.route('/api/user/<username>/groups', methods=['GET', 'POST'])
def study_groups(username):
    if request.method == 'GET':
        user_data = load_user(username)
        if not user_data:
            return jsonify([])
        return jsonify(user_data.get('study_groups', []))
    
    elif request.method == 'POST':
        data = request.json
        group_name = data.get('name', '')
        members = data.get('members', [])
        
        if not group_name:
            return jsonify({'error': 'Group name required'}), 400
        
        user_data = load_user(username)
        if not user_data:
            user_data = {}
        
        if 'study_groups' not in user_data:
            user_data['study_groups'] = []
        
        group = {
            'id': hashlib.md5(f"{username}{group_name}{datetime.datetime.now()}".encode()).hexdigest()[:8],
            'name': group_name,
            'created_by': username,
            'members': [username] + members,
            'created_at': datetime.datetime.now().isoformat(),
            'shared_notes': [],
            'shared_quizzes': []
        }
        
        user_data['study_groups'].append(group)
        save_user(username, user_data)
        
        for member in members:
            member_data = load_user(member)
            if member_data:
                if 'study_groups' not in member_data:
                    member_data['study_groups'] = []
                member_data['study_groups'].append(group)
                save_user(member, member_data)
        
        return jsonify(group)

@app.route('/api/user/<username>/export')
def export_data(username):
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    export = {
        'user': username,
        'export_date': datetime.datetime.now().isoformat(),
        'study_data': {
            'total_study_time': user_data.get('study_time', 0),
            'quiz_history': user_data.get('quiz_history', []),
            'topic_scores': user_data.get('topic_scores', {}),
            'mastered_concepts': user_data.get('mastered_concepts', []),
            'flashcards': user_data.get('flashcards', []),
            'tasks': user_data.get('tasks', []),
            'clinical_skills': user_data.get('clinical_skills', []),
            'wrong_answers': user_data.get('wrong_answers', [])
        }
    }
    return jsonify(export)

@app.route('/api/user/<username>/clinical-skills', methods=['POST'])
def update_clinical_skills(username):
    data = request.json
    skill_id = data.get('skill_id')
    completed = data.get('completed', True)
    
    user_data = load_user(username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    skills = user_data.get('clinical_skills', [])
    if skill_id in skills:
        if not completed:
            skills.remove(skill_id)
    else:
        if completed:
            skills.append(skill_id)
    
    user_data['clinical_skills'] = skills
    save_user(username, user_data)
    return jsonify({'success': True, 'skills': skills})

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
        {"id": "chest_xray", "name": "Chest X-Ray Interpretation", "category": "Diagnostic"},
        {"id": "cpr", "name": "CPR and Basic Life Support", "category": "Emergency"},
        {"id": "airway_management", "name": "Airway Management", "category": "Emergency"},
        {"id": "suturing", "name": "Suturing Techniques", "category": "Procedure"},
        {"id": "intubation", "name": "Endotracheal Intubation", "category": "Procedure"},
        {"id": "patient_counseling", "name": "Patient Counseling", "category": "Communication"},
        {"id": "medication_admin", "name": "Medication Administration", "category": "Pharmacology"},
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
        "erythema": "er-ih-THEE-mah",
        "anaphylaxis": "an-ah-fih-LAK-sis",
        "analgesia": "an-al-JEE-zee-ah",
        "anesthesia": "an-es-THEE-zee-ah",
        "antibiotic": "an-ti-by-OT-ik",
        "diuretic": "dye-yoo-RET-ik",
        "metabolism": "meh-TAB-oh-liz-um",
        "homeostasis": "ho-mee-oh-STAY-sis",
        "pharmacokinetics": "far-ma-ko-kih-NET-iks",
        "pharmacodynamics": "far-ma-ko-dye-NAM-iks"
    }
    
    results = []
    for term, pron in medical_terms.items():
        if query in term or query in pron.lower():
            results.append({'term': term, 'pronunciation': pron})
    
    return jsonify(results)

# ============================================================
# FALLBACK FUNCTIONS
# ============================================================

def generate_fallback_response(message):
    lower_msg = message.lower()
    if 'heart' in lower_msg or 'cardiac' in lower_msg:
        return "💓 The cardiovascular system: The heart has 4 chambers. The SA node is the pacemaker (60-100 bpm). Cardiac output = Heart Rate × Stroke Volume (~5 L/min at rest)."
    if 'kidney' in lower_msg or 'renal' in lower_msg:
        return "🧪 The kidneys filter blood to produce urine. Key functions: waste removal, fluid balance, electrolyte regulation. Creatinine and BUN are key markers."
    if 'liver' in lower_msg or 'hepatic' in lower_msg:
        return "🔬 The liver performs metabolism, detoxification, protein synthesis, and bile production. ALT and AST are liver enzymes."
    if 'lab' in lower_msg or 'value' in lower_msg:
        return "📊 Common Lab Values:\n• Hemoglobin: 13.8-17.2 g/dL (M), 12.1-15.1 g/dL (F)\n• Creatinine: 0.7-1.3 mg/dL\n• Fasting Glucose: 70-99 mg/dL\n• Potassium: 3.5-5.0 mEq/L"
    if 'dosage' in lower_msg or 'calculate' in lower_msg:
        return "💊 Dosage Formula: Amount = (Desired Dose / Dose on Hand) × Vehicle\n• IV Drip Rate = (Volume × Drip Factor) / Time in Minutes"
    if 'hello' in lower_msg or 'hi' in lower_msg:
        return "👋 Hello! I'm your AI Study Assistant. I can help with:\n• 📖 Anatomy, physiology, and pharmacology\n• 🧪 Lab values\n• 💊 Dosage calculations\n• 🩺 Clinical cases\n• 📝 Exam prep\n\nWhat would you like to learn about?"
    return f"🤔 That's a great question! I'd recommend checking the relevant study notes or quizzes in the app."

def generate_fallback_questions(topic, count, question_type):
    questions = []
    mcq_count = count if question_type == 'mcq' else count // 2 if question_type == 'mixed' else 0
    essay_count = count - mcq_count
    
    question_bank = [
        {"question": f"What is the primary function of the {topic}?", "options": ["Option A", "Option B", "Option C", "Option D"], "answer": 0},
        {"question": f"Which condition is most commonly associated with {topic}?", "options": ["Condition 1", "Condition 2", "Condition 3", "Condition 4"], "answer": 0},
        {"question": f"What is the first-line treatment for {topic}?", "options": ["Treatment A", "Treatment B", "Treatment C", "Treatment D"], "answer": 0},
    ]
    
    for i in range(min(mcq_count, len(question_bank))):
        q = question_bank[i % len(question_bank)]
        questions.append({
            "type": "mcq",
            "question": q["question"],
            "options": q["options"],
            "answer": q["answer"],
            "explanation": "AI not available. Using fallback."
        })
    
    for i in range(essay_count):
        questions.append({
            "type": "essay",
            "question": f"Discuss the pathophysiology, clinical presentation, and management of {topic}.",
            "hint": "Consider the underlying mechanisms, clinical features, and evidence-based approaches."
        })
    
    return questions

def generate_fallback_case():
    return {
        "title": "Sample Clinical Case",
        "patient": "Patient presents with symptoms related to the selected specialty.",
        "labs": "Lab results would be shown here.",
        "questions": [
            {
                "q": "What is the most likely diagnosis?",
                "options": ["Diagnosis A", "Diagnosis B", "Diagnosis C", "Diagnosis D"],
                "answer": 0,
                "rationale": "This is the most likely diagnosis based on the presentation."
            }
        ],
        "diagnosis": "Sample Diagnosis",
        "treatment": "Standard treatment protocol would be described here."
    }

def generate_fallback_summary(content):
    sentences = content.split('.')[:3]
    return f"📌 Key takeaways: {'. '.join(sentences)}..."

# ============================================================
# HEALTH CHECK
# ============================================================

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Health Study Hub is running!'})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Health Study Hub Server Starting...")
    print(f"🤖 AI Status: {'ENABLED (v0.28.0)' if USE_AI else 'DISABLED'}")
    if USE_AI:
        print(f"🔑 OpenAI API Key: {OPENAI_API_KEY[:15]}...")
    print("📱 PWA Mode: ENABLED")
    print("📶 Offline Mode: ENABLED")
    print("="*50 + "\n")
    
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True
    )