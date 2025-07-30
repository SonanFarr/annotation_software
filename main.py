import sys
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QLabel
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QStringListModel
from PyQt5 import uic
import json

from data_augmentation import DataAugmentationWindow

from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QRect, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGraphicsView, QGraphicsScene

from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QSizePolicy, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt
import math

HANDLE = 6
LIMIAR_LARGURA = 800
NUM_AREA_FRAC_6 = 0.30
NUM_AREA_FRAC_3 = 0.502
CIRCLE_RADIUS = 30
ALTURA_CENTRO = 0.5 

class AnnotationBox:
    def __init__(self, rect: QRect, classe: str):
        self.rect = rect 
        self.classe = classe 
        self.selected = False

    def contains(self, point: QPoint):
        return self.rect.contains(point)

    def handle_rects(self):
        r, h = self.rect, HANDLE // 2
        return {
            "tl": QRect(r.left()-h,  r.top()-h,     HANDLE, HANDLE),
            "tr": QRect(r.right()-h, r.top()-h,     HANDLE, HANDLE),
            "bl": QRect(r.left()-h,  r.bottom()-h,  HANDLE, HANDLE),
            "br": QRect(r.right()-h, r.bottom()-h,  HANDLE, HANDLE),
        }

    def handle_at(self, point: QPoint):
        for name, rc in self.handle_rects().items():
            if rc.contains(point):
                return name
        return None

    def move(self, dx, dy):
        self.rect.translate(dx, dy)

    def resize(self, dx, dy, handle):
        r = self.rect
        if handle == "tl":
            r.setTopLeft(r.topLeft() + QPoint(dx, dy))
        elif handle == "tr":
            r.setTopRight(r.topRight() + QPoint(dx, dy))
        elif handle == "bl":
            r.setBottomLeft(r.bottomLeft() + QPoint(dx, dy))
        elif handle == "br":
            r.setBottomRight(r.bottomRight() + QPoint(dx, dy))

        # normaliza e impõe tamanho mínimo
        r = r.normalized()
        if r.width()  < 10: r.setWidth(10)
        if r.height() < 10: r.setHeight(10)
        self.rect = r

class ClassSelectionDialog(QDialog):
    def __init__(self, num_questoes, opcoes, start_num, callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Classe das Questões")
        self.answers = [None] * num_questoes
        self.button_groups = []
        self.opcoes = opcoes
        self.callback = callback

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner  = QWidget(scroll)
        grid   = QGridLayout(inner)
        inner.setLayout(grid)
        scroll.setWidget(inner)

        # largura aproximada de cada bloco
        col_width = 1080
        screen_w  = self.screen().availableGeometry().width()
        max_cols  = max(1, screen_w // col_width)          # quantas colunas cabem
        rows      = math.ceil(num_questoes / max_cols)     # número de linhas necessárias

        for i in range(num_questoes):
            # bloco horizontal
            hbox = QHBoxLayout()
            hbox.addWidget(QLabel(f"Questão {start_num + i}:"))

            buttons = []
            for opcao in opcoes:
                btn = QPushButton(opcao.upper())
                btn.setCheckable(True)
                btn.clicked.connect(
                    lambda _, j=i, o=opcao: self.set_answer(j, o)
                )
                hbox.addWidget(btn)
                buttons.append(btn)
            self.button_groups.append(buttons)

            bloco = QWidget()
            bloco.setLayout(hbox)
            bloco.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

            row = i % rows
            col = i // rows
            grid.addWidget(bloco, row, col, Qt.AlignTop)
        
        # layout principal
        main = QVBoxLayout(self)
        main.addWidget(scroll)
        self.setLayout(main)
        
        LARGURA_FIXA = 650
        ALTURA_FIXA  = 480
        self.setFixedSize(LARGURA_FIXA, ALTURA_FIXA)
    
    def set_answer(self, idx: int, val: str):
        self.answers[idx] = val
        for btn in self.button_groups[idx]:
            btn.setStyleSheet(
                "background: lightblue; font-weight:bold;" if btn.text().lower() == val else ""
            )
        
        if self.callback:
            self.callback(idx, val)

        if all(self.answers):
            self.accept()

    #shortcut para marcação
    def keyPressEvent(self, event):
        key = event.text().lower()
        #Pela letra
        if key in self.opcoes:
            for i, answer in enumerate(self.answers):
                if answer is None:
                    self.set_answer(i, key)
                    break

        #Pelo número
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(self.opcoes):
                letra = self.opcoes[idx]
                for i, answer in enumerate(self.answers):
                    if answer is None:
                        self.set_answer(i, letra)
                        break

class ImageLabel(QLabel):
    def __init__(self, main_window):
        super().__init__(main_window.img_frame)
        self.main_window = main_window
        self.setMouseTracking(True)
        self.mode        = None   
        self.handle_name = None
        self.drag_start  = None
        self.mw = self.main_window

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return

        # verifica se clicou em handle de resize
        for box in reversed(self.mw.annotations):
            h = box.handle_at(ev.pos())
            if h:
                self.mode = "resize"
                self.handle_name = h

                for b in self.mw.annotations:
                    b.selected = False
                self.mw.selected_box = box
                box.selected = True

                
                self.drag_start = ev.pos()
                self.update()
                return

        for b in self.mw.annotations:
            b.selected = False  # desmarca todas
        for box in reversed(self.mw.annotations):
            if box.contains(ev.pos()):
                self.mode = "move"
                self.mw.selected_box = box
                box.selected = True
                self.drag_start = ev.pos()
                self.update()
                return

        
        # clicou fora: começa a desenhar nova coluna
        self.mw.selected_box = None
        for b in self.mw.annotations: b.selected = False
        self.mode = "draw"
        self.mw.start_point = ev.pos()
        self.mw.end_point   = ev.pos()
        self.mw.drawing     = True
        self.update()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            if self.mode == "move" and self.mw.selected_box:
                dx = ev.x() - self.drag_start.x()
                dy = ev.y() - self.drag_start.y()
                self.mw.selected_box.move(dx, dy)
                self.drag_start = ev.pos()
            elif self.mode == "resize" and self.mw.selected_box:
                dx = ev.x() - self.drag_start.x()
                dy = ev.y() - self.drag_start.y()
                self.mw.selected_box.resize(dx, dy, self.handle_name)
                self.drag_start = ev.pos()
            elif self.mode == "draw" and self.mw.drawing:
                self.mw.end_point = ev.pos()
            self.update()

    def mouseReleaseEvent(self, ev):
        if self.mode == "draw" and self.mw.drawing:
            self.mw.drawing = False
            self.mw.end_point = ev.pos()
            self.mw.finalize_box()  # cria as caixas‑questão
        elif self.mode in ("move", "resize") and self.mw.selected_box:
            self.mw.update_annotations_list() 
        self.mode = None
        self.drag_start = None
        self.update()
    
    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        for box in self.mw.annotations:
            if box.selected:
                # Caixa selecionada: borda verde
                p.setPen(QPen(Qt.green, 5, Qt.SolidLine))
                p.setBrush(Qt.NoBrush)  # Sem preenchimento
                p.drawRect(box.rect)

                # Desenha handles
                p.setBrush(Qt.green)
                for handle_rect in box.handle_rects().values():
                    p.drawRect(handle_rect)
                p.setBrush(Qt.NoBrush)
            else:
                # Caixa não selecionada: borda azul
                p.setPen(QPen(Qt.blue, 5))
                p.setBrush(Qt.NoBrush)
                p.drawRect(box.rect)

            # Desenhar círculo amarelo na alternativa marcada
            classe = box.classe.lower()
            if classe not in ['a', 'b', 'c', 'd', 'e', 'f', 'branco']:
                continue 

            num_alternativas = 3 if box.rect.width() < LIMIAR_LARGURA else 6
            opcoes_validas = ['a', 'b', 'c'] if num_alternativas == 3 else ['a', 'b', 'c', 'd', 'e', 'f']
            
            if classe == 'branco' or classe not in opcoes_validas:
                continue

            idx = opcoes_validas.index(classe)

            total_w = box.rect.width()
            total_h = box.rect.height()
            start_x = box.rect.left()
            start_y = box.rect.top()

            if(num_alternativas == 3):
                alt_area_x = start_x + int(total_w * NUM_AREA_FRAC_3)
                alt_area_w = int(total_w * (1 - NUM_AREA_FRAC_3))
            else:
                alt_area_x = start_x + int(total_w * NUM_AREA_FRAC_6)
                alt_area_w = int(total_w * (1 - NUM_AREA_FRAC_6))

            # Largura da alternativa + espaço
            espacamento = 0.1
            num_espacos = num_alternativas + 1
            total_espaco = alt_area_w * espacamento
            largura_util = alt_area_w - total_espaco
            largura_alt = largura_util / num_alternativas
            largura_esp = total_espaco / num_espacos

            # Posição do centro do marcador
            x_centro = alt_area_x + largura_esp * (idx + 1) + largura_alt * idx + largura_alt / 2
            y_centro = start_y + total_h * ALTURA_CENTRO

            # Desenha o círculo
            p.setBrush(Qt.yellow)
            p.setPen(QPen(Qt.black, 3))
            p.drawEllipse(
                QPoint(int(x_centro), int(y_centro)),
                CIRCLE_RADIUS, CIRCLE_RADIUS
            )
            p.setBrush(Qt.NoBrush)
        
        # Caixa que está sendo desenhada
        if self.mw.drawing and self.mw.start_point and self.mw.end_point:
            p.setPen(QPen(Qt.red, 6, Qt.DashLine))
            p.drawRect(QRect(self.mw.start_point, self.mw.end_point).normalized())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("./gui/main_window.ui", self)
        self.image_files = []
        self.current_dir = ""
        self.current_index = 0
        self.selected_box = None
        
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.annotations = []
        self.annotations_cache = {}
        self.column_coordinates = []
        
        #Jsons e Txt da imagem
        self.current_txt_content = ""
        self.current_json_content = {}
        
        self.img_label = ImageLabel(self)
        self.img_label.setParent(self.img_frame)

        self.img_label.setGeometry(0, 0, self.img_frame.width(), self.img_frame.height())

        self.img_list_model = QStringListModel()
        self.img_list.setModel(self.img_list_model)
        self.img_list.clicked.connect(self.select_img_from_list)

        self.img_label.setParent(None)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        layout = QVBoxLayout(self.img_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.proxy = self.scene.addWidget(self.img_label)
        self.view.fitInView(self.proxy, Qt.KeepAspectRatio)
        self.img_frame.setGeometry(self.imgFrame.rect())

        # Botões
        self.open_dir_button.clicked.connect(self.open_dir)
        self.next_img_button.clicked.connect(self.next_img)
        self.prev_img_button.clicked.connect(self.prev_img)
        self.save_img_button.clicked.connect(self.save_img)
        self.new_window_button.clicked.connect(self.open_new_window)

        # Espera um tempo para ajustar o tamanho do img_frame corretamente
        QTimer.singleShot(0, self.resize_img_frame)
        
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    def open_new_window(self):
        self.augment_window = DataAugmentationWindow(self)
        self.augment_window.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z:
            if self.selected_box and self.selected_box in self.annotations:
                self.annotations.remove(self.selected_box)
                self.selected_box = None
                self.update_annotations_list()
                self.img_label.update()
    
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.view.scale(1.1, 1.1)
        else:
            self.view.scale(1/1.1, 1/1.1)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.resize_img_frame()

    def resize_img_frame(self):
        self.img_frame.setGeometry(self.imgFrame.rect())

    def open_dir(self):
        dir = QFileDialog.getExistingDirectory(self)
        if dir:
            self.current_dir = dir
            self.image_files = [f for f in os.listdir(dir)
                                if f.lower().endswith(('.jpeg', '.jpg', '.png'))]
            self.current_index = 0
            if self.image_files:
                self.img_list_model.setStringList(self.image_files)
                self.show_img()

    def select_img_from_list(self, index):
        if index.row() != self.current_index:
            self.cache_current_annotations()
            self.current_index = index.row()
            self.show_img()
    
    def cache_current_annotations(self):
        if not self.image_files:
            return
        fname = self.image_files[self.current_index]
        self.annotations_cache[fname] = [
            AnnotationBox(QRect(box.rect), box.classe) for box in self.annotations
        ]
    
    def show_img(self):
        if not self.image_files:
            self.img_label.clear()
            self.update_annotations_list()
            return

        image_filename = self.image_files[self.current_index]
        caminho = os.path.join(self.current_dir, image_filename)

        self.annotations = []
        self.update_annotations_list()
        self.img_label.update()

        #Imagem é carregada em seu tamanho original
        pixmap = QPixmap(caminho)
        self.pixmap = QPixmap(caminho)
        self.img_label.resize(self.pixmap.size())
        self.img_label.setPixmap(self.pixmap)

        if image_filename in self.annotations_cache:
            self.annotations = [
                AnnotationBox(QRect(box.rect), box.classe)
                for box in self.annotations_cache[image_filename]
            ]
        else:
            # Carrega imagem do Json
            json_path = os.path.join(
                self.current_dir, f"{os.path.splitext(image_filename)[0]}.json"
            )
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for q in data.get("questions", []):
                        box_d = q.get("question_box", {})
                        classe = q.get("mark", "").lower()
                        if {"x", "y", "width", "height"} <= box_d.keys():
                            rect = QRect(
                                box_d["x"], box_d["y"],
                                box_d["width"], box_d["height"]
                            )
                            self.annotations.append(AnnotationBox(rect, classe))
                except Exception as e:
                    print(f"Erro ao ler JSON: {e}")
                    
        self.update_annotations_list()
        self.img_label.update()
            
    def update_annotations_list(self):
        linhas = [
            f"{i+1}: {box.classe} – ({box.rect.x()}, {box.rect.y()}, "
            f"{box.rect.width()}, {box.rect.height()})"
            for i, box in enumerate(self.annotations)
        ]
        self.annotations_list.setModel(QStringListModel(linhas))

            
    def save_img(self):
        if not self.image_files:
            return

        image_filename = self.image_files[self.current_index]
        base_name, _ = os.path.splitext(image_filename)
        txt_path = os.path.join(self.current_dir, f"{base_name}.txt")
        json_path = os.path.join(self.current_dir, f"{base_name}.json")

        # Salvar em .txt
        # Tamanho da imagem atual
        img_width = self.pixmap.width()
        img_height = self.pixmap.height()

        # Classe para ID
        mark_to_class = {
            "a": 0,
            "b": 1,
            "c": 2,
            "d": 3,
            "e": 4,
            "f": 5,
            "branco": 6
        }

        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                for box in self.annotations:
                    classe = box.classe
                    rect = box.rect

                    cls_id = mark_to_class[classe]
                    # Normalização
                    #x_center = (rect.x() + rect.width() / 2) / img_width
                    #y_center = (rect.y() + rect.height() / 2) / img_height
                    x_norm = rect.x() / img_width
                    y_norm = rect.y() / img_height
                    width = rect.width() / img_width
                    height = rect.height() / img_height

                    f.write(f"{cls_id} {x_norm:.17f} {y_norm:.17f} {width:.17f} {height:.17f}\n")
            print(f"Arquivo TXT salvo em: {txt_path}")
        except Exception as e:
            print(f"Erro ao salvar TXT: {e}")

        # Salvar em .json
        data = {
            "image": image_filename,
            "form_id": "", 
            "form_id_box": {},
            "columns": [], 
            "questions": []
        }
        
        for cr in self.column_coordinates:
            data["columns"].append({
                "x": cr.x(),
                "y": cr.y(),
                "width": cr.width(),
                "height": cr.height()
            })

        for i, box in enumerate(self.annotations, start=1):
            question_data = {
                "number": i,
                "mark": box.classe,
                "question_box": {
                    "x": box.rect.x(),
                    "y": box.rect.y(),
                    "width": box.rect.width(),
                    "height": box.rect.height()
                },
                "number_box": {},
                "mark_box": {}
            }
            data["questions"].append(question_data)

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Arquivo JSON salvo em: {json_path}")
        except Exception as e:
            print(f"Erro ao salvar JSON: {e}")

    def next_img(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.cache_current_annotations()
            self.current_index += 1
            self.show_img()

    def prev_img(self):
        if self.image_files and self.current_index > 0:
            self.cache_current_annotations()
            self.current_index -= 1
            self.show_img()
            
    def get_rect(self):
        if not self.start_point or not self.end_point:
            return QRect()
        return QRect(self.start_point, self.end_point).normalized()
    
    def finalize_box(self):
        rect = self.get_rect()
        if rect.height() < 10 or rect.width() < 10:
            return

        self.column_coordinates.append(rect)
        
        opcoes = ["a", "b", "c", "branco"] if rect.width() < LIMIAR_LARGURA else ["a", "b", "c", "d", "e", "f", "branco"]

        altura_media = 58.5
        num_caixas = int(rect.height() // altura_media)
        if num_caixas == 0:
            return

        start_num = len(self.annotations) + 1
        total_h = rect.height()
        step = total_h / num_caixas
        width = rect.width()
        left = rect.left()
        frac = 0.15

        # Lista dos retângulos das caixas
        self.temp_rects = []
        for i in range(num_caixas):
            center_y = rect.top() + (i + 0.5) * step
            new_h = step * (1 + frac)
            top = max(rect.top(), center_y - new_h / 2)
            bottom = min(rect.bottom(), center_y + new_h / 2)
            sub_rect = QRect(
                int(round(left)),
                int(round(top)),
                int(round(width)),
                int(round(bottom - top))
            )
            self.temp_rects.append(sub_rect)

        # Dicionário para armazenar classe associada ao índice
        self.temp_annotations = {}

        # Callback acionado ao selecionar a classe de uma questão
        def class_callback(idx, val):
            if 0 <= idx < len(self.temp_rects):
                rect = self.temp_rects[idx]
                self.temp_annotations[idx] = (rect, val)

                # Verifica se já existe um box para esse rect
                for ann in self.annotations:
                    if ann.rect == rect:
                        ann.classe = val
                        break
                else:
                    self.annotations.append(AnnotationBox(rect, val))

                self.update_annotations_list()
                self.img_label.update()

        # Mostra o diálogo com a função de callback
        dialog = ClassSelectionDialog(num_caixas, opcoes, start_num, callback=class_callback, parent=self)
        dialog.exec_()

        self.temp_rects = []
        self.temp_annotations = {}

            
    def load_annotations(self, img_path):
        import json, os
        base, _ = os.path.splitext(img_path)
        json_file = base + ".json"
        self.annotations.clear()
        self.column_coordinates.clear()
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for col in data.get("columns", []):
                cr = QRect(col["x"], col["y"], col["width"], col["height"])
                self.column_coordinates.append(cr)
            for item in data:
                rect = QRect(item["x"], item["y"], item["width"], item["height"])
                self.annotations.append(AnnotationBox(rect, item["mark"]))
        self.update_annotations_list()
        self.img_label.update()

    def update_annotations_list(self):
        linhas = [
            f"{i+1}: Classe {box.classe} - "
            f"({box.rect.x()}, {box.rect.y()}, "
            f"{box.rect.width()}, {box.rect.height()})"
            for i, box in enumerate(self.annotations)
        ]
        model = QStringListModel(linhas)
        self.annotations_list.setModel(model)

    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
