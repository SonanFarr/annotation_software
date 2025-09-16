# data_augmentation_window.py
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QLabel, QVBoxLayout, QGraphicsView, QGraphicsScene, QDialog, QComboBox, QPushButton, QInputDialog, QMessageBox, QDialogButtonBox, QWidget
from PyQt5.QtCore import QStringListModel, QTimer, Qt, QRect
from PyQt5 import uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QStandardItemModel, QStandardItem
from collections import Counter
import numpy as np
import json
import cv2
import os
import itertools
from copy import deepcopy
import random

HANDLE = 6
LIMIAR_LARGURA = 800
NUM_AREA_FRAC_6 = 0.30
NUM_AREA_FRAC_3 = 0.478
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
        self.class_selector.addItems(["a", "b", "c", "d", "e", "f", "branco", "indeterminado"])

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

class SinteseIndeterminado(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Síntese Múltipla")

        layout = QVBoxLayout(self)

        # Seleção da quantidade de alternativas
        self.alt_combo = QComboBox()
        self.alt_combo.addItems(["3", "6"])
        layout.addWidget(QLabel("Número de alternativas:"))
        layout.addWidget(self.alt_combo)

        # Seleção da alternativa originalmente marcada
        self.mark_combo = QComboBox()
        self.mark_combo.addItems(["a", "b", "c", "d", "e", "f"])
        layout.addWidget(QLabel("Alternativa originalmente marcada:"))
        layout.addWidget(self.mark_combo)

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def get_selection(self):
        return int(self.alt_combo.currentText()), self.mark_combo.currentText()

class DataAugmentationWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "gui", "augmentation_window.ui")
        uic.loadUi(ui_path, self)

        self.num_alternativas = 6
        
        lbl_alt = QLabel("Quantidade de alternativas:")
        self.combo_num_alt = QComboBox()
        self.combo_num_alt.addItems(["3", "6"])
        self.combo_num_alt.setCurrentText(str(self.num_alternativas))
        self.combo_num_alt.currentTextChanged.connect(self.on_num_alternativas_changed)

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
    
        self.alt_selector_widget = QWidget(self)
        alt_layout = QHBoxLayout(self.alt_selector_widget)
        alt_layout.setContentsMargins(0, 0, 0, 0)
        alt_layout.setSpacing(6)

        alt_layout.addWidget(lbl_alt)
        alt_layout.addWidget(self.combo_num_alt)
        alt_layout.addStretch()

        form_layout = self.groupBox.layout()
        row = form_layout.rowCount() - 1
        form_layout.insertRow(row, self.alt_selector_widget)
        
        self.btn_ind_sintese.clicked.connect(self.sintese_indeterminado)

        QTimer.singleShot(0, self.resize_img_frame)
        
        self.contar_classes_em_pasta()

    def on_num_alternativas_changed(self):
        self.num_alternativas = int(self.combo_num_alt.currentText())
        
        for col_index, coluna in enumerate(self.column_coordinates):
            col_width = coluna.rect.width()

            if self.num_alternativas == 3:
                frac_num = NUM_AREA_FRAC_3 if col_width < LIMIAR_LARGURA else NUM_AREA_FRAC_6
            else:
                frac_num = NUM_AREA_FRAC_6
        
        self.subcolunas.clear()
        for col_index, coluna in enumerate(self.column_coordinates):
            sub_rets = self.extrair_subcolunas_de_coluna(coluna, 
                                                        num_subcolunas=self.num_alternativas,
                                                        frac_num_area=frac_num)
            for sub_index, sub_rect in enumerate(sub_rets):
                self.subcolunas.append((sub_rect, col_index, sub_index))
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_X:
            self.contar_classes_em_pasta()
        else:
            super().keyPressEvent(event)

    def contar_classes_em_pasta(self):
        pasta = self.current_dir
        contador = Counter()

        if not os.path.exists(pasta):
            self.table_class.clear()
            self.table_class.setRowCount(0)
            return

        for nome_arquivo in os.listdir(pasta):
            if nome_arquivo.lower().endswith(".json"):
                caminho = os.path.join(pasta, nome_arquivo)
                try:
                    with open(caminho, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for q in data.get("questions", []):
                        mark = q.get("mark", "").strip().lower()
                        if mark:
                            contador[mark] += 1
                except Exception as e:
                    print(f"Erro {nome_arquivo}: {e}")
        
        itens = sorted(contador.items())
        itens = [i for i in itens if i[0] != "branco"] + [i for i in itens if i[0] == "branco"]
        
        # Limpa a tabela e define cabeçalhos
        self.table_class.clear()
        self.table_class.setRowCount(0)
        self.table_class.setColumnCount(2)
        self.table_class.setHorizontalHeaderLabels(["Classe", "Quantidade"])
        self.table_class.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Preenche a tabela
        for linha, (classe, qtd) in enumerate(itens):
            self.table_class.insertRow(linha)
            self.table_class.setItem(linha, 0, QTableWidgetItem(classe))
            self.table_class.setItem(linha, 1, QTableWidgetItem(str(qtd)))
 
    def abrir_dialogo_troca_subcolunas(self):
        import traceback
        image_filename = self.image_files[self.current_index]
        caminho = os.path.join(self.current_dir, image_filename)

        if not getattr(self, "pixmap", None):
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

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao carregar JSON: {e}")
            return

        questions = data.get("questions", [])

        total_sub = len(getattr(self, "subcolunas", []))
        if total_sub < 2:
            QMessageBox.warning(self, "Aviso", "Subcolunas insuficientes para trocar.")
            return
        if self.num_alternativas == 3:
            class_names = ["A", "B", "C"]
        else :
            class_names = ["A", "B", "C", "D", "E", "F"]
        visible_indices = [i for i in range(total_sub)]

        sub_labels = [
            f"Subcoluna {i+1} - ({class_names[i % len(class_names)]})"
            for i in visible_indices
        ]

        img_q = self.pixmap.toImage().convertToFormat(QImage.Format_RGB32)

        def _col_index_from_sub(idx):
            entry = self.subcolunas[idx]
            if isinstance(entry, (tuple, list)) and len(entry) > 1:
                return entry[1]
            return None

        def _sync_annotations_from_questions():
            try:
                for q in questions:
                    qb = q.get("question_box", {})
                    for ann in self.annotations:
                        r = ann.rect
                        if (r.x() == qb.get("x") and r.y() == qb.get("y")
                                and r.width() == qb.get("width") and r.height() == qb.get("height")):
                            ann.classe = q.get("mark", ann.classe)
            except Exception:
                traceback.print_exc()

        # monta diálogo
        dialog = QDialog(self)
        dialog.setWindowTitle("Trocar Subcolunas (múltiplas trocas)")
        layout = QVBoxLayout(dialog)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Primeira subcoluna:"))
        combo1 = QComboBox()
        combo1.addItems(sub_labels)
        h1.addWidget(combo1)
        layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Segunda subcoluna:"))
        combo2 = QComboBox()
        combo2.addItems(sub_labels)
        h2.addWidget(combo2)
        layout.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Nova classe para questões afetadas:"))
        combo_classe = QComboBox()
        combo_classe.addItems(["a", "b", "c", "d", "e", "f", "branco", "indeterminado"])
        h3.addWidget(combo_classe)
        layout.addLayout(h3)

        # botões de ação
        botoes_layout = QHBoxLayout()
        btn_add = QPushButton("Adicionar Troca")
        btn_save = QPushButton("Finalizar e Salvar")
        btn_ind = QPushButton("Sintetizar Indeterminado")
        btn_cancel = QPushButton("Cancelar")
        botoes_layout.addWidget(btn_add)
        botoes_layout.addWidget(btn_save)
        botoes_layout.addWidget(btn_cancel)
        botoes_layout.addWidget(btn_ind)
        layout.addLayout(botoes_layout)

        # estado mutável acessível pelas funções internas
        state = {"img_q": img_q}

        def aplicar_troca():
            # mapear seleção para índices reais
            sel1 = combo1.currentIndex()
            sel2 = combo2.currentIndex()
            if sel1 == sel2:
                QMessageBox.warning(dialog, "Erro", "Escolha duas subcolunas diferentes.")
                return

            actual_idx1 = visible_indices[sel1]
            actual_idx2 = visible_indices[sel2]
            nova_classe = combo_classe.currentText()

            try:
                current_pixmap = QPixmap.fromImage(state["img_q"])
                result = self.trocar_subcolunas_na_imagem(actual_idx1, actual_idx2, current_pixmap)
            except Exception as e:
                QMessageBox.warning(dialog, "Erro", f"Falha ao trocar subcolunas: {e}")
                traceback.print_exc()
                return

            if isinstance(result, QImage):
                state["img_q"] = result
            elif isinstance(result, QPixmap):
                state["img_q"] = result.toImage().convertToFormat(QImage.Format_RGB32)
            else:
                QMessageBox.warning(dialog, "Erro", "Função trocar_subcolunas_na_imagem retornou formato inesperado.")
                return

            # atualiza self.pixmap exibida
            pixmap_sintetizado = QPixmap.fromImage(state["img_q"])
            self.img_label.setPixmap(pixmap_sintetizado)
            self.pixmap = pixmap_sintetizado  # atualiza referência interna

            col1 = _col_index_from_sub(actual_idx1)
            col2 = _col_index_from_sub(actual_idx2)
            colunas_afetadas = set(c for c in (col1, col2) if c is not None)

            for q in questions:
                if q.get("column_index") in colunas_afetadas:
                    q["mark"] = nova_classe

            _sync_annotations_from_questions()

            QMessageBox.information(dialog, "Troca aplicada", f"Troca aplicada entre subcolunas {actual_idx1} e {actual_idx2}.")

        def salvar_e_sair():
            # pede número para compor nome
            numero, ok = QInputDialog.getInt(self, "Número da Versão", "Digite o número para o arquivo sintético:", 1, 1)
            if not ok:
                return

            nome_original = os.path.splitext(os.path.basename(image_filename))[0]
            novo_nome_base = f"{nome_original}_sintetic{numero}"

            pasta = os.path.dirname(caminho)
            sintetic_image_path = os.path.join(pasta, novo_nome_base + ".jpg")
            sintetic_json_path = os.path.join(pasta, novo_nome_base + ".json")
            sintetic_txt_path = os.path.join(pasta, novo_nome_base + ".txt")

            try:
                state["img_q"].save(sintetic_image_path, "JPG")
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível salvar a imagem: {e}")
                traceback.print_exc()
                return

            # Atualiza JSON e salva
            data["image"] = os.path.basename(sintetic_image_path)
            data["questions"] = questions
            try:
                with open(sintetic_json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível salvar o JSON: {e}")
                traceback.print_exc()
                return

            img_width = state["img_q"].width()
            img_height = state["img_q"].height()
            mark_to_class = {"a":0,"b":1,"c":2,"d":3,"e":4,"f":5,"branco":6,"indeterminado":7}
            try:
                with open(sintetic_txt_path, 'w', encoding='utf-8') as f:
                    for q in questions:
                        classe = q.get("mark", "branco")
                        cls_id = mark_to_class.get(classe, 6)
                        box = q.get("question_box", {})
                        x = box.get("x", 0) / img_width
                        y = box.get("y", 0) / img_height
                        width = box.get("width", 0) / img_width
                        height = box.get("height", 0) / img_height
                        f.write(f"{cls_id} {x:.17f} {y:.17f} {width:.17f} {height:.17f}\n")
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível salvar o TXT: {e}")
                traceback.print_exc()
                return

            QMessageBox.information(self, "Sucesso",
                                    f"Arquivos salvos:\n{os.path.basename(sintetic_image_path)}\n"
                                    f"{os.path.basename(sintetic_json_path)}\n{os.path.basename(sintetic_txt_path)}")

            # Atualiza a exibição principal para mostrar a imagem sintetizada
            pixmap_final = QPixmap.fromImage(state["img_q"])
            self.img_label.setPixmap(pixmap_final)
            self.pixmap = pixmap_final
            
            self.contar_classes_em_pasta()
            
            dialog.accept()      


        def sintetizar_indeterminado():
            dialog_ind = QDialog(self)
            dialog_ind.setWindowTitle("Indeterminado")
            layout = QVBoxLayout(dialog_ind)
            
            # Agrupar questões por coluna
            colunas_marks = {}
            for q in questions:
                col_idx = q.get("column_index")
                mark = q.get("mark", "").strip().lower()
                colunas_marks.setdefault(col_idx, []).append(mark)

            # Analisar cada coluna
            for col_idx, marks in colunas_marks.items():
                if all(m == marks[0] for m in marks):
                    texto = f"Coluna {col_idx+1}: {marks[0]}"
                else:
                    texto = f"Coluna {col_idx+1}: marcações diferentes"
                layout.addWidget(QLabel(texto))

            btn_ok = QPushButton("Fechar")
            btn_ok.clicked.connect(dialog_ind.accept)
            layout.addWidget(btn_ok)

            dialog_ind.exec_()
             

        btn_add.clicked.connect(aplicar_troca)
        btn_save.clicked.connect(salvar_e_sair)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ind.clicked.connect(sintetizar_indeterminado)
        
        dialog.exec_()
        _sync_annotations_from_questions()
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
            self.contar_classes_em_pasta()

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
            
            for col_index, coluna in enumerate(self.column_coordinates):
                col_width = coluna.rect.width()

                if self.num_alternativas == 3:
                    frac_num = NUM_AREA_FRAC_3 if col_width < LIMIAR_LARGURA else NUM_AREA_FRAC_6
                else:
                    frac_num = NUM_AREA_FRAC_6

            
            self.subcolunas.clear()
            for col_index, coluna in enumerate(self.column_coordinates):
                sub_rets = self.extrair_subcolunas_de_coluna(coluna, 
                                                            num_subcolunas=self.num_alternativas,
                                                            frac_num_area=frac_num)
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
    
    def sintese_indeterminado(self):
        if not self.image_files:
            QMessageBox.warning(self, "Erro", "Nenhuma imagem carregada.")
            return
        if not self.column_coordinates:
            QMessageBox.warning(self, "Erro", "Nenhuma coluna detectada.")
            return

        # número de alternativas pelo combo
        num_alt = self.num_alternativas
        if num_alt not in (3, 6):
            QMessageBox.warning(self, "Erro", "Número de alternativas inválido (apenas 3 ou 6).")
            return

        # pede quantas sínteses o usuário deseja
        total_possibilidades = 2**num_alt - (num_alt + 1)  # todas menos as combinações com 0 ou 1 marcado
        qtd, ok = QInputDialog.getInt(
            self, "Quantidade de sínteses",
            f"Existem {total_possibilidades} possibilidades.\nQuantas deseja gerar?",
            min(1, total_possibilidades), 1, total_possibilidades, 1
        )
        if not ok or qtd <= 0:
            return

        # lê JSON e recupera a alternativa marcada por coluna
        image_filename = self.image_files[self.current_index]
        caminho = os.path.join(self.current_dir, image_filename)
        json_path = os.path.splitext(caminho)[0] + '.json'
        if not os.path.exists(json_path):
            QMessageBox.warning(self, "Erro", f"JSON base não encontrado: {json_path}")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                base_data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao abrir JSON: {e}")
            return

        col_source_map = {}
        for col_idx, _ in enumerate(self.column_coordinates):
            marcada = None
            for q in base_data.get("questions", []):
                if q.get("column_index") == col_idx:
                    mark = q.get("mark", "").lower()
                    if mark in ["a", "b", "c", "d", "e", "f"]:
                        marcada = ["a", "b", "c", "d", "e", "f"].index(mark)
                        break
            if marcada is None:
                marcada = 0
            col_source_map[col_idx] = marcada

        # chama a função principal
        self.gerar_sinteses_multimarcacao(num_alt, col_source_map, qtd)

    def gerar_sinteses_multimarcacao(self, num_alternativas: int, col_source_map: dict, qtd: int):
        if not getattr(self, "pixmap", None) or self.pixmap.isNull():
            QMessageBox.warning(self, "Erro", "Nenhuma imagem carregada.")
            return
        if not self.column_coordinates:
            QMessageBox.warning(self, "Erro", "Nenhuma coluna encontrada.")
            return

        image_filename = self.image_files[self.current_index]
        caminho = os.path.join(self.current_dir, image_filename)
        json_path = os.path.splitext(caminho)[0] + '.json'
        if not os.path.exists(json_path):
            QMessageBox.warning(self, "Erro", f"JSON base não encontrado: {json_path}")
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                base_data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao abrir JSON: {e}")
            return

        # calcula subcolunas por coluna
        sub_por_col = {}
        for col_idx, col_rect in enumerate(self.column_coordinates):
            col_width = col_rect.rect.width()
            if num_alternativas == 3:
                frac_num = NUM_AREA_FRAC_3 if col_width < LIMIAR_LARGURA else NUM_AREA_FRAC_6
            else:
                frac_num = NUM_AREA_FRAC_6
            alt_rects = self.extrair_subcolunas_de_coluna(
                col_rect,
                num_subcolunas=num_alternativas,
                frac_num_area=frac_num
            )
            sub_por_col[col_idx] = alt_rects

        # gera combinações válidas
        combos = [bits for bits in itertools.product([0, 1], repeat=num_alternativas) if sum(bits) >= 2]

        # seleciona aleatoriamente as desejadas
        if qtd < len(combos):
            #combos = random.sample(combos, qtd)
            
            if num_alternativas == 3:
                prioridade_idx = [1, 2]
            else:
                prioridade_idx = [1, 2, 5]

            prioritarios = [c for c in combos if any(c[i] == 1 for i in prioridade_idx)]
            outros = [c for c in combos if c not in prioritarios]

            escolhidos = []
            if len(prioritarios) >= qtd:
                escolhidos = random.sample(prioritarios, qtd)
            else:
                escolhidos = prioritarios + random.sample(outros, qtd - len(prioritarios))

            combos = escolhidos

        nome_original = os.path.splitext(image_filename)[0]
        seq = 0

        for bits in combos:
            img_q = self.pixmap.toImage().convertToFormat(QImage.Format_RGB32)
            painter = QPainter(img_q)

            for col_idx, alt_rects in sub_por_col.items():
                chosen_rel = col_source_map.get(col_idx, 0)
                if chosen_rel < 0 or chosen_rel >= num_alternativas:
                    chosen_rel = 0

                source_rect = alt_rects[chosen_rel]
                source_pix = self.pixmap.copy(source_rect)

                idx_nao_marcado = next((i for i in range(num_alternativas) if i != chosen_rel), 0)
                source_nao_marcado = self.pixmap.copy(alt_rects[idx_nao_marcado])

                for rel_pos, target_rect in enumerate(alt_rects):
                    if bits[rel_pos] == 1:
                        painter.drawPixmap(target_rect.topLeft(), source_pix)
                    else:
                        painter.drawPixmap(target_rect.topLeft(), source_nao_marcado)
            painter.end()

            # JSON copia e ajusta
            data_copy = deepcopy(base_data)
            for q in data_copy.get("questions", []):
                q["mark"] = "indeterminado"
                q["marks"] = []

            # adiciona subcolunas no JSON
            for col_idx, alt_rects in sub_por_col.items():
                if col_idx < len(data_copy["columns"]):
                    sub_list = []
                    for r in alt_rects:
                        sub_list.append({
                            "x": r.left(),
                            "y": r.top(),
                            "width": r.width(),
                            "height": r.height()
                        })
                    data_copy["columns"][col_idx]["subcolumns"] = sub_list

            # salvar
            out_base = os.path.join(self.current_dir, f"{nome_original}_ind{seq+1}")
            img_q.save(out_base + ".jpg", "JPG")

            data_copy["image"] = os.path.basename(out_base + ".jpg")
            with open(out_base + ".json", "w", encoding="utf-8") as fj:
                json.dump(data_copy, fj, indent=4, ensure_ascii=False)

            img_w, img_h = img_q.width(), img_q.height()
            with open(out_base + ".txt", "w", encoding="utf-8") as ft:
                for q in data_copy.get("questions", []):
                    cls_id = 7
                    box = q.get("question_box", {})
                    x = box.get("x", 0) / img_w
                    y = box.get("y", 0) / img_h
                    w = box.get("width", 0) / img_w
                    h = box.get("height", 0) / img_h
                    ft.write(f"{cls_id} {x:.17f} {y:.17f} {w:.17f} {h:.17f}\n")

            seq += 1

        QMessageBox.information(self, "Concluído", f"{seq} sínteses geradas e salvas em: {self.current_dir}")
