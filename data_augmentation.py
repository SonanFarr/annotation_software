# data_augmentation_window.py
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QLabel, QVBoxLayout, QGraphicsView, QGraphicsScene, QDialog, QComboBox, QPushButton, QInputDialog, QMessageBox
from PyQt5.QtCore import QStringListModel, QTimer, Qt, QRect
from PyQt5 import uic
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
import numpy as np
import json
import cv2
import os

HANDLE = 6
LIMIAR_LARGURA = 800
NUM_AREA_FRAC_6 = 0.30
NUM_AREA_FRAC_3 = 0.502
CIRCLE_RADIUS = 30
ALTURA_CENTRO = 0.5

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox

class SubcolunaSwapDialog(QDialog):
    def __init__(self, subcolunas_labels, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Subcolunas para Troca")

        self.combo1 = QComboBox()
        self.combo1.addItems(subcolunas_labels)

        self.combo2 = QComboBox()
        self.combo2.addItems(subcolunas_labels)

        self.class_selector = QComboBox()
        self.class_selector.addItems(["a", "b", "c", "d", "e", "f", "branco"])

        layout = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Primeira subcoluna:"))
        row1.addWidget(self.combo1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Segunda subcoluna:"))
        row2.addWidget(self.combo2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Nova classe das questões:"))
        row3.addWidget(self.class_selector)

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)

        btn_ok = QPushButton("Trocar")
        btn_ok.clicked.connect(self.accept_if_valid)

        layout.addWidget(btn_ok)
        self.setLayout(layout)

    def accept_if_valid(self):
        if self.combo1.currentIndex() == self.combo2.currentIndex():
            QMessageBox.warning(self, "Erro", "Selecione duas subcolunas diferentes.")
            return
        self.accept()

    def get_selection(self):
        return (
            self.combo1.currentIndex(),
            self.combo2.currentIndex(),
            self.class_selector.currentText()
        )


class SelectNewClass(QDialog):
    def __init__(self, classes, current_class=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecione a classe")
        self.selected_class = None

        layout = QVBoxLayout(self)

        label = QLabel("Escolha a classe para a anotação:")
        layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.addItems(classes)
        if current_class and current_class in classes:
            self.combo.setCurrentText(current_class)
        layout.addWidget(self.combo)

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    def accept(self):
        self.selected_class = self.combo.currentText()
        super().accept()

class AnnotationBox:
    def __init__(self, rect: QRect, classe: str):
        self.rect = rect
        self.classe = classe
        self.selected = False

class ImageLabel(QLabel):
    def __init__(self, main_window):
        super().__init__(main_window.img_frame)
        self.main_window = main_window
        self.copy_start = None
        self.copied_region = None

        self.copy_start = None
        self.copied_region = None

    def mousePressEvent(self, event):
        if not self.main_window.pixmap or self.main_window.pixmap.isNull():
            return

        label_width = self.width()
        label_height = self.height()
        img_width = self.main_window.pixmap.width()
        img_height = self.main_window.pixmap.height()

        x = int(event.pos().x() * img_width / label_width)
        y = int(event.pos().y() * img_height / label_height)

        #Copiar região da anotação
        if event.button() == Qt.RightButton:
            for box in self.main_window.annotations:
                if box.rect.contains(x, y):
                    rect = box.rect
                    x1, y1, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                    x2 = x1 + w
                    y2 = y1 + h
                    self.main_window.copy_region(x1, y1, x2, y2)
                    return 
        elif event.button() == Qt.LeftButton: 
                #Seleciona uma região que deseja editar
                for box in self.main_window.annotations:
                    if box.rect.contains(x, y):
                        #Seleciona todas as classes da imagem atual e cria uma janela de seleção
                        classes = list(set(b.classe for b in self.main_window.annotations if b.classe))
                        dlg = SelectNewClass(classes, current_class=box.classe, parent=self.main_window)
                        if dlg.exec_() == QDialog.Accepted and dlg.selected_class:
                            nova_classe = dlg.selected_class
                            box.classe = nova_classe
                            self.main_window.img_label.update()

                            # Copia e cola a região da primeira anotação com essa classe
                            for other_box in self.main_window.annotations:
                                if other_box.classe == nova_classe and other_box != box:
                                    x1, y1 = other_box.rect.x(), other_box.rect.y()
                                    w, h = other_box.rect.width(), other_box.rect.height()
                                    x2, y2 = x1 + w, y1 + h
                                    self.main_window.copy_region(x1, y1, x2, y2)
                                    rect = box.rect
                                    self.main_window.paste_region(rect.x(), rect.y(), rect.width(), rect.height())
                                    break
                        return

    #Desenha as anotações
    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        for box in self.main_window.column_coordinates:
            p.setPen(QPen(Qt.blue, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRect(box.rect)
            
        if hasattr(self.parent(), "subcolunas"):
            for sub_rect, _, _ in self.parent().subcolunas:
                p.setPen(QPen(Qt.darkYellow, 1, Qt.DotLine))
                p.drawRect(sub_rect)


class DataAugmentationWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "gui", "augmentation_window.ui")
        uic.loadUi(ui_path, self)

        self.image_files = []
        self.current_dir = ""
        self.current_index = 0

        self.img_label = ImageLabel(self)
        self.img_label.setParent(self.img_frame)
        self.annotations = []
        self.column_coordinates = []
        self.subcolunas = []
        self.img_label.setGeometry(0, 0, self.img_frame.width(), self.img_frame.height())

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

        self.img_list_model = QStringListModel()
        self.img_list.setModel(self.img_list_model)
        self.img_list.clicked.connect(self.select_img_from_list)

        self.open_dir_button.clicked.connect(self.open_dir)
        self.next_img_button.clicked.connect(self.next_img)
        self.prev_img_button.clicked.connect(self.prev_img)
        self.btn_trocar_subcolunas.clicked.connect(self.abrir_dialogo_troca_subcolunas)

        QTimer.singleShot(0, self.resize_img_frame)
    
    def abrir_dialogo_troca_subcolunas(self):
        image_filename = self.image_files[self.current_index]
        caminho = os.path.join(self.current_dir, image_filename)
        
        if not self.pixmap:
            QMessageBox.warning(self, "Erro", "Nenhuma imagem carregada.")
            return

        if not self.column_coordinates:
            QMessageBox.warning(self, "Erro", "Nenhuma coluna detectada.")
            return

        # Lê o arquivo JSON associado à imagem
        json_path = os.path.splitext(caminho)[0] + '.json'
        if not os.path.exists(json_path):
            QMessageBox.warning(self, "Erro", f"Arquivo JSON não encontrado: {json_path}")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Falha ao carregar JSON: {e}")
                return

        self.questions = data.get("questions", [])

        # Monta os nomes das subcolunas disponíveis (ignorando a de número, se necessário)
        sub_labels = [f"Subcoluna {i}" for i in range(len(self.subcolunas))]

        # Abre o diálogo personalizado
        dialog = SubcolunaSwapDialog(sub_labels, self)
        if dialog.exec_():
            idx1, idx2, nova_classe = dialog.get_selection()

            # Troca visual das subcolunas na imagem
            imagem_sintetizada = self.trocar_subcolunas_na_imagem(idx1, idx2, self.pixmap)
            
            # Converte para QPixmap para exibição
            pixmap_sintetizado = QPixmap.fromImage(imagem_sintetizada)

            # Atualiza o QLabel ou widget de imagem com a nova imagem
            self.img_label.setPixmap(pixmap_sintetizado)

            # Determina quais colunas foram afetadas (com base no índice de subcolunas)
            col1 = self.subcolunas[idx1][1]
            col2 = self.subcolunas[idx2][1]
            colunas_afetadas = set([col1, col2])

            # Atualiza a classe ("mark") das questões nas colunas afetadas
            for q in self.questions:
                if q.get("column_index") in colunas_afetadas:
                    q["mark"] = nova_classe

            # Novo nome da imagem e JSON
            sintetic_image_name = os.path.basename(os.path.splitext(caminho)[0]) + "_sintetic.jpg"
            sintetic_json_name = os.path.basename(os.path.splitext(caminho)[0]) + "_sintetic.json"
            sintetic_txt_name = os.path.basename(os.path.splitext(caminho)[0]) + "_sintetic.txt"

            sintetic_image_path = os.path.join(os.path.dirname(os.path.splitext(caminho)[0]), sintetic_image_name)
            sintetic_json_path = os.path.join(os.path.dirname(json_path), sintetic_json_name)
            sintetic_txt_path = os.path.join(os.path.dirname(json_path), sintetic_txt_name)

            # Salva nova imagem
            imagem_sintetizada.save(sintetic_image_path, "JPG")

            # Atualiza o nome da imagem no JSON e salva o novo arquivo
            data["image"] = sintetic_image_name
            data["questions"] = self.questions

            with open(sintetic_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            #Gera novo txt
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

            with open(sintetic_txt_path, 'w', encoding='utf-8') as f:
                for q in self.questions:
                    classe = q["mark"] 
                    cls_id = mark_to_class[classe]

                    box = q["question_box"]

                    x = box["x"] / img_width
                    y = box["y"] / img_height
                    width = box["width"] / img_width
                    height = box["height"] / img_height
                     
                    f.write(f"{cls_id} {x:.17f} {y:.17f} {width:.17f} {height:.17f}\n")

            QMessageBox.information(self, "Sucesso", f"Imagem, TXT e JSON sintetizados salvos:\n{sintetic_image_name}\n{sintetic_json_name}\n{sintetic_txt_name}")

            self.show_img()  # Recarrega a imagem para refletir alterações visuais
    
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

    def select_img_from_list(self, index):
        if index.row() != self.current_index:
            self.current_index = index.row()
            self.show_img()

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

    def next_img(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_img()

    def prev_img(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_img()

    def show_img(self):
        image_filename = self.image_files[self.current_index]
        caminho = os.path.join(self.current_dir, image_filename)

        #Imagem é carregada em seu tamanho original
        pixmap = QPixmap(caminho)
        self.pixmap = QPixmap(caminho)
        self.img_label.resize(self.pixmap.size())
        self.img_label.setPixmap(self.pixmap) 

        self.annotations.clear()
        self.column_coordinates.clear()
        
        json_path = os.path.splitext(caminho)[0] + '.json'
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for q in data.get("questions", []):
                b = q["question_box"]
                classe = q.get("mark", "").lower()
                rect = QRect(b["x"], b["y"], b["width"], b["height"])
                self.annotations.append(AnnotationBox(rect, classe))
            
            for col in data.get("columns", []):
                rect = QRect(col["x"], col["y"], col["width"], col["height"])
                self.column_coordinates.append(AnnotationBox(rect, "x"))

            # Extrair subcolunas de alternativas (ignorando área dos números)
            self.subcolunas.clear()
            for col_index, coluna in enumerate(self.column_coordinates):
                sub_rets = self.extrair_subcolunas_de_coluna(coluna)
                for sub_index, sub_rect in enumerate(sub_rets):
                    self.subcolunas.append((sub_rect, col_index, sub_index))
                
            self.img_label.update()       
                
    def extrair_subcolunas_de_coluna(self, coluna: AnnotationBox, num_subcolunas=6, frac_num_area=0.3):
        subcolunas = []
        rect = coluna.rect

        largura_total = rect.width()
        altura_total = rect.height()

        largura_num_area = int(largura_total * frac_num_area)
        largura_alt_area = largura_total - largura_num_area

        largura_uma_alt = largura_alt_area // num_subcolunas

        for i in range(num_subcolunas):
            left = rect.left() + largura_num_area + i * largura_uma_alt
            sub_rect = QRect(left, rect.top(), largura_uma_alt, altura_total)
            subcolunas.append(sub_rect)
        
        return subcolunas

    def trocar_subcolunas_na_imagem(self, idx1, idx2, imagem=None):
        if imagem is None:
            imagem = self.image

        # Converte QPixmap -> QImage (para edição)
        image_qt = imagem.toImage().convertToFormat(QImage.Format_RGB32)

        # Cria pintor na QImage
        painter = QPainter(image_qt)

        # Define os retângulos das subcolunas
        col1_rect, _, _ = self.subcolunas[idx1]
        col2_rect, _, _ = self.subcolunas[idx2]

        # Copia os pedaços da imagem original (como QPixmap)
        col1_img = imagem.copy(col1_rect)
        col2_img = imagem.copy(col2_rect)

        # Desenha as subcolunas trocadas
        painter.drawPixmap(col1_rect.topLeft(), col2_img)
        painter.drawPixmap(col2_rect.topLeft(), col1_img)
        painter.end()

        # Retorna imagem modificada como QImage
        return image_qt
    
    def copy_region(self, x1, y1, x2, y2):
        qimage = self.pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        width, height = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape((height, width, 4))

        x1, x2 = sorted((max(0, x1), min(width, x2)))
        y1, y2 = sorted((max(0, y1), min(height, y2)))

        if x2 > x1 and y2 > y1:
            self.copied_region = arr[y1:y2, x1:x2].copy()

    def paste_region(self, x, y, width, height):
        region = self.copied_region

        #Cola a região em toda a região da anotação
        resized_region = cv2.resize(region, (width, height), interpolation=cv2.INTER_LINEAR)

        qimage = self.pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        img_width, img_height = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape((img_height, img_width, 4))

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img_width, x + width)
        y2 = min(img_height, y + height)

        region_w = x2 - x1
        region_h = y2 - y1

        if region_w > 0 and region_h > 0:
            arr[y1:y2, x1:x2] = resized_region[0:region_h, 0:region_w]

        new_qimage = QImage(arr.data, img_width, img_height, QImage.Format_RGBA8888)
        self.pixmap = QPixmap.fromImage(new_qimage)
        self.img_label.setPixmap(self.pixmap)
        self.img_label.resize(self.pixmap.size())
