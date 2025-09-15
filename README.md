# HHsearch - Автоматический отклик на вакансии hh.ru

`HHsearch` — это десктопное приложение для автоматического поиска вакансий на сайте hh.ru, генерации сопроводительных писем с помощью нейросети и отправки откликов.

![Скриншот приложения HHsearch](https://raw.githubusercontent.com/VL9110012010/HHsearch/1d841cb89a39bb5991626a2fbdf89fb24f65dfaa/screenshot.png)

## 🚀 Основные возможности

*   **Автоматический поиск:** Приложение ищет вакансии по заданным вами параметрам (ключевые слова, регион, зарплата и т. д.).
*   **Умная фильтрация:** Возможность исключать вакансии по стоп-словам.
*   **Генерация сопроводительных писем:** Использует **Google Gemini API** для создания персонализированных сопроводительных писем на основе вашего резюме и описания вакансии.
*   **Автоматическая отправка:** Самостоятельно откликается на подходящие вакансии с сгенерированным письмом.
*   **Защита от повторов:** Приложение запоминает вакансии, на которые вы уже откликнулись или которые были отклонены, чтобы не отправлять повторные запросы.
*   **Сохранение истории:** Все сгенерированные сопроводительные письма сохраняются в отдельную папку.
*   **Простой интерфейс:** Удобное графическое окно для настройки и запуска.

## ⚙️ Как это работает

1.  **Настройка:** При первом запуске приложение просит вас ввести API-ключи от hh.ru и Google Gemini. Эти данные сохраняются локально в файле `.env`.
2.  **Авторизация:** Вы проходите OAuth-авторизацию на сайте hh.ru, чтобы приложение получило доступ к вашим резюме и могло отправлять отклики от вашего имени.
3.  **Поиск и фильтрация:** Приложение периодически (раз в час) выполняет поиск новых вакансий по вашим критериям.
4.  **Анализ и генерация:** Каждая новая вакансия анализируется. Если она подходит, нейросеть Google Gemini генерирует уникальное сопроводительное письмо.
5.  **Отправка отклика:** Приложение отправляет отклик на вакансию с готовым письмом.

## 🛠️ Установка и запуск

1.  **Склонируйте репозиторий:**
    ```bash
    git clone https://github.com/VL9110012010/HHsearch.git
    cd HHsearch
    ```

2.  **Установите зависимости:**
    Рекомендуется использовать виртуальное окружение.
    ```bash
    python -m venv venv
    source venv/bin/activate  # Для Windows: venv\Scripts\activate
    ```
    Установите необходимые библиотеки:
    ```bash
    pip install -r requirements.txt
    ```
    *Если у вас нет файла `requirements.txt`, создайте его с содержимым:*
    ```
    requests
    python-dotenv
    google-generativeai
    ```

3.  **Запустите приложение:**
    ```bash
    python main.py
    ```
    
## 🔑 Первоначальная настройка

При первом запуске вам потребуется:

1.  **API ключ hh.ru:**
    *   Перейдите на [сайт для разработчиков hh.ru](https://dev.hh.ru/).
    *   Создайте новое приложение.
    *   В качестве "Redirect URI" укажите `http://localhost:8080/`.
    *   Скопируйте `Client ID` и `Client Secret` в соответствующие поля в приложении.

2.  **API ключ Google Gemini:**
    *   Перейдите в [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   Создайте новый API-ключ.
    *   Скопируйте ключ и вставьте его в приложение.

3.  **Выберите ваш пол** для корректной генерации писем.

После сохранения ключей вы будете перенаправлены на страницу авторизации hh.ru.

## 📝 Использование

1.  Заполните параметры поиска (ключевые слова, регион, зарплата).
2.  Выберите одно из ваших резюме из выпадающего списка.
3.  Нажмите кнопку **"Запустить автоотправку"**.
4.  Приложение начнет работать в фоновом режиме, а в правой части окна будет отображаться список компаний, на вакансии которых был отправлен отклик.

## 📄 Лицензия

Этот проект распространяется под лицензией MIT.





English Version

# HHsearch - Automatic Job Applicator for hh.ru

`HHsearch` is a desktop application that automates the process of searching for jobs on hh.ru, generating cover letters with an AI, and sending applications.

![HHsearch Application Screenshot](https://raw.githubusercontent.com/VL9110012010/HHsearch/1d841cb89a39bb5991626a2fbdf89fb24f65dfaa/screenshot.png)

## 🚀 Key Features

*   **Automated Search:** The app searches for vacancies based on your specified criteria (keywords, region, salary, etc.).
*   **Smart Filtering:** Ability to exclude vacancies using stop-words.
*   **Cover Letter Generation:** Uses the **Google Gemini API** to create personalized cover letters based on your resume and the job description.
*   **Auto-Apply:** Automatically applies to suitable vacancies with the generated cover letter.
*   **Duplicate Prevention:** The app remembers which jobs you've already applied to or rejected to avoid sending duplicate applications.
*   **History Saving:** All generated cover letters are saved to a dedicated folder.
*   **Simple UI:** A user-friendly graphical interface for setup and control.

## ⚙️ How It Works

1.  **Setup:** On the first launch, the application prompts you to enter API keys for hh.ru and Google Gemini. This data is saved locally in a `.env` file.
2.  **Authorization:** You complete an OAuth authorization on the hh.ru website, allowing the app to access your resumes and send applications on your behalf.
3.  **Search & Filter:** The application periodically (once an hour) searches for new vacancies based on your criteria.
4.  **Analysis & Generation:** Each new vacancy is analyzed. If it's a good fit, the Google Gemini AI generates a unique cover letter.
5.  **Application Submission:** The app sends the application for the job with the completed cover letter.

## 🛠️ Installation and Launch

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/VL9110012010/HHsearch.git
    cd HHsearch
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # For Windows: venv\Scripts\activate
    ```
    Install the required libraries:
    ```bash
    pip install -r requirements.txt
    ```
    *If you don't have a `requirements.txt` file, create one with the following content:*
    ```
    requests
    python-dotenv
    google-generativeai
    ```

3.  **Run the application:**
    ```bash
    python main.py
    ```
    
## 🔑 First-Time Setup

On the first launch, you will need to provide:

1.  **hh.ru API Key:**
    *   Go to the [hh.ru developer site](https://dev.hh.ru/).
    *   Create a new application.
    *   Use `http://localhost:8080/` as the "Redirect URI".
    *   Copy the `Client ID` and `Client Secret` into the corresponding fields in the app.

2.  **Google Gemini API Key:**
    *   Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   Create a new API key.
    *   Copy the key and paste it into the application.

3.  **Select your gender** for correctly generated cover letters.

After saving the keys, you will be redirected to the hh.ru authorization page.

## 📝 Usage

1.  Fill in the search parameters (keywords, region, salary).
2.  Select one of your resumes from the dropdown list.
3.  Click the **"Start Auto-Apply"** button.
4.  The application will start working in the background, and the right-hand side of the window will display a list of companies you've applied to.

## 📄 License

This project is licensed under the MIT License.
