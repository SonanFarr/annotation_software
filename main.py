import sys
import os
import numpy as np
from PyQt5.QtGui import QImage
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QLabel
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QStringListModel
from PyQt5 import uic
import json

from PyQt5.QtWidgets import QLabel, QInputDialog
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

class ClassSelectionDialog(QDialog):
    def __init__(self, num_questoes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Classe das Questões")
        self.answers = [None] * num_questoes

        self.button_groups = []  # Armazena os botões de cada questão
        layout = QVBoxLayout()

        for i in range(num_questoes):
            hbox = QHBoxLayout()
            label = QLabel(f"Questão {i+1}:")
            hbox.addWidget(label)

            buttons = []
            for opcao in ["a", "b", "c", "d"]:
                btn = QPushButton(opcao.upper())
                btn.setCheckable(True)
                btn.clicked.connect(lambda _, i=i, opcao=opcao: self.set_answer(i, opcao))
                hbox.addWidget(btn)
                buttons.append(btn)

            self.button_groups.append(buttons)
            layout.addLayout(hbox)

        self.setLayout(layout)

    def set_answer(self, index, value):
        self.answers[index] = value

        # Altera a cor dos botões: selecionado = azul, outros = padrão
        for btn in self.button_groups[index]:
            if btn.text().lower() == value:
                btn.setStyleSheet("background-color: lightblue; font-weight: bold;")
            else:
                btn.setStyleSheet("")

        # Fecha automaticamente quando todas forem selecionadas
        if all(a is not None for a in self.answers):
            self.accept()

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setMouseTracking(True)
        self.boxes = []

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_window.start_point = event.pos()
            self.main_window.drawing = True

    def mouseMoveEvent(self, event):
        if self.main_window.drawing:
            self.main_window.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_window.drawing = False
            self.main_window.end_point = event.pos()
            self.main_window.finalize_box()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))

        # Caixa temporária que está sendo desenhada com o mouse
        if self.main_window.drawing and self.main_window.start_point and self.main_window.end_point:
            rect = self.main_window.get_rect()
            painter.drawRect(rect)

        # Desenha cada anotação (caixas com classe)
        for rect, classe in self.main_window.annotations:
            painter.drawRect(rect)
            painter.drawText(rect.topLeft() + QPoint(5, 15), classe.upper())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("./gui/main_window.ui", self)
        self.image_files = []
        self.current_dir = ""
        self.current_index = 0
        
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.annotations = []
        
        #Jsons e Txt da imagem
        self.current_txt_content = ""
        self.current_json_content = {}
        
        self.img_label = ImageLabel(self)
        self.img_label.setParent(self.img_frame)

        self.img_label.setGeometry(0, 0, self.img_frame.width(), self.img_frame.height())

        self.img_list_model = QStringListModel()
        self.img_list.setModel(self.img_list_model)
        self.img_list.clicked.connect(self.select_img_from_list)

        # Botões
        self.open_dir_button.clicked.connect(self.open_dir)
        self.next_img_button.clicked.connect(self.next_img)
        self.prev_img_button.clicked.connect(self.prev_img)
        self.save_img_button.clicked.connect(self.save_img)

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
        self.current_index = index.row()
        self.show_img()

    def show_img(self):
        if self.image_files:
            caminho = os.path.join(self.current_dir, self.image_files[self.current_index])
            image_filename = self.image_files[self.current_index]
            pixmap = QPixmap(caminho)
            
            tamanho = self.img_label.size()
            pixmap_scaled = pixmap.scaled(
                tamanho,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.pixmap = pixmap_scaled
            self.img_label.setPixmap(self.pixmap)

            #Atualiza a seleção da lista para a imagem atual
            index = self.img_list_model.index(self.current_index)
            self.img_list.setCurrentIndex(index)
            
            self.annotations = []
            self.update_annotations_list()
            self.img_label.update()
            
            #Carrega o .json e .txt associados caso exista
            base_name, _ = os.path.splitext(image_filename)
            txt_path = os.path.join(self.current_dir, f"{base_name}.txt")
            json_path = os.path.join(self.current_dir, f"{base_name}.json")
            #Carrega o Json e importa as anotações
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        self.current_json_content = json.load(f)
                        print(self.current_json_content)

                        # Limpa anotações anteriores
                        self.annotations = []

                        # Recria as caixas
                        for question in self.current_json_content.get("questions", []):
                            box = question.get("question_box", {})
                            classe = question.get("mark", "").lower()

                            if all(k in box for k in ("x", "y", "width", "height")) and classe in ["a", "b", "c", "d", "e"]:
                                rect = QRect(
                                    box["x"],
                                    box["y"],
                                    box["width"],
                                    box["height"]
                                )
                                self.annotations.append((rect, classe))
                        #Atualiza a lista e anotações
                        self.update_annotations_list()
                        self.img_label.update()

                except Exception as e:
                    print(f"Erro ao ler JSON: {e}")

            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        self.current_txt_content = f.read()
                        print (f"{self.current_txt_content}")
                except Exception as e:
                    print(f"Erro ao ler TXT: {e}")
        else:
            self.img_label.clear()
            
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
            "e": 4
        }

        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                for rect, classe in self.annotations:
                    if classe not in mark_to_class:
                        continue 

                    cls_id = mark_to_class[classe]
                    # Normalização
                    x_center = (rect.x() + rect.width() / 2) / img_width
                    y_center = (rect.y() + rect.height() / 2) / img_height
                    width = rect.width() / img_width
                    height = rect.height() / img_height

                    f.write(f"{cls_id} {x_center:.17f} {y_center:.17f} {width:.17f} {height:.17f}\n")
            print(f"Arquivo TXT salvo em: {txt_path}")
        except Exception as e:
            print(f"Erro ao salvar TXT: {e}")

        # Salvar em .json
        data = {
            "image": image_filename,
            "form_id": "", 
            "form_id_box": {}, 
            "questions": []
        }

        for i, (rect, classe) in enumerate(self.annotations, start=1):
            question_data = {
                "number": i,
                "mark": classe,
                "question_box": {
                    "x": rect.x(),
                    "y": rect.y(),
                    "width": rect.width(),
                    "height": rect.height()
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
            self.current_index += 1
            self.show_img()

    def prev_img(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_img()
            
    def get_rect(self):
        if not self.start_point or not self.end_point:
            return QRect()
        return QRect(self.start_point, self.end_point).normalized()

    def finalize_box(self):
        rect = self.get_rect()
        if rect.height() < 10 or rect.width() < 10:
            return  # ignora regiões pequenas

        altura_media, ok = QInputDialog.getInt(self, "Altura Média", "Informe a altura média das questões:", min=1)
        if not ok:
            return

        num_caixas = rect.height() // altura_media
        if num_caixas == 0:
            return

        # Mostra o diálogo com os botões
        dialog = ClassSelectionDialog(num_caixas, self)
        if dialog.exec_() == QDialog.Accepted:
            boxes = []
            for i in range(num_caixas):
                sub_rect = QRect(rect.left(), rect.top() + i * altura_media, rect.width(), altura_media)
                classe = dialog.answers[i]
                if classe:
                    boxes.append((sub_rect, classe))
                    self.annotations.append((sub_rect, classe))
            self.update_annotations_list()
            self.img_label.update()

    def update_annotations_list(self):
        from PyQt5.QtCore import QStringListModel
        #lista = [f"{i+1}: Classe {c} - {r}" for i, (r, c) in enumerate(self.annotations)]
        lista = [f"{i+1}: Classe {c} - ({r.x()}, {r.y()}, {r.width()}, {r.height()})" for i, (r, c) in enumerate(self.annotations)]
        model = QStringListModel(lista)
        self.annotations_list.setModel(model)

    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
