# data_augmentation_window.py
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QLabel, QVBoxLayout, QGraphicsView, QGraphicsScene
from PyQt5.QtCore import QStringListModel, QTimer, Qt, QRect
from PyQt5 import uic
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
import numpy as np
import json

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

import os

class ImageLabel(QLabel):
    def __init__(self, main_window):
        super().__init__(main_window.img_frame)
        self.main_window = main_window
        self.copy_start = None
        self.copied_region = None

    # —— já existente: mousePressEvent etc. ——

    def paintEvent(self, ev):
        # primeiro desenha a imagem-base
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # desenha cada AnnotationBox carregada
        for box in self.main_window.annotations:
            # borda azul
            p.setPen(QPen(Qt.blue, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRect(box.rect)

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

        QTimer.singleShot(0, self.resize_img_frame)

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
        json_path = os.path.splitext(caminho)[0] + '.json'
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for q in data.get("questions", []):
                b = q["question_box"]
                classe = q.get("mark", "").lower()
                rect = QRect(b["x"], b["y"], b["width"], b["height"])
                self.annotations.append(AnnotationBox(rect, classe))

        # força redesenho do label
        self.img_label.update()       
        
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

    def paste_region(self, x, y):
        if not hasattr(self.copied_region, 'shape'):
            print("Região copiada não é um array.")
            return

        region = self.copied_region
        h, w, _ = region.shape

        qimage = self.pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        width, height = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape((height, width, 4))

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(width, x + w)
        y2 = min(height, y + h)

        region_w = x2 - x1
        region_h = y2 - y1

        if region_w > 0 and region_h > 0:
            arr[y1:y2, x1:x2] = region[0:region_h, 0:region_w]

        new_qimage = QImage(arr.data, width, height, QImage.Format_RGBA8888)
        self.pixmap = QPixmap.fromImage(new_qimage)
        self.img_label.setPixmap(self.pixmap)
        self.img_label.resize(self.pixmap.size())
