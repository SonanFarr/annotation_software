import sys
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QLabel
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QStringListModel
from PyQt5 import uic

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("./gui/main_window.ui", self)
        self.image_files = []
        self.current_dir = ""
        self.current_index = 0
        
        # QLabel dentro do QFrame para mostrar a imagem
        self.img_label = QLabel(self.img_frame)
        self.img_label.setGeometry(0, 0, self.img_frame.width(), self.img_frame.height())

        self.img_list_model = QStringListModel()
        self.img_list.setModel(self.img_list_model)
        self.img_list.clicked.connect(self.select_img_from_list)

        # Botões
        self.open_dir_button.clicked.connect(self.open_dir)
        self.next_img_button.clicked.connect(self.next_img)
        self.prev_img_button.clicked.connect(self.prev_img)

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
            pixmap = QPixmap(caminho)
            tamanho = self.img_label.size()
            pixmap_scaled = pixmap.scaled(
                tamanho,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.img_label.setPixmap(pixmap_scaled)
            #Atualiza a seleção da lista para a imagem atual
            index = self.img_list_model.index(self.current_index)
            self.img_list.setCurrentIndex(index)
        else:
            self.img_label.clear()

    def next_img(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_img()

    def prev_img(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_img()
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
