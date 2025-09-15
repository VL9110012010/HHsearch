import os
import webbrowser
import requests
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from dotenv import load_dotenv, set_key
import threading
import time
import logging
import re
import google.generativeai as genai
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Глобальные переменные и константы ---
# Загружаем переменные из .env, если он существует
load_dotenv()

HH_CLIENT_ID = os.getenv("HH_CLIENT_ID")
HH_CLIENT_SECRET = os.getenv("HH_CLIENT_SECRET")
HH_REDIRECT_URI = os.getenv("HH_REDIRECT_URI", "http://localhost:8080/") # Значение по умолчанию
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
USER_GENDER = os.getenv("USER_GENDER")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma-3-27b-it")

APPLIED_VACANCIES_FILE = "applied_vacancies.txt"
REJECTED_VACANCIES_FILE = "rejected_vacancies.txt"
COVER_LETTERS_DIR = "cover_letters"

access_token = None
resumes = {}
resume_cache = {}
auto_send_thread = None
stop_event = threading.Event()
httpd = None

applied_vacancy_ids = set()
rejected_vacancy_ids = set()

# --- Функции для работы с файлами ---
def load_ids_from_file(filename, id_set):
    """Универсальная функция для загрузки ID из файла в набор."""
    try:
        with open(filename, "r") as f:
            for line in f:
                vacancy_id = line.strip()
                if vacancy_id:
                    id_set.add(vacancy_id)
        logging.info(f"Загружено {len(id_set)} ID из файла {filename}.")
    except FileNotFoundError:
        logging.info(f"Файл {filename} не найден. Будет создан новый.")
    except Exception as e:
        logging.exception(f"Ошибка при загрузке файла {filename}: {e}")

def save_id_to_file(filename, vacancy_id):
    """Универсальная функция для сохранения ID в файл."""
    try:
        with open(filename, "a") as f:
            f.write(f"{vacancy_id}\n")
        logging.info(f"ID вакансии {vacancy_id} сохранен в файл {filename}.")
    except Exception as e:
        logging.exception(f"Не удалось сохранить ID {vacancy_id} в файл {filename}: {e}")

def load_applied_vacancies():
    load_ids_from_file(APPLIED_VACANCIES_FILE, applied_vacancy_ids)

def save_applied_vacancy(vacancy_id):
    save_id_to_file(APPLIED_VACANCIES_FILE, vacancy_id)

def load_rejected_vacancies():
    load_ids_from_file(REJECTED_VACANCIES_FILE, rejected_vacancy_ids)

def save_rejected_vacancy(vacancy_id):
    save_id_to_file(REJECTED_VACANCIES_FILE, vacancy_id)

def save_cover_letter(vacancy_id, vacancy_name, letter_text):
    """Сохраняет сгенерированное сопроводительное письмо в отдельный файл."""
    try:
        os.makedirs(COVER_LETTERS_DIR, exist_ok=True)
        safe_vacancy_name = re.sub(r'[\/*?:"<>|]', "", vacancy_name)
        filename = os.path.join(COVER_LETTERS_DIR, f"vacancy_{vacancy_id}_{safe_vacancy_name}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(letter_text)
        logging.info(f"Сопроводительное письмо для вакансии {vacancy_id} сохранено в файл: {filename}")
    except Exception as e:
        logging.exception(f"Не удалось сохранить сопроводительное письмо для вакансии {vacancy_id}: {e}")

# --- Функции для работы с резюме ---
def get_resume_details(resume_id):
    if resume_id in resume_cache:
        logging.info(f"Используем кэшированные данные резюме {resume_id}")
        return resume_cache[resume_id]
    if not access_token:
        logging.error("Токен доступа не найден")
        return None
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(f'https://api.hh.ru/resumes/{resume_id}', headers=headers)
        response.raise_for_status()
        resume_data = response.json()
        resume_cache[resume_id] = resume_data
        logging.info(f"Успешно загружены данные резюме {resume_id}")
        return resume_data
    except requests.exceptions.RequestException as e:
        logging.error(f"Не удалось получить данные резюме {resume_id}: {e}")
        return None

def format_resume_for_prompt(resume_data):
    if not resume_data:
        return ""
    # (Код этой функции остается без изменений, поэтому скрыт для краткости)
    formatted_resume = []
    if resume_data.get('title'):
        formatted_resume.append(f"Специализация: {resume_data['title']}")
    experience = resume_data.get('experience', [])
    if experience:
        formatted_resume.append("\nОпыт работы:")
        for exp in experience[:3]:
            company = exp.get('company', 'Неизвестная компания')
            position = exp.get('position', 'Неизвестная должность')
            start_str = exp.get('start')
            start_date = 'неизвестно'
            if start_str and isinstance(start_str, str):
                parts = start_str.split('-')
                if len(parts) >= 2:
                    start_date = f"{parts[1]}.{parts[0]}"
            end_str = exp.get('end')
            end_date = 'настоящее время'
            if end_str and isinstance(end_str, str):
                parts = end_str.split('-')
                if len(parts) >= 2:
                    end_date = f"{parts[1]}.{parts[0]}"
            formatted_resume.append(f"- {position} в {company} ({start_date} - {end_date})")
            description = exp.get('description', '')
            if description:
                clean_description = re.sub('<[^<]+?>', '', description).strip()[:200]
                formatted_resume.append(f"  Обязанности: {clean_description}")
    skills = resume_data.get('key_skills', [])
    if skills:
        skill_names = [skill.get('name', '') for skill in skills[:10]]
        formatted_resume.append(f"\nКлючевые навыки: {', '.join(skill_names)}")
    education_data = resume_data.get('education') or {}
    education = education_data.get('primary', [])
    if education:
        formatted_resume.append(f"\nОбразование:")
        for edu in education[:2]:
            name = edu.get('name', '')
            organization = edu.get('organization', '')
            year = edu.get('year', '')
            if name and organization:
                formatted_resume.append(f"- {name}, {organization} ({year})")
    languages = resume_data.get('language', [])
    if languages:
        lang_list = [f"{lang.get('name', '')} ({lang.get('level', {}).get('name', '')})" for lang in languages if lang.get('name') and lang.get('level', {}).get('name')]
        if lang_list:
            formatted_resume.append(f"\nЯзыки: {', '.join(lang_list)}")
    return '\n'.join(formatted_resume)


# --- Функции для работы с LLM ---
def generate_cover_letter(vacancy_details, resume_data=None):
    if not GOOGLE_API_KEY:
        logging.error("GOOGLE_API_KEY не найден в .env файле.")
        return None
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(MODEL_NAME)
        
        gender_instruction = ""
        if USER_GENDER == "Мужчина":
            gender_instruction = "Обязательно пиши от лица мужчины. Используй глаголы и прилагательные в мужском роде (например, 'выполнил', 'уверен', 'профессиональный')."
        elif USER_GENDER == "Женщина":
            gender_instruction = "Обязательно пиши от лица женщины. Используй глаголы и прилагательные в женском роде (например, 'выполнила', 'уверена', 'профессиональная')."

        system_prompt = (
            f"Ты - высококлассный специалист по написанию персонализированных сопроводительных писем. {gender_instruction} "
            "Твоя задача: На основе вакансии и резюме создать сопроводительное письмо от первого лица. "
            "ЗАПРЕЩЕНО: Придумывать навыки, которых нет в резюме; давать советы; добавлять пояснения; использовать заполнители типа '[Ваше имя]'; включать инструкции. "
            "ФОРМАТ ОТВЕТА: ТОЛЬКО готовое сопроводительное письмо без каких-либо дополнений. "
            "ПРИНЦИПЫ: 1. Точность - используй ТОЛЬКО данные из резюме. 2. Релевантность - подчеркивай пересечения между вакансией и резюме. 3. Структура - зацепка, релевантность, ценность, призыв к действию. 4. Краткость: 150-250 слов. "
            "КРИТИЧЕСКИ ВАЖНО: Твой ответ должен содержать ИСКЛЮЧИТЕЛЬНО готовое к отправке сопроводительное письмо."
        )

        clean_description = re.sub('<[^<]+?>', '', vacancy_details.get('description', ''))
        vacancy_info = f"Название: {vacancy_details.get('name')}\nКомпания: {vacancy_details.get('employer', {}).get('name')}\nОписание:\n{clean_description}"
        
        resume_info = ""
        if resume_data:
            formatted_resume = format_resume_for_prompt(resume_data)
            if formatted_resume:
                resume_info = f"\n\nДанные резюме кандидата:\n{formatted_resume}"
        
        prompt_content = f"Вот информация о вакансии:\n\n{vacancy_info}{resume_info}"
        full_prompt = f"{system_prompt}\n\n{prompt_content}"
        
        logging.info(f"Отправка запроса в LLM для вакансии {vacancy_details.get('id')}...")
        response = model.generate_content(full_prompt)
        generated_text = response.text
        logging.info(f"Ответ от LLM для вакансии {vacancy_details.get('id')} успешно получен.")
        return generated_text

    except Exception as e:
        logging.exception(f"Ошибка при генерации сопроводительного письма через LLM: {e}")
        return None

# --- Функции для работы с API hh.ru ---
def get_access_token(auth_code):
    global access_token
    logging.info(f"Попытка получить токен доступа с кодом: {auth_code}")
    data = {
        'grant_type': 'authorization_code',
        'client_id': HH_CLIENT_ID,
        'client_secret': HH_CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': HH_REDIRECT_URI
    }
    try:
        response = requests.post('https://hh.ru/oauth/token', data=data)
        response.raise_for_status()
        access_token = response.json()['access_token']
        logging.info("Токен доступа успешно получен.")
        messagebox.showinfo("Успех", "Авторизация прошла успешно!")
        show_main_window()
    except requests.exceptions.RequestException as e:
        logging.exception("Ошибка при получении токена доступа.")
        messagebox.showerror("Ошибка", f"Не удалось получить токен: {e}")

def get_resumes():
    global resumes
    if not access_token: return
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get('https://api.hh.ru/resumes/mine', headers=headers)
        response.raise_for_status()
        resumes_data = response.json().get('items', [])
        resumes = {f"{r['title']} ({r['id']})": r['id'] for r in resumes_data}
        logging.info(f"Загружено {len(resumes)} резюме.")
        root.after(0, update_resume_combobox, list(resumes.keys()))
    except requests.exceptions.RequestException:
        logging.exception("Ошибка при загрузке резюме.")
        messagebox.showerror("Ошибка", "Не удалось загрузить резюме.")

def search_vacancies(params):
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get('https://api.hh.ru/vacancies', headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.exception("Ошибка при поиске вакансий.")
        root.after(0, messagebox.showerror, "Ошибка", f"Ошибка при поиске вакансий: {e}")
        return None

def get_vacancy_details(vacancy_id):
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(f'https://api.hh.ru/vacancies/{vacancy_id}', headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Не удалось получить детали вакансии {vacancy_id}: {e}")
        return None

def apply_to_vacancy(vacancy_id, resume_id, message):
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'resume_id': resume_id, 'vacancy_id': vacancy_id, 'message': message}
    try:
        response = requests.post('https://api.hh.ru/negotiations', headers=headers, params=params)
        if response.status_code == 201:
            logging.info(f"Успешный отклик на вакансию {vacancy_id}")
            return True, "Успешно"
        response.raise_for_status()
        return False, f"Неожиданный статус-код: {response.status_code}"
    except requests.exceptions.RequestException as e:
        error_description = str(e)
        if e.response is not None:
            try:
                error_info = e.response.json()
                error_description = error_info.get('description', str(e))
                if e.response.status_code == 400:
                    for error in error_info.get('errors', []):
                        if error.get('type') == 'bad_argument' and 'negotiation_exists' in str(error.get('value')):
                            logging.info(f"Пропускаем вакансию {vacancy_id}: отклик уже существует.")
                            return False, "уже откликались"
            except ValueError:
                error_description = e.response.text
        logging.error(f"Не удалось откликнуться на вакансию {vacancy_id}: {error_description}")
        return False, error_description

# --- Логика автоматической отправки ---
def auto_send_logic():
    # (Код этой функции остается без изменений, поэтому скрыт для краткости)
    params = {
        'text': keyword_entry.get(),
        'order_by': 'publication_time',
        'per_page': 50
    }
    if area_entry.get():
        params['area'] = area_entry.get()

    params['only_with_salary'] = salary_only_var.get()

    if salary_entry.get().isdigit():
        params['salary'] = int(salary_entry.get())
        params['currency'] = 'RUR'

    search_depth = int(search_depth_entry.get()) if search_depth_entry.get().isdigit() else 5
    exclude_words = [word.strip() for word in exclude_keyword_entry.get().lower().split(',') if word.strip()]
    min_keywords_required = int(min_keywords_entry.get()) if min_keywords_entry.get().isdigit() else 1
    keywords = [word.strip() for word in keyword_entry.get().lower().split(',') if word.strip()]

    selected_resume_title = resume_combobox.get()
    if not selected_resume_title:
        root.after(0, messagebox.showwarning, "Внимание", "Пожалуйста, выберите резюме.")
        root.after(0, stop_auto_send)
        return
    resume_id = resumes[selected_resume_title]

    resume_data = get_resume_details(resume_id)
    if not resume_data:
        logging.warning("Не удалось загрузить данные резюме. Письма будут генерироваться без них.")

    # Главный цикл, который повторяется раз в час
    while not stop_event.is_set():
        logging.info(f"=== Начинаю новый цикл поиска вакансий. Глубина поиска: {search_depth} страниц. ===")
        
        # Цикл по страницам
        for page in range(search_depth):
            if stop_event.is_set():
                logging.info("Получен сигнал остановки, прекращаю цикл.")
                break

            params['page'] = page
            logging.info(f"Запрашиваю страницу {page}...")
            
            response_data = search_vacancies(params)
            if not response_data:
                logging.warning(f"Не удалось получить данные для страницы {page}. Пропускаю.")
                continue

            vacancies = response_data.get('items', [])
            if not vacancies:
                logging.info(f"На странице {page} не найдено вакансий. Завершаю цикл.")
                break
            
            logging.info(f"Страница {page}: получено {len(vacancies)} вакансий.")
            known_vacancies_on_page = 0

            # Шаг 2: Проверка каждой вакансии на странице
            for vacancy in vacancies:
                if stop_event.is_set():
                    break
                
                vacancy_id = vacancy['id']
                vacancy_name = vacancy['name']

                if vacancy_id in applied_vacancy_ids:
                    logging.info(f"Вакансия '{vacancy_name}' ({vacancy_id}) уже в списке 'applied'. Пропускаю.")
                    known_vacancies_on_page += 1
                    continue
                
                if vacancy_id in rejected_vacancy_ids:
                    logging.info(f"Вакансия '{vacancy_name}' ({vacancy_id}) уже в списке 'rejected'. Пропускаю.")
                    known_vacancies_on_page += 1
                    continue

                logging.info(f"Найдена новая вакансия '{vacancy_name}' ({vacancy_id}). Загружаю детали...")
                time.sleep(1) 
                details = get_vacancy_details(vacancy_id)
                if not details:
                    logging.warning(f"Не удалось получить детали для вакансии {vacancy_id}, пропускаю.")
                    continue
                
                full_text = (details.get('name', '') + ' ' + re.sub('<[^<]+?>', '', details.get('description', ''))).lower()
                
                found_stop_word = False
                for stop_word in exclude_words:
                    if stop_word in full_text:
                        logging.info(f"Вакансия '{vacancy_name}' ({vacancy_id}) отклонена: найдено стоп-слово '{stop_word}'.")
                        rejected_vacancy_ids.add(vacancy_id)
                        save_rejected_vacancy(vacancy_id)
                        found_stop_word = True
                        break
                if found_stop_word:
                    continue
                
                matched_keywords_count = sum(1 for keyword in keywords if keyword in full_text)
                if matched_keywords_count < min_keywords_required:
                    logging.info(f"Вакансия '{vacancy_name}' ({vacancy_id}) отклонена: найдено {matched_keywords_count} из {min_keywords_required} ключевых слов.")
                    rejected_vacancy_ids.add(vacancy_id)
                    save_rejected_vacancy(vacancy_id)
                    continue

                logging.info(f"Вакансия '{vacancy_name}' ({vacancy_id}) подходит по критериям. Генерирую письмо...")
                generated_letter = generate_cover_letter(details, resume_data)
                
                if not generated_letter:
                    logging.error(f"Не удалось сгенерировать письмо для вакансии {vacancy_id}, пропускаю.")
                    continue

                logging.info(f"Отправляю отклик на вакансию '{vacancy_name}' ({vacancy_id})...")
                success, reason = apply_to_vacancy(vacancy_id, resume_id, generated_letter)
                
                applied_vacancy_ids.add(vacancy_id)
                save_applied_vacancy(vacancy_id)

                if success:
                    save_cover_letter(vacancy_id, vacancy_name, generated_letter)
                    root.after(0, add_to_sent_list, vacancy['employer']['name'], vacancy['alternate_url'])
                
                time.sleep(5) 

            if known_vacancies_on_page == len(vacancies):
                logging.info(f"Все {len(vacancies)} вакансий на странице {page} уже были обработаны ранее. Досрочно завершаю поиск.")
                break
        
        logging.info("Цикл поиска завершен. Следующая проверка через 1 час.")
        stop_event.wait(3600)

# --- Функции для GUI и запуска ---
def start_server_and_authorize():
    global httpd
    try:
        port = urlparse(HH_REDIRECT_URI).port
        if not port:
            raise ValueError("Порт не указан в HH_REDIRECT_URI.")
    except Exception as e:
        messagebox.showerror("Ошибка конфигурации", str(e))
        return

    class AuthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            auth_code = parse_qs(urlparse(self.path).query).get('code', [None])[0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            if auth_code:
                success_message = "<html><body><h1>Успешно!</h1><p>Можно закрыть эту вкладку.</p></body></html>"
                self.wfile.write(success_message.encode('utf-8'))
                root.after(0, get_access_token, auth_code)
            else:
                error_message = "<html><body><h1>Ошибка!</h1><p>Не удалось получить код авторизации.</p></body></html>"
                self.wfile.write(error_message.encode('utf-8'))
            
            threading.Thread(target=httpd.shutdown, daemon=True).start()

        def log_message(self, format, *args):
            return

    try:
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("localhost", port), AuthHandler)
        logging.info(f"Запуск сервера на порту {port}...")
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        webbrowser.open(f"https://hh.ru/oauth/authorize?response_type=code&client_id={HH_CLIENT_ID}&redirect_uri={HH_REDIRECT_URI}")
    except Exception as e:
        logging.exception(f"Не удалось запустить сервер на порту {port}.")
        messagebox.showerror("Ошибка", f"Не удалось запустить сервер на порту {port}: {e}")

def update_resume_combobox(resume_keys):
    resume_combobox['values'] = resume_keys
    if resume_keys:
        resume_combobox.current(0)
    load_settings()

def start_auto_send():
    global auto_send_thread
    if auto_send_thread and auto_send_thread.is_alive(): return
    if not GOOGLE_API_KEY:
        messagebox.showerror("Ошибка", "Ключ GOOGLE_API_KEY не найден.")
        return
    save_settings()
    stop_event.clear()
    logging.info("Запуск автоматической отправки откликов.")
    auto_send_button.config(text="Остановить автоотправку", command=stop_auto_send)
    status_label.config(text="Статус: Автоотправка запущена", style="Green.TLabel")
    auto_send_thread = threading.Thread(target=auto_send_logic, daemon=True)
    auto_send_thread.start()

def stop_auto_send():
    logging.info("Остановка автоматической отправки откликов.")
    stop_event.set()
    auto_send_button.config(text="Запустить автоотправку", command=start_auto_send)
    status_label.config(text="Статус: Автоотправка остановлена", style="Red.TLabel")

def add_to_sent_list(company_name, vacancy_url):
    def open_link(url):
        webbrowser.open(url, new=2)
    company_label = tk.Label(sent_list_frame, text=company_name, fg="blue", cursor="hand2")
    company_label.pack(anchor="w")
    company_label.bind("<Button-1>", lambda e, url=vacancy_url: open_link(url))

def save_settings():
    try:
        with open("settings.txt", "w", encoding="utf-8") as f:
            f.write(f"keyword={keyword_entry.get()}\n")
            f.write(f"exclude_keyword={exclude_keyword_entry.get()}\n")
            f.write(f"area={area_entry.get()}\n")
            f.write(f"resume={resume_combobox.get()}\n")
            f.write(f"salary_from={salary_entry.get()}\n")
            f.write(f"only_with_salary={salary_only_var.get()}\n")
            f.write(f"min_keywords={min_keywords_entry.get()}\n")
            f.write(f"search_depth={search_depth_entry.get()}\n")
        logging.info("Параметры поиска сохранены.")
    except Exception as e:
        logging.exception("Не удалось сохранить настройки.")
        messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {e}")

def load_settings():
    try:
        with open("settings.txt", "r", encoding="utf-8") as f:
            settings = dict(line.strip().split("=", 1) for line in f if "=" in line)
        keyword_entry.delete(0, tk.END); keyword_entry.insert(0, settings.get("keyword", ""))
        exclude_keyword_entry.delete(0, tk.END); exclude_keyword_entry.insert(0, settings.get("exclude_keyword", ""))
        area_entry.delete(0, tk.END); area_entry.insert(0, settings.get("area", ""))
        salary_entry.delete(0, tk.END); salary_entry.insert(0, settings.get("salary_from", ""))
        min_keywords_entry.delete(0, tk.END); min_keywords_entry.insert(0, settings.get("min_keywords", "1"))
        search_depth_entry.delete(0, tk.END); search_depth_entry.insert(0, settings.get("search_depth", "5"))
        salary_only_var.set(settings.get("only_with_salary", "False").lower() == "true")
        if (resume_to_set := settings.get("resume", "")) and resume_to_set in resume_combobox['values']:
            resume_combobox.set(resume_to_set)
        logging.info("Настройки успешно загружены.")
    except FileNotFoundError:
        logging.info("Файл настроек не найден.")
    except Exception as e:
        logging.exception("Не удалось загрузить настройки.")
        messagebox.showerror("Ошибка", f"Не удалось загрузить настройки: {e}")

def on_closing():
    logging.info("Приложение закрывается.");
    stop_auto_send()
    if httpd:
        httpd.shutdown()
    root.destroy()

# --- Функции для первоначальной настройки ---
def save_keys_and_proceed():
    """Сохраняет введенные ключи в .env и переходит к авторизации."""
    hh_id = hh_client_id_entry.get()
    hh_secret = hh_client_secret_entry.get()
    google_key = google_api_key_entry.get()
    gender = gender_var.get()

    if not all([hh_id, hh_secret, google_key, gender]):
        messagebox.showwarning("Ошибка", "Пожалуйста, заполните все поля.")
        return

    try:
        if not os.path.exists('.env'):
            with open('.env', 'w') as f:
                f.write('')
        
        set_key('.env', 'HH_CLIENT_ID', hh_id)
        set_key('.env', 'HH_CLIENT_SECRET', hh_secret)
        set_key('.env', 'GOOGLE_API_KEY', google_key)
        set_key('.env', 'USER_GENDER', gender)
        set_key('.env', 'HH_REDIRECT_URI', "http://localhost:8080/")

        global HH_CLIENT_ID, HH_CLIENT_SECRET, GOOGLE_API_KEY, USER_GENDER, HH_REDIRECT_URI
        HH_CLIENT_ID = hh_id
        HH_CLIENT_SECRET = hh_secret
        GOOGLE_API_KEY = google_key
        USER_GENDER = gender
        HH_REDIRECT_URI = "http://localhost:8080/"
        
        logging.info("Ключи API и пол пользователя успешно сохранены в .env")
        
        setup_frame.pack_forget()
        auth_frame.pack(fill="both", expand=True)

    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить файл .env: {e}")
        logging.exception("Ошибка при сохранении .env файла.")

def open_hyperlink(url):
    webbrowser.open_new(url)

# >>>>> НАЧАЛО НОВОГО БЛОКА <<<<<
def make_entry_context_menu(entry):
    """Создает контекстное меню для поля ввода (Вырезать, Копировать, Вставить)."""
    menu = tk.Menu(entry, tearoff=0)
    menu.add_command(label="Вырезать", command=lambda: entry.event_generate("<<Cut>>"))
    menu.add_command(label="Копировать", command=lambda: entry.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: entry.event_generate("<<Paste>>"))
    
    def show_menu(event):
        # Показываем меню только если есть что вставлять или выделен текст
        can_paste = False
        try:
            # Проверяем, есть ли текст в буфере обмена
            if entry.clipboard_get():
                can_paste = True
        except tk.TclError:
            pass # Буфер обмена пуст

        # Активируем/деактивируем пункты меню
        if entry.selection_present():
            menu.entryconfig("Вырезать", state="normal")
            menu.entryconfig("Копировать", state="normal")
        else:
            menu.entryconfig("Вырезать", state="disabled")
            menu.entryconfig("Копировать", state="disabled")
            
        if can_paste:
            menu.entryconfig("Вставить", state="normal")
        else:
            menu.entryconfig("Вставить", state="disabled")
            
        menu.tk_popup(event.x_root, event.y_root)

    entry.bind("<Button-3>", show_menu) # Привязываем к правой кнопке мыши
# >>>>> КОНЕЦ НОВОГО БЛОКА <<<<<

# --- Создание GUI ---
def show_main_window():
    auth_frame.pack_forget()
    setup_frame.pack_forget()
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    threading.Thread(target=get_resumes, daemon=True).start()

# --- Главное окно ---
root = tk.Tk()
root.title("HHSearch - несмешной поиск вакансий")
root.geometry("900x700")
root.protocol("WM_DELETE_WINDOW", on_closing)

salary_only_var = tk.BooleanVar()
gender_var = tk.StringVar()

style = ttk.Style(root)
style.configure("Green.TLabel", foreground="green", font=("Arial", 10, "bold"))
style.configure("Red.TLabel", foreground="red", font=("Arial", 10, "bold"))
style.configure("Link.TLabel", foreground="blue", font=("Arial", 10, "underline"))

load_applied_vacancies()
load_rejected_vacancies()

# --- Фрейм первоначальной настройки ---
setup_frame = ttk.Frame(root, padding="20")
setup_frame.columnconfigure(0, weight=1)

ttk.Label(setup_frame, text="Первоначальная настройка", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
info_label = ttk.Label(setup_frame, wraplength=700, justify="left",
    text="Для работы приложения необходимо получить ключи API от hh.ru и Google Gemini. "
         "Это нужно сделать всего один раз. Приложение сохранит ключи в файл .env в своей папке.")
info_label.grid(row=1, column=0, columnspan=2, pady=(0, 15), sticky="w")

hh_link = ttk.Label(setup_frame, text="1. Получить API ключ от hh.ru (создать приложение)", style="Link.TLabel", cursor="hand2")
hh_link.grid(row=2, column=0, columnspan=2, pady=5, sticky="w")
hh_link.bind("<Button-1>", lambda e: open_hyperlink("https://dev.hh.ru/"))

gemini_link = ttk.Label(setup_frame, text="2. Получить API ключ от Google Gemini", style="Link.TLabel", cursor="hand2")
gemini_link.grid(row=3, column=0, columnspan=2, pady=(5, 20), sticky="w")
gemini_link.bind("<Button-1>", lambda e: open_hyperlink("https://aistudio.google.com/app/apikey"))

ttk.Label(setup_frame, text="HH.ru Client ID:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
hh_client_id_entry = ttk.Entry(setup_frame, width=60)
hh_client_id_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

ttk.Label(setup_frame, text="HH.ru Client Secret:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
hh_client_secret_entry = ttk.Entry(setup_frame, width=60)
hh_client_secret_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")

ttk.Label(setup_frame, text="Google Gemini API Key:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
google_api_key_entry = ttk.Entry(setup_frame, width=60)
google_api_key_entry.grid(row=6, column=1, padx=5, pady=5, sticky="ew")

# >>>>> НАЧАЛО ИЗМЕНЕНИЙ <<<<<
# Применяем контекстное меню к полям ввода
make_entry_context_menu(hh_client_id_entry)
make_entry_context_menu(hh_client_secret_entry)
make_entry_context_menu(google_api_key_entry)
# >>>>> КОНЕЦ ИЗМЕНЕНИЙ <<<<<

gender_frame = ttk.Frame(setup_frame)
gender_frame.grid(row=7, column=0, columnspan=2, pady=10, sticky="w")
ttk.Label(gender_frame, text="Ваш пол (для корректных писем):").pack(side="left", padx=5)
ttk.Radiobutton(gender_frame, text="Мужчина", variable=gender_var, value="Мужчина").pack(side="left")
ttk.Radiobutton(gender_frame, text="Женщина", variable=gender_var, value="Женщина").pack(side="left")

save_button = ttk.Button(setup_frame, text="Сохранить и продолжить", command=save_keys_and_proceed)
save_button.grid(row=8, column=0, columnspan=2, pady=20, ipady=5)

# --- Фрейм авторизации ---
auth_frame = ttk.Frame(root, padding="10")
auth_frame.columnconfigure(0, weight=1)
ttk.Label(auth_frame, text="Для начала работы необходимо авторизоваться.", font=("Arial", 14)).pack(pady=10)
ttk.Button(auth_frame, text="Авторизоваться через hh.ru", command=start_server_and_authorize).pack(pady=20, ipady=10)

# --- Главный фрейм ---
main_frame = ttk.Frame(root, padding="10")
settings_frame = ttk.Frame(main_frame); settings_frame.pack(fill="x", pady=5)
left_frame = ttk.Frame(settings_frame); left_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
search_frame = ttk.LabelFrame(left_frame, text="Параметры поиска"); search_frame.pack(fill="x", pady=5)
search_frame.columnconfigure(1, weight=1)
ttk.Label(search_frame, text="Ключевые слова:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
keyword_entry = ttk.Entry(search_frame); keyword_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
ttk.Label(search_frame, text="Мин. совпадений:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
min_keywords_entry = ttk.Entry(search_frame, width=10); min_keywords_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
min_keywords_entry.insert(0, "1")
ttk.Label(search_frame, text="Исключить слова:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
exclude_keyword_entry = ttk.Entry(search_frame); exclude_keyword_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
ttk.Label(search_frame, text="Регион (ID):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
area_entry = ttk.Entry(search_frame); area_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
ttk.Label(search_frame, text="Зарплата от:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
salary_entry = ttk.Entry(search_frame); salary_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
ttk.Checkbutton(search_frame, text="Искать только с зарплатой", variable=salary_only_var).grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="w")
ttk.Label(search_frame, text="Глубина поиска (стр):").grid(row=6, column=0, padx=5, pady=5, sticky="w")
search_depth_entry = ttk.Entry(search_frame, width=10); search_depth_entry.grid(row=6, column=1, padx=5, pady=5, sticky="w")
search_depth_entry.insert(0, "5")
resume_frame = ttk.LabelFrame(left_frame, text="Резюме"); resume_frame.pack(fill="x", pady=5)
ttk.Label(resume_frame, text="Выберите резюме для откликов:").pack(anchor="w", padx=5, pady=5)
resume_combobox = ttk.Combobox(resume_frame, state="readonly"); resume_combobox.pack(fill="x", padx=5, pady=5)
right_frame = ttk.Frame(settings_frame); right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
sent_list_container = ttk.LabelFrame(right_frame, text="Отправленные отклики"); sent_list_container.pack(fill="both", expand=True)
sent_canvas = tk.Canvas(sent_list_container); sent_scrollbar = ttk.Scrollbar(sent_list_container, orient="vertical", command=sent_canvas.yview)
sent_list_frame = ttk.Frame(sent_canvas)
sent_list_frame.bind("<Configure>", lambda e: sent_canvas.configure(scrollregion=sent_canvas.bbox("all")))
sent_canvas.create_window((0, 0), window=sent_list_frame, anchor="nw"); sent_canvas.configure(yscrollcommand=sent_scrollbar.set)
sent_canvas.pack(side="left", fill="both", expand=True); sent_scrollbar.pack(side="right", fill="y")
control_frame = ttk.Frame(main_frame); control_frame.pack(fill="x", pady=10)
ttk.Button(control_frame, text="Сохранить параметры", command=save_settings).pack(side="left", padx=5)
auto_send_button = ttk.Button(control_frame, text="Запустить автоотправку", command=start_auto_send); auto_send_button.pack(side="left", padx=5)
status_label = ttk.Label(control_frame, text="Статус: Не запущено", style="Red.TLabel"); status_label.pack(side="left", padx=10, pady=5)

# --- Логика выбора стартового экрана ---
if all([HH_CLIENT_ID, HH_CLIENT_SECRET, GOOGLE_API_KEY, USER_GENDER]):
    logging.info("Ключи API найдены. Отображается экран авторизации.")
    auth_frame.pack(fill="both", expand=True)
else:
    logging.info("Один или несколько ключей API не найдены. Отображается экран настройки.")
    setup_frame.pack(fill="both", expand=True)

root.mainloop()