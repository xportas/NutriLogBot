import flet as ft
import os
import requests
import google.generativeai as genai
from datetime import datetime
import re
import base64
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import difflib

# --- CONFIGURACIÓN ---
# En Android el .env no se empaqueta, así que las claves van embebidas como fallback.
# Intenta cargar .env si existe (escritorio), si no usa los valores directos.
try:
    from dotenv import load_dotenv
    # Cargar .env desde el directorio del script (funciona en escritorio)
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _env_path = os.path.join(_script_dir, ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv no disponible en Android, no pasa nada

# Claves API - os.getenv primero (escritorio), fallback embebido (Android)
GENAI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FITBIT_CLIENT_ID = os.getenv("FITBIT_CLIENT_ID", "")
FITBIT_CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET", "")

if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)

system_instruction = 'Formatea la respuesta exclusivamente como una lista de alimentos, uno por linea, incluyendo la cantidad y el ingrediente. Ejemplo: "Pechuga de pollo - 40g"'

def get_gemini_model():
    return genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite-preview",
        generation_config={"temperature": 0.1}
    )

# --- HELPERS PARA UNIDADES ---
def safe_unit_id(raw):
    """Extrae el ID de una unidad que puede ser int o dict."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, dict):
        return raw.get('id')
    return None

def get_all_unit_ids(food):
    """Devuelve todos los IDs de unidad de un alimento."""
    ids = set()
    for u in food.get('units', []):
        uid = safe_unit_id(u)
        if uid:
            ids.add(uid)
    uid = safe_unit_id(food.get('defaultUnit'))
    if uid:
        ids.add(uid)
    return ids

def get_default_unit(food):
    """Devuelve el ID de unidad por defecto de forma segura."""
    raw = food.get('defaultUnit')
    uid = safe_unit_id(raw)
    if uid:
        return uid
    all_ids = get_all_unit_ids(food)
    return next(iter(all_ids), 304)

# --- CLASES DE UI ---

class UserMessage(ft.Row):
    def __init__(self, text):
        super().__init__(
            alignment=ft.MainAxisAlignment.END,
            controls=[
                ft.Container(
                    content=ft.Text(text, color=ft.Colors.ON_PRIMARY),
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=ft.border_radius.all(18),
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    margin=ft.margin.symmetric(vertical=4),
                    width=300,
                )
            ]
        )

class GeminiMessage(ft.Column):
    def __init__(self, text, on_send_fitbit):
        super().__init__()
        self.on_send_fitbit = on_send_fitbit
        self.current_text = text.strip()

        self.text_view = ft.Text(self.current_text, selectable=True, size=14)
        self.send_btn = ft.FilledButton("Enviar a Fitbit", on_click=self.send_clicked, icon=ft.Icons.SEND)

        self.controls = [
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=ft.Colors.PURPLE), ft.Text("Gemini", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE)]),
                        self.text_view,
                        ft.Row([self.send_btn], alignment=ft.MainAxisAlignment.END)
                    ], spacing=10),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=ft.border_radius.only(top_left=18, top_right=18, bottom_right=18, bottom_left=4),
                    padding=16,
                    margin=ft.margin.symmetric(vertical=4),
                    width=340,
                )
            ], alignment=ft.MainAxisAlignment.START)
        ]

    def send_clicked(self, e):
        self.send_btn.disabled = True
        self.update()
        self.on_send_fitbit(self.current_text, self)

class MealSelectionMessage(ft.Column):
    def __init__(self, parsed_foods, on_meal_selected):
        super().__init__()
        self.parsed_foods = parsed_foods
        self.on_meal_selected = on_meal_selected

        meals = [
            {"name": "Desayuno", "id": 1},
            {"name": "Media Manana", "id": 2},
            {"name": "Comida", "id": 3},
            {"name": "Merienda", "id": 4},
            {"name": "Cena", "id": 5},
            {"name": "Cualquier hora", "id": 6},
        ]

        buttons = []
        for meal in meals:
            btn = ft.ElevatedButton(
                meal["name"],
                data={"id": meal["id"], "name": meal["name"]},
                on_click=self.meal_clicked
            )
            buttons.append(btn)

        self.controls = [
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.RESTAURANT, size=16, color=ft.Colors.ORANGE), ft.Text("Selecciona comida del dia", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE)]),
                        ft.Row(buttons, wrap=True, spacing=5, run_spacing=5)
                    ]),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=ft.border_radius.only(top_left=18, top_right=18, bottom_right=18, bottom_left=4),
                    padding=16,
                    margin=ft.margin.symmetric(vertical=4),
                    width=340,
                )
            ], alignment=ft.MainAxisAlignment.START)
        ]

    def meal_clicked(self, e):
        for c in self.controls[0].controls[0].content.controls[1].controls:
            c.disabled = True
        self.update()
        self.on_meal_selected(self.parsed_foods, e.control.data["id"], e.control.data["name"])

class SystemMessage(ft.Row):
    def __init__(self, text, is_error=False):
        color = ft.Colors.ERROR if is_error else ft.Colors.GREEN
        icon = ft.Icons.ERROR if is_error else ft.Icons.CHECK_CIRCLE
        super().__init__(
            alignment=ft.MainAxisAlignment.START,
            controls=[
                ft.Container(
                    content=ft.Row([ft.Icon(icon, color=color, size=16), ft.Text(text, color=color, size=12, selectable=True)], wrap=True),
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    width=340,
                )
            ]
        )

# Variable global para guardar el token de la sesion
fitbit_access_token = None

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class OAuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global fitbit_access_token
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        if 'code' in query:
            code = query['code'][0]
            auth_str = f"{FITBIT_CLIENT_ID}:{FITBIT_CLIENT_SECRET}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "client_id": FITBIT_CLIENT_ID,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost:8080/api/oauth/callback",
                "code": code
            }
            res = requests.post("https://api.fitbit.com/oauth2/token", headers=headers, data=data)

            if res.status_code == 200:
                fitbit_access_token = res.json().get('access_token')
                self.wfile.write(b"<html><head><style>body{font-family:sans-serif;text-align:center;padding:50px;background:#1a1a2e;color:#e0e0e0;}</style></head><body><h1>Conexion Exitosa</h1><p>Ya puedes cerrar esta ventana y volver a NutriLog Bot.</p></body></html>")
            else:
                self.wfile.write(f"<html><body><h1>Error</h1><p>{res.text}</p></body></html>".encode())
            self.server.done = True
        else:
            self.wfile.write(b"<h1>Error</h1><p>No se recibio codigo de autorizacion.</p>")
            self.server.done = True

# --- APP PRINCIPAL ---

def main(page: ft.Page):
    page.title = "NutriLog Bot"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True, padding=ft.Padding.all(10))

    def on_login_success():
        chat_list.controls.append(SystemMessage("Conectado a Fitbit correctamente."))
        login_row.visible = False
        input_row.visible = True
        page.update()

    def on_login_error(err):
        chat_list.controls.append(SystemMessage(f"Error Login: {err}", is_error=True))
        page.update()

    server_thread_active = [False]

    def start_oauth(e):
        url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={FITBIT_CLIENT_ID}&redirect_uri=http://localhost:8080/api/oauth/callback&scope=nutrition%20profile"
        
        if server_thread_active[0]:
            chat_list.controls.append(SystemMessage("Esperando a que completes el login..."))
            page.update()
            return

        chat_list.controls.append(SystemMessage("Esperando autorización de Fitbit..."))
        page.update()

        def run_server():
            server_thread_active[0] = True
            try:
                server = ReusableHTTPServer(('127.0.0.1', 8080), OAuthHandler)
                server.timeout = 180  # 3 mins de timeout
                server.handle_request()
                if fitbit_access_token:
                    on_login_success()
            except Exception as ex:
                on_login_error(str(ex))
            finally:
                server_thread_active[0] = False

        threading.Thread(target=run_server, daemon=True).start()

    def add_loading(text="Cargando..."):
        loading_row = ft.Row([ft.ProgressRing(width=16, height=16, stroke_width=2), ft.Text(text, size=12)])
        chat_list.controls.append(loading_row)
        page.update()
        return loading_row

    def remove_loading(loading_row):
        if loading_row in chat_list.controls:
            chat_list.controls.remove(loading_row)
            page.update()

    def handle_submit(e):
        user_text = text_input.value
        if not user_text or not user_text.strip():
            return

        text_input.value = ""
        chat_list.controls.append(UserMessage(user_text))
        page.update()

        loading_row = add_loading("Gemini analizando...")

        try:
            model = get_gemini_model()
            prompt = f"{system_instruction}\n\nTexto del usuario: {user_text}"
            response = model.generate_content(prompt)

            remove_loading(loading_row)

            bot_text = response.text
            chat_list.controls.append(GeminiMessage(bot_text, process_fitbit_get))
            page.update()

        except Exception as ex:
            remove_loading(loading_row)
            chat_list.controls.append(SystemMessage(f"Error Gemini: {ex}", is_error=True))
            page.update()

    def process_fitbit_get(text, message_widget):
        global fitbit_access_token
        if not fitbit_access_token:
            chat_list.controls.append(SystemMessage("Por favor, conectate a Fitbit primero.", is_error=True))
            message_widget.send_btn.disabled = False
            page.update()
            return

        loading_row = add_loading("Buscando alimentos en Fitbit...")

        try:
            lines = text.strip().split('\n')
            parsed_foods = []

            for line in lines:
                if not line.strip():
                    continue
                parts = line.split('-')
                if len(parts) >= 2:
                    ingredient = parts[0].strip()
                    qty_str = parts[1].strip()

                    match = re.match(r"([\d\.,]+)", qty_str)
                    amount = 1.0
                    if match:
                        amount = float(match.group(1).replace(',', '.'))

                    headers = {"Authorization": f"Bearer {fitbit_access_token}"}
                    res = requests.get(f"https://api.fitbit.com/1/foods/search.json?query={ingredient}", headers=headers)

                    if res.status_code != 200:
                        raise Exception(f"HTTP {res.status_code} - {res.text}")

                    qty_lower = qty_str.lower()
                    needs_grams = 'g' in qty_lower or 'gram' in qty_lower
                    needs_ml = 'ml' in qty_lower or 'mili' in qty_lower

                    best_food_id = None
                    best_unit_id = 304
                    best_score = -1.0
                    fallback_food_id = None
                    fallback_unit_id = 304
                    fallback_score = -1.0

                    if res.json().get('foods'):
                        for food in res.json()['foods']:
                            food_name = food['name'].lower()
                            score = difflib.SequenceMatcher(None, ingredient.lower(), food_name).ratio()
                            all_uids = get_all_unit_ids(food)
                            default_uid = get_default_unit(food)

                            if score > fallback_score:
                                fallback_score = score
                                fallback_food_id = food['foodId']
                                fallback_unit_id = default_uid

                            found_unit_id = None
                            if needs_grams:
                                if 147 in all_uids:
                                    found_unit_id = 147
                            elif needs_ml:
                                if 148 in all_uids:
                                    found_unit_id = 148
                            else:
                                found_unit_id = default_uid

                            if found_unit_id is not None and score > best_score:
                                best_score = score
                                best_food_id = food['foodId']
                                best_unit_id = found_unit_id

                    if best_food_id is None and fallback_food_id is not None:
                        best_food_id = fallback_food_id
                        best_unit_id = fallback_unit_id

                    parsed_foods.append({
                        "name": ingredient,
                        "foodId": best_food_id,
                        "amount": amount,
                        "unitId": best_unit_id
                    })

            remove_loading(loading_row)

            valid_foods = [f for f in parsed_foods if f["foodId"] is not None]
            missing_foods = [f for f in parsed_foods if f["foodId"] is None]

            if missing_foods:
                names = ", ".join([f["name"] for f in missing_foods])
                chat_list.controls.append(SystemMessage(f"No se encontro en Fitbit: {names}", is_error=True))

            if not valid_foods:
                chat_list.controls.append(SystemMessage("No hay alimentos validos para registrar.", is_error=True))
                message_widget.send_btn.disabled = False
            else:
                chat_list.controls.append(SystemMessage(f"Se encontraron {len(valid_foods)} alimentos listos."))
                chat_list.controls.append(MealSelectionMessage(valid_foods, process_fitbit_post))

            page.update()

        except Exception as ex:
            remove_loading(loading_row)
            message_widget.send_btn.disabled = False
            chat_list.controls.append(SystemMessage(f"Error busqueda Fitbit: {ex}", is_error=True))
            page.update()

    def process_fitbit_post(foods, meal_type_id, meal_name):
        global fitbit_access_token
        loading_row = add_loading(f"Registrando en {meal_name}...")

        success_count = 0
        try:
            for food in foods:
                headers = {"Authorization": f"Bearer {fitbit_access_token}"}
                payload = {
                    "foodId": food["foodId"],
                    "mealTypeId": meal_type_id,
                    "unitId": food["unitId"],
                    "amount": food["amount"],
                    "date": datetime.now().strftime("%Y-%m-%d")
                }

                res = requests.post("https://api.fitbit.com/1/user/-/foods/log.json", data=payload, headers=headers)
                if res.status_code in [200, 201]:
                    success_count += 1
                else:
                    chat_list.controls.append(SystemMessage(f"Error Fitbit: {food['name']}: {res.text}", is_error=True))
                    page.update()

            remove_loading(loading_row)
            if success_count == len(foods):
                chat_list.controls.append(SystemMessage(f"Registrados {success_count} alimentos en {meal_name}."))
            else:
                chat_list.controls.append(SystemMessage(f"Registrados {success_count} de {len(foods)}.", is_error=True))

            page.update()

        except Exception as ex:
            remove_loading(loading_row)
            chat_list.controls.append(SystemMessage(f"Error registrando: {ex}", is_error=True))
            page.update()

    # --- UI COMPONENTS ---
    text_input = ft.TextField(
        hint_text="Ej: He comido 40g de pechuga...",
        expand=True,
        border_radius=25,
        filled=True,
        on_submit=handle_submit
    )

    send_button = ft.IconButton(
        icon=ft.Icons.SEND,
        icon_color=ft.Colors.PRIMARY,
        on_click=handle_submit
    )

    url_fitbit = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={FITBIT_CLIENT_ID}&redirect_uri=http://localhost:8080/api/oauth/callback&scope=nutrition%20profile"

    login_button = ft.ElevatedButton(
        "Conectar con Fitbit",
        icon=ft.Icons.LOCK_OPEN,
        url=url_fitbit,
        on_click=start_oauth,
    )

    input_row = ft.Container(
        content=ft.Row([text_input, send_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding.only(top=10, bottom=20, left=10, right=10),
        visible=False
    )

    login_row = ft.Container(
        content=ft.Row([login_button], alignment=ft.MainAxisAlignment.CENTER),
        padding=ft.Padding.all(20),
        visible=True
    )

    header = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.RESTAURANT, color=ft.Colors.PRIMARY),
            ft.Icon(ft.Icons.COMPUTER, color=ft.Colors.PRIMARY),
            ft.Text("NutriLog Bot", size=20, weight=ft.FontWeight.BOLD)
        ], alignment=ft.MainAxisAlignment.CENTER),
        padding=ft.Padding.only(top=40, bottom=10),
        border=ft.Border.only(bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
    )

    page.add(
        ft.Column([
            header,
            ft.Container(content=chat_list, expand=True),
            login_row,
            input_row
        ], expand=True, spacing=0)
    )

ft.app(target=main)
