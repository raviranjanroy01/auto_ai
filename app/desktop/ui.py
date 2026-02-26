import customtkinter as ctk
import threading
from app.desktop.service import DesktopAssistantService

# Configure Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AutoAIFloatingUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ─── Window Configuration ───
        self.title("AutoAI Assistant")
        self.geometry("300x220")
        self.attributes("-topmost", True)
        self.overrideredirect(True)  # Remove title bar
        self.attributes("-alpha", 0.95) # Slight transparency
        self.configure(fg_color="#1a1a1a")

        # ─── Variables ───
        self.predictions = []
        
        # ─── UI Elements ───
        self._setup_ui()

        # ─── Dragging Logic ───
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)

        # ─── Start Service ───
        self.service = DesktopAssistantService(
            on_predictions_updated=self._update_ui_predictions,
            on_correction_made=self._show_correction_toast
        )
        self.service.start()

    def _setup_ui(self):
        # Header / Grip
        self.header = ctk.CTkFrame(self, height=30, fg_color="#2d2d2d", corner_radius=0)
        self.header.pack(fill="x", side="top")
        
        self.title_label = ctk.CTkLabel(
            self.header, 
            text="🤖 AUTOAI ASSISTANT", 
            font=("Inter", 11, "bold"),
            text_color="#888888"
        )
        self.title_label.pack(pady=5)

        # Container for prediction buttons
        self.pred_container = ctk.CTkFrame(self, fg_color="transparent")
        self.pred_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Prediction Buttons (Placeholders)
        self.buttons = []
        for i in range(5):
            btn = ctk.CTkButton(
                self.pred_container,
                text="-",
                fg_color="#333333",
                hover_color="#444444",
                font=("Inter", 13),
                anchor="w",
                height=32,
                corner_radius=6,
                command=lambda idx=i: self._on_prediction_click(idx)
            )
            btn.pack(fill="x", pady=2)
            self.buttons.append(btn)

        # Correction Toast Label (Hidden by default)
        self.toast_label = ctk.CTkLabel(
            self, 
            text="", 
            font=("Inter", 12, "italic"),
            text_color="#4ade80" # Green
        )
        self.toast_label.pack(side="bottom", pady=5)

    # ─── Event Handlers ───
    def _update_ui_predictions(self, preds):
        """Called by service thread to update predictions list."""
        self.predictions = preds
        
        # We need to update UI from main thread
        def update():
            for i, btn in enumerate(self.buttons):
                if i < len(preds):
                    word, prob = preds[i]
                    btn.configure(text=f"{i+1}. {word}", state="normal", fg_color="#333333")
                else:
                    btn.configure(text="-", state="disabled", fg_color="#222222")
        
        self.after(0, update)

    def _on_prediction_click(self, idx):
        if idx < len(self.predictions):
            word, _ = self.predictions[idx]
            self.service.accept_prediction(word)

    def _show_correction_toast(self, original, corrected):
        """Show a brief message when a correction happens."""
        def show():
            self.toast_label.configure(text=f"Fixed: {original} → {corrected}")
            self.after(2000, lambda: self.toast_label.configure(text=""))
        
        self.after(0, show)

    # ─── Window Dragging ───
    def _start_drag(self, event):
        self.x = event.x
        self.y = event.y

    def _on_drag(self, event):
        # Move window while dragging
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def quit_app(self):
        self.service.stop()
        self.destroy()

if __name__ == "__main__":
    app = AutoAIFloatingUI()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.quit_app()
