# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'hawkeye.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenuBar,
    QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QSpacerItem, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1000, 700)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.mainLayout = QVBoxLayout(self.centralwidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.titleLabel = QLabel(self.centralwidget)
        self.titleLabel.setObjectName(u"titleLabel")
        self.titleLabel.setAlignment(Qt.AlignCenter)

        self.mainLayout.addWidget(self.titleLabel)

        self.mainTabs = QTabWidget(self.centralwidget)
        self.mainTabs.setObjectName(u"mainTabs")
        self.inputTab = QWidget()
        self.inputTab.setObjectName(u"inputTab")
        self.inputTabLayout = QVBoxLayout(self.inputTab)
        self.inputTabLayout.setObjectName(u"inputTabLayout")
        self.inputGroupBox = QGroupBox(self.inputTab)
        self.inputGroupBox.setObjectName(u"inputGroupBox")
        self.inputGridLayout = QGridLayout(self.inputGroupBox)
        self.inputGridLayout.setObjectName(u"inputGridLayout")
        self.redditUrlLabel = QLabel(self.inputGroupBox)
        self.redditUrlLabel.setObjectName(u"redditUrlLabel")

        self.inputGridLayout.addWidget(self.redditUrlLabel, 0, 0, 1, 1)

        self.redditUrlInput = QLineEdit(self.inputGroupBox)
        self.redditUrlInput.setObjectName(u"redditUrlInput")

        self.inputGridLayout.addWidget(self.redditUrlInput, 0, 1, 1, 2)

        self.claimTextLabel = QLabel(self.inputGroupBox)
        self.claimTextLabel.setObjectName(u"claimTextLabel")

        self.inputGridLayout.addWidget(self.claimTextLabel, 1, 0, 1, 1)

        self.claimTextInput = QTextEdit(self.inputGroupBox)
        self.claimTextInput.setObjectName(u"claimTextInput")

        self.inputGridLayout.addWidget(self.claimTextInput, 1, 1, 1, 2)

        self.imagePathLabel = QLabel(self.inputGroupBox)
        self.imagePathLabel.setObjectName(u"imagePathLabel")

        self.inputGridLayout.addWidget(self.imagePathLabel, 2, 0, 1, 1)

        self.imagePathInput = QLineEdit(self.inputGroupBox)
        self.imagePathInput.setObjectName(u"imagePathInput")
        self.imagePathInput.setReadOnly(True)

        self.inputGridLayout.addWidget(self.imagePathInput, 2, 1, 1, 1)

        self.chooseImageButton = QPushButton(self.inputGroupBox)
        self.chooseImageButton.setObjectName(u"chooseImageButton")

        self.inputGridLayout.addWidget(self.chooseImageButton, 2, 2, 1, 1)

        self.modelLabel = QLabel(self.inputGroupBox)
        self.modelLabel.setObjectName(u"modelLabel")

        self.inputGridLayout.addWidget(self.modelLabel, 3, 0, 1, 1)

        self.modelComboBox = QComboBox(self.inputGroupBox)
        self.modelComboBox.addItem("")
        self.modelComboBox.addItem("")
        self.modelComboBox.addItem("")
        self.modelComboBox.setObjectName(u"modelComboBox")

        self.inputGridLayout.addWidget(self.modelComboBox, 3, 1, 1, 2)

        self.useFactCheckCheckBox = QCheckBox(self.inputGroupBox)
        self.useFactCheckCheckBox.setObjectName(u"useFactCheckCheckBox")
        self.useFactCheckCheckBox.setChecked(True)

        self.inputGridLayout.addWidget(self.useFactCheckCheckBox, 4, 1, 1, 1)

        self.useCacheCheckBox = QCheckBox(self.inputGroupBox)
        self.useCacheCheckBox.setObjectName(u"useCacheCheckBox")
        self.useCacheCheckBox.setChecked(True)

        self.inputGridLayout.addWidget(self.useCacheCheckBox, 4, 2, 1, 1)


        self.inputTabLayout.addWidget(self.inputGroupBox)

        self.imagePreviewLabel = QLabel(self.inputTab)
        self.imagePreviewLabel.setObjectName(u"imagePreviewLabel")
        self.imagePreviewLabel.setMinimumSize(QSize(0, 180))
        self.imagePreviewLabel.setFrameShape(QFrame.Box)
        self.imagePreviewLabel.setAlignment(Qt.AlignCenter)

        self.inputTabLayout.addWidget(self.imagePreviewLabel)

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setObjectName(u"buttonLayout")
        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonLayout.addItem(self.buttonSpacer)

        self.clearButton = QPushButton(self.inputTab)
        self.clearButton.setObjectName(u"clearButton")

        self.buttonLayout.addWidget(self.clearButton)

        self.runButton = QPushButton(self.inputTab)
        self.runButton.setObjectName(u"runButton")

        self.buttonLayout.addWidget(self.runButton)


        self.inputTabLayout.addLayout(self.buttonLayout)

        self.mainTabs.addTab(self.inputTab, "")
        self.verdictTab = QWidget()
        self.verdictTab.setObjectName(u"verdictTab")
        self.verdictTabLayout = QVBoxLayout(self.verdictTab)
        self.verdictTabLayout.setObjectName(u"verdictTabLayout")
        self.verdictGroupBox = QGroupBox(self.verdictTab)
        self.verdictGroupBox.setObjectName(u"verdictGroupBox")
        self.verdictGridLayout = QGridLayout(self.verdictGroupBox)
        self.verdictGridLayout.setObjectName(u"verdictGridLayout")
        self.verdictTitleLabel = QLabel(self.verdictGroupBox)
        self.verdictTitleLabel.setObjectName(u"verdictTitleLabel")

        self.verdictGridLayout.addWidget(self.verdictTitleLabel, 0, 0, 1, 1)

        self.verdictResultLabel = QLabel(self.verdictGroupBox)
        self.verdictResultLabel.setObjectName(u"verdictResultLabel")

        self.verdictGridLayout.addWidget(self.verdictResultLabel, 0, 1, 1, 1)

        self.confidenceLabel = QLabel(self.verdictGroupBox)
        self.confidenceLabel.setObjectName(u"confidenceLabel")

        self.verdictGridLayout.addWidget(self.confidenceLabel, 1, 0, 1, 1)

        self.confidenceProgressBar = QProgressBar(self.verdictGroupBox)
        self.confidenceProgressBar.setObjectName(u"confidenceProgressBar")
        self.confidenceProgressBar.setValue(0)

        self.verdictGridLayout.addWidget(self.confidenceProgressBar, 1, 1, 1, 1)


        self.verdictTabLayout.addWidget(self.verdictGroupBox)

        self.explanationGroupBox = QGroupBox(self.verdictTab)
        self.explanationGroupBox.setObjectName(u"explanationGroupBox")
        self.explanationLayout = QVBoxLayout(self.explanationGroupBox)
        self.explanationLayout.setObjectName(u"explanationLayout")
        self.explanationTextEdit = QTextEdit(self.explanationGroupBox)
        self.explanationTextEdit.setObjectName(u"explanationTextEdit")
        self.explanationTextEdit.setReadOnly(True)

        self.explanationLayout.addWidget(self.explanationTextEdit)


        self.verdictTabLayout.addWidget(self.explanationGroupBox)

        self.mainTabs.addTab(self.verdictTab, "")
        self.timelineTab = QWidget()
        self.timelineTab.setObjectName(u"timelineTab")
        self.timelineTabLayout = QVBoxLayout(self.timelineTab)
        self.timelineTabLayout.setObjectName(u"timelineTabLayout")
        self.timelineChartPlaceholderLabel = QLabel(self.timelineTab)
        self.timelineChartPlaceholderLabel.setObjectName(u"timelineChartPlaceholderLabel")
        self.timelineChartPlaceholderLabel.setMinimumSize(QSize(0, 180))
        self.timelineChartPlaceholderLabel.setFrameShape(QFrame.Box)
        self.timelineChartPlaceholderLabel.setAlignment(Qt.AlignCenter)

        self.timelineTabLayout.addWidget(self.timelineChartPlaceholderLabel)

        self.timelineTableWidget = QTableWidget(self.timelineTab)
        if (self.timelineTableWidget.columnCount() < 4):
            self.timelineTableWidget.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.timelineTableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.timelineTableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.timelineTableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.timelineTableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.timelineTableWidget.setObjectName(u"timelineTableWidget")

        self.timelineTabLayout.addWidget(self.timelineTableWidget)

        self.mainTabs.addTab(self.timelineTab, "")
        self.sourcesTab = QWidget()
        self.sourcesTab.setObjectName(u"sourcesTab")
        self.sourcesTabLayout = QVBoxLayout(self.sourcesTab)
        self.sourcesTabLayout.setObjectName(u"sourcesTabLayout")
        self.sourcesTableWidget = QTableWidget(self.sourcesTab)
        if (self.sourcesTableWidget.columnCount() < 6):
            self.sourcesTableWidget.setColumnCount(6)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.sourcesTableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.sourcesTableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.sourcesTableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.sourcesTableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.sourcesTableWidget.setHorizontalHeaderItem(4, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.sourcesTableWidget.setHorizontalHeaderItem(5, __qtablewidgetitem9)
        self.sourcesTableWidget.setObjectName(u"sourcesTableWidget")

        self.sourcesTabLayout.addWidget(self.sourcesTableWidget)

        self.mainTabs.addTab(self.sourcesTab, "")
        self.rawEvidenceTab = QWidget()
        self.rawEvidenceTab.setObjectName(u"rawEvidenceTab")
        self.rawEvidenceTabLayout = QVBoxLayout(self.rawEvidenceTab)
        self.rawEvidenceTabLayout.setObjectName(u"rawEvidenceTabLayout")
        self.rawEvidencePlainTextEdit = QPlainTextEdit(self.rawEvidenceTab)
        self.rawEvidencePlainTextEdit.setObjectName(u"rawEvidencePlainTextEdit")
        self.rawEvidencePlainTextEdit.setReadOnly(True)

        self.rawEvidenceTabLayout.addWidget(self.rawEvidencePlainTextEdit)

        self.mainTabs.addTab(self.rawEvidenceTab, "")
        self.logsTab = QWidget()
        self.logsTab.setObjectName(u"logsTab")
        self.logsTabLayout = QVBoxLayout(self.logsTab)
        self.logsTabLayout.setObjectName(u"logsTabLayout")
        self.logsPlainTextEdit = QPlainTextEdit(self.logsTab)
        self.logsPlainTextEdit.setObjectName(u"logsPlainTextEdit")
        self.logsPlainTextEdit.setReadOnly(True)

        self.logsTabLayout.addWidget(self.logsPlainTextEdit)

        self.mainTabs.addTab(self.logsTab, "")

        self.mainLayout.addWidget(self.mainTabs)

        self.bottomStatusLayout = QHBoxLayout()
        self.bottomStatusLayout.setObjectName(u"bottomStatusLayout")
        self.statusLabel = QLabel(self.centralwidget)
        self.statusLabel.setObjectName(u"statusLabel")

        self.bottomStatusLayout.addWidget(self.statusLabel)

        self.runProgressBar = QProgressBar(self.centralwidget)
        self.runProgressBar.setObjectName(u"runProgressBar")
        self.runProgressBar.setValue(0)

        self.bottomStatusLayout.addWidget(self.runProgressBar)

        self.exportJsonButton = QPushButton(self.centralwidget)
        self.exportJsonButton.setObjectName(u"exportJsonButton")

        self.bottomStatusLayout.addWidget(self.exportJsonButton)

        self.exportPdfButton = QPushButton(self.centralwidget)
        self.exportPdfButton.setObjectName(u"exportPdfButton")

        self.bottomStatusLayout.addWidget(self.exportPdfButton)


        self.mainLayout.addLayout(self.bottomStatusLayout)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1000, 22))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.mainTabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"HawkEye", None))
        self.titleLabel.setText(QCoreApplication.translate("MainWindow", u"HawkEye OSINT Image Analysis", None))
        self.inputGroupBox.setTitle(QCoreApplication.translate("MainWindow", u"Input", None))
        self.redditUrlLabel.setText(QCoreApplication.translate("MainWindow", u"Reddit URL:", None))
        self.redditUrlInput.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Paste newspaper/news article URL here", None))
        self.claimTextLabel.setText(QCoreApplication.translate("MainWindow", u"Claim / Caption:", None))
        self.claimTextInput.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Paste optional claim/caption to compare against the article", None))
        self.imagePathLabel.setText(QCoreApplication.translate("MainWindow", u"Image:", None))
        self.imagePathInput.setPlaceholderText(QCoreApplication.translate("MainWindow", u"No image selected", None))
        self.chooseImageButton.setText(QCoreApplication.translate("MainWindow", u"Choose Image", None))
        self.modelLabel.setText(QCoreApplication.translate("MainWindow", u"Model:", None))
        self.modelComboBox.setItemText(0, QCoreApplication.translate("MainWindow", u"Phi-3 3.8B", None))
        self.modelComboBox.setItemText(1, QCoreApplication.translate("MainWindow", u"Llama 3.1 8B", None))
        self.modelComboBox.setItemText(2, QCoreApplication.translate("MainWindow", u"Custom Ollama Model", None))

        self.useFactCheckCheckBox.setText(QCoreApplication.translate("MainWindow", u"Use Google Fact Check API", None))
        self.useCacheCheckBox.setText(QCoreApplication.translate("MainWindow", u"Use local cache", None))
        self.imagePreviewLabel.setText(QCoreApplication.translate("MainWindow", u"Image preview", None))
        self.clearButton.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.runButton.setText(QCoreApplication.translate("MainWindow", u"Run Analysis", None))
        self.mainTabs.setTabText(self.mainTabs.indexOf(self.inputTab), QCoreApplication.translate("MainWindow", u"Input", None))
        self.verdictGroupBox.setTitle(QCoreApplication.translate("MainWindow", u"Result", None))
        self.verdictTitleLabel.setText(QCoreApplication.translate("MainWindow", u"Verdict:", None))
        self.verdictResultLabel.setText(QCoreApplication.translate("MainWindow", u"No result yet", None))
        self.confidenceLabel.setText(QCoreApplication.translate("MainWindow", u"Confidence:", None))
        self.explanationGroupBox.setTitle(QCoreApplication.translate("MainWindow", u"Explanation", None))
        self.mainTabs.setTabText(self.mainTabs.indexOf(self.verdictTab), QCoreApplication.translate("MainWindow", u"Verdict", None))
        self.timelineChartPlaceholderLabel.setText(QCoreApplication.translate("MainWindow", u"Timeline chart placeholder", None))
        ___qtablewidgetitem = self.timelineTableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"Date", None))
        ___qtablewidgetitem1 = self.timelineTableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Source", None))
        ___qtablewidgetitem2 = self.timelineTableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"URL", None))
        ___qtablewidgetitem3 = self.timelineTableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Context Match", None))
        self.mainTabs.setTabText(self.mainTabs.indexOf(self.timelineTab), QCoreApplication.translate("MainWindow", u"Timeline", None))
        ___qtablewidgetitem4 = self.sourcesTableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"Domain", None))
        ___qtablewidgetitem5 = self.sourcesTableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MainWindow", u"Date", None))
        ___qtablewidgetitem6 = self.sourcesTableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("MainWindow", u"Similarity", None))
        ___qtablewidgetitem7 = self.sourcesTableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("MainWindow", u"Scrape Status", None))
        ___qtablewidgetitem8 = self.sourcesTableWidget.horizontalHeaderItem(4)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("MainWindow", u"Claim Match", None))
        ___qtablewidgetitem9 = self.sourcesTableWidget.horizontalHeaderItem(5)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("MainWindow", u"URL", None))
        self.mainTabs.setTabText(self.mainTabs.indexOf(self.sourcesTab), QCoreApplication.translate("MainWindow", u"Sources", None))
        self.mainTabs.setTabText(self.mainTabs.indexOf(self.rawEvidenceTab), QCoreApplication.translate("MainWindow", u"Raw Evidence", None))
        self.mainTabs.setTabText(self.mainTabs.indexOf(self.logsTab), QCoreApplication.translate("MainWindow", u"Logs", None))
        self.statusLabel.setText(QCoreApplication.translate("MainWindow", u"Ready", None))
        self.exportJsonButton.setText(QCoreApplication.translate("MainWindow", u"Export JSON", None))
        self.exportPdfButton.setText(QCoreApplication.translate("MainWindow", u"Export PDF", None))
    # retranslateUi

