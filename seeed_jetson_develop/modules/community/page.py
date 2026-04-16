"""Community page UI with quick links and product purchase entry."""
import webbrowser
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.widgets.page_base import PageBase
from seeed_jetson_develop.gui.theme import (
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, apply_shadow as _shadow, DropdownButton,
)

_LINKS = [
    ("📖", "community.link.wiki.name", "community.link.wiki.desc", "https://wiki.seeedstudio.com/"),
    ("💬", "community.link.forum.name", "community.link.forum.desc", "https://forum.seeedstudio.com/"),
    ("🐙", "community.link.github.name", "community.link.github.desc", "https://github.com/Seeed-Studio"),
    ("🎥", "community.link.video.name", "community.link.video.desc", "https://www.youtube.com/@SeeedStudio"),
    ("📦", "community.link.ngc.name", "community.link.ngc.desc", "https://catalog.ngc.nvidia.com/"),
    ("🤗", "community.link.hf.name", "community.link.hf.desc", "https://huggingface.co/"),
]

_PURCHASE_MAP = {
    "j4012s":                    "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
    "j4011s":                    "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
    "j3011s":                    "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
    "j3010s":                    "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
    "j4012mini":                 "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
    "j4011mini":                 "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
    "j3011mini":                 "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
    "j3010mini":                 "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
    "j4012robotics":             "https://www.seeedstudio.com/reComputer-Robotics-J4012-p-6505.html",
    "j4011robotics":             "https://www.seeedstudio.com/reComputer-Robotics-J4012-p-6505.html",
    "j3011robotics":             "https://www.seeedstudio.com/reComputer-Robotics-J3011-p-6503.html",
    "j3010robotics":             "https://www.seeedstudio.com/reComputer-Robotics-J4012-p-6505.html",
    "j4012classic":              "https://www.seeedstudio.com/reComputer-J4012-w-o-power-adapter-p-5628.html",
    "j4011classic":              "https://www.seeedstudio.com/reComputer-J4011-w-o-power-adapter-p-5629.html",
    "j3011classic":              "https://www.seeedstudio.com/reComputer-J3011-p-5590.html",
    "j3010classic":              "https://www.seeedstudio.com/reComputer-J3010-w-o-power-adapter-p-5631.html",
    "j4012industrial":           "https://www.seeedstudio.com/reComputer-Industrial-J4012-p-5684.html",
    "j4011industrial":           "https://www.seeedstudio.com/reComputer-Industrial-J4011-p-5681.html",
    "j3011industrial":           "https://www.seeedstudio.com/reComputer-Industrial-J3011-p-5682.html",
    "j3010industrial":           "https://www.seeedstudio.com/reComputer-Industrial-J3010-p-5686.html",
    "j2012industrial":           "https://www.seeedstudio.com/reComputer-Industrial-J2012-p-5685.html",
    "j2011industrial":           "https://www.seeedstudio.com/reComputer-Industrial-J2011-p-5683.html",
    "j4012reserver":             "https://www.seeedstudio.com/reServer-industrial-J4012-p-5747.html",
    "j4011reserver":             "https://www.seeedstudio.com/reServer-industrial-J4011-p-5748.html",
    "j3011reserver":             "https://www.seeedstudio.com/reServer-industrial-J3011-p-5750.html",
    "j3010reserver":             "https://www.seeedstudio.com/reServer-industrial-J3010-p-5749.html",
    "j501-carrier AGX-Orin 64g": "https://www.seeedstudio.com/reServer-Industrial-J501-Carrier-Board-Add-on.html",
    "j501-carrier AGX-Orin 32g": "https://www.seeedstudio.com/reServer-Industrial-J501-Carrier-Board-Add-on.html",
    "j501mini-agx-orin-64g":     "https://www.seeedstudio.com/reComputer-Mini-J501-Carrier-Board-for-Jetson-AGX-Orin-p-6606.html",
    "j501mini-agx-orin-32g":     "https://www.seeedstudio.com/reComputer-Mini-J501-Carrier-Board-for-Jetson-AGX-Orin-p-6606.html",
    "j501-agx-orin-64g":         "https://www.seeedstudio.com/reComputer-Robotics-J5012-with-GMSL-extension-board-p-6682.html",
    "j501-agx-orin-32g":         "https://www.seeedstudio.com/reComputer-Robotics-J5012-with-GMSL-extension-board-p-6682.html",
}


def _get_purchase_url(product: str, product_images: dict) -> str:
    info = product_images.get(product, {})
    url = (info.get("purchase_url") or "").strip()
    return url or _PURCHASE_MAP.get(product, (info.get("getting_started") or "").strip())


def build_page(products: dict, product_images: dict) -> QWidget:
    _ct = lambda key, **kwargs: t(key, lang=get_language(), **kwargs)
    page = PageBase(_ct("community.page.title"), _ct("community.page.subtitle"))
    lay = page.get_content_layout()

    # Quick links card.
    links_card = _card(12)
    _shadow(links_card)
    lc_lay = QVBoxLayout(links_card)
    lc_lay.setContentsMargins(_pt(24), _pt(20), _pt(24), _pt(20))
    lc_lay.setSpacing(_pt(16))
    quick_links_title = _lbl(_ct("community.quick_links.title"), 15, C_TEXT, bold=True)
    lc_lay.addWidget(quick_links_title)
    page.i18n.bind_text(quick_links_title, "community.quick_links.title")

    grid = QGridLayout()
    grid.setSpacing(_pt(16))
    for i, (icon, name_key, desc_key, url) in enumerate(_LINKS):
        c = _card(10)
        cl = QVBoxLayout(c)
        cl.setContentsMargins(_pt(16), _pt(14), _pt(16), _pt(14))
        cl.setSpacing(_pt(6))
        top = QHBoxLayout()
        top.addWidget(_lbl(icon, 20))
        top.addStretch()
        cl.addLayout(top)
        name_lbl = _lbl(_ct(name_key), 13, C_TEXT, bold=True)
        desc_lbl = _lbl(_ct(desc_key), 11, C_TEXT2)
        cl.addWidget(name_lbl)
        cl.addWidget(desc_lbl)
        btn = _btn(_ct("community.quick_links.open"), small=True)
        btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
        cl.addWidget(btn)
        page.i18n.bind_text(name_lbl, name_key)
        page.i18n.bind_text(desc_lbl, desc_key)
        page.i18n.bind_text(btn, "community.quick_links.open")
        grid.addWidget(c, i // 3, i % 3)

    lc_lay.addLayout(grid)
    lay.addWidget(links_card)

    # Product purchase card.
    buy_card = _card(12)
    _shadow(buy_card)
    bc_lay = QVBoxLayout(buy_card)
    bc_lay.setContentsMargins(_pt(24), _pt(20), _pt(24), _pt(20))
    bc_lay.setSpacing(_pt(16))
    buy_title = _lbl(_ct("community.buy.title"), 15, C_TEXT, bold=True)
    buy_desc = _lbl(_ct("community.buy.desc"), 12, C_TEXT3)
    bc_lay.addWidget(buy_title)
    bc_lay.addWidget(buy_desc)
    page.i18n.bind_text(buy_title, "community.buy.title")
    page.i18n.bind_text(buy_desc, "community.buy.desc")

    combo = DropdownButton(max_popup_height=_pt(320))
    combo.addItems(sorted(products.keys()))
    bc_lay.addWidget(combo)

    buy_btn = _btn(_ct("community.buy.button"), primary=True, small=True)
    bc_lay.addWidget(buy_btn)
    page.i18n.bind_text(buy_btn, "community.buy.button")
    lay.addWidget(buy_card)

    def _update_btn(product: str):
        url = _get_purchase_url(product, product_images)
        buy_btn.setEnabled(bool(url))
        buy_btn.setToolTip(url if url else _ct("community.buy.no_link"))

    def _open_purchase():
        url = _get_purchase_url(combo.currentText(), product_images)
        if url:
            webbrowser.open(url)

    combo.currentTextChanged.connect(_update_btn)
    buy_btn.clicked.connect(_open_purchase)
    if combo.count():
        _update_btn(combo.currentText())

    def _retranslate_header_and_tooltip():
        page.set_header_text(_ct("community.page.title"), _ct("community.page.subtitle"))
        if combo.count():
            _update_btn(combo.currentText())

    page.i18n.bind_callable(_retranslate_header_and_tooltip)
    lay.addStretch()
    return page
