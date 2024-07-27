import requests
from flask import Flask, render_template, request, flash, session, redirect, url_for
import os
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import google.generativeai as genai
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'bytecrafters'

# Create a new SQLite database connection
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# Create a table to store user information
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
""")
conn.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("You need to log in to access this page.", 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'user' not in session:
            flash("You need to log in to access this page.", 'error')
            return redirect(url_for('login'))

        search_term = request.form['searchbar']
        search_option = request.form['searchOption']

        prompt_text = ""
        if search_option == "By Food Name":
            prompt_text = f"your indian masterchef you know every indian recipe so tell me how to make {search_term} if its food then only response start with food name at top then ingredients, instructions, tips dont add extra spaces if {search_term} not  a food tell them what food ,and why  its called food in same structure as answer "
        elif search_option == "By Ingredients":
            prompt_text = f"your indian masterchef you know every indian recipe so tell me how to make a dish using {search_term}if its food then only as the primary ingredient response start with food name at top then ingredients, instructions, tips, dont add extra spaces if{search_term} is not a food tell them what food is ,and why its called food   "

        response = generate_recipe(prompt_text)
        generated_recipe = response.text

        session['generated_recipe'] = generated_recipe
        return redirect(url_for('results'))

    return render_template('index.html')

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

@app.route('/contactus')
def contactus():
    return render_template('contactus.html')

@app.route('/results')
@login_required
def results():
    generated_recipe_text = session.get('generated_recipe')

    if generated_recipe_text:
        generated_recipe = parse_generated_recipe(generated_recipe_text)
        food_name = generated_recipe['food_name']
        image_url = fetch_food_image(food_name)
        return render_template('results.html', generated_recipe=generated_recipe, image_url=image_url)
    else:
        flash("No recipe generated. Please try again.", 'error')
        return redirect(url_for('home'))


def parse_generated_recipe(generated_recipe_text):
    try:
        food_name = ""
        ingredients = ""
        instructions = ""
        tips = ""

        generated_recipe_text = generated_recipe_text.replace("", "").replace("\n\n", "\n").strip()
        sections = generated_recipe_text.split("Instructions:")

        if len(sections) > 1:
            food_name, ingredients_section = sections[0].split("Ingredients:")
            ingredients = ingredients_section.strip()

        if len(sections) > 1:
            instructions_and_tips = sections[1]
            if "Tips:" in instructions_and_tips:
                instructions, tips = instructions_and_tips.split("Tips:")
                tips = tips.strip()
            else:
                instructions = instructions_and_tips

        ingredients_list = [ingredient.strip("*") for ingredient in ingredients.split("\n")] if ingredients else []
        instructions_list = [step.strip("*").strip() for step in instructions.split("\n")] if instructions else []
        tips_list = [tip.strip("*").strip() for tip in tips.split("\n")] if tips else []

        return {
            "food_name": food_name.strip(),
            "ingredients": ingredients_list,
            "instructions": instructions_list,
            "tips": tips_list
        }
    except Exception as e:
        print(f"Error parsing generated recipe: {e}")
        return {}

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form['Name']
        username = request.form['Username']
        email = request.form['Email']
        password = request.form['Password']

        try:
            cursor.execute("INSERT INTO users (name, username, email, password) VALUES (?, ?, ?, ?)",
                           (name, username, email, password))
            conn.commit()
            flash("Registration successful!", 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already registered.", 'error')
        except Exception as e:
            flash(str(e), 'error')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()
            if user:
                session['user'] = user[0]  # Store the user ID in the session
                flash("Login successful!", 'success')
                return redirect(url_for('home'))
            else:
                flash("Invalid email or password.", 'error')
        except Exception as e:
            flash(str(e), 'error')

    return render_template('login.html')



def generate_recipe(prompt_text):
    genai.configure(api_key="AIzaSyCi9VO_ezaweZur7uSpAgQVsWKSRNoDnyc")

    generation_config = {
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    model = genai.GenerativeModel(model_name="gemini-pro",
                                  generation_config=generation_config,
                                  safety_settings=safety_settings)

    response = model.generate_content(prompt_text)
    return response



def fetch_food_image(food_name):
    
    search_query = f"{food_name} dish"
    url = f'https://www.google.co.in/search?q={search_query}&source=lnms&tbm=isch'
    image_tag = get_image_tag_from_page(url)

    if image_tag:
        image_url = image_tag.get('src')
        return image_url

    return "https://via.placeholder.com/400x300.png"

def get_image_tag_from_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    img_tags = soup.find_all('img')
    return img_tags[5] if img_tags else None

@app.route('/logout')
@login_required
def logout():
    session.pop('user', None)
    flash("You have been logged out.", 'info')
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
