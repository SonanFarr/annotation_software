import sys
import os
import json
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
        self.save_img_button.clicked.connect(self.save_img)

        #Jsons e Txt da imagem
        self.current_txt_content = ""
        self.current_json_content = {}

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
            self.img_label.setPixmap(pixmap_scaled)

            #Atualiza a seleção da lista para a imagem atual
            index = self.img_list_model.index(self.current_index)
            self.img_list.setCurrentIndex(index)

            #Carrega o .json e .txt associados caso exista
            base_name, _ = os.path.splitext(image_filename)
            txt_path = os.path.join(self.current_dir, f"{base_name}.txt")
            json_path = os.path.join(self.current_dir, f"{base_name}.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        self.current_json_content = json.load(f)
                        print(self.current_json_content)
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

    def next_img(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_img()

    def prev_img(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_img()

    def save_img(self):
        if self.image_files:
            #Configurando o arquivo
            image_filename = self.image_files[self.current_index]
            base_name, _ = os.path.splitext(image_filename)
            txt_path = os.path.join(self.current_dir, f"{base_name}.txt")
            json_path = os.path.join(self.current_dir, f"{base_name}.json")
            content = f"Nome: {image_filename}\n"
            #.txt
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(content)
            #.json
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({"conteudo": content}, f, indent=4, ensure_ascii=False)
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
