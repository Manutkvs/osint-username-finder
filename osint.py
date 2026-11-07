import customtkinter as ctk
import requests
from bs4 import BeautifulSoup
import threading
import webbrowser
from tkinter import messagebox

# Configuración de apariencia
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PLATAFORMAS = {
    "GitHub": "https://github.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "Twitch": "https://www.twitch.tv/{}",
    "Instagram": "https://www.instagram.com/{}/",
    "TikTok": "https://www.tiktok.com/@{}"
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Buscador de Identidades")
        self.geometry("700x650")
        self.resizable(False, False)

        # Título
        self.label_titulo = ctk.CTkLabel(
            self, text="Buscador de Identidades", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.label_titulo.pack(pady=(20, 5))

        self.label_sub = ctk.CTkLabel(
            self, text="Pequeño proyecto de osint",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.label_sub.pack(pady=(0, 20))

        # Marco de búsqueda
        self.frame_busqueda = ctk.CTkFrame(self)
        self.frame_busqueda.pack(pady=10, padx=20, fill="x")

        self.entry_usuario = ctk.CTkEntry(
            self.frame_busqueda, placeholder_text="Escribe el nombre de usuario...",
            width=400, height=40, font=ctk.CTkFont(size=14)
        )
        self.entry_usuario.pack(side="left", padx=(10, 10), pady=10)
        self.entry_usuario.bind("<Return>", lambda e: self.iniciar_busqueda())

        self.btn_buscar = ctk.CTkButton(
            self.frame_busqueda, text="Buscar", command=self.iniciar_busqueda,
            width=120, height=40, font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_buscar.pack(side="left", padx=(0, 10), pady=10)

        # Barra de progreso
        self.progressbar = ctk.CTkProgressBar(self)
        self.progressbar.pack(pady=10, padx=20, fill="x")
        self.progressbar.set(0)
        self.progressbar.pack_forget()

        # Cabecera de la tabla
        self.frame_header = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_header.pack(pady=(10, 0), padx=20, fill="x")
        
        ctk.CTkLabel(self.frame_header, text="PLATAFORMA", width=100, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(side="left", padx=(10, 5))
        ctk.CTkLabel(self.frame_header, text="NOMBRE REAL", width=200, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(side="left", padx=(5, 5))
        ctk.CTkLabel(self.frame_header, text="ESTADO", width=120, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(side="left", padx=(5, 5))
        ctk.CTkLabel(self.frame_header, text="ACCIÓN", width=80, anchor="center", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(side="right", padx=(5, 10))

        # Marco de resultados (Scrollable)
        self.frame_resultados = ctk.CTkScrollableFrame(
            self, width=640, height=380, label_text=""
        )
        self.frame_resultados.pack(pady=0, padx=20, fill="both", expand=True)

    def iniciar_busqueda(self):
        usuario = self.entry_usuario.get().strip()
        if not usuario:
            messagebox.showwarning("Falta usuario", "Escribe un nombre de usuario.")
            return

        # Limpiar resultados
        for widget in self.frame_resultados.winfo_children():
            widget.destroy()

        self.btn_buscar.configure(state="disabled", text="Buscando...")
        self.progressbar.pack(pady=10, padx=20, fill="x")
        self.progressbar.start()

        threading.Thread(target=self.buscar, args=(usuario,), daemon=True).start()

    def buscar(self, usuario):
        resultados = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # Frases que indican que la cuenta NO existe, aunque la página cargue (error 200 falso)
        ERRORES_NO_ENCONTRADO = [
            "page not found", 
            "no se encontró", 
            "this page isn't available", 
            "sorry, this page", 
            "user not found",
            "no encontrado",
            "page not available"
        ]

        for plataforma, url_base in PLATAFORMAS.items():
            url = url_base.format(usuario)
            try:
                respuesta = requests.get(url, headers=headers, timeout=8)
                html_min = respuesta.text.lower()
                
                # 1. Si el código es 404, la cuenta no existe.
                if respuesta.status_code == 404:
                    resultados.append((plataforma, "❌ No encontrado", "—", url, "#e74c3c"))
                    continue

                # 2. Si el código es 200, revisamos el texto para asegurarnos de que no sea un falso positivo
                if respuesta.status_code == 200:
                    es_falso_positivo = any(frase in html_min for frase in ERRORES_NO_ENCONTRADO)
                    
                    if es_falso_positivo:
                        resultados.append((plataforma, "❌ No encontrado", "—", url, "#e74c3c"))
                    else:
                        nombre_real = self.extraer_nombre(respuesta.text, plataforma)
                        
                        # Si el nombre real es igual al nombre de la plataforma o no se puede leer
                        if nombre_real.lower() == plataforma.lower() or nombre_real == "Nombre no visible":
                            nombre_real = "Perfil privado / Bloqueado"
                            
                        resultados.append((plataforma, "✅ Encontrado", nombre_real, url, "#2ecc71"))
                else:
                    # Cualquier otro código (403, 429, etc.)
                    resultados.append((plataforma, "⚠️ Bloqueado", "—", url, "#f39c12"))
                    
            except requests.exceptions.RequestException:
                resultados.append((plataforma, "🚫 Error de red", "—", url, "#95a5a6"))

        self.after(0, self.mostrar_resultados, resultados)

    def extraer_nombre(self, html, plataforma):
        try:
            soup = BeautifulSoup(html, "html.parser")
            titulo = soup.find("title")
            if titulo:
                texto = titulo.text.strip()
                if "•" in texto: nombre = texto.split("•")[0].strip()
                elif "|" in texto: nombre = texto.split("|")[0].strip()
                elif " - " in texto: nombre = texto.split(" - ")[0].strip()
                else: nombre = texto
                if "(" in nombre: nombre = nombre.split("(")[0].strip()
                
                # Limpieza extra para evitar el nombre de la plataforma
                if nombre.lower() != plataforma.lower() and len(nombre) < 50:
                    return nombre
                    
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"): 
                return og_title["content"].strip()
        except Exception:
            pass
        return "Nombre no visible"

    def mostrar_resultados(self, resultados):
        self.progressbar.stop()
        self.progressbar.pack_forget()
        self.btn_buscar.configure(state="normal", text="Buscar")

        for i, (plataforma, estado, nombre, url, color) in enumerate(resultados):
            # Alternamos colores de fondo para efecto de tabla
            color_fondo = "#2b2b2b" if i % 2 == 0 else "#212121"
            
            tarjeta = ctk.CTkFrame(self.frame_resultados, fg_color=color_fondo, corner_radius=8)
            tarjeta.pack(fill="x", pady=3, padx=5)

            # Plataforma
            ctk.CTkLabel(
                tarjeta, text=plataforma, width=100, anchor="w",
                font=ctk.CTkFont(size=13, weight="bold")
            ).pack(side="left", padx=(10, 5), pady=8)

            # Nombre real
            ctk.CTkLabel(
                tarjeta, text=nombre, width=200, anchor="w",
                font=ctk.CTkFont(size=12), text_color="#38bdf8"
            ).pack(side="left", padx=(5, 5), pady=8)

            # Estado
            ctk.CTkLabel(
                tarjeta, text=estado, width=120, anchor="w",
                text_color=color, font=ctk.CTkFont(size=12, weight="bold")
            ).pack(side="left", padx=(5, 5), pady=8)

            # Botón de abrir
            if "Encontrado" in estado:
                ctk.CTkButton(
                    tarjeta, text="Abrir", width=70, height=28,
                    font=ctk.CTkFont(size=12),
                    command=lambda u=url: webbrowser.open(u)
                ).pack(side="right", padx=10, pady=8)
            else:
                ctk.CTkLabel(
                    tarjeta, text="—", width=70, text_color="gray"
                ).pack(side="right", padx=10, pady=8)

if __name__ == "__main__":
    app = App()
    app.mainloop()