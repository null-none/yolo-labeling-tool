import sys
import os
import cv2
import json
import numpy as np


from PIL import Image, ExifTags
from glob import glob
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QFileDialog, QLabel
from PyQt5.QtWidgets import QDesktopWidget, QMessageBox, QCheckBox, QProgressBar, QScrollArea
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor, QPen, QFont
from PyQt5.QtCore import QRect, QPoint
from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QColorDialog

class Config:
    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and PyInstaller bundle."""
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


class SettingsDialog(QDialog, Config):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Settings')
        self.colors = {}

        with open(self.resource_path('config.json'), 'r') as f:
            self.cfg = json.load(f)

        layout = QFormLayout(self)

        self.project_field = QLineEdit(self.cfg.get('project_name', ''))
        layout.addRow('project_name', self.project_field)

        self.key_fields = {}
        self.color_buttons = {}
        for i in range(1, 10):
            key = f'key_{i}'
            field = QLineEdit(self.cfg.get(key, ''))
            self.key_fields[key] = field

            color_hex = self.cfg.get(f'color_{i}', '#ff0000')
            self.colors[f'color_{i}'] = color_hex
            btn = QPushButton()
            btn.setFixedWidth(40)
            btn.setStyleSheet(f'background-color: {color_hex}')
            btn.clicked.connect(lambda _, k=f'color_{i}', b=btn: self.pickColor(k, b))
            self.color_buttons[f'color_{i}'] = btn

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0,0,0,0)
            row_layout.addWidget(field)
            row_layout.addWidget(btn)
            layout.addRow(key, row_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def pickColor(self, color_key, btn):
        color = QColorDialog.getColor()
        if color.isValid():
            self.colors[color_key] = color.name()
            btn.setStyleSheet(f'background-color: {color.name()}')

    def save(self):
        self.cfg['project_name'] = self.project_field.text()
        for key, field in self.key_fields.items():
            self.cfg[key] = field.text()
        for k, v in self.colors.items():
            self.cfg[k] = v
        with open(self.resource_path('config.json'), 'w') as f:
            json.dump(self.cfg, f, indent=4)
        self.accept()


class MyApp(QMainWindow, Config):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        mainWidget = MainWidget(self)

        self.setCentralWidget(mainWidget)
        statusbar = self.statusBar()
        self.setStatusBar(statusbar)
        self.fileName = QLabel('Ready')
        self.cursorPos = QLabel('      ')
        self.imageSize = QLabel('      ')
        self.autoLabel = QLabel('Manual Label')
        self.progress = QLabel('0/0')
        self.progressBar = QProgressBar()
        self.progressBar.setFixedWidth(150)
        self.progressBar.setValue(0)
        self.progressBar.setFormat('%v/%m')

        widget = QWidget(self)
        widget.setLayout(QHBoxLayout())
        widget.layout().addWidget(self.fileName)
        widget.layout().addStretch(1)
        widget.layout().addWidget(self.imageSize)
        widget.layout().addWidget(self.cursorPos)
        widget.layout().addStretch(1)
        widget.layout().addWidget(self.autoLabel)
        widget.layout().addStretch(2)
        widget.layout().addWidget(self.progress)
        widget.layout().addWidget(self.progressBar)
        statusbar.addWidget(widget, 1)

        self.setGeometry(50, 50, 1200, 800)
        self.setWindowTitle('im2trainData')
        self.showMaximized()
        
    def fitSize(self):
        pass

class ImageWidget(QWidget, Config):

    def __init__(self, parent, key_cfg, key_colors=None):
        super(ImageWidget, self).__init__(parent)
        self.parent = parent
        self.results = []
        self.setMouseTracking(True)
        self.key_config = key_cfg
        self.key_colors = key_colors or ['#ff0000'] * len(key_cfg)
        self.screen_height = QDesktopWidget().screenGeometry().height()
        self.last_idx = 0

        self.initUI()
        
    def initUI(self):
        self.pixmap = QPixmap(self.resource_path('start.png'))
        self.label_img = QLabel()
        self.label_img.setObjectName("image")
        self.pixmapOriginal = QPixmap.copy(self.pixmap)
        
        self.drawing = False
        self.lastPoint = QPoint()
        hbox = QHBoxLayout(self.label_img)
        self.setLayout(hbox)
        self.setFixedSize(1200,800)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.prev_pixmap = self.pixmap
            self.drawing = True
            self.lastPoint = event.pos()
        elif event.button() == Qt.RightButton:
            x, y = event.pos().x(), event.pos().y()
            for i, box in enumerate(self.results):
                lx, ly, rx, ry = box[:4]
                if lx <= x <= rx and ly <= y <= ry:
                    self.results.pop(i)
                    self.pixmap = self.drawResultBox()
                    self.update()
                    break
            
    def mouseMoveEvent(self, event):
        self.parent.cursorPos.setText('({}, {})'
                                    .format(event.pos().x(), event.pos().y()))
        if event.buttons() & Qt.LeftButton and self.drawing:
            self.pixmap = QPixmap.copy(self.prev_pixmap)
            painter = QPainter(self.pixmap)
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            p1_x, p1_y = self.lastPoint.x(), self.lastPoint.y()
            p2_x, p2_y = event.pos().x(), event.pos().y()
            painter.drawRect(min(p1_x, p2_x), min(p1_y, p2_y), 
                              abs(p1_x-p2_x), abs(p1_y-p2_y))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            p1_x, p1_y = self.lastPoint.x(), self.lastPoint.y() 
            p2_x, p2_y = event.pos().x(), event.pos().y()
            lx, ly = min(p1_x, p2_x), min(p1_y, p2_y)
            w, h = abs(p1_x-p2_x), abs(p1_y-p2_y)
            if (p1_x, p1_y) != (p2_x, p2_y):
                if self.results and (len(self.results[-1]) == 4) and self.parent.autoLabel.text() == 'Manual Label':
                    self.showPopupOk('warning messege', 
                                      'Please mark the box you drew.')
                    self.pixmap = self.drawResultBox()
                    self.update()
                elif self.parent.autoLabel.text() == 'Auto Label':
                    self.results.append([lx, ly, lx+w, ly+h, self.last_idx])
                    for i, result in enumerate(self.results):  
                        if len(result) == 4:  # fill empty labels
                            self.results[i].append(self.last_idx)
                    self.pixmap = self.drawResultBox()
                    self.update()
                else:
                    self.results.append([lx, ly, lx+w, ly+h])
                self.drawing = False

    def showPopupOk(self, title: str, content: str):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(content)
        msg.setStandardButtons(QMessageBox.Ok)
        result = msg.exec_()
        if result == QMessageBox.Ok:
            msg.close()

    def drawResultBox(self):
        res = QPixmap.copy(self.pixmapOriginal)
        painter = QPainter(res)
        font = QFont('mono', 15, 1)
        painter.setFont(font)
        for box in self.results:
            lx, ly, rx, ry = box[:4]
            if len(box) == 5:
                idx = box[-1]
                color = QColor(self.key_colors[idx])
            else:
                color = QColor(Qt.red)
            painter.setPen(QPen(color, 2, Qt.SolidLine))
            painter.drawRect(lx, ly, rx-lx, ry-ly)
            if len(box) == 5:
                painter.drawText(lx, ly+15, self.key_config[idx])
        return res

    def setPixmap(self, image_fn):
        self.pixmap = QPixmap(image_fn)
        self.W, self.H = self.pixmap.width(), self.pixmap.height()

        self.parent.imageSize.setText('{}x{}'.format(self.W, self.H))
        self.setFixedSize(self.W, self.H)
        self.pixmapOriginal = QPixmap.copy(self.pixmap)

    def cancelLast(self):
        if self.results:
            self.results.pop()  # pop last
            self.pixmap = self.drawResultBox()
            self.update()
    
    def getRatio(self):
        return self.W, self.H

    def getResult(self):
        return self.results

    def resetResult(self):
        self.results = []

    def markBox(self, idx):
        self.last_idx = idx
        if self.results:
            if len(self.results[-1]) == 4:
                self.results[-1].append(idx)
            elif len(self.results[-1]) == 5:
                self.results[-1][-1] = idx
            else:
                raise ValueError('invalid results')
            self.pixmap = self.drawResultBox()
            self.update()

class MainWidget(QWidget, Config):
    def __init__(self, parent):
        super(MainWidget, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.parent = parent
        self.currentImg = "start.png"
        config_dict = self.getConfigFromJson(self.resource_path('config.json'))
        self.key_config = [config_dict[k] for i in range(1, 10)
                           if (k := 'key_'+str(i)) in config_dict and config_dict[k]]
        self.key_colors = [config_dict.get('color_'+str(i), '#ff0000') for i in range(1, 10)
                           if config_dict.get('key_'+str(i))]
        self.crop_mode = False
        self.save_directory = None
        self.history = []

        self.initUI()

    def initUI(self):
        # UI elements
        inputPathButton = QPushButton('Input Path', self)
        savePathButton = QPushButton('Save Path', self)
        savePathButton.setEnabled(False)
        self.okButton = QPushButton('Next', self)
        self.backButton = QPushButton('Back', self)
        self.backButton.setEnabled(False)
        cancelButton = QPushButton('Cancel', self)
        cropModeCheckBox = QCheckBox("Crop Mode", self)
        inputPathLabel = QLabel('Input Path not selected', self)
        self.savePathLabel = QLabel('Save Path not selected', self)
        self.savePathLabel.setEnabled(False)

        self.label_img = ImageWidget(self.parent, self.key_config, self.key_colors)

        # Events
        self.okButton.clicked.connect(self.setNextImage)
        self.okButton.setEnabled(False)
        self.backButton.clicked.connect(self.setPrevImage)
        cancelButton.clicked.connect(self.label_img.cancelLast)
        cropModeCheckBox.stateChanged.connect(lambda state:
                                        self.cropMode(state, savePathButton))
        inputPathButton.clicked.connect(lambda:self.registerInputPath(
                                    inputPathButton, inputPathLabel, self.okButton))
        savePathButton.clicked.connect(lambda:self.registerSavePath(
                                          savePathButton, self.savePathLabel))
        
        hbox = QHBoxLayout()

        vbox = QVBoxLayout()
        vbox.addWidget(inputPathButton)
        vbox.addWidget(savePathButton)
    
        hbox.addLayout(vbox)

        
        vbox = QVBoxLayout()
        vbox.addWidget(inputPathLabel)
        vbox.addWidget(self.savePathLabel)

        hbox.addLayout(vbox)
        settingsButton = QPushButton('Settings', self)
        settingsButton.clicked.connect(lambda: SettingsDialog(self).exec_())
        hbox.addStretch(3)
        hbox.addWidget(settingsButton)
        hbox.addWidget(cropModeCheckBox)
        hbox.addStretch(1)
        hbox.addWidget(self.backButton)
        hbox.addWidget(self.okButton)
        hbox.addWidget(cancelButton)

        scroll = QScrollArea()
        scroll.setWidget(self.label_img)
        scroll.setWidgetResizable(False)
        scroll.setMaximumHeight(int(QDesktopWidget().screenGeometry().height() * 0.8))

        vbox = QVBoxLayout()
        vbox.addWidget(scroll)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

    def setNextImage(self, img=None):
        if self.savePathLabel.text() == 'Results' and self.crop_mode:
            os.makedirs(self.save_directory, exist_ok=True)

        if not img:
            res = self.label_img.getResult()
            if res and len(res[-1]) != 5:
                self.label_img.showPopupOk('warning messege', 
                                            'please mark the box you drew.')
                return 'Not Marked'
            self.writeResults(res)
            self.label_img.resetResult()
            if self.currentImg not in ['start.png', 'end.png']:
                self.history.append(self.currentImg)
                self.backButton.setEnabled(True)
            try:
                self.currentImg = self.imgList.pop(0)
            except Exception:
                self.currentImg = 'end.png'
        else:
            self.label_img.resetResult()

        try:
            im = Image.open(self.currentImg)
            for orientation in ExifTags.TAGS.keys(): 
                if ExifTags.TAGS[orientation]=='Orientation':
                    break 
            exif=dict(im.getexif().items())
            if exif[orientation] in [3,6,8]: 
                im = im.transpose(Image.ROTATE_180)
                im.save(self.currentImg)
        except:
            pass

        basename = os.path.basename(self.currentImg)
        self.parent.fileName.setText(basename)
        done = self.total_imgs - len(self.imgList)
        self.parent.progress.setText(str(done) + '/' + str(self.total_imgs))
        self.parent.progressBar.setMaximum(self.total_imgs)
        self.parent.progressBar.setValue(done)

        self.label_img.setPixmap(self.currentImg)
        self.label_img.update()
        self.parent.fitSize()

    def writeResults(self, res:list):
        if self.parent.fileName.text() != 'Ready':
            W, H = self.label_img.getRatio()
            if not res:
                open(self.currentImg[:-4]+'.txt', 'a', encoding='utf8').close()
            for i, elements in enumerate(res):  # box : (lx, ly, rx, ry, idx)
                lx, ly, rx, ry, idx = elements
                # yolo : (idx center_x_ratio, center_y_ratio, width_ratio, height_ratio)
                yolo_format = [idx, (lx+rx)/2/W, (ly+ry)/2/H, (rx-lx)/W, (ry-ly)/H]
                with open(self.currentImg[:-4]+'.txt', 'a', encoding='utf8') as resultFile:
                    resultFile.write(' '.join([str(x) for x in yolo_format])+'\n')
                if self.crop_mode:
                    img = cv2.imread(self.currentImg)
                    if img is None:
                        n = np.fromfile(self.currentImg, np.uint8) 
                        img = cv2.imdecode(n, cv2.IMREAD_COLOR)
                    oh, ow = img.shape[:2]
                    w, h = round(yolo_format[3]*ow), round(yolo_format[4]*oh)
                    x, y = round(yolo_format[1]*ow - w/2), round(yolo_format[2]*oh - h/2)
                    crop_img = img[y:y+h, x:x+w]
                    basename = os.path.basename(self.currentImg)
                    filename = basename[:-4]+'-{}-{}.jpg'.format(self.key_config[idx], i)

                    # Korean dir support
                    crop_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                    crop_img = Image.fromarray(crop_img)
                    crop_img.save(os.path.join(self.save_directory, filename), dpi=(300,300))

    def setPrevImage(self):
        if not self.history:
            return
        if self.currentImg not in ['start.png', 'end.png']:
            self.imgList.insert(0, self.currentImg)
        self.currentImg = self.history.pop()
        if not self.history:
            self.backButton.setEnabled(False)

        self.label_img.resetResult()
        self.label_img.setPixmap(self.currentImg)

        txt_path = self.currentImg[:-4] + '.txt'
        if os.path.exists(txt_path):
            W, H = self.label_img.getRatio()
            boxes = []
            with open(txt_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        idx = int(parts[0])
                        cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        lx = round((cx - bw / 2) * W)
                        ly = round((cy - bh / 2) * H)
                        rx = round((cx + bw / 2) * W)
                        ry = round((cy + bh / 2) * H)
                        boxes.append([lx, ly, rx, ry, idx])
            self.label_img.results = boxes
            os.remove(txt_path)

        self.label_img.pixmap = self.label_img.drawResultBox()
        self.label_img.update()
        self.parent.fileName.setText(os.path.basename(self.currentImg))
        done = self.total_imgs - len(self.imgList)
        self.parent.progress.setText(str(done) + '/' + str(self.total_imgs))
        self.parent.progressBar.setMaximum(self.total_imgs)
        self.parent.progressBar.setValue(done)
        self.parent.fitSize()

    def registerSavePath(self, savePathButton, label):
        savePathButton.toggle()
        self.save_directory = str(QFileDialog.getExistingDirectory(self, "Select Save Directory"))
        basename = os.path.basename(self.save_directory)
        if basename:
            label.setText(basename+'/')
        else:
            print("Output Path not selected")
            self.save_directory = None

    def registerInputPath(self, inputPathButton, inputPathLabel, okButton):
        inputPathButton.toggle()
        directory = str(QFileDialog.getExistingDirectory(self, "Select Input Directory"))
        basename = os.path.basename(directory)
        if not basename:
            print("Input Path not selected")
            return -1 
        
        types = ('*.jpg', '*.JPG', '*.jpeg', '*.JPEG', '*.png', '*.PNG')
        self.imgList = []
        for t in types:
            self.imgList.extend(glob(directory+'/'+t))
        self.total_imgs = len(self.imgList)

        to_skip = []
        for imgPath in self.imgList:
            if os.path.exists(imgPath[:-4] + '.txt'):
                to_skip.append(imgPath)
        for skip in to_skip:
            self.imgList.remove(skip)

        inputPathLabel.setText(basename+'/')
        okButton.setEnabled(True)

        if self.save_directory is None or self.savePathLabel.text() == 'Results':
            self.savePathLabel.setText('Results')
            self.save_directory = os.path.join(directory, 'Results')

    def getConfigFromJson(self, json_file):
        # parse the configurations from the config json file provided
        with open(json_file, 'r') as config_file:
            try:
                config_dict = json.load(config_file)
                # EasyDict allows to access dict values as attributes (works recursively).
                return config_dict
            except ValueError:
                print("INVALID JSON file format.. Please provide a good json file")
                exit(-1)

    def cropMode(self, state, savePathButton):
        if state == Qt.Checked:
            self.crop_mode = True
            savePathButton.setEnabled(True)
        else:
            self.crop_mode = False
            savePathButton.setEnabled(False)
    
    def keyPressEvent(self, e):
        config_len = len(self.key_config)
        for i, key_n in enumerate(range(49,58), 1):
            if e.key() == key_n and config_len >= i:
                self.label_img.markBox(i-1) 
                break
        if e.key() == Qt.Key_Escape:
            self.label_img.cancelLast()
        elif e.key() == Qt.Key_W:
            self.setPrevImage()
        elif e.key() == Qt.Key_E:
            self.setNextImage()
        elif e.key() == Qt.Key_Q:
            self.label_img.resetResult()
            self.label_img.pixmap = self.label_img.drawResultBox()
            self.label_img.update()
        elif e.key() == Qt.Key_A:
            if self.parent.autoLabel.text() == 'Auto Label':
                self.parent.autoLabel.setText('Manual Label')
            else:
                self.parent.autoLabel.setText('Auto Label')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())