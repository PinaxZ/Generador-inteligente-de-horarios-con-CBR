# app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd, numpy as np, os
from core import generar_horario   # importa tu función

class HorarioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Generador de Horario Inteligente")
        self.geometry("600x420")
        self.resizable(False, False)

        # -------- Selección de archivos ----------------------------------
        marco = ttk.LabelFrame(self, text="Archivos de entrada")
        marco.pack(fill="x", padx=10, pady=5)

        self.ruta_hor    = tk.StringVar(); self._fila_archivo(marco,"Horarios UACJ:", self.ruta_hor)
        self.ruta_plan   = tk.StringVar(); self._fila_archivo(marco,"Plan académico:", self.ruta_plan)
        self.ruta_perfil = tk.StringVar(); self._fila_archivo(marco,"Perfil estudiante:", self.ruta_perfil)

        # -------- Disponibilidad -----------------------------------------
        disp = ttk.LabelFrame(self, text="Disponibilidad (HH:MM-HH:MM)")
        disp.pack(fill="x", padx=10, pady=5)

        self.entries_disp = {}
        for dia in ["Lunes","Martes","Miércoles","Jueves","Viernes"]:
            fila = ttk.Frame(disp); fila.pack(fill="x", pady=2)
            ttk.Label(fila,text=dia,width=10).pack(side="left")
            e_ini = tk.Entry(fila,width=6); e_ini.insert(0,"07:00"); e_ini.pack(side="left")
            tk.Label(fila,text="-").pack(side="left")
            e_fin = tk.Entry(fila,width=6); e_fin.insert(0,"13:00"); e_fin.pack(side="left")
            self.entries_disp[dia] = (e_ini,e_fin)

        ttk.Button(self,text="Generar horario",command=self._run).pack(pady=10)

        # -------- Tabla resultado ----------------------------------------
        self.geometry("800x600")
        self.tree = ttk.Treeview(self, columns=("clave","mat","doc","hor","prob"), show="headings", height=10)
        for col,txt in zip(("clave","mat","doc","hor","prob"),("Materia","Docente","Horario","% Acred.")):
            self.tree.heading(col,text=txt); self.tree.column(col, anchor="center")
        self.tree.pack(fill="x", padx=10, pady=6)

    # Helpers GUI
    def _fila_archivo(self,parent,etiqueta,var):
        fila=ttk.Frame(parent); fila.pack(fill="x", pady=2)
        ttk.Label(fila,text=etiqueta,width=14).pack(side="left")
        ttk.Entry(fila,textvariable=var,width=46).pack(side="left",expand=True,fill="x")
        ttk.Button(fila,text="Examinar…",command=lambda:var.set(filedialog.askopenfilename())).pack(side="left")

    def _run(self):
        try:
            # Validar rutas
            for v in (self.ruta_hor,self.ruta_plan,self.ruta_perfil):
                if not os.path.isfile(v.get()):
                    raise FileNotFoundError("Falta seleccionar uno de los CSV.")
            # Construir diccionario ventana
            ventana = {d:f"{e0.get()}-{e1.get()}" for d,(e0,e1) in self.entries_disp.items()}

            horario_df, puntaje = generar_horario(
                self.ruta_hor.get(),
                self.ruta_plan.get(),
                self.ruta_perfil.get(),
                ventana
            )

            # Mostrar resultado
            for i in self.tree.get_children(): self.tree.delete(i)
            if horario_df.empty:
                messagebox.showwarning("Sin horario","No se encontró un horario dentro de la disponibilidad.")
                return
            for _,r in horario_df.iterrows():
                self.tree.insert("", "end", values=(r['Materia'],r['Docente'],r['Horario'],f"{r['probabilidad_acreditar']:.0%}"))
            messagebox.showinfo("Horario generado",
                                f"Materias: {len(horario_df)}\nPuntaje total: {puntaje:.2f}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    HorarioApp().mainloop()
