import os, sys, json, hashlib, zipfile, shutil, subprocess, threading, urllib.request, urllib.error
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QProgressBar, QTextEdit, QMessageBox

APP="Technovate"
ROOT=Path(os.environ.get("APPDATA",str(Path.home()))) / ".technovate"
GAME=ROOT/"game"
JAVA_CANDIDATES=[ROOT/"runtime"/"java"/"bin"/"javaw.exe",ROOT/"runtime"/"bin"/"javaw.exe",GAME/"java"/"bin"/"javaw.exe",GAME/"runtime"/"java"/"bin"/"javaw.exe"]
RUNTIME_URL="https://github.com/Xonety/Technovate-Distribution/releases/download/Runtime-v1.1.1/Technovate-Runtime-1.1.1.zip"
MODPACK_URL="https://github.com/Xonety/Technovate-Distribution/releases/download/Modpack-v1.1.3/Technovate-Modpack-1.1.3.zip"
RUNTIME_SHA="dbe48f7d41c39705ef5939d8ff44fba9c7e52f22450f5c1d6515b6c733e7238f"
MODPACK_SHA="21f6f969a75eebc2465754973cd30e2c7f2d6cdf8ae0d3b5d4abe613c04b0355"

class Bus(QObject):
    log=Signal(str); progress=Signal(int); done=Signal(bool,str)

def download(url,dest,progress):
    dest.parent.mkdir(parents=True,exist_ok=True); tmp=dest.with_suffix(".part")
    req=urllib.request.Request(url,headers={"User-Agent":"TechnovateLauncher/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r, open(tmp,"wb") as f:
        total=int(r.headers.get("Content-Length",0)); got=0
        while True:
            b=r.read(1024*1024)
            if not b: break
            f.write(b); got+=len(b)
            if total: progress(int(got*100/total))
    tmp.replace(dest)

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""): h.update(b)
    return h.hexdigest()

def safe_extract(zf,dest):
    base=dest.resolve()
    for item in zf.infolist():
        target=(dest/item.filename).resolve()
        if target!=base and base not in target.parents: raise RuntimeError("Небезопасный путь в архиве: "+item.filename)
    zf.extractall(dest)

def extract_archive(archive,dest,progress):
    with zipfile.ZipFile(archive) as z:
        entries=[x for x in z.infolist() if not x.is_dir()]
        total=sum(x.file_size for x in entries) or 1; done=0
        base=dest.resolve()
        for x in z.infolist():
            target=(dest/x.filename).resolve()
            if target!=base and base not in target.parents: raise RuntimeError("Небезопасный путь в архиве")
        for x in entries:
            z.extract(x,dest); done+=x.file_size; progress(int(done*100/total))

def find_game_root():
    # Runtime may contain a wrapper folder; find the directory containing versions and libraries.
    if (GAME/"versions").is_dir(): return GAME
    for p in GAME.iterdir() if GAME.exists() else []:
        if p.is_dir() and (p/"versions").is_dir(): return p
    return GAME

def find_version(game):
    versions=game/"versions"
    if not versions.exists(): raise RuntimeError("В Runtime не найдена папка versions.")
    candidates=[]
    for p in versions.iterdir():
        if p.is_dir() and ("neoforge" in p.name.lower() or "1.21.1" in p.name):
            if (p/(p.name+".json")).exists(): candidates.append(p.name)
    if not candidates: raise RuntimeError("Не найден установленный профиль NeoForge в versions.")
    exact=[v for v in candidates if "21.1.228" in v]
    return exact[0] if exact else candidates[0]

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.bus=Bus(); self.bus.log.connect(self.addlog); self.bus.progress.connect(self.bar.setValue); self.bus.done.connect(self.finished)
        self.setWindowTitle("Technovate Launcher"); self.setMinimumSize(850,560)
        w=QWidget(); self.setCentralWidget(w); root=QVBoxLayout(w); root.setContentsMargins(34,26,34,24); root.setSpacing(14)
        head=QHBoxLayout(); title=QLabel("TECHNOVATE"); title.setObjectName("title"); head.addWidget(title); head.addStretch(); self.status=QLabel("MINECRAFT 1.21.1 • NEOFORGE 21.1.228"); head.addWidget(self.status); root.addLayout(head)
        hero=QLabel("ТВОЯ ВСЕЛЕННАЯ. ТВОИ ПРАВИЛА."); hero.setObjectName("hero"); root.addWidget(hero)
        self.news=QLabel("Добро пожаловать в Technovate!\nПеред первым запуском установи игровые файлы. Лаунчер проверит архивы и подготовит клиент."); self.news.setWordWrap(True); self.news.setObjectName("news"); root.addWidget(self.news)
        row=QHBoxLayout(); self.nick=QLineEdit(); self.nick.setPlaceholderText("Твой игровой ник (3–16 символов)"); self.nick.setMaxLength(16); row.addWidget(self.nick); root.addLayout(row)
        self.bar=QProgressBar(); self.bar.setValue(0); root.addWidget(self.bar)
        self.logs=QTextEdit(); self.logs.setReadOnly(True); self.logs.setMaximumHeight(140); root.addWidget(self.logs)
        actions=QHBoxLayout(); self.install=QPushButton("УСТАНОВИТЬ / ПРОВЕРИТЬ"); self.install.clicked.connect(self.install_client); actions.addWidget(self.install)
        self.play=QPushButton("ИГРАТЬ"); self.play.setObjectName("play"); self.play.clicked.connect(self.launch); actions.addWidget(self.play); root.addLayout(actions)
        self.setStyleSheet("QMainWindow{background:#10141c;color:#f4f6fb} QWidget{color:#f4f6fb;font-family:Segoe UI} QLabel#title{font-size:27px;font-weight:900;letter-spacing:4px;color:#71d6ff} QLabel#hero{font-size:25px;font-weight:800;padding:22px 0;color:#fff} QLabel#news{background:#1a2432;border:1px solid #2a3b50;border-radius:12px;padding:20px;font-size:15px;min-height:85px} QLineEdit{background:#1a2432;border:1px solid #34465b;border-radius:8px;padding:13px;font-size:15px} QPushButton{background:#26384d;border:0;border-radius:9px;padding:16px;font-weight:800} QPushButton#play{background:#159bd0;color:white} QPushButton:hover{background:#267da0} QProgressBar{background:#1a2432;border:0;border-radius:5px;height:12px;text-align:center} QProgressBar::chunk{background:#24b8ed;border-radius:5px} QTextEdit{background:#0b0f15;border:1px solid #273342;border-radius:8px;color:#9db2c8}")
        self.showMaximized()
    def addlog(self,s): self.logs.append(s)
    def work(self,fn):
        self.install.setEnabled(False); self.play.setEnabled(False)
        threading.Thread(target=fn,daemon=True).start()
    def install_client(self):
        def run():
            try:
                ROOT.mkdir(parents=True,exist_ok=True); GAME.mkdir(parents=True,exist_ok=True)
                for name,url,digest in [("runtime.zip",RUNTIME_URL,RUNTIME_SHA),("modpack.zip",MODPACK_URL,MODPACK_SHA)]:
                    dest=ROOT/"downloads"/name
                    self.bus.log.emit("Проверка "+name)
                    if not dest.exists() or sha(dest)!=digest:
                        self.bus.log.emit("Скачивание "+name+" с GitHub Releases…")
                        download(url,dest,lambda n:self.bus.progress.emit(n))
                    if sha(dest)!=digest: raise RuntimeError("SHA-256 не совпадает: "+name)
                    self.bus.log.emit("Распаковка "+name+"…")
                    extract_archive(dest,GAME,lambda n:self.bus.progress.emit(n))
                self.bus.log.emit("Runtime и Modpack установлены. Проверяю профиль…")
                game=find_game_root(); version=find_version(game)
                self.bus.log.emit("Найден профиль: "+version)
                self.bus.done.emit(True,"Установка и проверка завершены.")
            except Exception as e: self.bus.done.emit(False,str(e))
        self.work(run)
    def finished(self,ok,msg):
        self.install.setEnabled(True); self.play.setEnabled(True); self.bar.setValue(100 if ok else 0)
        self.addlog(("ГОТОВО: " if ok else "ОШИБКА: ")+msg)
        if not ok: QMessageBox.critical(self,"Technovate",msg)
    def launch(self):
        nick=self.nick.text().strip()
        if not (3<=len(nick)<=16) or not nick.isalnum(): QMessageBox.warning(self,"Ник","Введи ник из 3–16 латинских букв и цифр."); return
        try:
            import minecraft_launcher_lib
            game=find_game_root(); version=find_version(game)
            java=next((str(p) for p in JAVA_CANDIDATES if p.exists()),None)
            if not java:
                for p in game.rglob("javaw.exe"):
                    java=str(p); break
            if not java: raise RuntimeError("Не найден javaw.exe в Runtime.")
            opts={"username":nick,"uuid": "00000000-0000-0000-0000-"+hashlib.md5(nick.encode()).hexdigest()[:12],
                  "token":"","jvmArguments":["-Xms2G","-Xmx6G"],"executablePath":java}
            cmd=minecraft_launcher_lib.command.get_minecraft_command(version,str(game),opts)
            self.addlog("Запуск Minecraft "+version+"…")
            subprocess.Popen(cmd,cwd=game,creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))
        except Exception as e: QMessageBox.critical(self,"Не удалось запустить Minecraft",str(e))
    def closeEvent(self,event): event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv); win=Window(); sys.exit(app.exec())
