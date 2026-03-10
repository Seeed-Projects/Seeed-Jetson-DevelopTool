"""Seeed/NVIDIA-like style with bilingual-friendly defaults."""

ACCENT_GREEN = "#8DC21F"
ACCENT_GREEN_DARK = "#74B281"
ACCENT_NVIDIA = "#76B900"
ACCENT_DARK = "#1C2331"
ACCENT_INFO = "#2C7BE5"
ACCENT_ERROR = "#C53030"

SEEED_GREEN = ACCENT_GREEN
SEEED_DARK_GREEN = ACCENT_GREEN_DARK
SEEED_BLUE = "#003A4A"
SEEED_LIGHT_GRAY = "#F5F7FA"
SEEED_DARK_GRAY = "#333333"
SEEED_WHITE = "#FFFFFF"

MAIN_STYLE = """
QMainWindow, QWidget#RootContainer {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #DDE8E2,
                                      stop:0.55 #D4E1D9,
                                      stop:1 #CCD9D1);
    color: #16212D;
    font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
}

QFrame#WindowFrame {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F4F9F3,
                                      stop:0.42 #E9F1EA,
                                      stop:1 #DBE6DE);
    border-radius: 15px;
    border-top: 2px solid #FFFFFF;
    border-left: 2px solid #EDF5ED;
    border-right: 2px solid #9AB1A3;
    border-bottom: 3px solid #718A7C;
}

QFrame#WindowChrome {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #35516A,
                                      stop:0.5 #2A4258,
                                      stop:1 #1A2E40);
    border-top-left-radius: 13px;
    border-top-right-radius: 13px;
    border-top: 1px solid #6E8AA2;
    border-left: 1px solid #58748B;
    border-right: 1px solid #32485A;
    border-bottom: 3px solid #12202C;
}

QLabel#WindowChromeTitle {
    color: #F1F7FC;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#WindowChromeBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #415A73,
                                      stop:1 #31465D);
    color: #EAF1F9;
    border-top: 1px solid #5A7693;
    border-left: 1px solid #55708B;
    border-right: 1px solid #2A3D52;
    border-bottom: 2px solid #243648;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#WindowChromeBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #4E6C88,
                                      stop:1 #3A526A);
}

QPushButton#WindowChromeCloseBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #8D4251,
                                      stop:1 #6E2F3B);
    color: #FFF1F4;
    border-top: 1px solid #A35A67;
    border-left: 1px solid #9A4F5D;
    border-right: 1px solid #65303B;
    border-bottom: 2px solid #55242D;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#WindowChromeCloseBtn:hover {
    background-color: #8A3945;
}

QFrame#Sidebar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #1C2733,
                                      stop:1 #121922);
    border-radius: 14px;
    border: 1px solid #273446;
    border-top: 1px solid #32485D;
    border-left: 1px solid #2F4357;
    border-right: 1px solid #1A2735;
    border-bottom: 2px solid #0D151E;
    border-left: 3px solid #8DC21F;
}

QLabel#BrandTitle {
    color: #F6FAFF;
    font-size: 20px;
    font-weight: 700;
}

QLabel#BrandSubtitle {
    color: #B5C8D0;
    font-size: 12px;
}

QLabel#BrandLogo {
    background: transparent;
    border: none;
    padding: 2px 0 6px 0;
}

QPushButton[nav="true"] {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    color: #DCE5F5;
    font-weight: 600;
    text-align: left;
    min-height: 18px;
    padding: 10px 12px;
}

QPushButton[nav="true"]:hover {
    background-color: #2A3347;
}

QPushButton[nav="true"][active="true"] {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #394B66,
                                      stop:1 #2E3E56);
    border: 1px solid #425572;
    color: white;
}

QFrame#TopBar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #2A3F53,
                                      stop:0.52 #213548,
                                      stop:1 #172838);
    border: 1px solid #334B60;
    border-radius: 12px;
    border-top: 3px solid #76B900;
    border-left: 1px solid #43607A;
    border-right: 1px solid #1B2F41;
    border-bottom: 3px solid #0F1D2A;
}

QLabel#TopTitle {
    color: #F3F8FF;
    font-size: 19px;
    font-weight: 700;
}

QLabel#TopSubtitle {
    color: #C6D4DF;
    font-size: 12px;
}

QLabel#TopBarHint {
    color: #D2DFEA;
    font-size: 12px;
}

QFrame#MainWorkspace {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #E8F1EC,
                                      stop:0.52 #DFEAE4,
                                      stop:1 #D5E1DA);
    border-radius: 14px;
    border-top: 1px solid #F7FCF9;
    border-left: 1px solid #ECF5EF;
    border-right: 1px solid #ADC0B4;
    border-bottom: 3px solid #91A79A;
}

QStackedWidget#MainStack {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F1F7F3,
                                      stop:0.5 #ECF4EE,
                                      stop:1 #E3ECE5);
    border-radius: 12px;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #F2F8F4;
    border-right: 1px solid #C4D2C9;
    border-bottom: 3px solid #A6B9AD;
}

QWidget#ContentPage {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F7FBF8,
                                      stop:1 #EFF5F1);
    border-radius: 10px;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #F2F8F4;
    border-right: 1px solid #D3E0D8;
    border-bottom: 2px solid #C3D2C8;
}

QLabel#StatusChip {
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#StatusChip[status="info"] {
    color: #0B2A50;
    background-color: #D8E8FF;
}

QLabel#StatusChip[status="busy"] {
    color: #203042;
    background-color: #DCE6F0;
}

QLabel#StatusChip[status="success"] {
    color: #234E07;
    background-color: #DFF2C0;
}

QLabel#StatusChip[status="error"] {
    color: #A02020;
    background-color: #FCE6E6;
}

QFrame#Card {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F8FCFA,
                                      stop:0.6 #F2F8F4,
                                      stop:1 #EBF2EE);
    border: 1px solid #C4D2CA;
    border-radius: 12px;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #EFF7F2;
    border-right: 1px solid #BCCEC2;
    border-bottom: 3px solid #AFC1B5;
}

QFrame#Card:hover {
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #F2F9F4;
    border-right: 1px solid #B4C8BA;
    border-bottom: 3px solid #A3B8AA;
}

QFrame#Card[priority="high"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F6FBF7,
                                      stop:1 #EAF2ED);
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #EDF6F0;
    border-right: 1px solid #B3C6B9;
    border-bottom: 3px solid #9EB5A7;
}

QLabel#CardTitle {
    color: #121C2D;
    font-size: 16px;
    font-weight: 700;
}

QLabel#CardSubtitle,
QLabel#LabelHint {
    color: #4F6473;
    font-size: 12px;
}

QLabel#InfoPanel {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F3F9F5,
                                      stop:1 #EAF2ED);
    border: 1px solid #CEDDD3;
    border-radius: 8px;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #F0F7F2;
    border-right: 1px solid #C4D4C9;
    border-bottom: 2px solid #B8CABD;
    color: #223645;
    padding: 10px;
}

QLabel#InfoPanel a {
    color: #2C7BE5;
    text-decoration: underline;
}

QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #A1D63A,
                                      stop:1 #8DC21F);
    color: #122105;
    border: 1px solid #7AAF20;
    border-top: 1px solid #B9E86A;
    border-left: 1px solid #AEDD50;
    border-right: 1px solid #699717;
    border-bottom: 2px solid #587E13;
    border-radius: 9px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #8CC92F,
                                      stop:1 #76B900);
    border-bottom: 2px solid #4D760F;
}

QPushButton#PrimaryButton:disabled {
    background-color: #BCD893;
    color: #4A5F2D;
}

QPushButton#SecondaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F5FAF7,
                                      stop:1 #EAF3EE);
    color: #244761;
    border: 1px solid #BFD3C7;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #EEF5F1;
    border-right: 1px solid #B2C7BA;
    border-bottom: 2px solid #A6BCAE;
    border-radius: 9px;
    padding: 9px 13px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#SecondaryButton:hover {
    background-color: #E4F0EA;
}

QComboBox {
    background-color: #F8FCFA;
    border: 1px solid #B8CABC;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #EEF5F1;
    border-right: 1px solid #ADC1B2;
    border-bottom: 2px solid #A0B5A6;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
    selection-background-color: #DCEBC2;
}

QComboBox:hover {
    border: 1px solid #96B39F;
}

QComboBox:focus {
    border: 1px solid #8DC21F;
}

QCheckBox {
    color: #1C2A3D;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #9EB0C8;
    border-radius: 3px;
    background: white;
}

QCheckBox::indicator:checked {
    background: #8DC21F;
    border-color: #8DC21F;
}

QProgressBar {
    border: 1px solid #B8C8BD;
    border-radius: 7px;
    text-align: center;
    background-color: #EAF2EC;
    color: #2C4A3B;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #8DC21F;
    border-radius: 6px;
}

QTextEdit {
    background-color: #F2F8F4;
    border: 1px solid #CFE0D5;
    border-radius: 9px;
    color: #1E2E3A;
    padding: 6px;
}

QTextEdit#LogPanel {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #EDF5F0,
                                      stop:1 #E4EEE8);
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #EEF6F1;
    border-right: 1px solid #B7C9BC;
    border-bottom: 2px solid #A9BDAF;
}

QScrollArea {
    border: none;
}

QScrollArea#SectionScroll {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F7FBF8,
                                      stop:1 #EEF4F0);
    border-radius: 9px;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #F0F7F2;
    border-right: 1px solid #C0D0C5;
    border-bottom: 2px solid #ADBEB2;
    padding: 2px;
}

QWidget#SectionContent, QWidget#RecoveryContent {
    background: transparent;
}

QScrollBar:vertical {
    background: #E5ECE8;
    width: 11px;
    margin: 2px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #93AFA0;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #7FA08E;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #E5ECE8;
    height: 11px;
    margin: 2px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #93AFA0;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #7FA08E;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""
